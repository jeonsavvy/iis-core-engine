"""Agent Loop — multi-agent orchestrator for interactive game generation.

The loop coordinates three agents:
  1. Codegen Agent: generates/modifies game code
  2. Visual QA Agent: finds polish / readability issues
  3. Playtester Agent: finds runtime / gameplay blockers

Flow:
  User prompt → Codegen → Visual QA + Playtester
  → if fatal/runtime issues exist → Codegen auto-repair (max 2 rounds)
  → return draft or fail if fatal issues remain
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.agents.codegen_agent import CodegenAgent, ConversationMessage
from app.agents.genre_acceptance import validate_genre_acceptance
from app.agents.genre_briefs import build_genre_brief, scaffold_seed_for_brief
from app.agents.scaffolds import get_scaffold_seed
from app.agents.playtester_agent import PlaytesterAgent, PlaytestResult
from app.agents.visual_qa_agent import VisualQAAgent, VisualQAResult

logger = logging.getLogger(__name__)

_MAX_AUTO_REFINE_ROUNDS = 2
_AUTO_REPAIR_CATEGORIES = {"fatal_runtime", "runtime_bug", "gameplay_bug"}


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
    reverted_to_baseline: bool = False


@dataclass
class LoopIssue:
    category: str
    severity: str
    message: str
    source: str
    auto_repair: bool
    error_code: str | None = None


def _truncate_issue_lines(messages: list[str], *, limit: int = 4) -> str:
    return "; ".join(message.strip() for message in messages[:limit] if message.strip())


def _issue_messages(issues: list[LoopIssue], *, categories: set[str] | None = None) -> list[str]:
    return [
        issue.message
        for issue in issues
        if categories is None or issue.category in categories
    ]


def _has_category(issues: list[LoopIssue], category: str) -> bool:
    return any(issue.category == category for issue in issues)


def _categorize_visual_issue(issue: str) -> str:
    lowered = issue.casefold()
    if any(token in lowered for token in ("mostly_black", "no_edges", "blank", "empty")):
        return "runtime_bug"
    return "visual_polish"


def _collect_visual_issues(result: VisualQAResult) -> list[LoopIssue]:
    issues: list[LoopIssue] = []
    for raw_issue in result.issues:
        category = _categorize_visual_issue(raw_issue)
        issues.append(
            LoopIssue(
                category=category,
                severity="warn" if category == "visual_polish" else "error",
                message=raw_issue,
                source="visual_qa",
                auto_repair=category in _AUTO_REPAIR_CATEGORIES,
            )
        )
    return issues


def _collect_playtest_issues(result: PlaytestResult) -> list[LoopIssue]:
    issues: list[LoopIssue] = []

    for raw_issue in result.fatal_issues:
        issues.append(
            LoopIssue(
                category="fatal_runtime",
                severity="fatal",
                message=raw_issue,
                source="playtester",
                auto_repair=True,
                error_code="runtime_boot_failed",
            )
        )

    for raw_issue in result.issues:
        if raw_issue in result.fatal_issues:
            continue
        lowered = raw_issue.casefold()
        if "restart" in lowered or "game-over" in lowered or "gameover" in lowered:
            category = "gameplay_bug"
        elif "input" in lowered or "keyboard" in lowered:
            category = "gameplay_bug"
        else:
            category = "runtime_bug"
        issues.append(
            LoopIssue(
                category=category,
                severity="error",
                message=raw_issue,
                source="playtester",
                auto_repair=True,
                error_code="runtime_bug_detected",
            )
        )

    return issues


def _build_repair_prompt(
    *,
    issues: list[LoopIssue],
    user_prompt: str,
    genre_hint: str,
    round_number: int,
    genre_brief: dict[str, Any],
    scaffold_key: str | None,
    scaffold_version: str | None,
) -> str:
    fatal_or_runtime = _issue_messages(issues, categories=_AUTO_REPAIR_CATEGORIES)
    visual_polish = _issue_messages(issues, categories={"visual_polish"})
    lines = [
        "You are refining an existing browser game draft.",
        "Apply the SMALLEST viable change set that fixes the reported problems.",
        "Preserve all currently working mechanics, layout, and successful systems.",
        "Do not rewrite unrelated parts of the game.",
        "Return the COMPLETE HTML document only.",
        "",
        f"Original user request: {user_prompt}",
    ]
    if genre_hint.strip():
        lines.append(f"Genre hint: {genre_hint}")
    lines.append(f"Genre brief JSON: {genre_brief}")
    if scaffold_key:
        lines.append(f"Active scaffold: {scaffold_key}@{scaffold_version or 'unknown'}")
    lines.extend(
        [
            f"Repair round: {round_number}",
            "",
            "Must fix before this draft can be accepted:",
            *[f"- {message}" for message in fatal_or_runtime],
        ]
    )
    if visual_polish:
        lines.extend(
            [
                "",
                "Improve if the fix is local and low-risk:",
                *[f"- {message}" for message in visual_polish],
            ]
        )
    lines.extend(
        [
            "",
            "Rules:",
            "- Keep window.__iis_game_boot_ok = true when the game is actually ready.",
            "- Keep requestAnimationFrame-based animation/game loop intact.",
            "- Keep controls, restart flow, and scoreboard working unless fixing them is the goal.",
            "- Prefer surgical patches over wholesale rewrites.",
            "- Do not collapse the scaffold into a simpler genre or lower-fidelity template.",
        ]
    )
    return "\n".join(lines)


def _append_acceptance_reject_activity(
    *,
    activities: list[AgentActivity],
    user_prompt: str,
    genre_brief: dict[str, Any],
    scaffold_key: str | None,
    scaffold_version: str | None,
    acceptance_failures: list[str],
    generation_mode: str,
) -> None:
    activities.append(
        AgentActivity(
            agent="codegen",
            action="refine",
            summary=f"Rejected scaffold specialization: {', '.join(acceptance_failures[:4])}",
            decision_reason="scaffold_specialization_rejected",
            input_signal=user_prompt[:500],
            change_impact="reverted_to_scaffold_baseline",
            confidence=0.95,
            error_code="scaffold_specialization_rejected",
            metadata={
                "genre_brief": genre_brief,
                "scaffold_key": scaffold_key,
                "scaffold_version": scaffold_version,
                "generation_mode": generation_mode,
                "acceptance_report": {
                    "failures": acceptance_failures,
                },
            },
        )
    )


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

    async def _run_visual_qa(
        self,
        *,
        html: str,
        genre_hint: str,
        activities: list[AgentActivity],
    ) -> list[LoopIssue]:
        if self._visual_qa is None:
            return []

        visual_result = await self._visual_qa.evaluate(
            html_content=html,
            genre=genre_hint,
        )
        issues = _collect_visual_issues(visual_result)
        auto_repair = _issue_messages(issues, categories=_AUTO_REPAIR_CATEGORIES)
        activities.append(
            AgentActivity(
                agent="visual_qa",
                action="evaluate",
                summary=visual_result.feedback[:300],
                decision_reason="visual_polish_review",
                input_signal=f"genre={genre_hint or 'n/a'}, html_size={len(html)}",
                change_impact="auto_repair_requested" if auto_repair else ("polish_feedback_available" if issues else "visual_pass"),
                confidence=0.72,
                metadata={
                    "issues": visual_result.issues[:8],
                    "issue_categories": sorted({issue.category for issue in issues}),
                    "auto_repair": bool(auto_repair),
                },
            )
        )
        return issues

    async def _run_playtester(
        self,
        *,
        html: str,
        activities: list[AgentActivity],
    ) -> list[LoopIssue]:
        if self._playtester is None:
            return []

        play_result = await self._playtester.test(html_content=html)
        issues = _collect_playtest_issues(play_result)
        fatal_messages = _issue_messages(issues, categories={"fatal_runtime"})
        runtime_messages = _issue_messages(issues, categories={"runtime_bug", "gameplay_bug"})
        activities.append(
            AgentActivity(
                agent="playtester",
                action="test",
                summary=play_result.feedback[:300],
                decision_reason="runtime_boot_and_interaction_validation",
                input_signal=f"html_size={len(html)}",
                change_impact=(
                    "fatal_runtime_detected"
                    if fatal_messages
                    else ("runtime_followup_needed" if runtime_messages else "runtime_pass")
                ),
                confidence=0.76,
                error_code="runtime_boot_failed" if fatal_messages else None,
                metadata={
                    "issues": play_result.issues[:8],
                    "fatal_issues": play_result.fatal_issues[:8],
                    "issue_categories": sorted({issue.category for issue in issues}),
                },
            )
        )
        return issues

    async def run(
        self,
        *,
        user_prompt: str,
        history: list[ConversationMessage] | None = None,
        current_html: str = "",
        genre_hint: str = "",
        auto_qa: bool = True,
        image_attachment: dict[str, str] | None = None,
    ) -> AgentLoopResult:
        activities: list[AgentActivity] = []

        is_modification = bool(current_html.strip())
        action = "modify" if is_modification else "generate"
        genre_brief = build_genre_brief(user_prompt=user_prompt, genre_hint=genre_hint)
        scaffold_seed = scaffold_seed_for_brief(genre_brief)
        scaffold = get_scaffold_seed(str(genre_brief.get("scaffold_key", "")).strip()) if scaffold_seed else None
        scaffold_key = scaffold.key if scaffold else None
        scaffold_version = scaffold.version if scaffold else None
        generation_mode = "repair_from_scaffold" if is_modification and scaffold else ("scaffold_seeded" if scaffold else "blank")
        baseline_html = scaffold.html if scaffold is not None and not is_modification else current_html

        if scaffold is not None and not is_modification:
            activities.append(
                AgentActivity(
                    agent="codegen",
                    action="generate",
                    summary=f"Materialized scaffold baseline {scaffold.key}",
                    decision_reason="deterministic_scaffold_baseline",
                    input_signal=user_prompt[:500],
                    change_impact="baseline_draft_created",
                    confidence=1.0,
                    metadata={
                        "genre_brief": genre_brief,
                        "scaffold_key": scaffold_key,
                        "scaffold_version": scaffold_version,
                        "generation_mode": "deterministic_scaffold",
                    },
                )
            )

        codegen_result = await self._codegen.generate(
            user_prompt=user_prompt,
            history=history,
            current_html=baseline_html,
            genre_hint=genre_hint,
            image_attachment=image_attachment,
        )

        activities.append(
            AgentActivity(
                agent="codegen",
                action=action,
                summary=f"Generated {len(codegen_result.html)} chars via {codegen_result.generation_source}",
                decision_reason="initial_user_prompt" if not is_modification else "user_requested_modification",
                input_signal=user_prompt[:500],
                change_impact="initial_generation" if not is_modification else "targeted_revision_requested",
                confidence=0.9 if codegen_result.generation_source == "vertex" else 0.25,
                error_code=codegen_result.error or None,
                metadata={
                    "model": codegen_result.model_name,
                    "source": codegen_result.generation_source,
                    "edit_mode": "surgical" if is_modification else "blank_slate",
                    "genre_brief": genre_brief,
                    "scaffold_key": scaffold_key,
                    "scaffold_version": scaffold_version,
                    "generation_mode": generation_mode,
                },
            )
        )

        if codegen_result.error:
            return AgentLoopResult(
                html=baseline_html,
                activities=activities,
                final_score=0,
                generation_source=codegen_result.generation_source,
                auto_refined=False,
                refinement_rounds=0,
                error=codegen_result.error,
                reverted_to_baseline=False,
            )

        final_html = codegen_result.html
        reverted_to_baseline = False
        if scaffold is not None and not is_modification:
            acceptance = validate_genre_acceptance(
                archetype=str(genre_brief.get("archetype", "")),
                html=final_html,
            )
            if not acceptance.ok:
                _append_acceptance_reject_activity(
                    activities=activities,
                    user_prompt=user_prompt,
                    genre_brief=genre_brief,
                    scaffold_key=scaffold_key,
                    scaffold_version=scaffold_version,
                    acceptance_failures=acceptance.failures,
                    generation_mode="scaffold_reverted_to_baseline",
                )
                final_html = baseline_html
                reverted_to_baseline = True
        refinement_rounds = 0
        latest_issues: list[LoopIssue] = []

        if auto_qa and (self._visual_qa is not None or self._playtester is not None):
            for round_idx in range(_MAX_AUTO_REFINE_ROUNDS + 1):
                latest_issues = []
                latest_issues.extend(
                    await self._run_visual_qa(
                        html=final_html,
                        genre_hint=genre_hint,
                        activities=activities,
                    )
                )
                latest_issues.extend(
                    await self._run_playtester(
                        html=final_html,
                        activities=activities,
                    )
                )

                auto_repair_issues = [issue for issue in latest_issues if issue.auto_repair]
                if not auto_repair_issues:
                    break

                if round_idx >= _MAX_AUTO_REFINE_ROUNDS:
                    break

                repair_prompt = _build_repair_prompt(
                    issues=auto_repair_issues,
                    user_prompt=user_prompt,
                    genre_hint=genre_hint,
                    round_number=refinement_rounds + 1,
                    genre_brief=genre_brief,
                    scaffold_key=scaffold_key,
                    scaffold_version=scaffold_version,
                )
                refine_result = await self._codegen.generate(
                    user_prompt=repair_prompt,
                    history=history,
                    current_html=final_html,
                    genre_hint=genre_hint,
                    image_attachment=image_attachment,
                )

                if refine_result.error:
                    activities.append(
                        AgentActivity(
                            agent="codegen",
                            action="refine",
                            summary="Auto-repair failed",
                            decision_reason="qa_generated_repair_brief",
                            input_signal=repair_prompt[:500],
                            change_impact="repair_attempt_failed",
                            confidence=0.2,
                            error_code=refine_result.error,
                            metadata={
                                "round": refinement_rounds + 1,
                                "issue_categories": sorted({issue.category for issue in auto_repair_issues}),
                                "genre_brief": genre_brief,
                                "scaffold_key": scaffold_key,
                                "scaffold_version": scaffold_version,
                                "generation_mode": "repair_from_scaffold" if scaffold else "repair_generic",
                            },
                        )
                    )
                    return AgentLoopResult(
                        html=final_html,
                        activities=activities,
                        final_score=0,
                        generation_source=codegen_result.generation_source,
                        auto_refined=refinement_rounds > 0,
                        refinement_rounds=refinement_rounds,
                        error=refine_result.error,
                        reverted_to_baseline=reverted_to_baseline,
                )

                final_html = refine_result.html
                if scaffold is not None:
                    refined_acceptance = validate_genre_acceptance(
                        archetype=str(genre_brief.get("archetype", "")),
                        html=final_html,
                    )
                    if not refined_acceptance.ok:
                        _append_acceptance_reject_activity(
                            activities=activities,
                            user_prompt=user_prompt,
                            genre_brief=genre_brief,
                            scaffold_key=scaffold_key,
                            scaffold_version=scaffold_version,
                            acceptance_failures=refined_acceptance.failures,
                            generation_mode="repair_from_scaffold",
                        )
                        final_html = baseline_html
                        reverted_to_baseline = True
                        latest_issues = []
                        break
                refinement_rounds += 1
                activities.append(
                    AgentActivity(
                        agent="codegen",
                        action="refine",
                        summary=f"Auto-repair round {refinement_rounds}",
                        decision_reason="qa_generated_repair_brief",
                        input_signal=_truncate_issue_lines(_issue_messages(auto_repair_issues), limit=4)[:500],
                        change_impact="targeted_repair_applied",
                        confidence=0.64,
                        metadata={
                            "round": refinement_rounds,
                            "issue_categories": sorted({issue.category for issue in auto_repair_issues}),
                            "genre_brief": genre_brief,
                            "scaffold_key": scaffold_key,
                            "scaffold_version": scaffold_version,
                            "generation_mode": "repair_from_scaffold" if scaffold else "repair_generic",
                        },
                    )
                )

        fatal_messages = _issue_messages(latest_issues, categories={"fatal_runtime"})
        if fatal_messages:
            return AgentLoopResult(
                html=final_html,
                activities=activities,
                final_score=0,
                generation_source=codegen_result.generation_source,
                auto_refined=refinement_rounds > 0,
                refinement_rounds=refinement_rounds,
                error=f"fatal_runtime_unresolved: {_truncate_issue_lines(fatal_messages)}",
                reverted_to_baseline=reverted_to_baseline,
            )

        return AgentLoopResult(
            html=final_html,
            activities=activities,
            final_score=0,
            generation_source=codegen_result.generation_source,
            auto_refined=refinement_rounds > 0,
            refinement_rounds=refinement_rounds,
            reverted_to_baseline=reverted_to_baseline,
        )
