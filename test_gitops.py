import sys
import logging
from app.core.config import Settings
from app.services.github_service import GitHubArchiveService

logging.basicConfig(level=logging.INFO)
settings = Settings()
svc = GitHubArchiveService(settings)

print("Archive path:", svc.repo_path)
res = svc.commit_archive_game(
    game_slug="test-game-gitops",
    game_name="Test Game GitOps",
    genre="action",
    html_content="<h1>Test</h1>",
    public_url="https://example.com",
    artifact_files=[]
)
print("Result:", res)
