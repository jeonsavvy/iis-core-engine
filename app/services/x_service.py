from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from threading import Lock

from app.core.config import Settings
from app.services.http_client import ExternalCallError, request_with_retry


class XService:
    """X posting service with daily per-game quota and failure stop lock."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._state_lock = Lock()
        self._state_path = Path(settings.x_quota_state_file)
        self._quota: dict[str, dict[str, int]] = {}
        self._blocked_dates: dict[str, set[str]] = {}
        self._load_state()

    def publish_update(self, game_slug: str, text: str) -> dict[str, str]:
        if not self.settings.x_auto_post_enabled:
            return {"status": "skipped", "reason": "X_AUTO_POST_ENABLED=false"}

        if not self.settings.x_bearer_token:
            return {"status": "skipped", "reason": "X_BEARER_TOKEN is missing."}

        today = date.today().isoformat()

        with self._state_lock:
            if today in self._blocked_dates.get(game_slug, set()):
                return {"status": "skipped", "reason": "posting blocked for today after previous failure"}

            today_count = self._quota.get(game_slug, {}).get(today, 0)
            if today_count >= self.settings.x_posts_per_game_per_day:
                return {
                    "status": "skipped",
                    "reason": f"daily quota reached ({self.settings.x_posts_per_game_per_day}/day)",
                }

        try:
            request_with_retry(
                "POST",
                f"{self.settings.x_api_base_url.rstrip('/')}/2/posts",
                timeout_seconds=self.settings.http_timeout_seconds,
                max_retries=self.settings.http_max_retries,
                headers={
                    "Authorization": f"Bearer {self.settings.x_bearer_token}",
                    "Content-Type": "application/json",
                },
                json={"text": text},
            )
        except ExternalCallError as exc:
            with self._state_lock:
                if self.settings.x_daily_stop_on_error:
                    self._blocked_dates.setdefault(game_slug, set()).add(today)
                self._save_state()
            return {"status": "error", "reason": str(exc)}

        with self._state_lock:
            self._quota.setdefault(game_slug, {})[today] = self._quota.get(game_slug, {}).get(today, 0) + 1
            self._save_state()

        return {"status": "posted"}

    def _load_state(self) -> None:
        if not self._state_path.exists():
            return

        try:
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception:
            return

        quota = raw.get("quota", {})
        blocked = raw.get("blocked_dates", {})

        if isinstance(quota, dict):
            for slug, by_day in quota.items():
                if isinstance(by_day, dict):
                    self._quota[str(slug)] = {str(day): int(count) for day, count in by_day.items()}

        if isinstance(blocked, dict):
            for slug, days in blocked.items():
                if isinstance(days, list):
                    self._blocked_dates[str(slug)] = {str(day) for day in days}

    def _save_state(self) -> None:
        payload = {
            "quota": self._quota,
            "blocked_dates": {slug: sorted(days) for slug, days in self._blocked_dates.items()},
        }

        tmp_path = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(self._state_path)
