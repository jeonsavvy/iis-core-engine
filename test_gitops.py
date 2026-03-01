from __future__ import annotations

import logging
import os

from app.core.config import Settings
from app.services.github_service import GitHubArchiveService

logging.basicConfig(level=logging.INFO)


def main() -> int:
    if os.getenv("ENABLE_GITOPS_TEST") != "1":
        print("Skipped: set ENABLE_GITOPS_TEST=1 to run this destructive GitOps check.")
        return 0

    settings = Settings()
    svc = GitHubArchiveService(settings)

    print("Archive path:", svc.repo_path)
    res = svc.commit_archive_game(
        game_slug="test-game-gitops",
        game_name="Test Game GitOps",
        genre="action",
        html_content="<h1>Test</h1>",
        public_url="https://example.com",
        artifact_files=[],
    )
    print("Result:", res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
