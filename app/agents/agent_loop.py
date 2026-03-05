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
    result_summary: str = ""
    score: int = 0
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
    """Multi-agent loop orchestrator.

    Unlike the old 8-node serial pipeline, this loop:
    - Runs agents in a feedback loop (not linear)
    - Auto-refines based on QA feedback
    - Supports optional agent activation (skip QA for speed)
    - Returns structured activity log for UI display
    """

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
        """Execute the agent loop.

        Args:
            user_prompt: User's natural language request
            history: Conversation history for context
            current_html: Existing game HTML (empty for new games)
            genre_hint: Optional genre hint
            auto_qa: Whether to run Visual QA + Playtester automatically
        """
        activities: list[AgentActivity] = []

        # Step 1: Codegen Agent — generate/modify game code
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
                result_summary=(
                    f"Generated {len(codegen_result.html)} chars via {codegen_result.generation_source}"
                ),
                score=0,
                metadata={
                    "model": codegen_result.model_name,
                    "source": codegen_result.generation_source,
                },
            )
        )

        if codegen_result.error:
            return AgentLoopResult(
                html=codegen_result.html,
                activities=activities,
                generation_source=codegen_result.generation_source,
                error=codegen_result.error,
            )

        final_html = codegen_result.html
        combined_score = 0
        refinement_rounds = 0

        # Step 2: Optional QA loop
        if auto_qa and (self._visual_qa is not None or self._playtester is not None):
            for round_idx in range(_MAX_AUTO_REFINE_ROUNDS + 1):
                qa_feedback_parts: list[str] = []

                # Visual QA
                if self._visual_qa is not None:
                    visual_result = await self._visual_qa.evaluate(
                        html_content=final_html,
                        genre=genre_hint,
                    )
                    activities.append(
                        AgentActivity(
                            agent="visual_qa",
                            action="evaluate",
                            result_summary=visual_result.feedback[:200],
                            score=visual_result.score,
                        )
                    )
                    if not visual_result.ok:
                        qa_feedback_parts.append(
                            f"Visual QA (score {visual_result.score}/100): {visual_result.feedback}"
                        )
                    combined_score = max(combined_score, visual_result.score)

                # Playtester
                if self._playtester is not None:
                    play_result = await self._playtester.test(html_content=final_html)
                    activities.append(
                        AgentActivity(
                            agent="playtester",
                            action="test",
                            result_summary=play_result.feedback[:200],
                            score=play_result.score,
                        )
                    )
                    if not play_result.boots_ok or play_result.has_errors:
                        qa_feedback_parts.append(
                            f"Playtester (score {play_result.score}/100): {play_result.feedback}"
                        )
                    combined_score = (combined_score + play_result.score) // 2

                # Decide whether to auto-refine
                if not qa_feedback_parts or round_idx >= _MAX_AUTO_REFINE_ROUNDS:
                    break

                if combined_score >= _AUTO_REFINE_SCORE_THRESHOLD:
                    break

                # Auto-refine: send QA feedback back to Codegen
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
                final_html = refine_result.html
                refinement_rounds += 1

                activities.append(
                    AgentActivity(
                        agent="codegen",
                        action="refine",
                        result_summary=f"Auto-refinement round {refinement_rounds}",
                        score=0,
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
