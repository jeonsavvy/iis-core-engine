from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import Settings


class GitHubArchiveService:
    """Repo3 archive commit integration with allowlist guards."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def commit_archive_game(
        self,
        *,
        game_slug: str,
        game_name: str,
        genre: str,
        html_content: str,
        public_url: str,
    ) -> dict[str, str]:
        if not self.settings.github_token or not self.settings.github_archive_repo:
            return {
                "status": "skipped",
                "reason": "GITHUB_TOKEN or GITHUB_ARCHIVE_REPO is not configured.",
            }

        game_path = f"games/{game_slug}/index.html"
        manifest_path = "manifest/games.json"
        self._assert_allowlisted_path(game_path)
        self._assert_allowlisted_path(manifest_path)

        try:
            existing_manifest = self._fetch_json_file(manifest_path)
        except Exception as exc:
            return {"status": "error", "reason": f"manifest_fetch_failed: {exc}"}

        if isinstance(existing_manifest, dict):
            existing_games = existing_manifest.get("games", [])
            if not isinstance(existing_games, list):
                existing_games = []
            manifest_schema_version = int(existing_manifest.get("schema_version", 1) or 1)
        elif isinstance(existing_manifest, list):
            existing_games = existing_manifest
            manifest_schema_version = 1
        else:
            existing_games = []
            manifest_schema_version = 1

        now = datetime.now(timezone.utc).isoformat()
        previous_row = next(
            (
                row
                for row in existing_games
                if isinstance(row, dict) and row.get("slug") == game_slug
            ),
            None,
        )

        created_at = now
        if isinstance(previous_row, dict) and isinstance(previous_row.get("created_at"), str):
            created_at = previous_row["created_at"]

        updated_games: list[dict[str, Any]] = [
            row for row in existing_games if isinstance(row, dict) and row.get("slug") != game_slug
        ]
        updated_games.append(
            {
                "slug": game_slug,
                "name": game_name,
                "genre": genre,
                "path": game_path,
                "url": public_url,
                "created_at": created_at,
            }
        )

        updated_manifest = {
            "schema_version": manifest_schema_version,
            "generated_at": now,
            "games": updated_games,
        }

        commit_message = f"feat: archive {game_slug}"

        try:
            self._put_file(game_path, html_content, commit_message)
            self._put_file(manifest_path, json.dumps(updated_manifest, ensure_ascii=False, indent=2) + "\n", commit_message)
        except Exception as exc:
            return {"status": "error", "reason": f"archive_commit_failed: {exc}"}

        return {
            "status": "committed",
            "slug": game_slug,
            "repo": self.settings.github_archive_repo,
            "branch": self.settings.github_archive_branch,
            "message": commit_message,
        }

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        }

    def _contents_url(self, path: str) -> str:
        base = self.settings.github_api_base_url.rstrip("/")
        return f"{base}/repos/{self.settings.github_archive_repo}/contents/{path}"

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError, RuntimeError)),
    )
    def _request(self, method: str, url: str, *, json_payload: dict[str, Any] | None = None) -> httpx.Response:
        with httpx.Client(timeout=self.settings.http_timeout_seconds) as client:
            response = client.request(method, url, headers=self._headers(), json=json_payload)
            if response.status_code >= 500:
                raise RuntimeError(f"github_server_error_{response.status_code}")
            return response

    def _fetch_json_file(self, path: str) -> Any:
        response = self._request("GET", f"{self._contents_url(path)}?ref={self.settings.github_archive_branch}")
        if response.status_code == 404:
            return []
        if response.status_code != 200:
            raise RuntimeError(f"github_read_failed_{response.status_code}")

        body = response.json()
        content = body.get("content", "")
        if not content:
            return []

        decoded = base64.b64decode(content).decode("utf-8")
        return json.loads(decoded)

    def _fetch_sha(self, path: str) -> str | None:
        response = self._request("GET", f"{self._contents_url(path)}?ref={self.settings.github_archive_branch}")
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise RuntimeError(f"github_sha_lookup_failed_{response.status_code}")
        return response.json().get("sha")

    def _put_file(self, path: str, content: str, commit_message: str) -> None:
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        payload: dict[str, Any] = {
            "message": commit_message,
            "content": encoded,
            "branch": self.settings.github_archive_branch,
        }

        current_sha = self._fetch_sha(path)
        if current_sha:
            payload["sha"] = current_sha

        response = self._request("PUT", self._contents_url(path), json_payload=payload)
        if response.status_code not in (200, 201):
            raise RuntimeError(f"github_put_failed_{response.status_code}")

    @staticmethod
    def _assert_allowlisted_path(path: str) -> None:
        if path.startswith("games/") and path.count("/") == 2 and path.endswith("/index.html"):
            return
        if path == "manifest/games.json":
            return
        raise ValueError(f"path is not allowlisted for archive repo: {path}")
