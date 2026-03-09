"""Publish pipeline adapter for editor sessions.

세션에서 확정된 HTML을 받아 저장소 업로드, 공개 메타데이터 기록,
아카이브 동기화, 알림 전송을 한 번의 퍼블리시 흐름으로 묶습니다.
"""

from __future__ import annotations

import logging
import re
from base64 import b64encode
from typing import Any
from urllib.parse import urlparse
from datetime import datetime, timezone

from app.core.config import Settings
from app.services.quality_service import QualityService
from app.services.publisher_service import PublisherService
from app.services.github_service import GitHubArchiveService
from app.services.telegram_service import TelegramService
from app.services.vertex_text_utils import build_presentation_contract_script, compile_generated_artifact

logger = logging.getLogger(__name__)

_PUBLISH_PRESENTATION_REPAIR_MARKER = 'id="iis-publish-presentation-repair"'


class PublishPresentationError(RuntimeError):
    def __init__(self, *, code: str, issues: list[str] | None = None) -> None:
        resolved_issues = [str(item).strip() for item in (issues or []) if str(item).strip()]
        super().__init__(resolved_issues[0] if resolved_issues else code)
        self.code = code
        self.issues = resolved_issues or [code]


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

    def validate_presentation_contract(
        self,
        *,
        html_content: str,
        artifact_files: list[dict[str, Any]] | None = None,
        entrypoint_path: str | None = None,
    ) -> tuple[bool, list[str]]:
        return self._quality.validate_presentation_contract(
            html_content,
            artifact_files=artifact_files,
            entrypoint_path=entrypoint_path,
        )

    def repair_presentation_contract_html(self, *, html_content: str) -> tuple[str, list[str]]:
        compiled, meta = compile_generated_artifact(html_content)
        raw_transforms = meta.get("transforms_applied")
        transforms = [str(item) for item in raw_transforms] if isinstance(raw_transforms, list) else []
        if _PUBLISH_PRESENTATION_REPAIR_MARKER not in compiled:
            repair_script = build_presentation_contract_script(
                script_id="iis-publish-presentation-repair",
                reason="publisher_repair_presentation",
                force_override=True,
            )
            lowered = compiled.casefold()
            body_close = lowered.rfind("</body>")
            if body_close >= 0:
                compiled = f"{compiled[:body_close]}{repair_script}{compiled[body_close:]}"
            else:
                compiled = f"{compiled}{repair_script}"
            transforms.append("inject_publish_presentation_repair")
        return compiled, transforms


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
        selected_thumbnail_bytes: bytes | None = None,
        selected_thumbnail_mime_type: str | None = None,
        selected_thumbnail_name: str | None = None,
    ) -> dict[str, Any]:
        """Publish game HTML to Supabase storage + games_metadata.

        Returns:
            dict with keys: success, public_url, game_id, error
        """
        # 퍼블리시에는 실제 대표 이미지가 필요합니다.
        presentation_screenshot = selected_thumbnail_bytes
        screenshot_mime_type = str(selected_thumbnail_mime_type or "image/png").strip() or "image/png"
        if not presentation_screenshot:
            presentation_screenshot = self._quality.capture_presentation_screenshot(html_content)
            screenshot_mime_type = "image/png"
        if not presentation_screenshot:
            raise PublishPresentationError(
                code="publish_presentation_capture_failed",
                issues=["actual_presentation_screenshot_missing"],
            )

        result = self._publisher.publish_game(
            slug=slug,
            name=game_name,
            genre=genre,
            html_content=html_content,
            artifact_files=None,
            entrypoint_path=None,
            created_by=created_by,
        )

        if str(result.get("status", "")).strip() != "published":
            raise RuntimeError(str(result.get("reason") or "publish_game_failed"))

        public_url = result.get("public_url", "")
        game_id = result.get("game_id", "")
        play_url = self._resolve_play_url(slug=slug)
        actual_screenshot_url = self._publisher.upload_screenshot(
            slug=slug,
            screenshot_bytes=presentation_screenshot,
            mime_type=screenshot_mime_type,
        )
        if not actual_screenshot_url:
            self._publisher.update_game_marketing(
                slug=slug,
                screenshot_url=None,
                thumbnail_url=None,
                hero_image_url=None,
                visibility="hidden",
            )
            raise PublishPresentationError(
                code="publish_presentation_capture_failed",
                issues=["actual_presentation_screenshot_upload_failed"],
            )

        canonical_thumbnail_url = self._resolve_telegram_media_url(
            thumbnail_url=actual_screenshot_url,
            screenshot_url=actual_screenshot_url,
        )
        if not canonical_thumbnail_url:
            self._publisher.update_game_marketing(
                slug=slug,
                screenshot_url=actual_screenshot_url,
                thumbnail_url=None,
                hero_image_url=None,
                visibility="hidden",
            )
            raise PublishPresentationError(
                code="publish_presentation_capture_failed",
                issues=["actual_presentation_thumbnail_url_invalid"],
            )

        thumbnail_url = actual_screenshot_url
        telegram_photo_url = actual_screenshot_url
        presentation_status = "ready"
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
            screenshot_url=actual_screenshot_url,
            marketing_summary=marketing_summary,
            play_overview=play_overview,
            controls_guide=controls_guide,
        )

        self._publisher.update_game_marketing(
            slug=slug,
            ai_review="\n".join(play_overview[:3]).strip() or None,
            screenshot_url=actual_screenshot_url,
            thumbnail_url=thumbnail_url,
            marketing_summary=marketing_summary or None,
            play_overview=play_overview or None,
            controls_guide=controls_guide or None,
            publish_copy_version="v1",
            short_description=str(public_game_metadata.get("short_description", "")).strip() or None,
            description=str(public_game_metadata.get("description", "")).strip() or None,
            genre_primary=str(public_game_metadata.get("genre_primary", "")).strip() or None,
            genre_tags=public_game_metadata.get("genre_tags") if isinstance(public_game_metadata.get("genre_tags"), list) else None,
            hero_image_url=actual_screenshot_url,
            released_at=str(public_game_metadata.get("released_at", "")).strip() or None,
            visibility="public",
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
            "screenshot_url": actual_screenshot_url,
            "marketing_summary": marketing_summary,
            "play_overview": play_overview,
            "controls_guide": controls_guide,
        }

    def generate_publish_thumbnail_candidates(self, *, html_content: str) -> list[dict[str, str]]:
        raw_candidates = self._quality.capture_publish_thumbnail_candidates(html_content)
        response: list[dict[str, str]] = []
        for index, row in enumerate(raw_candidates, start=1):
            image_bytes = row.get("bytes") if isinstance(row, dict) else None
            if not isinstance(image_bytes, (bytes, bytearray)):
                continue
            label = str((row or {}).get("label", "")).strip() or f"자동 캡처 {index}"
            response.append(
                {
                    "id": f"auto-{index}",
                    "label": label,
                    "source": "auto",
                    "mime_type": "image/png",
                    "data_url": f"data:image/png;base64,{b64encode(bytes(image_bytes)).decode('ascii')}",
                }
            )
        return response
