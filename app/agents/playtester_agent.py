"""Playtester Agent — automated gameplay testing via Playwright.

Responsibilities:
  - Boot the game and verify it loads correctly
  - Simulate keyboard/mouse input
  - Check for JS console errors
  - Measure basic responsiveness
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PlaytestResult:
    boots_ok: bool
    has_errors: bool = False
    console_errors: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    fatal_issues: list[str] = field(default_factory=list)
    feedback: str = ""
    score: int = 0  # 0-100


class PlaytesterAgent:
    """Automated playtesting agent using Playwright.

    Reuses the existing quality_smoke.py infrastructure:
    1. Load game HTML in headless browser
    2. Verify boot (window.__iis_game_boot_ok)
    3. Simulate basic inputs
    4. Collect console errors
    5. Return structured feedback
    """

    def __init__(self, *, quality_service: Any | None = None) -> None:
        self._quality = quality_service

    async def test(self, *, html_content: str) -> PlaytestResult:
        """Run automated playtest on game HTML."""
        if self._quality is None:
            return self._heuristic_test(html_content)

        try:
            smoke = self._quality.run_smoke_check(
                html_content,
                artifact_files=[],
                entrypoint_path="inline",
            )
            errors = smoke.fatal_errors or []
            warnings = smoke.non_fatal_warnings or []

            score = 80 if smoke.ok else 20
            if errors:
                score = max(score - len(errors) * 15, 0)
            if warnings:
                score = max(score - len(warnings) * 5, 0)

            feedback_parts: list[str] = []
            if not smoke.ok:
                feedback_parts.append(f"Boot failed: {smoke.reason}")
            if errors:
                feedback_parts.append(
                    "Console errors:\n" + "\n".join(f"  - {e}" for e in errors[:5])
                )
            if warnings:
                feedback_parts.append(
                    "Warnings:\n" + "\n".join(f"  - {w}" for w in warnings[:5])
                )
            if not feedback_parts:
                feedback_parts.append("Game boots and runs without errors.")

            return PlaytestResult(
                boots_ok=smoke.ok,
                has_errors=bool(errors),
                console_errors=errors,
                issues=[*errors, *warnings],
                fatal_issues=list(errors) if not smoke.ok else [],
                feedback="\n".join(feedback_parts),
                score=min(100, score),
            )
        except Exception as exc:
            logger.warning("Playwright test failed: %s", exc)
            return self._heuristic_test(html_content)

    @staticmethod
    def _heuristic_test(html_content: str) -> PlaytestResult:
        """Fallback heuristic when Playwright is unavailable."""
        lower = html_content.lower()
        issues: list[str] = []
        fatal_issues: list[str] = []

        has_boot_flag = "__iis_game_boot_ok" in lower
        has_raf = "requestanimationframe" in lower
        has_input = "keydown" in lower or "keyup" in lower or "addeventlistener" in lower
        has_restart = "restart" in lower or "reset" in lower or "gameover" in lower

        score = 40
        if has_boot_flag:
            score += 15
        else:
            issue = "Missing boot flag (window.__iis_game_boot_ok)"
            issues.append(issue)
            fatal_issues.append(issue)
        if has_raf:
            score += 15
        else:
            issue = "Missing animation loop (requestAnimationFrame)"
            issues.append(issue)
            fatal_issues.append(issue)
        if has_input:
            score += 15
        else:
            issues.append("Missing input handling (no keyboard listeners)")
        if has_restart:
            score += 15
        else:
            issues.append("Missing restart/game-over flow")

        is_racing = "open-wheel circuit racing" in lower or "lap-state" in lower
        if is_racing:
            if "respawntocheckpoint" not in lower:
                issues.append("Missing checkpoint respawn safety")
            if "offtracktimer" not in lower and "off track" not in lower:
                issues.append("Missing off-track penalty flow")
            if "countdown" not in lower:
                issues.append("Missing race countdown flow")

        is_dogfight = "space dogfight" in lower or "target-readout" in lower
        if is_dogfight:
            if "enemylasers" not in lower and "fireenemylaser" not in lower:
                issues.append("Missing enemy attack loop")
            if "shield" not in lower:
                issues.append("Missing shield feedback")
            if "boostcharge" not in lower:
                issues.append("Missing boost feedback")

        is_island_flight = "low-poly island flight" in lower or "ring-readout" in lower
        if is_island_flight:
            if "yaw" not in lower:
                issues.append("Missing yaw authority for island flight")
            if "stabilize" not in lower:
                issues.append("Missing stabilize / auto-level control")
            if "ring" not in lower:
                issues.append("Missing traversal ring loop")
            if "terrainheightat" not in lower:
                issues.append("Missing terrain clearance guard")
            if "lastsafepoint" not in lower:
                issues.append("Missing safe respawn tracking")

        is_topdown = "lowpoly tactical arena" in lower or "title-screen" in lower
        if is_topdown:
            if "enemybullets" not in lower and "fireenemybullet" not in lower:
                issues.append("Missing enemy pressure loop")
            if "title-screen" not in lower:
                issues.append("Missing title/menu state flow")
            if "coverblocks" not in lower:
                issues.append("Missing arena cover landmarks")
            if "shake(" not in lower:
                issues.append("Missing impact screen shake")

        return PlaytestResult(
            boots_ok=has_boot_flag and has_raf,
            has_errors=bool(issues),
            console_errors=issues,
            issues=issues,
            fatal_issues=fatal_issues,
            feedback="\n".join(f"- {i}" for i in issues) if issues else "Heuristic check passed.",
            score=min(100, score),
        )
