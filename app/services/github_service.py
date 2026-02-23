from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings

logger = logging.getLogger(__name__)


class GitHubArchiveService:
    """Repo3 archive commit integration via local subprocess GitOps."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
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

        # 1. Update manifest
        manifest_path = os.path.join(self.repo_path, "manifest", "games.json")
        os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = {"schema_version": 1, "games": []}

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

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
            f.write("\n")

        # 2. Write game files
        game_dir = os.path.join(self.repo_path, "games", game_slug)
        os.makedirs(game_dir, exist_ok=True)

        with open(os.path.join(game_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html_content)

        if artifact_files:
            for af in artifact_files:
                p = af.get("path", "").strip()
                if not p.startswith(f"games/{game_slug}/"):
                    continue
                content = af.get("content", "")
                rel_path = p[len(f"games/{game_slug}/") :]
                full_p = os.path.join(game_dir, rel_path)
                os.makedirs(os.path.dirname(full_p), exist_ok=True)
                with open(full_p, "w", encoding="utf-8") as f:
                    f.write(content)

        # 3. git add, commit, push
        try:
            subprocess.run(["git", "add", "--all"], cwd=self.repo_path, check=True)
            commit_msg = f"feat: archive {game_slug}"
            
            st = subprocess.run(
                ["git", "status", "--porcelain"], cwd=self.repo_path, capture_output=True, text=True
            )
            if st.stdout.strip():
                subprocess.run(["git", "commit", "-m", commit_msg], cwd=self.repo_path, check=True)
                subprocess.run(["git", "push"], cwd=self.repo_path, check=True)
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

        manifest_path = os.path.join(self.repo_path, "manifest", "games.json")
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = {"schema_version": 1, "games": []}

        games = manifest.get("games", [])
        if not isinstance(games, list):
            games = []

        original_count = len(games)
        games = [g for g in games if isinstance(g, dict) and g.get("slug") != game_slug]
        manifest["games"] = games
        manifest["generated_at"] = datetime.now(timezone.utc).isoformat()

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
            f.write("\n")

        game_dir = os.path.join(self.repo_path, "games", game_slug)
        if os.path.exists(game_dir):
            shutil.rmtree(game_dir)

        try:
            # We use git add --all to stage the deleted files robustly
            subprocess.run(["git", "add", "--all"], cwd=self.repo_path, check=True)
            commit_msg = f"chore: delete archive {game_slug}"

            st = subprocess.run(
                ["git", "status", "--porcelain"], cwd=self.repo_path, capture_output=True, text=True
            )
            if st.stdout.strip():
                subprocess.run(["git", "commit", "-m", commit_msg], cwd=self.repo_path, check=True)
                subprocess.run(["git", "push"], cwd=self.repo_path, check=True)
                return {"status": "deleted", "slug": game_slug, "message": commit_msg}
            else:
                return {"status": "skipped", "reason": "no changes to commit"}
        except subprocess.CalledProcessError as exc:
            logger.error(f"Git delete/push failed: {exc}")
            return {"status": "error", "reason": f"git_operation_failed: {exc}"}

