from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings
from app.services.supabase_service import create_supabase_admin_client

logger = logging.getLogger(__name__)


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
        artifact_files: list[dict[str, str]] | None = None,
        entrypoint_path: str | None = None,
    ) -> dict[str, Any]:
        try:
            fallback_entry = self._normalize_storage_path(entrypoint_path or f"games/{slug}/index.html", slug)
        except Exception as exc:
            return {"status": "error", "reason": f"invalid_artifact_path: {exc}"}

        if not self.client:
            fallback_url = f"{self.settings.public_games_base_url.rstrip('/')}/{fallback_entry}"
            return {
                "status": "skipped",
                "reason": "supabase client is not configured",
                "public_url": fallback_url,
                "game_id": None,
            }

        bucket = self.client.storage.from_(self.settings.supabase_storage_bucket)
        files_to_upload = self._normalize_artifact_files(
            slug=slug,
            html_content=html_content,
            artifact_files=artifact_files,
        )
        entry_storage_path = fallback_entry

        try:
            for file_row in files_to_upload:
                storage_path = str(file_row["storage_path"])
                upload_payload = str(file_row["content"]).encode("utf-8")
                content_type = str(file_row["content_type"])
                file_options = {
                    "content-type": content_type,
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
                            "content-type": content_type,
                            "cache-control": "60",
                            "upsert": "true",
                        },
                    )
                except Exception:
                    bucket.update(storage_path, upload_payload, file_options=file_options)

                # Some storage backends/SDK versions preserve old metadata on POST upsert.
                # Force a follow-up metadata refresh for entry HTML to avoid text/plain regressions.
                if storage_path.endswith("index.html"):
                    bucket.update(
                        storage_path,
                        upload_payload,
                        file_options={
                            "content-type": "text/html; charset=utf-8",
                            "cache-control": "60",
                        },
                    )
        except Exception as exc:  # pragma: no cover - integration path
            return {
                "status": "error",
                "reason": f"storage_upload_failed: {exc}",
            }

        try:
            public_url = bucket.get_public_url(entry_storage_path)
        except Exception:
            public_url = f"{self.settings.public_games_base_url.rstrip('/')}/{entry_storage_path}"

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
            "storage_path": entry_storage_path,
            "uploaded_files": [row["storage_path"] for row in files_to_upload],
        }

    def upload_screenshot(self, *, slug: str, screenshot_bytes: bytes) -> str | None:
        if not self.client:
            return None
        
        bucket = self.client.storage.from_(self.settings.supabase_storage_bucket)
        storage_path = f"{slug}/screenshot.png"
        file_options = {
            "content-type": "image/png",
            "cache-control": "60",
            "x-upsert": "true",
        }
        try:
            try:
                bucket.upload(storage_path, screenshot_bytes, file_options=file_options)
            except TypeError:
                bucket.upload(
                    storage_path,
                    screenshot_bytes,
                    file_options={"content-type": "image/png", "cache-control": "60", "upsert": "true"}
                )
            except Exception:
                bucket.update(storage_path, screenshot_bytes, file_options=file_options)
            return bucket.get_public_url(storage_path)
        except Exception:
            return None

    def update_game_marketing(self, *, slug: str, ai_review: str | None = None, screenshot_url: str | None = None) -> bool:
        if not self.client:
            return False
            
        update_dist = {}
        if ai_review is not None:
            update_dist["ai_review"] = ai_review
        if screenshot_url is not None:
            update_dist["screenshot_url"] = screenshot_url
            
        if not update_dist:
            return True
            
        max_retries = max(1, int(self.settings.http_max_retries))
        for attempt in range(1, max_retries + 1):
            try:
                self.client.table("games_metadata").update(update_dist).eq("slug", slug).execute()
                return True
            except Exception as exc:
                if attempt >= max_retries:
                    logger.warning("update_game_marketing failed after retries: slug=%s, error=%s", slug, exc)
                    return False
                time.sleep(min(0.15 * attempt, 0.5))
        return False

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

    @staticmethod
    def _normalize_storage_path(path: str, slug: str) -> str:
        normalized = path.strip().lstrip("/")
        if normalized.startswith("games/"):
            normalized = normalized[len("games/") :]
        if not normalized.startswith(f"{slug}/"):
            raise ValueError("artifact path is outside game slug prefix")
        return normalized

    def _normalize_artifact_files(
        self,
        *,
        slug: str,
        html_content: str,
        artifact_files: list[dict[str, str]] | None,
    ) -> list[dict[str, str]]:
        if not artifact_files:
            return [
                {
                    "storage_path": f"{slug}/index.html",
                    "content": html_content,
                    "content_type": "text/html; charset=utf-8",
                }
            ]

        normalized_files: list[dict[str, str]] = []
        for row in artifact_files:
            raw_path = str(row.get("path", "")).strip()
            if not raw_path:
                continue
            storage_path = self._normalize_storage_path(raw_path, slug)
            content = str(row.get("content", ""))
            if not content:
                continue
            content_type = str(row.get("content_type", "")).strip() or self._guess_content_type(storage_path)
            normalized_files.append(
                {
                    "storage_path": storage_path,
                    "content": content,
                    "content_type": content_type,
                }
            )

        if not normalized_files:
            return [
                {
                    "storage_path": f"{slug}/index.html",
                    "content": html_content,
                    "content_type": "text/html; charset=utf-8",
                }
            ]
        return normalized_files

    @staticmethod
    def _guess_content_type(path: str) -> str:
        lower = path.lower()
        if lower.endswith(".html"):
            return "text/html; charset=utf-8"
        if lower.endswith(".js"):
            return "application/javascript; charset=utf-8"
        if lower.endswith(".css"):
            return "text/css; charset=utf-8"
        if lower.endswith(".json"):
            return "application/json; charset=utf-8"
        return "text/plain; charset=utf-8"
