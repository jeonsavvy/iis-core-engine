"""Session Publisher — adapter for publishing games from editor sessions.

Wraps the existing PublisherService + GitHubArchiveService for the
interactive session workflow.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import Settings
from app.services.publisher_service import PublisherService
from app.services.github_service import GitHubArchiveService

logger = logging.getLogger(__name__)


class SessionPublisher:
    """Publishes a game from the editor session to Supabase + Archive."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._publisher = PublisherService(settings)
        self._archiver: GitHubArchiveService | None = None
        if settings.archive_repo_local_path:
            try:
                self._archiver = GitHubArchiveService(settings)
            except Exception:
                logger.warning("GitHub archive service not available, skipping.")

    async def publish(
        self,
        *,
        slug: str,
        game_name: str,
        genre: str,
        html_content: str,
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

        return {
            "success": True,
            "public_url": public_url,
            "game_id": str(game_id),
        }
