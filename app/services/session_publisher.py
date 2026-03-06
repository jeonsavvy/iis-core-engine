"""Session Publisher — adapter for publishing games from editor sessions.

Wraps the existing PublisherService + GitHubArchiveService for the
interactive session workflow.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import Settings
from app.services.quality_service import QualityService
from app.services.publisher_service import PublisherService
from app.services.github_service import GitHubArchiveService
from app.services.telegram_service import TelegramService

logger = logging.getLogger(__name__)


class SessionPublisher:
    """Publishes a game from the editor session to Supabase + Archive."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._publisher = PublisherService(settings)
        self._quality = QualityService(settings)
        self._telegram = TelegramService(settings)
        self._vertex: Any | None = None
        try:
            from app.services.vertex_service import VertexService

            self._vertex = VertexService(settings)
        except Exception:
            logger.warning("Vertex service unavailable for publish copy generation.")
        self._archiver: GitHubArchiveService | None = None
        try:
            self._archiver = GitHubArchiveService(settings)
        except Exception:
            logger.warning("GitHub archive service not available, skipping.")

    @staticmethod
    def _fallback_preview_asset(*, genre_brief: dict[str, Any] | None = None, genre: str = "") -> str | None:
        asset_pack_key = str((genre_brief or {}).get("asset_pack_key", "") or "").strip()
        if asset_pack_key == "racing_synthwave_pack_v1":
            return "/assets/preview/neon-drift.svg"
        if asset_pack_key == "island_flight_pack_v1":
            return "/assets/preview/aether-courier.svg"
        if asset_pack_key == "space_dogfight_pack_v1":
            return "/assets/preview/skyline-jet.svg"
        if asset_pack_key == "topdown_lowpoly_pack_v1":
            return "/assets/preview/timebreakers.svg"

        lowered = genre.casefold()
        if "race" in lowered or "racing" in lowered or "레이싱" in lowered:
            return "/assets/preview/neon-drift.svg"
        if "flight" in lowered or "비행" in lowered:
            return "/assets/preview/aether-courier.svg"
        if "shoot" in lowered or "슈팅" in lowered:
            return "/assets/preview/timebreakers.svg"
        return None

    async def publish(
        self,
        *,
        slug: str,
        game_name: str,
        genre: str,
        html_content: str,
        recent_history: list[dict[str, Any]] | None = None,
        recent_events: list[dict[str, Any]] | None = None,
        genre_brief: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Publish game HTML to Supabase storage + games_metadata.

        Returns:
            dict with keys: success, public_url, game_id, error
        """
        result = self._publisher.publish_game(
            slug=slug,
            name=game_name,
            genre=genre,
            html_content=html_content,
            artifact_files=None,
            entrypoint_path=None,
        )

        public_url = result.get("public_url", "")
        game_id = result.get("game_id", "")
        play_url = f"/play/{slug}"
        screenshot_url: str | None = None
        if result.get("status") == "published":
            try:
                smoke = self._quality.run_smoke_check(html_content)
                if smoke.screenshot_bytes:
                    screenshot_url = self._publisher.upload_screenshot(slug=slug, screenshot_bytes=smoke.screenshot_bytes)
            except Exception as exc:
                logger.warning("Publish screenshot capture failed (non-fatal): %s", exc)
        if not screenshot_url:
            screenshot_url = self._fallback_preview_asset(genre_brief=genre_brief, genre=genre)
        publish_copy = {
            "marketing_summary": "",
            "play_overview": [],
            "controls_guide": [],
        }

        if self._vertex is not None:
            try:
                generated = self._vertex.generate_publish_copy(
                    game_name=game_name,
                    genre=genre,
                    current_html=html_content,
                    recent_history=recent_history,
                    recent_events=recent_events,
                    genre_brief=genre_brief,
                )
                if isinstance(generated.payload, dict):
                    publish_copy.update(generated.payload)
            except Exception as exc:
                logger.warning("Publish copy generation failed (fallback in use): %s", exc)

        self._publisher.update_game_marketing(
            slug=slug,
            ai_review="\n".join(str(item) for item in publish_copy.get("play_overview", [])[:3]).strip() or None,
            screenshot_url=screenshot_url,
            thumbnail_url=screenshot_url,
            marketing_summary=str(publish_copy.get("marketing_summary", "")).strip() or None,
            play_overview=[str(item) for item in publish_copy.get("play_overview", [])] if isinstance(publish_copy.get("play_overview"), list) else None,
            controls_guide=[str(item) for item in publish_copy.get("controls_guide", [])] if isinstance(publish_copy.get("controls_guide"), list) else None,
            publish_copy_version="v1",
        )

        # Archive to GitHub repo (best-effort, non-blocking)
        if self._archiver and public_url:
            try:
                self._archiver.commit_archive_game(
                    game_slug=slug,
                    game_name=game_name,
                    genre=genre,
                    html_content=html_content,
                    public_url=public_url,
                    artifact_files=None,
                )
            except Exception as exc:
                logger.warning("Archive commit failed (non-fatal): %s", exc)

        try:
            message = (
                "✅ Publish success\n"
                f"- slug: {slug}\n"
                f"- game: {game_name}\n"
                f"- play: {play_url}\n"
                f"- public: {public_url or 'n/a'}"
            )
            self._telegram.broadcast_message(message)
        except Exception as exc:
            logger.warning("Telegram publish notification failed (non-fatal): %s", exc)

        return {
            "success": True,
            "public_url": public_url,
            "game_id": str(game_id),
            "game_slug": slug,
            "play_url": play_url,
            "screenshot_url": screenshot_url,
            "marketing_summary": str(publish_copy.get("marketing_summary", "")),
            "play_overview": publish_copy.get("play_overview", []),
            "controls_guide": publish_copy.get("controls_guide", []),
        }
