from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

import pytest

from app.agents.agent_loop import AgentLoop
from app.agents.codegen_agent import CodegenResult
from app.agents.scaffolds import get_scaffold_seed
from app.agents.playtester_agent import PlaytestResult
from app.agents.visual_qa_agent import VisualQAResult


@dataclass
class StubCodegen:
    results: list[CodegenResult]
    prompts: list[str] = field(default_factory=list)

    async def generate(self, **kwargs: Any) -> CodegenResult:
        self.prompts.append(str(kwargs.get("user_prompt", "")))
        return self.results.pop(0)


@dataclass
class StubVisualQA:
    results: list[VisualQAResult]

    async def evaluate(self, **_: Any) -> VisualQAResult:
        return self.results.pop(0)


@dataclass
class StubPlaytester:
    results: list[PlaytestResult]

    async def test(self, **_: Any) -> PlaytestResult:
        return self.results.pop(0)


@pytest.mark.asyncio
async def test_agent_loop_auto_repairs_fatal_runtime_issue() -> None:
    codegen = StubCodegen(
        results=[
            CodegenResult(html="<html>draft</html>", generation_source="vertex", model_name="gemini"),
            CodegenResult(html="<html>patched</html>", generation_source="vertex", model_name="gemini"),
        ]
    )
    visual = StubVisualQA(
        results=[
            VisualQAResult(ok=True, score=0, feedback="visual fine", issues=[]),
            VisualQAResult(ok=True, score=0, feedback="visual fine", issues=[]),
        ]
    )
    playtester = StubPlaytester(
        results=[
            PlaytestResult(
                boots_ok=False,
                has_errors=True,
                issues=["Missing animation loop (requestAnimationFrame)"],
                fatal_issues=["Missing animation loop (requestAnimationFrame)"],
                feedback="- Missing animation loop (requestAnimationFrame)",
                score=0,
            ),
            PlaytestResult(
                boots_ok=True,
                has_errors=False,
                issues=[],
                fatal_issues=[],
                feedback="ok",
                score=0,
            ),
        ]
    )
    loop = AgentLoop(
        codegen=cast(Any, codegen),
        visual_qa=cast(Any, visual),
        playtester=cast(Any, playtester),
    )

    result = await loop.run(user_prompt="3D 레이싱 게임 만들어줘")

    assert result.error == ""
    assert result.auto_refined is True
    assert result.refinement_rounds == 1
    assert result.html == "<html>patched</html>"
    assert any(activity.action == "refine" for activity in result.activities)


@pytest.mark.asyncio
async def test_agent_loop_fails_when_fatal_runtime_remains() -> None:
    codegen = StubCodegen(
        results=[
            CodegenResult(html="<html>draft</html>", generation_source="vertex", model_name="gemini"),
            CodegenResult(html="<html>repair1</html>", generation_source="vertex", model_name="gemini"),
            CodegenResult(html="<html>repair2</html>", generation_source="vertex", model_name="gemini"),
        ]
    )
    visual = StubVisualQA(
        results=[
            VisualQAResult(ok=True, score=0, feedback="visual fine", issues=[]),
            VisualQAResult(ok=True, score=0, feedback="visual fine", issues=[]),
            VisualQAResult(ok=True, score=0, feedback="visual fine", issues=[]),
        ]
    )
    playtester = StubPlaytester(
        results=[
            PlaytestResult(
                boots_ok=False,
                has_errors=True,
                issues=["Missing animation loop (requestAnimationFrame)"],
                fatal_issues=["Missing animation loop (requestAnimationFrame)"],
                feedback="- Missing animation loop (requestAnimationFrame)",
                score=0,
            ),
            PlaytestResult(
                boots_ok=False,
                has_errors=True,
                issues=["Missing animation loop (requestAnimationFrame)"],
                fatal_issues=["Missing animation loop (requestAnimationFrame)"],
                feedback="- Missing animation loop (requestAnimationFrame)",
                score=0,
            ),
            PlaytestResult(
                boots_ok=False,
                has_errors=True,
                issues=["Missing animation loop (requestAnimationFrame)"],
                fatal_issues=["Missing animation loop (requestAnimationFrame)"],
                feedback="- Missing animation loop (requestAnimationFrame)",
                score=0,
            ),
        ]
    )
    loop = AgentLoop(
        codegen=cast(Any, codegen),
        visual_qa=cast(Any, visual),
        playtester=cast(Any, playtester),
    )

    result = await loop.run(user_prompt="3D 레이싱 게임 만들어줘")

    assert result.error.startswith("fatal_runtime_unresolved:")
    assert result.refinement_rounds == 2


@pytest.mark.asyncio
async def test_agent_loop_reverts_to_scaffold_when_specialization_breaks_genre() -> None:
    codegen = StubCodegen(
        results=[CodegenResult(html="<html><body>terrain demo only</body></html>", generation_source="vertex", model_name="gemini")]
    )
    visual = StubVisualQA(results=[VisualQAResult(ok=True, score=0, feedback="visual fine", issues=[])])
    playtester = StubPlaytester(results=[PlaytestResult(boots_ok=True, has_errors=False, issues=[], fatal_issues=[], feedback="ok", score=0)])
    loop = AgentLoop(
        codegen=cast(Any, codegen),
        visual_qa=cast(Any, visual),
        playtester=cast(Any, playtester),
    )

    result = await loop.run(
        user_prompt="오픈휠 레이스카로 서킷을 주행하며 랩타임을 기록하는 풀 3D 레이싱 게임 만들어줘"
    )

    seed = get_scaffold_seed("three_openwheel_circuit_seed")
    assert seed is not None
    assert result.html == seed.html
    assert any(activity.error_code == "scaffold_specialization_rejected" for activity in result.activities)


@pytest.mark.asyncio
async def test_agent_loop_reverts_flight_specialization_when_genre_breaks() -> None:
    codegen = StubCodegen(
        results=[CodegenResult(html="<html><body>autoscroll corridor shooter</body></html>", generation_source="vertex", model_name="gemini")]
    )
    visual = StubVisualQA(results=[VisualQAResult(ok=True, score=0, feedback="visual fine", issues=[])])
    playtester = StubPlaytester(results=[PlaytestResult(boots_ok=True, has_errors=False, issues=[], fatal_issues=[], feedback="ok", score=0)])
    loop = AgentLoop(codegen=cast(Any, codegen), visual_qa=cast(Any, visual), playtester=cast(Any, playtester))

    result = await loop.run(user_prompt="우주 도그파이트에 초점을 맞춘 풀 3D 플라이트 슈팅 게임 만들어줘")

    seed = get_scaffold_seed("three_space_dogfight_seed")
    assert seed is not None
    assert result.html == seed.html
    assert result.reverted_to_baseline is True


@pytest.mark.asyncio
async def test_agent_loop_reverts_topdown_specialization_when_genre_breaks() -> None:
    codegen = StubCodegen(
        results=[CodegenResult(html="<html><body>clicker 8-way shooter</body></html>", generation_source="vertex", model_name="gemini")]
    )
    visual = StubVisualQA(results=[VisualQAResult(ok=True, score=0, feedback="visual fine", issues=[])])
    playtester = StubPlaytester(results=[PlaytestResult(boots_ok=True, has_errors=False, issues=[], fatal_issues=[], feedback="ok", score=0)])
    loop = AgentLoop(codegen=cast(Any, codegen), visual_qa=cast(Any, visual), playtester=cast(Any, playtester))

    result = await loop.run(user_prompt="트윈스틱 이동과 에임, 대시, 웨이브 전투가 있는 탑뷰 슈팅 게임 만들어줘")

    seed = get_scaffold_seed("phaser_twinstick_arena_seed")
    assert seed is not None
    assert result.html == seed.html
    assert result.reverted_to_baseline is True
