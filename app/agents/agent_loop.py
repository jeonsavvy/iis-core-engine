"""Agent Loop — multi-agent orchestrator for interactive game generation.

The loop coordinates three agents:
  1. Codegen Agent: generates/modifies game code
  2. Visual QA Agent: evaluates visual quality (optional, async)
  3. Playtester Agent: tests playability (optional, async)

Flow:
  User prompt → Codegen → (auto) Visual QA + Playtester
  → if needs improvement → Codegen refine (max 2 rounds)
  → return result to user
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.agents.codegen_agent import CodegenAgent, ConversationMessage
from app.agents.playtester_agent import PlaytesterAgent
from app.agents.visual_qa_agent import VisualQAAgent

logger = logging.getLogger(__name__)

_MAX_AUTO_REFINE_ROUNDS = 2
_AUTO_REFINE_SCORE_THRESHOLD = 50


@dataclass
class AgentActivity:
    """Record of a single agent action within the loop."""

    agent: str  # "codegen" | "visual_qa" | "playtester"
    action: str  # "generate" | "modify" | "evaluate" | "test" | "refine"
    summary: str = ""
    score: int = 0
    decision_reason: str = ""
    input_signal: str = ""
    change_impact: str = ""
    confidence: float = 0.0
    error_code: str | None = None
    before_score: int | None = None
    after_score: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentLoopResult:
    """Final result from the agent loop."""

    html: str
    activities: list[AgentActivity] = field(default_factory=list)
    final_score: int = 0
    generation_source: str = "vertex"
    auto_refined: bool = False
    refinement_rounds: int = 0
    error: str = ""


class AgentLoop:
    """Multi-agent loop orchestrator."""

    def __init__(
        self,
        *,
        codegen: CodegenAgent,
        visual_qa: VisualQAAgent | None = None,
        playtester: PlaytesterAgent | None = None,
    ) -> None:
        self._codegen = codegen
        self._visual_qa = visual_qa
        self._playtester = playtester

    async def run(
        self,
        *,
        user_prompt: str,
        history: list[ConversationMessage] | None = None,
        current_html: str = "",
        genre_hint: str = "",
        auto_qa: bool = True,
    ) -> AgentLoopResult:
        activities: list[AgentActivity] = []

        is_modification = bool(current_html.strip())
        action = "modify" if is_modification else "generate"

        codegen_result = await self._codegen.generate(
            user_prompt=user_prompt,
            history=history,
            current_html=current_html,
            genre_hint=genre_hint,
        )

        activities.append(
            AgentActivity(
                agent="codegen",
                action=action,
                summary=f"Generated {len(codegen_result.html)} chars via {codegen_result.generation_source}",
                score=0,
                decision_reason="initial_user_prompt" if not is_modification else "user_requested_modification",
                input_signal=user_prompt[:500],
                change_impact="initial_generation" if not is_modification else "updated_existing_game",
                confidence=0.9 if codegen_result.generation_source == "vertex" else 0.25,
                error_code=codegen_result.error or None,
                metadata={
                    "model": codegen_result.model_name,
                    "source": codegen_result.generation_source,
                },
            )
        )

        if codegen_result.error:
            return AgentLoopResult(
                html=current_html,
                activities=activities,
                final_score=0,
                generation_source=codegen_result.generation_source,
                auto_refined=False,
                refinement_rounds=0,
                error=codegen_result.error,
            )

        final_html = codegen_result.html
        combined_score = 0
        refinement_rounds = 0

        if auto_qa and (self._visual_qa is not None or self._playtester is not None):
            for round_idx in range(_MAX_AUTO_REFINE_ROUNDS + 1):
                qa_feedback_parts: list[str] = []

                if self._visual_qa is not None:
                    before = combined_score
                    visual_result = await self._visual_qa.evaluate(
                        html_content=final_html,
                        genre=genre_hint,
                    )
                    combined_score = max(combined_score, visual_result.score)
                    activities.append(
                        AgentActivity(
                            agent="visual_qa",
                            action="evaluate",
                            summary=visual_result.feedback[:300],
                            score=visual_result.score,
                            decision_reason="visual_metrics_assessment",
                            input_signal=f"genre={genre_hint or 'n/a'}, html_size={len(final_html)}",
                            change_impact=("quality_below_threshold" if not visual_result.ok else "quality_pass"),
                            confidence=0.72,
                            before_score=before,
                            after_score=combined_score,
                            metadata={"issues": visual_result.issues[:8]},
                        )
                    )
                    if not visual_result.ok:
                        qa_feedback_parts.append(
                            f"Visual QA (score {visual_result.score}/100): {visual_result.feedback}"
                        )

                if self._playtester is not None:
                    before = combined_score
                    play_result = await self._playtester.test(html_content=final_html)
                    combined_score = play_result.score if combined_score == 0 else (combined_score + play_result.score) // 2
                    activities.append(
                        AgentActivity(
                            agent="playtester",
                            action="test",
                            summary=play_result.feedback[:300],
                            score=play_result.score,
                            decision_reason="runtime_boot_and_console_validation",
                            input_signal=f"html_size={len(final_html)}",
                            change_impact=("runtime_issue_detected" if (not play_result.boots_ok or play_result.has_errors) else "runtime_pass"),
                            confidence=0.76,
                            before_score=before,
                            after_score=combined_score,
                            error_code="runtime_boot_failed" if not play_result.boots_ok else None,
                            metadata={"console_errors": play_result.console_errors[:8]},
                        )
                    )
                    if not play_result.boots_ok or play_result.has_errors:
                        qa_feedback_parts.append(
                            f"Playtester (score {play_result.score}/100): {play_result.feedback}"
                        )

                if not qa_feedback_parts or round_idx >= _MAX_AUTO_REFINE_ROUNDS:
                    break

                if combined_score >= _AUTO_REFINE_SCORE_THRESHOLD:
                    break

                refinement_prompt = (
                    "The following quality issues were detected. "
                    "Please fix them while preserving all working features:\n\n"
                    + "\n\n".join(qa_feedback_parts)
                )
                refine_result = await self._codegen.generate(
                    user_prompt=refinement_prompt,
                    history=history,
                    current_html=final_html,
                    genre_hint=genre_hint,
                )

                if refine_result.error:
                    activities.append(
                        AgentActivity(
                            agent="codegen",
                            action="refine",
                            summary="Auto-refine failed",
                            score=combined_score,
                            decision_reason="qa_feedback_refinement",
                            input_signal=refinement_prompt[:500],
                            change_impact="no_change_due_to_error",
                            confidence=0.2,
                            error_code=refine_result.error,
                            metadata={"round": refinement_rounds + 1},
                        )
                    )
                    return AgentLoopResult(
                        html=final_html,
                        activities=activities,
                        final_score=combined_score,
                        generation_source=codegen_result.generation_source,
                        auto_refined=refinement_rounds > 0,
                        refinement_rounds=refinement_rounds,
                        error=refine_result.error,
                    )

                final_html = refine_result.html
                refinement_rounds += 1
                activities.append(
                    AgentActivity(
                        agent="codegen",
                        action="refine",
                        summary=f"Auto-refinement round {refinement_rounds}",
                        score=combined_score,
                        decision_reason="qa_feedback_refinement",
                        input_signal=refinement_prompt[:500],
                        change_impact="qa_issues_addressed",
                        confidence=0.64,
                        metadata={"round": refinement_rounds},
                    )
                )

        return AgentLoopResult(
            html=final_html,
            activities=activities,
            final_score=combined_score,
            generation_source=codegen_result.generation_source,
            auto_refined=refinement_rounds > 0,
            refinement_rounds=refinement_rounds,
        )
