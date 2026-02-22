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

    def _list_archive_game_paths(self, game_slug: str) -> list[str]:
        return [f"games/{game_slug}/index.html", f"games/{game_slug}/styles.css", f"games/{game_slug}/game.js"]

    def _delete_file(self, path: str, commit_message: str) -> bool:
        self.put_calls.append((f"DELETE:{path}", "", commit_message))
        return True


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


def test_commit_archive_game_supports_multi_file_bundle() -> None:
    settings = Settings(github_token="token", github_archive_repo="owner/repo")
    service = DummyGitHubArchiveService(settings, manifest_payload={"schema_version": 1, "games": []})

    result = service.commit_archive_game(
        game_slug="bundle-game",
        game_name="Bundle Game",
        genre="racing",
        html_content="<html>fallback</html>",
        public_url="https://example.com/games/bundle-game/index.html",
        artifact_files=[
            {"path": "games/bundle-game/index.html", "content": "<html>index</html>", "content_type": "text/html; charset=utf-8"},
            {"path": "games/bundle-game/styles.css", "content": "body{}", "content_type": "text/css; charset=utf-8"},
            {"path": "games/bundle-game/game.js", "content": "console.log(1)", "content_type": "application/javascript; charset=utf-8"},
        ],
    )

    assert result["status"] == "committed"
    written_paths = [call[0] for call in service.put_calls]
    assert "games/bundle-game/index.html" in written_paths
    assert "games/bundle-game/styles.css" in written_paths
    assert "games/bundle-game/game.js" in written_paths
    assert "manifest/games.json" in written_paths


def test_delete_archive_game_deletes_bundle_files_and_updates_manifest() -> None:
    settings = Settings(github_token="token", github_archive_repo="owner/repo")
    service = DummyGitHubArchiveService(
        settings,
        manifest_payload={
            "schema_version": 1,
            "games": [
                {"slug": "bundle-game", "name": "Bundle", "genre": "arcade", "path": "games/bundle-game/index.html"},
                {"slug": "other", "name": "Other", "genre": "arcade", "path": "games/other/index.html"},
            ],
        },
    )

    result = service.delete_archive_game(game_slug="bundle-game")

    assert result["status"] == "deleted"
    delete_paths = [call[0] for call in service.put_calls if call[0].startswith("DELETE:")]
    assert "DELETE:games/bundle-game/index.html" in delete_paths
    assert "DELETE:games/bundle-game/styles.css" in delete_paths
    assert "DELETE:games/bundle-game/game.js" in delete_paths
    manifest_call = next(call for call in service.put_calls if call[0] == "manifest/games.json")
    manifest = json.loads(manifest_call[1])
    assert all(game["slug"] != "bundle-game" for game in manifest["games"])
