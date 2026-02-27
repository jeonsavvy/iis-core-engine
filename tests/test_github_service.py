from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from app.core.config import Settings
from app.services.github_service import GitHubArchiveService


def _prepare_archive_repo(root: Path) -> Path:
    repo_path = root / "iis-games-archive"
    (repo_path / ".git").mkdir(parents=True)
    (repo_path / "manifest").mkdir(parents=True)
    return repo_path


def _install_archive_guard_script(repo_path: Path) -> None:
    script_path = repo_path / "scripts" / "archive_guard.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text("print('ok')\n", encoding="utf-8")


def _install_subprocess_stub(monkeypatch, *, changed: bool = True) -> list[list[str]]:
    calls: list[list[str]] = []

    def _fake_run(cmd, cwd=None, check=False, capture_output=False, text=False, timeout=None):  # noqa: ANN001, ARG001
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


def test_commit_archive_game_ignores_unsafe_artifact_paths(tmp_path, monkeypatch) -> None:
    repo_path = _prepare_archive_repo(tmp_path)
    manifest_path = repo_path / "manifest" / "games.json"
    manifest_path.write_text(json.dumps({"schema_version": 1, "games": []}), encoding="utf-8")
    sentinel = repo_path / "README.md"
    sentinel.write_text("do-not-touch", encoding="utf-8")
    _install_subprocess_stub(monkeypatch)

    service = GitHubArchiveService(Settings())
    service.repo_path = str(repo_path)

    result = service.commit_archive_game(
        game_slug="safe-game",
        game_name="Safe Game",
        genre="arcade",
        html_content="<html>fallback</html>",
        public_url="https://example.com/games/safe-game/index.html",
        artifact_files=[
            {"path": "games/safe-game/index.html", "content": "<html>index</html>"},
            {"path": "games/safe-game/assets/game.js", "content": "console.log('safe')"},
            {"path": "games/safe-game/.hidden.js", "content": "hidden"},
            {"path": "games/safe-game/../../README.md", "content": "hacked"},
            {"path": "games/other-game/index.html", "content": "wrong-slug"},
            {"path": "games/safe-game/payload.exe", "content": "binary"},
        ],
    )

    assert result["status"] == "committed"
    assert (repo_path / "games" / "safe-game" / "index.html").read_text(encoding="utf-8") == "<html>index</html>"
    assert (repo_path / "games" / "safe-game" / "assets" / "game.js").read_text(encoding="utf-8") == "console.log('safe')"
    assert not (repo_path / "games" / "safe-game" / ".hidden.js").exists()
    assert not (repo_path / "games" / "safe-game" / "payload.exe").exists()
    assert sentinel.read_text(encoding="utf-8") == "do-not-touch"


def test_commit_archive_game_ignores_oversized_artifact(tmp_path, monkeypatch) -> None:
    repo_path = _prepare_archive_repo(tmp_path)
    manifest_path = repo_path / "manifest" / "games.json"
    manifest_path.write_text(json.dumps({"schema_version": 1, "games": []}), encoding="utf-8")
    _install_subprocess_stub(monkeypatch)

    service = GitHubArchiveService(Settings())
    service.repo_path = str(repo_path)
    huge_payload = "x" * (5 * 1024 * 1024 + 1)

    result = service.commit_archive_game(
        game_slug="large-game",
        game_name="Large Game",
        genre="arcade",
        html_content="<html>fallback</html>",
        public_url="https://example.com/games/large-game/index.html",
        artifact_files=[
            {"path": "games/large-game/index.html", "content": "<html>index</html>"},
            {"path": "games/large-game/assets/huge.json", "content": huge_payload},
        ],
    )

    assert result["status"] == "committed"
    assert (repo_path / "games" / "large-game" / "index.html").read_text(encoding="utf-8") == "<html>index</html>"
    assert not (repo_path / "games" / "large-game" / "assets" / "huge.json").exists()


def test_safe_archive_relative_path_validation() -> None:
    assert GitHubArchiveService._safe_archive_relative_path(
        game_slug="safe-game",
        candidate_path="games/safe-game/assets/game.js",
    ) == "assets/game.js"

    assert (
        GitHubArchiveService._safe_archive_relative_path(
            game_slug="safe-game",
            candidate_path="games/safe-game/../../README.md",
        )
        is None
    )
    assert (
        GitHubArchiveService._safe_archive_relative_path(
            game_slug="safe-game",
            candidate_path="games/safe-game/.hidden.js",
        )
        is None
    )
    assert (
        GitHubArchiveService._safe_archive_relative_path(
            game_slug="safe-game",
            candidate_path="games/safe-game/payload.exe",
        )
        is None
    )


def test_commit_archive_game_runs_archive_guard_when_script_exists(tmp_path, monkeypatch) -> None:
    repo_path = _prepare_archive_repo(tmp_path)
    _install_archive_guard_script(repo_path)
    (repo_path / "manifest" / "games.json").write_text(json.dumps({"schema_version": 1, "games": []}), encoding="utf-8")
    calls = _install_subprocess_stub(monkeypatch)

    service = GitHubArchiveService(Settings())
    service.repo_path = str(repo_path)

    result = service.commit_archive_game(
        game_slug="guarded-game",
        game_name="Guarded Game",
        genre="arcade",
        html_content="<html>ok</html>",
        public_url="https://example.com/games/guarded-game/index.html",
    )

    assert result["status"] == "committed"
    assert any(cmd[:3] == ["python3", "scripts/archive_guard.py", "all"] or cmd[1:3] == ["scripts/archive_guard.py", "all"] for cmd in calls)


def test_commit_archive_game_aborts_when_archive_guard_fails(tmp_path, monkeypatch) -> None:
    repo_path = _prepare_archive_repo(tmp_path)
    _install_archive_guard_script(repo_path)
    (repo_path / "manifest" / "games.json").write_text(json.dumps({"schema_version": 1, "games": []}), encoding="utf-8")
    calls: list[list[str]] = []

    def _fake_run(cmd, cwd=None, check=False, capture_output=False, text=False, timeout=None):  # noqa: ANN001, ARG001
        normalized = [str(item) for item in cmd]
        calls.append(normalized)
        if normalized[1:3] == ["scripts/archive_guard.py", "all"]:
            raise subprocess.CalledProcessError(
                1,
                normalized,
                output="",
                stderr="Disallowed file detected: tests/poc.txt",
            )
        if normalized[:3] == ["git", "status", "--porcelain"]:
            return SimpleNamespace(stdout=" M manifest/games.json\n", returncode=0)
        return SimpleNamespace(stdout="", returncode=0)

    monkeypatch.setattr("app.services.github_service.subprocess.run", _fake_run)

    service = GitHubArchiveService(Settings())
    service.repo_path = str(repo_path)

    result = service.commit_archive_game(
        game_slug="blocked-game",
        game_name="Blocked Game",
        genre="arcade",
        html_content="<html>blocked</html>",
        public_url="https://example.com/games/blocked-game/index.html",
    )

    assert result["status"] == "error"
    assert result["reason"].startswith("archive_guard_failed:")
    assert not any(cmd[:2] == ["git", "commit"] for cmd in calls)
    assert not any(cmd[:2] == ["git", "push"] for cmd in calls)
    assert any(cmd[:3] == ["git", "restore", "--worktree"] for cmd in calls)
    assert any(cmd[:2] == ["git", "checkout"] for cmd in calls)
    assert any(cmd[:2] == ["git", "clean"] for cmd in calls)
