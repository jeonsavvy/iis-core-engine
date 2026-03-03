from __future__ import annotations

from app.orchestration.nodes.builder_parts.intent_contract import build_intent_contract
from app.schemas.payloads import (
    AnalyzeContractPayload,
    DesignContractPayload,
    GDDPayload,
    PlanContractPayload,
)


def test_build_intent_contract_clips_overlong_text_fields() -> None:
    keyword = "섬을 자유롭게 돌아다닐 수 있는 풀3D 비행기 조종 시뮬레이터 " * 6
    gdd = GDDPayload(
        title="Island Pilot",
        genre="simulation",
        objective="활주로 이륙, 저고도 항법, 링 통과, 섬 주변 정찰, 연료 관리, 난기류 회복, 착륙까지 이어지는 장기 루프",
    )
    analyze_contract = AnalyzeContractPayload(
        intent="request faithful simulation build",
        scope_in=["runtime", "artifact", "controls"],
        scope_out=["multiplayer"],
        hard_constraints=[
            "preserve flight fantasy without genre substitution",
            "keep restart latency under two seconds",
        ],
        forbidden_patterns=[
            "generic arcade replacement",
            "autoplay without input",
        ],
        success_outcome="player can control aircraft and complete island route",
    )
    plan_contract = PlanContractPayload(
        core_mechanics=["throttle", "pitch", "roll", "yaw"],
        progression_plan=["training takeoff", "island orbit", "precision landing"],
        encounter_plan=["crosswind corridor", "ring challenge", "storm pocket"],
        risk_reward_plan=["safe route", "high-speed shortcut", "fuel risk route"],
        control_model="keyboard and mouse hybrid cockpit controls with analog-like sensitivity and deterministic response",
        balance_baseline={"hp": 1.0, "fuel": 100.0},
    )
    design_contract = DesignContractPayload(
        camera_ui_contract=[
            "third-person chase camera that preserves horizon and runway cues even during aggressive banking maneuvers",
            "cockpit overlay with altitude, speed, heading, throttle, fuel, waypoint distance, and warning annunciators",
        ],
        asset_blueprint_2d3d=["player aircraft", "island terrain", "checkpoint rings"],
        scene_layers=["terrain", "sky", "clouds"],
        feedback_fx_contract=["stall warning", "engine overload"],
        readability_contract=["high contrast HUD"],
    )

    contract = build_intent_contract(
        keyword=keyword,
        title="Island Pilot",
        gdd=gdd,
        analyze_contract=analyze_contract,
        plan_contract=plan_contract,
        design_contract=design_contract,
    )

    assert len(contract.fantasy) <= 260
    assert len(contract.camera_interaction) <= 200
    assert len(contract.fail_restart_loop) <= 240
    assert len(contract.player_verbs) >= 1
    assert all(len(item) <= 120 for item in contract.progression_loop)
    assert all(len(item) <= 120 for item in contract.non_negotiables)
