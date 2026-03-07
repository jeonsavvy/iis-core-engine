from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any

from app.core.config import Settings

logger = logging.getLogger(__name__)

ARCHIVE_ALLOWED_EXTENSIONS: set[str] = {
    ".html",
    ".css",
    ".js",
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".avif",
    ".svg",
    ".gif",
    ".mp3",
    ".ogg",
    ".wav",
    ".woff2",
}
ARCHIVE_MAX_FILE_BYTES = 5 * 1024 * 1024
ARCHIVE_GIT_TIMEOUT_SECONDS = 20


class CommandRunner:
    def run(self, cmd: list[str], **kwargs: Any) -> Any:
        return subprocess.run(cmd, **kwargs)


class GitHubArchiveService:
    """Repo3 archive commit integration via local subprocess GitOps."""

    def __init__(self, settings: Settings, *, runner: CommandRunner | None = None) -> None:
        self.settings = settings
        self.runner = runner or CommandRunner()
        # iis-core-engine/app/services/github_service.py
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        self.repo_path = os.path.join(base_dir, "iis-games-archive")

    def commit_archive_game(
        self,
        *,
        game_slug: str,
        game_name: str,
        genre: str,
        html_content: str,
        public_url: str,
        artifact_files: list[dict[str, str]] | None = None,
    ) -> dict[str, str]:
        if not os.path.exists(os.path.join(self.repo_path, ".git")):
            return {
                "status": "skipped",
                "reason": "Local archive repo not found at iis-games-archive",
            }

        sync_error = self._sync_archive_repo()
        if sync_error:
            return {"status": "error", "reason": sync_error}

        # 1. Update manifest
        manifest_path = os.path.join(self.repo_path, "manifest", "games.json")
        os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
        manifest = self._load_manifest(manifest_path)
        games = manifest.get("games", [])
        if not isinstance(games, list):
            games = []

        now = datetime.now(timezone.utc).isoformat()
        previous_row = next((g for g in games if isinstance(g, dict) and g.get("slug") == game_slug), None)
        created_at = previous_row.get("created_at", now) if isinstance(previous_row, dict) else now

        games = [g for g in games if isinstance(g, dict) and g.get("slug") != game_slug]
        games.append(
            {
                "slug": game_slug,
                "name": game_name,
                "genre": genre,
                "path": f"games/{game_slug}/index.html",
                "url": public_url,
                "created_at": created_at,
            }
        )
        manifest["games"] = games
        manifest["generated_at"] = now

        self._write_manifest(manifest_path, manifest)

        # 2. Write game files
        game_dir = os.path.join(self.repo_path, "games", game_slug)
        os.makedirs(game_dir, exist_ok=True)

        with open(os.path.join(game_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html_content)

        if artifact_files:
            for af in artifact_files:
                p = af.get("path", "").strip()
                rel_path = self._safe_archive_relative_path(game_slug=game_slug, candidate_path=p)
                if rel_path is None:
                    logger.warning("Skipping unsafe archive artifact path: %s", p)
                    continue
                content = af.get("content", "")
                encoded = content.encode("utf-8", errors="ignore")
                if len(encoded) > ARCHIVE_MAX_FILE_BYTES:
                    logger.warning("Skipping oversized archive artifact (%s bytes): %s", len(encoded), p)
                    continue
                full_p = os.path.join(game_dir, rel_path)
                normalized_game_dir = os.path.abspath(game_dir)
                normalized_target = os.path.abspath(full_p)
                if os.path.commonpath([normalized_game_dir, normalized_target]) != normalized_game_dir:
                    logger.warning("Skipping archive artifact that escapes game directory: %s", p)
                    continue
                os.makedirs(os.path.dirname(full_p), exist_ok=True)
                with open(full_p, "w", encoding="utf-8") as f:
                    f.write(content)

        stage_error = self._stage_archive_changes()
        if stage_error:
            self._rollback_archive_changes(game_slug=game_slug)
            return {"status": "error", "reason": stage_error}

        guard_error = self._run_archive_guard()
        if guard_error:
            self._rollback_archive_changes(game_slug=game_slug)
            return {"status": "error", "reason": guard_error}

        # 3. git add, commit, push
        try:
            commit_msg = f"feat: archive {game_slug}"

            st = self.runner.run(
                ["git", "status", "--porcelain"], cwd=self.repo_path, capture_output=True, text=True
            )
            if st.stdout.strip():
                self.runner.run(["git", "commit", "-m", commit_msg], cwd=self.repo_path, check=True)
                self.runner.run(["git", "push"], cwd=self.repo_path, check=True)
                return {"status": "committed", "slug": game_slug, "message": commit_msg}
            else:
                return {"status": "skipped", "reason": "no changes to commit"}
        except subprocess.CalledProcessError as exc:
            logger.error(f"Git commit/push failed: {exc}")
            return {"status": "error", "reason": f"git_operation_failed: {exc}"}

    def delete_archive_game(self, *, game_slug: str) -> dict[str, str]:
        if not os.path.exists(os.path.join(self.repo_path, ".git")):
            return {
                "status": "skipped",
                "reason": "Local archive repo not found at iis-games-archive",
            }

        sync_error = self._sync_archive_repo()
        if sync_error:
            return {"status": "error", "reason": sync_error}

        manifest_path = os.path.join(self.repo_path, "manifest", "games.json")
        manifest = self._load_manifest(manifest_path)
        games = manifest.get("games", [])
        if not isinstance(games, list):
            games = []

        games = [g for g in games if isinstance(g, dict) and g.get("slug") != game_slug]
        manifest["games"] = games
        manifest["generated_at"] = datetime.now(timezone.utc).isoformat()

        self._write_manifest(manifest_path, manifest)

        game_dir = os.path.join(self.repo_path, "games", game_slug)
        if os.path.exists(game_dir):
            shutil.rmtree(game_dir)

        stage_error = self._stage_archive_changes()
        if stage_error:
            self._rollback_archive_changes(game_slug=game_slug)
            return {"status": "error", "reason": stage_error}

        guard_error = self._run_archive_guard()
        if guard_error:
            self._rollback_archive_changes(game_slug=game_slug)
            return {"status": "error", "reason": guard_error}

        try:
            commit_msg = f"chore: delete archive {game_slug}"

            st = self.runner.run(
                ["git", "status", "--porcelain"], cwd=self.repo_path, capture_output=True, text=True
            )
            if st.stdout.strip():
                self.runner.run(["git", "commit", "-m", commit_msg], cwd=self.repo_path, check=True)
                self.runner.run(["git", "push"], cwd=self.repo_path, check=True)
                return {"status": "deleted", "slug": game_slug, "message": commit_msg}
            else:
                return {"status": "skipped", "reason": "no changes to commit"}
        except subprocess.CalledProcessError as exc:
            logger.error(f"Git delete/push failed: {exc}")
            return {"status": "error", "reason": f"git_operation_failed: {exc}"}

    def _stage_archive_changes(self) -> str | None:
        try:
            self.runner.run(
                ["git", "add", "--all"],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True,
                timeout=ARCHIVE_GIT_TIMEOUT_SECONDS,
            )
            return None
        except subprocess.TimeoutExpired as exc:
            logger.error("Archive stage timeout: %s", exc)
            return "archive_stage_failed: timeout"
        except subprocess.CalledProcessError as exc:
            output = (exc.stderr or exc.stdout or "").strip() or str(exc)
            logger.error("Archive stage failed: %s", output)
            return f"archive_stage_failed: {output}"

    def _sync_archive_repo(self) -> str | None:
        try:
            self.runner.run(
                ["git", "fetch", "--prune", "origin", "main"],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True,
                timeout=ARCHIVE_GIT_TIMEOUT_SECONDS,
            )
            self.runner.run(
                ["git", "checkout", "main"],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True,
                timeout=ARCHIVE_GIT_TIMEOUT_SECONDS,
            )
            self.runner.run(
                ["git", "reset", "--hard", "origin/main"],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True,
                timeout=ARCHIVE_GIT_TIMEOUT_SECONDS,
            )
            self.runner.run(
                ["git", "clean", "-fd"],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True,
                timeout=ARCHIVE_GIT_TIMEOUT_SECONDS,
            )
            return None
        except subprocess.TimeoutExpired as exc:
            logger.error("Archive sync timeout: %s", exc)
            return "archive_sync_failed: timeout"
        except subprocess.CalledProcessError as exc:
            output = (exc.stderr or exc.stdout or "").strip() or str(exc)
            logger.error("Archive sync failed: %s", output)
            return f"archive_sync_failed: {output}"

    def _run_archive_guard(self) -> str | None:
        script_path = os.path.join(self.repo_path, "scripts", "archive_guard.py")
        if not os.path.isfile(script_path):
            return None

        try:
            proc = self.runner.run(
                [sys.executable, "scripts/archive_guard.py", "all"],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info("Archive guard passed: %s", (proc.stdout or "").strip())
            return None
        except subprocess.CalledProcessError as exc:
            output = (exc.stderr or exc.stdout or "").strip() or str(exc)
            logger.error("Archive guard failed: %s", output)
            return f"archive_guard_failed: {output}"

    def _rollback_archive_changes(self, *, game_slug: str) -> None:
        manifest_path = "manifest/games.json"
        game_dir = f"games/{game_slug}"

        def _run_git(args: list[str]) -> None:
            try:
                self.runner.run(args, cwd=self.repo_path, check=False, capture_output=True, text=True)
            except Exception:
                return

        _run_git(["git", "restore", "--worktree", "--staged", "--", manifest_path, game_dir])
        _run_git(["git", "checkout", "--", manifest_path, game_dir])
        _run_git(["git", "clean", "-fd", "--", game_dir])

    @staticmethod
    def _normalize_manifest(raw_manifest: Any) -> dict[str, Any]:
        if isinstance(raw_manifest, dict):
            schema_version = raw_manifest.get("schema_version", 1)
            games = raw_manifest.get("games", [])
            if not isinstance(games, list):
                games = []
            try:
                normalized_schema_version = int(schema_version)
            except (TypeError, ValueError):
                normalized_schema_version = 1
            return {
                **raw_manifest,
                "schema_version": normalized_schema_version,
                "games": games,
            }

        if isinstance(raw_manifest, list):
            games = [item for item in raw_manifest if isinstance(item, dict)]
            return {"schema_version": 1, "games": games}

        return {"schema_version": 1, "games": []}

    def _load_manifest(self, manifest_path: str) -> dict[str, Any]:
        try:
            with open(manifest_path, "r", encoding="utf-8") as file:
                raw_manifest = json.load(file)
        except (OSError, json.JSONDecodeError):
            raw_manifest = {"schema_version": 1, "games": []}
        return self._normalize_manifest(raw_manifest)

    @staticmethod
    def _write_manifest(manifest_path: str, manifest: dict[str, Any]) -> None:
        with open(manifest_path, "w", encoding="utf-8") as file:
            json.dump(manifest, file, ensure_ascii=False, indent=2)
            file.write("\n")

    @staticmethod
    def _safe_archive_relative_path(*, game_slug: str, candidate_path: str) -> str | None:
        normalized = str(candidate_path or "").strip().replace("\\", "/")
        base_prefix = f"games/{game_slug}/"
        if not normalized.startswith(base_prefix):
            return None

        raw_rel = normalized[len(base_prefix) :].lstrip("/")
        if not raw_rel or "//" in raw_rel:
            return None

        pure = PurePosixPath(raw_rel)
        if pure.is_absolute():
            return None
        for part in pure.parts:
            if part in {"", ".", ".."}:
                return None
            if part.startswith("."):
                return None

        extension = pure.suffix.casefold()
        if extension not in ARCHIVE_ALLOWED_EXTENSIONS:
            return None

        return str(pure)
