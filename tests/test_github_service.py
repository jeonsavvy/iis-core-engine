from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.core.config import Settings
from app.services.github_service import GitHubArchiveService


def _prepare_archive_repo(root: Path) -> Path:
    repo_path = root / "iis-games-archive"
    (repo_path / ".git").mkdir(parents=True)
    (repo_path / "manifest").mkdir(parents=True)
    return repo_path


def _install_subprocess_stub(monkeypatch, *, changed: bool = True) -> list[list[str]]:
    calls: list[list[str]] = []

    def _fake_run(cmd, cwd=None, check=False, capture_output=False, text=False):  # noqa: ANN001
        normalized = [str(item) for item in cmd]
        calls.append(normalized)
        if normalized[:3] == ["git", "status", "--porcelain"]:
            return SimpleNamespace(stdout=" M manifest/games.json\n" if changed else "", returncode=0)
        return SimpleNamespace(stdout="", returncode=0)

    monkeypatch.setattr("app.services.github_service.subprocess.run", _fake_run)
    return calls


def test_commit_archive_game_normalizes_manifest_to_versioned_object(tmp_path, monkeypatch) -> None:
    repo_path = _prepare_archive_repo(tmp_path)
    manifest_path = repo_path / "manifest" / "games.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "slug": "old-game",
                    "name": "Old Game",
                    "genre": "arcade",
                    "path": "games/old-game/index.html",
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ]
        ),
        encoding="utf-8",
    )
    calls = _install_subprocess_stub(monkeypatch)

    service = GitHubArchiveService(Settings())
    service.repo_path = str(repo_path)

    result = service.commit_archive_game(
        game_slug="new-game",
        game_name="New Game",
        genre="puzzle",
        html_content="<html><body>ok</body></html>",
        public_url="https://example.com/games/new-game/index.html",
    )

    assert result["status"] == "committed"
    assert result["message"] == "feat: archive new-game"
    assert ["git", "push"] in calls

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert any(game["slug"] == "new-game" for game in manifest["games"])
    assert (repo_path / "games" / "new-game" / "index.html").exists()


def test_commit_archive_game_supports_multi_file_bundle(tmp_path, monkeypatch) -> None:
    repo_path = _prepare_archive_repo(tmp_path)
    manifest_path = repo_path / "manifest" / "games.json"
    manifest_path.write_text(json.dumps({"schema_version": 1, "games": []}), encoding="utf-8")
    _install_subprocess_stub(monkeypatch)

    service = GitHubArchiveService(Settings())
    service.repo_path = str(repo_path)

    result = service.commit_archive_game(
        game_slug="bundle-game",
        game_name="Bundle Game",
        genre="racing",
        html_content="<html>fallback</html>",
        public_url="https://example.com/games/bundle-game/index.html",
        artifact_files=[
            {"path": "games/bundle-game/index.html", "content": "<html>index</html>"},
            {"path": "games/bundle-game/styles.css", "content": "body{}"},
            {"path": "games/bundle-game/game.js", "content": "console.log(1)"},
        ],
    )

    assert result["status"] == "committed"
    assert (repo_path / "games" / "bundle-game" / "index.html").read_text(encoding="utf-8") == "<html>index</html>"
    assert (repo_path / "games" / "bundle-game" / "styles.css").read_text(encoding="utf-8") == "body{}"
    assert (repo_path / "games" / "bundle-game" / "game.js").read_text(encoding="utf-8") == "console.log(1)"


def test_delete_archive_game_removes_bundle_and_updates_manifest(tmp_path, monkeypatch) -> None:
    repo_path = _prepare_archive_repo(tmp_path)
    manifest_path = repo_path / "manifest" / "games.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "games": [
                    {"slug": "bundle-game", "name": "Bundle", "genre": "arcade", "path": "games/bundle-game/index.html"},
                    {"slug": "other-game", "name": "Other", "genre": "arcade", "path": "games/other-game/index.html"},
                ],
            }
        ),
        encoding="utf-8",
    )
    target_dir = repo_path / "games" / "bundle-game"
    target_dir.mkdir(parents=True)
    (target_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    (target_dir / "styles.css").write_text("body{}", encoding="utf-8")
    calls = _install_subprocess_stub(monkeypatch)

    service = GitHubArchiveService(Settings())
    service.repo_path = str(repo_path)

    result = service.delete_archive_game(game_slug="bundle-game")

    assert result["status"] == "deleted"
    assert ["git", "push"] in calls
    assert not target_dir.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert all(game["slug"] != "bundle-game" for game in manifest["games"])
