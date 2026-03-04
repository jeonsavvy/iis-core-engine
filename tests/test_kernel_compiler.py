from __future__ import annotations

from app.orchestration.nodes.builder_parts.kernel_compiler import build_kernel_locked_html


def test_kernel_compiler_builds_runtime_contract_html() -> None:
    html = build_kernel_locked_html(
        keyword="서킷을 달리는 3d 오픈휠 레이싱 게임",
        title="Circuit Apex",
        genre="racing_3d",
        core_loop_type="f1_formula_circuit_3d",
        runtime_engine_mode="3d_three",
        objective="Finish laps and keep speed while avoiding hazards.",
        intent_contract={
            "fantasy": "도시 서킷에서 질주하는 오픈휠 레이싱",
            "player_verbs": ["steer", "throttle", "drift", "boost"],
            "progression_loop": ["0-45s onboarding", "45-90s pressure", "90-135s hazards"],
            "non_negotiables": ["single html output", "no generic fallback route"],
            "camera_interaction": "third person chase camera",
            "fail_restart_loop": "game over and restart loop required",
        },
        synapse_contract={
            "required_mechanics": ["checkpoint", "lap", "drift", "throttle", "overtake"],
            "required_progression": ["intro", "mid", "pressure", "peak"],
        },
    )
    lowered = html.casefold()
    assert "<canvas" in lowered
    assert "window.__iis_game_boot_ok" in lowered
    assert "window.iisleaderboard" in lowered
    assert "requestanimationframe" in lowered
    assert "config.mode === \"f1_formula_circuit_3d\"" in lowered
    assert "vertexshader fragmentshader gl_position gl_fragcolor" in lowered
    assert "overflow-guard" in lowered
    assert "safe-area" in lowered
    assert "checkpoint" in lowered
    assert "lap" in lowered
    assert "throttle" in lowered
    assert "drift" in lowered


def test_kernel_compiler_meets_quality_floor_shape() -> None:
    html = build_kernel_locked_html(
        keyword="비행",
        title="Aero Isle",
        genre="flight_sim_3d",
        core_loop_type="flight_sim_3d",
        runtime_engine_mode="3d_three",
        objective="Navigate and survive.",
        intent_contract=None,
        synapse_contract=None,
    )
    line_count = html.count("\n") + 1
    function_count = html.count("function ")
    lowered = html.casefold()
    shader_signal_count = sum(
        lowered.count(token)
        for token in ("fragmentshader", "vertexshader", "shadermaterial", "glsl", "gl_position", "gl_fragcolor")
    )
    assert line_count >= 360
    assert function_count >= 12
    assert shader_signal_count >= 1
