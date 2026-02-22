from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings
from app.services.supabase_service import create_supabase_admin_client


class PublisherService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = create_supabase_admin_client(settings)

    def publish_game(
        self,
        *,
        slug: str,
        name: str,
        genre: str,
        html_content: str,
    ) -> dict[str, Any]:
        if not self.client:
            fallback_url = f"{self.settings.public_games_base_url.rstrip('/')}/{slug}/index.html"
            return {
                "status": "skipped",
                "reason": "supabase client is not configured",
                "public_url": fallback_url,
                "game_id": None,
            }

        bucket = self.client.storage.from_(self.settings.supabase_storage_bucket)
        storage_path = f"{slug}/index.html"

        try:
            upload_payload = html_content.encode("utf-8")
            file_options = {
                "content-type": "text/html; charset=utf-8",
                "cache-control": "60",
                "x-upsert": "true",
            }
            try:
                bucket.upload(
                    storage_path,
                    upload_payload,
                    file_options=file_options,
                )
            except TypeError:
                bucket.upload(
                    storage_path,
                    upload_payload,
                    file_options={
                        "content-type": "text/html; charset=utf-8",
                        "cache-control": "60",
                        "upsert": "true",
                    },
                )
            except Exception:
                # Some storage backends/SDK versions preserve old metadata on upsert.
                # Force an explicit update so HTML content-type/charset is refreshed.
                bucket.update(storage_path, upload_payload, file_options=file_options)
        except Exception as exc:  # pragma: no cover - integration path
            return {
                "status": "error",
                "reason": f"storage_upload_failed: {exc}",
            }

        try:
            public_url = bucket.get_public_url(storage_path)
        except Exception:
            public_url = f"{self.settings.public_games_base_url.rstrip('/')}/{storage_path}"

        metadata_row = {
            "slug": slug,
            "name": name,
            "genre": genre,
            "url": public_url,
            "status": "active",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            result = self.client.table("games_metadata").upsert(metadata_row, on_conflict="slug").execute()
        except Exception as exc:  # pragma: no cover - integration path
            return {
                "status": "error",
                "reason": f"games_metadata_upsert_failed: {exc}",
                "public_url": public_url,
            }

        rows = result.data or []
        game_id = rows[0].get("id") if rows else None
        return {
            "status": "published",
            "public_url": public_url,
            "game_id": game_id,
            "storage_path": storage_path,
        }

    def delete_game_assets(self, *, slug: str) -> dict[str, Any]:
        if not self.client:
            return {"status": "error", "reason": "supabase client is not configured"}

        bucket = self.client.storage.from_(self.settings.supabase_storage_bucket)
        prefix = slug.strip().strip("/")
        if not prefix:
            return {"status": "error", "reason": "invalid_slug"}

        candidate_paths: set[str] = {
            f"{prefix}/index.html",
            f"{prefix}/game.js",
            f"{prefix}/styles.css",
            f"{prefix}/manifest.json",
        }

        listed_entries: Any = None
        for call in (
            lambda: bucket.list(prefix),
            lambda: bucket.list(prefix, {"limit": 1000}),
            lambda: bucket.list(path=prefix),
        ):
            try:
                listed_entries = call()
                break
            except TypeError:
                continue
            except Exception:
                listed_entries = None
                break

        if isinstance(listed_entries, list):
            for entry in listed_entries:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name")
                if isinstance(name, str) and name:
                    candidate_paths.add(f"{prefix}/{name}")

        try:
            bucket.remove(sorted(candidate_paths))
        except Exception as exc:  # pragma: no cover - integration path
            return {
                "status": "error",
                "reason": f"storage_delete_failed: {exc}",
                "paths": sorted(candidate_paths),
            }

        return {
            "status": "deleted",
            "paths": sorted(candidate_paths),
        }
