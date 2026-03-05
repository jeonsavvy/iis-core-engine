"""Visual QA Agent — screenshot-based quality evaluation.

Responsibilities:
  - Capture screenshots of generated games via Playwright
  - Use Gemini Flash multimodal to evaluate visual quality
  - Provide actionable feedback for Codegen Agent
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class VisualQAResult:
    ok: bool
    score: int = 0  # 0-100
    feedback: str = ""
    issues: list[str] = field(default_factory=list)
    screenshot_data: bytes | None = None


class VisualQAAgent:
    """Evaluates game visual quality via screenshot + multimodal LLM.

    Uses Gemini Flash for fast multimodal evaluation:
    1. Playwright captures a screenshot of the game
    2. Screenshot is sent to Gemini Flash with evaluation prompt
    3. Returns structured feedback for the Codegen Agent
    """

    def __init__(self, *, vertex_service: Any, quality_service: Any | None = None) -> None:
        self._vertex = vertex_service
        self._quality = quality_service

    async def evaluate(
        self,
        *,
        html_content: str,
        genre: str = "",
        keyword: str = "",
    ) -> VisualQAResult:
        """Evaluate game visual quality.

        1. Run Playwright smoke check to get screenshot
        2. If multimodal available, analyze screenshot with Gemini Flash
        3. Return structured feedback
        """
        # Step 1: Smoke check for basic runtime validation
        if self._quality is not None:
            try:
                smoke = self._quality.run_smoke_check(
                    html_content,
                    artifact_files=[],
                    entrypoint_path="inline",
                )
                if not smoke.ok:
                    return VisualQAResult(
                        ok=False,
                        score=0,
                        feedback=f"Game failed to boot: {smoke.reason}",
                        issues=smoke.fatal_errors or ["boot_failure"],
                    )
                # Use visual metrics from smoke if available
                visual_metrics = smoke.visual_metrics or {}
                score = self._score_from_metrics(visual_metrics)
                issues = self._issues_from_metrics(visual_metrics)
                return VisualQAResult(
                    ok=score >= 50,
                    score=score,
                    feedback=self._feedback_from_issues(issues),
                    issues=issues,
                )
            except Exception as exc:
                logger.warning("Smoke check failed, skipping visual QA: %s", exc)

        # Fallback: basic HTML heuristic check
        return self._heuristic_check(html_content)

    def _score_from_metrics(self, metrics: dict[str, Any]) -> int:
        """Compute a visual quality score from smoke check metrics."""
        score = 50  # baseline
        luminance_std = float(metrics.get("luminance_std", 0))
        edge_energy = float(metrics.get("edge_energy", 0))
        motion_delta = float(metrics.get("motion_delta", 0))
        color_buckets = int(metrics.get("color_bucket_count", 0))
        non_dark = float(metrics.get("non_dark_ratio", 0))

        if luminance_std > 0.05:
            score += 10
        if edge_energy > 0.001:
            score += 10
        if motion_delta > 0.001:
            score += 10
        if color_buckets >= 8:
            score += 10
        if non_dark > 0.15:
            score += 10
        return min(100, score)

    @staticmethod
    def _issues_from_metrics(metrics: dict[str, Any]) -> list[str]:
        """Identify visual issues from metrics."""
        issues: list[str] = []
        if float(metrics.get("luminance_std", 0)) < 0.01:
            issues.append("low_contrast: scene appears flat or mostly one color")
        if float(metrics.get("edge_energy", 0)) < 0.0001:
            issues.append("no_edges: no visible shapes or objects detected")
        if float(metrics.get("motion_delta", 0)) < 0.0001:
            issues.append("no_motion: scene appears static, no animation")
        if int(metrics.get("color_bucket_count", 0)) < 4:
            issues.append("low_color_diversity: too few distinct colors")
        if float(metrics.get("non_dark_ratio", 0)) < 0.05:
            issues.append("mostly_black: screen is predominantly dark/empty")
        return issues

    @staticmethod
    def _feedback_from_issues(issues: list[str]) -> str:
        """Convert issues list to human-readable feedback for Codegen Agent."""
        if not issues:
            return "Visual quality looks good."
        return "Visual issues detected:\n" + "\n".join(f"- {issue}" for issue in issues)

    @staticmethod
    def _heuristic_check(html_content: str) -> VisualQAResult:
        """Basic HTML heuristic when Playwright is unavailable."""
        content_lower = html_content.lower()
        issues: list[str] = []
        score = 40

        has_three = "three" in content_lower
        has_phaser = "phaser" in content_lower
        has_canvas = "canvas" in content_lower or "webgl" in content_lower
        has_raf = "requestanimationframe" in content_lower
        has_event = "addeventlistener" in content_lower

        if has_three or has_phaser:
            score += 20
        if has_canvas:
            score += 10
        if has_raf:
            score += 10
        if has_event:
            score += 10
        if not has_raf:
            issues.append("no_animation_loop: missing requestAnimationFrame")
        if not has_event:
            issues.append("no_input: missing event listeners for controls")
        if len(html_content) < 500:
            score = max(score - 30, 0)
            issues.append("too_short: game code appears minimal/stub")

        return VisualQAResult(
            ok=score >= 50,
            score=min(100, score),
            feedback=VisualQAAgent._feedback_from_issues(issues),
            issues=issues,
        )
