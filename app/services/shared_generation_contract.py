from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.visual_contract import resolve_visual_contract_profile


def infer_runtime_engine_mode(*, keyword: str, genre: str | None = None) -> str:
    combined = f"{keyword} {genre or ''}".casefold()
    if any(token in combined for token in ("2d", "pixel", "도트", "탑다운", "카드", "보드", "플랫")):
        return "2d_phaser"
    return "3d_three"


def _dedupe(rows: list[str], *, limit: int) -> list[str]:
    merged: list[str] = []
    for row in rows:
        text = str(row).strip()
        if text and text not in merged:
            merged.append(text)
        if len(merged) >= limit:
            break
    return merged


def build_shared_generation_contract(
    *,
    keyword: str,
    genre: str | None = None,
    runtime_engine_mode: str | None = None,
    quality_bar: dict[str, int] | None = None,
) -> dict[str, Any]:
    resolved_mode = str(runtime_engine_mode or "").strip().casefold() or infer_runtime_engine_mode(
        keyword=keyword,
        genre=genre,
    )
    if resolved_mode not in {"2d_phaser", "3d_three"}:
        resolved_mode = "3d_three"
    visual = resolve_visual_contract_profile(
        core_loop_type=genre or "",
        runtime_engine_mode=resolved_mode,
        keyword=keyword,
    )
    required_visual_signals = ["contrast", "diversity", "edge", "motion"]
    required_asset_usage = ["player", "enemy", "boost", "hud_frame", "track_grid"]
    visual_payload = visual.as_dict()
    visual_payload["required_visual_signals"] = required_visual_signals
    visual_payload["required_asset_usage"] = required_asset_usage
    quality = quality_bar or {}
    return {
        "schema_version": "shared_generation_contract_v1",
        "intent": {
            "keyword_anchor": keyword,
            "title_anchor": "",
            "objective_anchor": "",
            "player_verbs": [],
            "non_negotiables": [],
        },
        "runtime": {
            "engine_mode": resolved_mode,
            "runtime_stack": "phaser.js" if resolved_mode == "2d_phaser" else "three.js",
            "single_artifact_html": True,
        },
        "visual": visual_payload,
        "quality_bar": {
            "quality_min": int(quality.get("quality_min", 50) or 50),
            "gameplay_min": int(quality.get("gameplay_min", 55) or 55),
            "visual_min": int(quality.get("visual_min", 45) or 45),
        },
        "required_visual_signals": required_visual_signals,
        "required_asset_usage": required_asset_usage,
        "checklist": {
            "boot_flag": True,
            "leaderboard_contract": True,
            "realtime_loop": True,
            "input_reaction": True,
            "state_transition": True,
            "restart_loop": True,
            "visual_contrast": True,
            "visual_diversity": True,
            "visual_edge": True,
            "visual_motion": True,
        },
    }


def validate_shared_generation_contract(contract: dict[str, Any] | None) -> list[str]:
    typed = contract if isinstance(contract, dict) else {}
    issues: list[str] = []
    if str(typed.get("schema_version", "")).strip() != "shared_generation_contract_v1":
        issues.append("schema_version_invalid")
    runtime = typed.get("runtime")
    if not isinstance(runtime, dict):
        issues.append("runtime_missing")
    else:
        engine_mode = str(runtime.get("engine_mode", "")).strip().casefold()
        if engine_mode not in {"2d_phaser", "3d_three"}:
            issues.append("runtime_engine_mode_invalid")
    visual = typed.get("visual")
    if not isinstance(visual, dict):
        issues.append("visual_contract_missing")
    else:
        for key in ("contrast_min", "color_diversity_min", "edge_energy_min", "motion_delta_min"):
            value = visual.get(key)
            if not isinstance(value, (int, float)):
                issues.append(f"visual_{key}_invalid")
        signal_rows = visual.get("required_visual_signals")
        if signal_rows is not None and (
            not isinstance(signal_rows, list) or len([item for item in signal_rows if str(item).strip()]) < 3
        ):
            issues.append("visual_required_signals_invalid")
        asset_rows = visual.get("required_asset_usage")
        if asset_rows is not None and (
            not isinstance(asset_rows, list) or len([item for item in asset_rows if str(item).strip()]) < 3
        ):
            issues.append("visual_required_asset_usage_invalid")
    quality_bar = typed.get("quality_bar")
    if not isinstance(quality_bar, dict):
        issues.append("quality_bar_missing")
    checklist = typed.get("checklist")
    if not isinstance(checklist, dict):
        issues.append("checklist_missing")
    return issues


def merge_shared_generation_contract(
    *,
    contract: dict[str, Any] | None,
    keyword: str,
    title: str | None = None,
    objective: str | None = None,
    player_verbs: list[str] | None = None,
    non_negotiables: list[str] | None = None,
    runtime_engine_mode: str | None = None,
    visual_profile_hint: str | None = None,
    required_visual_signals: list[str] | None = None,
    required_asset_usage: list[str] | None = None,
) -> dict[str, Any]:
    merged = build_shared_generation_contract(keyword=keyword)
    if isinstance(contract, dict):
        merged.update(contract)

    intent = merged.get("intent")
    if not isinstance(intent, dict):
        intent = {}
        merged["intent"] = intent
    intent["keyword_anchor"] = keyword
    if isinstance(title, str):
        intent["title_anchor"] = title.strip()
    if isinstance(objective, str):
        intent["objective_anchor"] = objective.strip()
    if isinstance(player_verbs, list):
        intent["player_verbs"] = _dedupe([str(item) for item in player_verbs], limit=10)
    if isinstance(non_negotiables, list):
        intent["non_negotiables"] = _dedupe([str(item) for item in non_negotiables], limit=12)

    runtime = merged.get("runtime")
    if not isinstance(runtime, dict):
        runtime = {}
        merged["runtime"] = runtime
    normalized_mode = str(runtime_engine_mode or runtime.get("engine_mode", "")).strip().casefold()
    if normalized_mode not in {"2d_phaser", "3d_three"}:
        normalized_mode = infer_runtime_engine_mode(keyword=keyword)
    runtime["engine_mode"] = normalized_mode
    runtime["runtime_stack"] = "phaser.js" if normalized_mode == "2d_phaser" else "three.js"
    runtime["single_artifact_html"] = True

    visual = resolve_visual_contract_profile(
        core_loop_type=visual_profile_hint or "",
        runtime_engine_mode=normalized_mode,
        keyword=keyword,
    ).as_dict()
    if isinstance(required_visual_signals, list):
        visual["required_visual_signals"] = _dedupe([str(item) for item in required_visual_signals], limit=10)
    elif not isinstance(visual.get("required_visual_signals"), list):
        visual["required_visual_signals"] = ["contrast", "diversity", "edge", "motion"]
    if isinstance(required_asset_usage, list):
        visual["required_asset_usage"] = _dedupe([str(item) for item in required_asset_usage], limit=10)
    elif not isinstance(visual.get("required_asset_usage"), list):
        visual["required_asset_usage"] = ["player", "enemy", "boost", "hud_frame", "track_grid"]
    merged["visual"] = visual
    merged["required_visual_signals"] = visual.get("required_visual_signals", [])
    merged["required_asset_usage"] = visual.get("required_asset_usage", [])
    return merged


def compute_shared_generation_contract_hash(contract: dict[str, Any] | None) -> str:
    if not isinstance(contract, dict) or not contract:
        return "missing"
    normalized = json.dumps(contract, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
