from __future__ import annotations

import hashlib
import json
import re
from typing import Any

_TOKEN_PATTERN = re.compile(r"[a-z0-9가-힣]+", flags=re.IGNORECASE)
_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "game",
    "player",
    "loop",
    "mode",
    "요청",
    "게임",
    "플레이",
}


def _normalize_text(value: object, *, limit: int | None = None) -> str:
    text = re.sub(r"\s+", " ", str(value)).strip()
    if limit is None or len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    return f"{text[: limit - 1].rstrip()}…"


def _to_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for item in value:
        text = _normalize_text(item)
        if text:
            rows.append(text)
    return rows


def _merge_unique(*groups: list[str], limit: int, item_limit: int) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for row in group:
            text = _normalize_text(row, limit=item_limit)
            if not text or text in merged:
                continue
            merged.append(text)
            if len(merged) >= limit:
                return merged
    return merged


def _extract_tokens(value: str, *, limit: int = 6) -> list[str]:
    tokens: list[str] = []
    for raw in _TOKEN_PATTERN.findall(str(value).casefold()):
        token = raw.strip().casefold()
        if len(token) < 3 or token in _STOPWORDS:
            continue
        if token not in tokens:
            tokens.append(token)
        if len(tokens) >= limit:
            break
    return tokens


def _detect_runtime_engine(*, keyword: str, genre: str) -> str:
    combined = f"{keyword} {genre}".casefold()
    if any(token in combined for token in ("2d", "pixel", "도트", "탑다운", "카드", "보드")):
        return "2d_phaser"
    return "3d_three"


def build_synapse_contract(
    *,
    keyword: str,
    title: str,
    genre: str,
    objective: str,
    analyze_contract: dict[str, Any] | None = None,
    plan_contract: dict[str, Any] | None = None,
    design_contract: dict[str, Any] | None = None,
    design_spec: dict[str, Any] | None = None,
    base_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    analyze = analyze_contract or {}
    plan = plan_contract or {}
    design = design_contract or {}
    spec = design_spec or {}
    base = base_contract or {}

    keyword_tokens = _extract_tokens(keyword, limit=6)
    title_tokens = _extract_tokens(title, limit=4)
    mechanic_tokens = _merge_unique(
        _to_str_list(plan.get("core_mechanics")),
        keyword_tokens,
        title_tokens,
        limit=10,
        item_limit=64,
    )
    progression_tokens = _merge_unique(
        _to_str_list(plan.get("progression_plan")),
        _to_str_list(plan.get("encounter_plan")),
        [objective],
        limit=10,
        item_limit=96,
    )
    visual_tokens = _merge_unique(
        _to_str_list(design.get("camera_ui_contract")),
        _to_str_list(design.get("scene_layers")),
        _to_str_list(design.get("readability_contract")),
        limit=10,
        item_limit=96,
    )
    asset_tokens = _merge_unique(
        _to_str_list(design.get("asset_blueprint_2d3d")),
        limit=10,
        item_limit=80,
    )
    non_negotiables = _merge_unique(
        _to_str_list(analyze.get("hard_constraints")),
        ["preserve_requested_intent_without_generic_substitution", "single_artifact_html_output"],
        limit=10,
        item_limit=120,
    )

    quality_bar = {
        "quality_min": int(base.get("quality_bar", {}).get("quality_min", 50) if isinstance(base.get("quality_bar"), dict) else 50),
        "gameplay_min": int(base.get("quality_bar", {}).get("gameplay_min", 55) if isinstance(base.get("quality_bar"), dict) else 55),
        "visual_min": int(base.get("quality_bar", {}).get("visual_min", 45) if isinstance(base.get("quality_bar"), dict) else 45),
    }

    return {
        "schema_version": "synapse_v1",
        "runtime_contract": {
            "engine_mode": _detect_runtime_engine(keyword=keyword, genre=genre),
            "single_artifact_html": True,
            "preserve_boot_flags": True,
        },
        "quality_bar": quality_bar,
        "intent_anchor": {
            "keyword": _normalize_text(keyword, limit=180),
            "title": _normalize_text(title, limit=120),
            "objective": _normalize_text(objective, limit=240),
            "visual_style": _normalize_text(spec.get("visual_style", ""), limit=80),
        },
        "required_mechanics": mechanic_tokens,
        "required_progression": progression_tokens,
        "required_visual_signals": visual_tokens,
        "required_assets": asset_tokens,
        "non_negotiables": non_negotiables,
        "stage_alignment": {
            "analyze_contract_present": bool(analyze),
            "plan_contract_present": bool(plan),
            "design_contract_present": bool(design),
        },
    }


def validate_synapse_contract(contract: dict[str, Any] | None) -> list[str]:
    typed = contract if isinstance(contract, dict) else {}
    issues: list[str] = []
    if str(typed.get("schema_version", "")).strip() != "synapse_v1":
        issues.append("schema_version_invalid")
    required_mechanics = _to_str_list(typed.get("required_mechanics"))
    required_progression = _to_str_list(typed.get("required_progression"))
    required_visual_signals = _to_str_list(typed.get("required_visual_signals"))
    if len(required_mechanics) < 2:
        issues.append("required_mechanics_underfilled")
    if len(required_progression) < 2:
        issues.append("required_progression_underfilled")
    if len(required_visual_signals) < 1:
        issues.append("required_visual_signals_missing")
    runtime_contract = typed.get("runtime_contract")
    if not isinstance(runtime_contract, dict):
        issues.append("runtime_contract_missing")
    else:
        engine_mode = str(runtime_contract.get("engine_mode", "")).strip()
        if engine_mode not in {"2d_phaser", "3d_three"}:
            issues.append("runtime_engine_mode_invalid")
    quality_bar = typed.get("quality_bar")
    if not isinstance(quality_bar, dict):
        issues.append("quality_bar_missing")
    return issues


def compute_synapse_contract_hash(contract: dict[str, Any] | None) -> str:
    if not isinstance(contract, dict) or not contract:
        return "missing"
    normalized = json.dumps(contract, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

