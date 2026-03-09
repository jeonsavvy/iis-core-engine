from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.config import Settings
from app.services.github_service import GitHubArchiveService
from app.services.http_client import ExternalCallError, request_with_retry
from app.services.publisher_service import PublisherService
from app.services.supabase_service import create_supabase_admin_client
from app.services.quality_service import QualityService
from app.services.telegram_service import TelegramService


class GameAdminService:
    def __init__(
        self,
        settings: Settings,
        *,
        publisher_service: PublisherService | None = None,
        github_archive_service: GitHubArchiveService | None = None,
    ) -> None:
        self.settings = settings
        self.client = create_supabase_admin_client(settings)
        self.publisher_service = publisher_service or PublisherService(settings)
        self.github_archive_service = github_archive_service or GitHubArchiveService(settings)
        self.quality_service = QualityService(settings)
        self.telegram_service = TelegramService(settings)

    def delete_game(
        self,
        *,
        game_id: UUID,
        delete_storage: bool,
        delete_archive: bool,
        reason: str,
    ) -> dict[str, Any]:
        if not self.client:
            return {"status": "error", "reason": "supabase client is not configured"}

        lookup = self.client.table("games_metadata").select("*").eq("id", str(game_id)).limit(1).execute()
        rows = lookup.data or []
        if not rows:
            return {"status": "not_found", "reason": "game_not_found", "game_id": str(game_id)}

        game_row = rows[0]
        slug = str(game_row.get("slug") or "").strip()
        if not slug:
            return {"status": "error", "reason": "game_slug_missing", "game_id": str(game_id)}

        deleted = {"db": False, "storage": False, "archive": False}
        details: dict[str, Any] = {
            "reason": reason,
            "storage": None,
            "archive": None,
            "db": None,
        }
        warnings: list[dict[str, str]] = []

        if delete_storage:
            storage_result = self.publisher_service.delete_game_assets(slug=slug)
            details["storage"] = storage_result
            if storage_result.get("status") == "error":
                return {
                    "status": "partial_error",
                    "reason": "storage_delete_failed",
                    "game_id": str(game_id),
                    "slug": slug,
                    "deleted": deleted,
                    "details": details,
                }
            deleted["storage"] = storage_result.get("status") == "deleted"
        else:
            details["storage"] = {"status": "skipped", "reason": "delete_storage=false"}

        if delete_archive:
            archive_result = self.github_archive_service.delete_archive_game(game_slug=slug)
            details["archive"] = archive_result
            if archive_result.get("status") == "error":
                warnings.append(
                    {
                        "code": "archive_delete_failed",
                        "detail": str(archive_result.get("reason") or "archive_delete_failed"),
                    }
                )
            else:
                deleted["archive"] = archive_result.get("status") == "deleted"
        else:
            details["archive"] = {"status": "skipped", "reason": "delete_archive=false"}

        try:
            self.client.table("games_metadata").delete().eq("id", str(game_id)).execute()
            deleted["db"] = True
            details["db"] = {"status": "deleted"}
        except Exception as exc:  # pragma: no cover - integration path
            details["db"] = {"status": "error", "reason": f"db_delete_failed: {exc}"}
            return {
                "status": "partial_error",
                "reason": "db_delete_failed",
                "game_id": str(game_id),
                "slug": slug,
                "deleted": deleted,
                "details": details,
            }

        return {
            "status": "ok",
            "game_id": str(game_id),
            "slug": slug,
            "deleted": deleted,
            "details": details,
            "warnings": warnings,
        }

    def repair_presentation(
        self,
        *,
        game_id: UUID,
        rebroadcast_telegram: bool,
        require_thumbnail: bool,
    ) -> dict[str, Any]:
        if not self.client:
            return {"status": "error", "reason": "supabase client is not configured", "game_id": str(game_id)}

        lookup = self.client.table("games_metadata").select("*").eq("id", str(game_id)).limit(1).execute()
        rows = lookup.data or []
        if not rows:
            return {"status": "not_found", "reason": "game_not_found", "game_id": str(game_id)}

        game_row = rows[0]
        slug = str(game_row.get("slug") or "").strip()
        public_url = str(game_row.get("url") or "").strip()
        if not slug or not public_url.startswith(("http://", "https://")):
            return {
                "status": "error",
                "reason": "game_public_url_missing",
                "game_id": str(game_id),
                "slug": slug or "",
            }

        details: dict[str, Any] = {"public_url": public_url}
        try:
            response = request_with_retry(
                "GET",
                public_url,
                timeout_seconds=self.settings.http_timeout_seconds,
                max_retries=self.settings.http_max_retries,
            )
        except ExternalCallError as exc:
            return {
                "status": "partial_error",
                "reason": "artifact_fetch_failed",
                "game_id": str(game_id),
                "slug": slug,
                "visibility": str(game_row.get("visibility") or "hidden"),
                "details": {"error": str(exc)},
            }

        screenshot_url = None
        presentation_screenshot = self.quality_service.capture_presentation_screenshot(response.text)
        if presentation_screenshot:
            screenshot_url = self.publisher_service.upload_screenshot(slug=slug, screenshot_bytes=presentation_screenshot)

        if not screenshot_url and require_thumbnail:
            self.publisher_service.update_game_marketing(slug=slug, visibility="hidden")
            return {
                "status": "partial_error",
                "reason": "thumbnail_generation_failed",
                "game_id": str(game_id),
                "slug": slug,
                "visibility": "hidden",
                "thumbnail_url": None,
                "telegram": {"status": "skipped"},
                "details": details,
            }

        visibility = "public" if screenshot_url else str(game_row.get("visibility") or "hidden")
        self.publisher_service.update_game_marketing(
            slug=slug,
            screenshot_url=screenshot_url,
            thumbnail_url=screenshot_url,
            hero_image_url=screenshot_url,
            visibility=visibility,
        )

        telegram_result: dict[str, Any] = {"status": "skipped"}
        if rebroadcast_telegram and screenshot_url:
            play_base = str(self.settings.public_portal_base_url or "").strip().rstrip("/")
            play_url = f"{play_base}/play/{slug}" if play_base else f"/play/{slug}"
            telegram_result = self.telegram_service.broadcast_launch_announcement(
                title=str(game_row.get("name") or slug),
                marketing_line=str(game_row.get("marketing_summary") or game_row.get("short_description") or "").strip(),
                play_url=play_url,
                photo_url=screenshot_url,
                genre=str(game_row.get("genre_primary") or game_row.get("genre") or "").strip(),
                slug=slug,
            )

        return {
            "status": "ok",
            "game_id": str(game_id),
            "slug": slug,
            "visibility": visibility,
            "thumbnail_url": screenshot_url,
            "telegram": telegram_result,
            "details": details,
        }
