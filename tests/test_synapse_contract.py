from __future__ import annotations

from app.orchestration.nodes.builder_parts.synapse_contract import (
    build_synapse_contract,
    compute_synapse_contract_hash,
    validate_synapse_contract,
)


def test_build_synapse_contract_produces_valid_payload() -> None:
    contract = build_synapse_contract(
        keyword="섬을 돌아다닐 수 있는 풀3D 비행기 조종 시뮬레이터",
        title="Island Pilot",
        genre="flight-sim",
        objective="이륙 후 체크포인트를 통과하고 착륙한다",
        analyze_contract={
            "hard_constraints": [
                "preserve_requested_intent_without_generic_substitution",
                "single html artifact export",
            ]
        },
        plan_contract={
            "core_mechanics": ["pitch", "roll", "yaw", "throttle", "checkpoint"],
            "progression_plan": ["takeoff", "checkpoint route", "landing"],
            "encounter_plan": ["crosswind", "storm pocket"],
        },
        design_contract={
            "camera_ui_contract": ["cockpit + chase camera"],
            "scene_layers": ["island terrain", "cloud layer", "ring gate"],
            "readability_contract": ["ring visibility"],
            "asset_blueprint_2d3d": ["aircraft", "island mesh", "ring checkpoint"],
        },
        design_spec={"visual_style": "aero-cinematic"},
        base_contract={"quality_bar": {"quality_min": 50, "gameplay_min": 55, "visual_min": 45}},
    )

    assert validate_synapse_contract(contract) == []
    assert contract["runtime_contract"]["engine_mode"] == "3d_three"
    assert compute_synapse_contract_hash(contract) != "missing"


def test_validate_synapse_contract_detects_required_fields() -> None:
    issues = validate_synapse_contract(
        {
            "schema_version": "synapse_v1",
            "runtime_contract": {"engine_mode": "3d_three"},
            "quality_bar": {"quality_min": 50, "gameplay_min": 55, "visual_min": 45},
            "required_mechanics": ["move"],
            "required_progression": [],
            "required_visual_signals": [],
        }
    )

    assert "required_mechanics_underfilled" in issues
    assert "required_progression_underfilled" in issues
    assert "required_visual_signals_missing" in issues
