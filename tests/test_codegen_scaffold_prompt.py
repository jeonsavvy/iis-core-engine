from __future__ import annotations

from app.agents.codegen_agent import CodegenAgent


class DummyVertex:
    class settings:
        builder_codegen_max_output_tokens = 48000

    def _is_enabled(self) -> bool:
        return False


def test_initial_racing_prompt_uses_hard_scaffold_html() -> None:
    agent = CodegenAgent(vertex_service=DummyVertex())
    prompt = agent._build_prompt(  # noqa: SLF001 - intentional white-box contract test
        user_prompt="오픈휠 레이스카로 서킷을 주행하며 랩타임을 기록하는 풀 3D 레이싱 게임 만들어줘",
        history=[],
        current_html="",
        genre_hint="racing",
    )

    assert "Generation mode: initial_from_scaffold" in prompt
    assert "three_openwheel_circuit_seed" in prompt
    assert "Base scaffold HTML:" in prompt
    assert "lap timer" in prompt.lower() or "lap-timer" in prompt.lower()
    assert "endless obstacle runner" in prompt.lower()
    assert "First frame requirement" in prompt
    assert "extending a production baseline" in prompt.lower()
    assert "Preserve system" in prompt
    assert "Structural contract" in prompt


def test_initial_flight_prompt_uses_hard_scaffold_html() -> None:
    agent = CodegenAgent(vertex_service=DummyVertex())
    prompt = agent._build_prompt(  # noqa: SLF001
        user_prompt="우주 도그파이트에 초점을 맞춘 풀 3D 플라이트 슈팅 게임 만들어줘",
        history=[],
        current_html="",
        genre_hint="flight",
    )

    assert "three_space_dogfight_seed" in prompt
    assert "Base scaffold HTML:" in prompt
    assert "forward auto-scroll shooter" in prompt.lower()
    assert "extending a production baseline" in prompt.lower()


def test_initial_topdown_prompt_uses_hard_scaffold_html() -> None:
    agent = CodegenAgent(vertex_service=DummyVertex())
    prompt = agent._build_prompt(  # noqa: SLF001
        user_prompt="트윈스틱 이동과 에임, 대시, 웨이브 전투가 있는 탑뷰 슈팅 게임 만들어줘",
        history=[],
        current_html="",
        genre_hint="topdown shooter",
    )

    assert "phaser_twinstick_arena_seed" in prompt
    assert "Base scaffold HTML:" in prompt
    assert "single-button clicker" in prompt.lower()
    assert "extending a production baseline" in prompt.lower()
