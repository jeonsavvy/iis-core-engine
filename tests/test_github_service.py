from __future__ import annotations

import json

from app.core.config import Settings
from app.services.github_service import GitHubArchiveService


class DummyGitHubArchiveService(GitHubArchiveService):
    def __init__(self, settings: Settings, manifest_payload):
        super().__init__(settings)
        self.manifest_payload = manifest_payload
        self.put_calls: list[tuple[str, str, str]] = []

    def _fetch_json_file(self, path: str):
        assert path == "manifest/games.json"
        return self.manifest_payload

    def _put_file(self, path: str, content: str, commit_message: str) -> None:
        self.put_calls.append((path, content, commit_message))


def test_commit_archive_game_normalizes_manifest_to_versioned_object() -> None:
    settings = Settings(github_token="token", github_archive_repo="owner/repo")
    service = DummyGitHubArchiveService(
        settings,
        manifest_payload=[
            {
                "slug": "old-game",
                "name": "Old Game",
                "genre": "arcade",
                "path": "games/old-game/index.html",
                "created_at": "2026-01-01T00:00:00Z",
            }
        ],
    )

    result = service.commit_archive_game(
        game_slug="new-game",
        game_name="New Game",
        genre="puzzle",
        html_content="<html><body>ok</body></html>",
        public_url="https://example.com/games/new-game/index.html",
    )

    assert result["status"] == "committed"
    assert result["message"] == "feat: archive new-game"

    manifest_call = next(call for call in service.put_calls if call[0] == "manifest/games.json")
    manifest = json.loads(manifest_call[1])

    assert manifest["schema_version"] == 1
    assert isinstance(manifest["games"], list)
    assert any(game["slug"] == "new-game" for game in manifest["games"])
