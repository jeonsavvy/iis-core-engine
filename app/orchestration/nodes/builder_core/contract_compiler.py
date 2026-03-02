from __future__ import annotations

from typing import Any


def compile_builder_contract(
    *,
    keyword: str,
    title: str,
    genre: str,
    capability_profile: dict[str, Any],
    analyze_contract: dict[str, Any] | None = None,
    plan_contract: dict[str, Any] | None = None,
    design_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    analyze = analyze_contract or {}
    plan = plan_contract or {}
    design = design_contract or {}
    mechanics = plan.get("core_mechanics", [])
    scene_layers = design.get("scene_layers", [])

    summary_parts: list[str] = [
        f"요청:{keyword}",
        f"카메라:{capability_profile.get('camera_model', 'third_person')}",
        f"상호작용:{capability_profile.get('interaction_model', 'action')}",
        f"월드:{capability_profile.get('world_topology', 'arena')}",
    ]
    if isinstance(mechanics, list) and mechanics:
        summary_parts.append(f"핵심루프:{', '.join(str(item) for item in mechanics[:3])}")
    if isinstance(scene_layers, list) and scene_layers:
        summary_parts.append(f"레이어:{', '.join(str(item) for item in scene_layers[:3])}")

    return {
        "contract_version": "builder-contract-v1",
        "title": title,
        "genre": genre,
        "summary": " | ".join(summary_parts),
        "hard_constraints": list(analyze.get("hard_constraints", []))[:10],
        "forbidden_patterns": list(analyze.get("forbidden_patterns", []))[:12],
        "deliverables": {
            "analyze": list(analyze.get("scope_in", []))[:8],
            "plan": list(plan.get("core_mechanics", []))[:10],
            "design": list(design.get("asset_blueprint_2d3d", []))[:12],
        },
    }
