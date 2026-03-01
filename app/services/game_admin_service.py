from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.config import Settings
from app.services.github_service import GitHubArchiveService
from app.services.publisher_service import PublisherService
from app.services.supabase_service import create_supabase_admin_client


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
