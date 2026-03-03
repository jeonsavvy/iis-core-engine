from __future__ import annotations

from typing import Any


def _normalize_rows(value: object, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            rows.append(text)
        if len(rows) >= limit:
            break
    return rows


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

    mechanics = _normalize_rows(plan.get("core_mechanics"), limit=6)
    progression = _normalize_rows(plan.get("progression_plan"), limit=6)
    encounter = _normalize_rows(plan.get("encounter_plan"), limit=6)
    scene_layers = _normalize_rows(design.get("scene_layers"), limit=6)
    asset_blueprint = _normalize_rows(design.get("asset_blueprint_2d3d"), limit=8)
    hard_constraints = _normalize_rows(analyze.get("hard_constraints"), limit=10)
    forbidden_patterns = _normalize_rows(analyze.get("forbidden_patterns"), limit=12)

    summary_parts: list[str] = [
        f"요청:{keyword}",
        f"카메라:{capability_profile.get('camera_model', 'third_person')}",
        f"이동:{capability_profile.get('locomotion_model', 'on_foot')}",
        f"상호작용:{capability_profile.get('interaction_model', 'action')}",
        f"월드:{capability_profile.get('world_topology', 'arena')}",
    ]
    if mechanics:
        summary_parts.append(f"핵심루프:{', '.join(mechanics[:3])}")
    if scene_layers:
        summary_parts.append(f"레이어:{', '.join(scene_layers[:3])}")

    expanded_spec = {
        "intent": str(analyze.get("intent", "")).strip() or keyword,
        "must_have": mechanics[:4] + progression[:2],
        "encounter_contract": encounter[:4],
        "scene_contract": scene_layers[:4],
        "asset_contract": asset_blueprint[:6],
        "render_stack": "threejs_modular_runtime",
        "output_contract": "single_html_document",
        "hud_allowlist": ["score", "time", "hp", "objective"],
        "forbidden_hud_tokens": ["lv", "xp", "relic", "syn", "build", "wave"],
    }

    return {
        "contract_version": "builder-contract-v2",
        "title": title,
        "genre": genre,
        "summary": " | ".join(summary_parts),
        "hard_constraints": hard_constraints,
        "forbidden_patterns": forbidden_patterns,
        "deliverables": {
            "analyze": _normalize_rows(analyze.get("scope_in"), limit=8),
            "plan": mechanics,
            "plan_progression": progression,
            "plan_encounter": encounter,
            "design": asset_blueprint,
            "design_scene_layers": scene_layers,
        },
        "expanded_spec": expanded_spec,
    }
