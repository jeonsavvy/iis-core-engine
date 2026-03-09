"""Session Publisher — adapter for publishing games from editor sessions.

Wraps the existing PublisherService + GitHubArchiveService for the
interactive session workflow.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse
from datetime import datetime, timezone

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

    @staticmethod
    def _fallback_preview_raster_asset(*, genre_brief: dict[str, Any] | None = None, genre: str = "") -> str | None:
        asset_pack_key = str((genre_brief or {}).get("asset_pack_key", "") or "").strip()
        if asset_pack_key == "racing_synthwave_pack_v1":
            return "/assets/preview-raster/neon-drift.png"
        if asset_pack_key == "island_flight_pack_v1":
            return "/assets/preview-raster/aether-courier.png"
        if asset_pack_key == "space_dogfight_pack_v1":
            return "/assets/preview-raster/skyline-jet.png"
        if asset_pack_key == "topdown_lowpoly_pack_v1":
            return "/assets/preview-raster/timebreakers.png"

        lowered = genre.casefold()
        if "race" in lowered or "racing" in lowered or "레이싱" in lowered:
            return "/assets/preview-raster/neon-drift.png"
        if "flight" in lowered or "비행" in lowered:
            return "/assets/preview-raster/aether-courier.png"
        if "shoot" in lowered or "슈팅" in lowered:
            return "/assets/preview-raster/timebreakers.png"
        return None

    @staticmethod
    def _resolve_telegram_media_url(*, thumbnail_url: str | None = None, screenshot_url: str | None = None) -> str | None:
        for candidate in (thumbnail_url, screenshot_url):
            normalized = str(candidate or "").strip()
            if not normalized:
                continue
            parsed = urlparse(normalized)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue
            if parsed.path.casefold().endswith(".svg"):
                continue
            return normalized
        return None

    def _resolve_play_url(self, *, slug: str) -> str:
        base_url = str(self.settings.public_portal_base_url or "").strip().rstrip("/")
        if base_url:
            return f"{base_url}/play/{slug}"
        return f"/play/{slug}"

    def _resolve_portal_asset_url(self, asset_path: str | None) -> str | None:
        normalized_path = str(asset_path or "").strip()
        base_url = str(self.settings.public_portal_base_url or "").strip().rstrip("/")
        if not normalized_path or not base_url or not normalized_path.startswith("/"):
            return None
        return f"{base_url}{normalized_path}"

    @staticmethod
    def _normalize_catalog_tag(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().casefold()).strip("-")
        return normalized[:32]

    @classmethod
    def _build_public_game_metadata(
        cls,
        *,
        slug: str,
        game_name: str,
        genre: str,
        genre_brief: dict[str, Any] | None,
        screenshot_url: str | None,
        marketing_summary: str,
        play_overview: list[str],
        controls_guide: list[str],
    ) -> dict[str, Any]:
        resolved_genre = str(genre or "").strip().casefold() or "arcade"
        resolved_brief = genre_brief or {}
        archetype = str(resolved_brief.get("archetype", "") or "").strip().casefold()
        engine_mode = str(resolved_brief.get("engine_mode", "") or "").strip().casefold()
        mechanics = [
            cls._normalize_catalog_tag(str(item))
            for item in resolved_brief.get("must_have_mechanics", [])
            if cls._normalize_catalog_tag(str(item))
        ]

        tags: list[str] = []
        for candidate in [
            resolved_genre,
            "3d" if archetype.endswith("_3d") or engine_mode == "3d_three" else "",
            "2d" if archetype.endswith("_2d") or engine_mode == "2d_phaser" else "",
            *mechanics[:4],
        ]:
            normalized = cls._normalize_catalog_tag(candidate)
            if normalized and normalized not in tags:
                tags.append(normalized)

        summary = marketing_summary.strip()
        overview = [str(item).strip() for item in play_overview if str(item).strip()]
        controls = [str(item).strip() for item in controls_guide if str(item).strip()]

        description_lines = [game_name]
        if summary:
            description_lines.append(summary)
        if overview:
            description_lines.append("핵심 포인트")
            description_lines.extend(f"- {line}" for line in overview[:3])
        if controls:
            description_lines.append("조작")
            description_lines.extend(f"- {line}" for line in controls[:3])

        return {
            "slug": slug,
            "short_description": summary or f"{game_name}을 바로 플레이해보세요.",
            "description": "\n".join(description_lines),
            "genre_primary": resolved_genre,
            "genre_tags": tags,
            "hero_image_url": screenshot_url,
            "released_at": datetime.now(timezone.utc).isoformat(),
            "visibility": "public" if screenshot_url else "hidden",
            "play_count_cached": 0,
        }


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
        created_by: str | None = None,
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
            created_by=created_by,
        )

        public_url = result.get("public_url", "")
        game_id = result.get("game_id", "")
        play_url = self._resolve_play_url(slug=slug)
        screenshot_url: str | None = None
        thumbnail_url: str | None = None
        if result.get("status") == "published":
            try:
                smoke = self._quality.run_smoke_check(html_content)
                if smoke.screenshot_bytes:
                    screenshot_url = self._publisher.upload_screenshot(slug=slug, screenshot_bytes=smoke.screenshot_bytes)
            except Exception as exc:
                logger.warning("Publish screenshot capture failed (non-fatal): %s", exc)
        canonical_thumbnail_url = self._resolve_telegram_media_url(thumbnail_url=screenshot_url, screenshot_url=screenshot_url)
        screenshot_url = canonical_thumbnail_url
        thumbnail_url = canonical_thumbnail_url
        telegram_photo_url = canonical_thumbnail_url
        presentation_status = "ready" if canonical_thumbnail_url else "repair_pending"
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

        marketing_summary = str(publish_copy.get("marketing_summary", "")).strip()
        play_overview = [str(item) for item in publish_copy.get("play_overview", [])] if isinstance(publish_copy.get("play_overview"), list) else []
        controls_guide = [str(item) for item in publish_copy.get("controls_guide", [])] if isinstance(publish_copy.get("controls_guide"), list) else []
        public_game_metadata = self._build_public_game_metadata(
            slug=slug,
            game_name=game_name,
            genre=genre,
            genre_brief=genre_brief,
            screenshot_url=screenshot_url,
            marketing_summary=marketing_summary,
            play_overview=play_overview,
            controls_guide=controls_guide,
        )

        self._publisher.update_game_marketing(
            slug=slug,
            ai_review="\n".join(play_overview[:3]).strip() or None,
            screenshot_url=screenshot_url,
            thumbnail_url=thumbnail_url,
            marketing_summary=marketing_summary or None,
            play_overview=play_overview or None,
            controls_guide=controls_guide or None,
            publish_copy_version="v1",
            short_description=str(public_game_metadata.get("short_description", "")).strip() or None,
            description=str(public_game_metadata.get("description", "")).strip() or None,
            genre_primary=str(public_game_metadata.get("genre_primary", "")).strip() or None,
            genre_tags=public_game_metadata.get("genre_tags") if isinstance(public_game_metadata.get("genre_tags"), list) else None,
            hero_image_url=thumbnail_url,
            released_at=str(public_game_metadata.get("released_at", "")).strip() or None,
            visibility="public" if presentation_status == "ready" else "hidden",
            play_count_cached=int(public_game_metadata.get("play_count_cached", 0) or 0),
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

        if telegram_photo_url:
            try:
                self._telegram.broadcast_launch_announcement(
                    title=game_name,
                    marketing_line=marketing_summary,
                    play_url=play_url,
                    public_url=public_url or None,
                    photo_url=telegram_photo_url,
                    genre=genre,
                    slug=slug,
                )
            except Exception as exc:
                logger.warning("Telegram publish notification failed (non-fatal): %s", exc)

        return {
            "success": True,
            "public_url": public_url,
            "game_id": str(game_id),
            "game_slug": slug,
            "play_url": play_url,
            "presentation_status": presentation_status,
            "thumbnail_url": thumbnail_url,
            "screenshot_url": screenshot_url,
            "marketing_summary": marketing_summary,
            "play_overview": play_overview,
            "controls_guide": controls_guide,
        }
