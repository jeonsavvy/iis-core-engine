from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import mean

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.pipeline import PipelineLogRecord, PipelineStage, PipelineStatus


@dataclass(frozen=True)
class AssetMemoryContext:
    hint: str
    recurring_failures: list[str]
    retrieval_profile: dict[str, object]
    registry_snapshot: dict[str, object]


def _to_float(value: object, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _to_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    values: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            values.append(text)
    return values


def _resolve_pipeline_engine(logs: list[PipelineLogRecord]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for log in logs:
        if log.stage != PipelineStage.BUILD:
            continue
        metadata = log.metadata if isinstance(log.metadata, dict) else {}
        engine = metadata.get("core_loop_type")
        if not isinstance(engine, str) or not engine.strip():
            engine = metadata.get("genre_engine_selected")
        if isinstance(engine, str) and engine.strip():
            mapping[str(log.pipeline_id)] = engine.strip()
    return mapping


def collect_asset_memory_context(
    *,
    state: PipelineState,
    deps: NodeDependencies,
    core_loop_type: str,
    limit: int = 240,
) -> AssetMemoryContext:
    logs = deps.repository.list_recent_logs(limit=limit)
    if not logs:
        empty_profile = {
            "source": "pipeline_logs_v1",
            "preferred_asset_pack": None,
            "preferred_variant_id": None,
            "preferred_variant_theme": None,
            "failure_reasons": [],
            "failure_tokens": [],
            "sample_size": 0,
        }
        return AssetMemoryContext(
            hint="",
            recurring_failures=[],
            retrieval_profile=empty_profile,
            registry_snapshot={"build_success_samples": 0, "qa_failure_samples": 0},
        )

    pipeline_engine = _resolve_pipeline_engine(logs)
    current_pipeline_id = str(state["pipeline_id"])

    pack_scores: dict[str, list[float]] = defaultdict(list)
    variant_scores: dict[str, list[float]] = defaultdict(list)
    theme_scores: dict[str, list[float]] = defaultdict(list)
    failure_reason_counter: Counter[str] = Counter()
    failure_token_counter: Counter[str] = Counter()
    related_pipeline_ids: set[str] = set()
    build_success_samples = 0
    qa_failure_samples = 0

    for log in logs:
        pipeline_id = str(log.pipeline_id)
        if pipeline_id == current_pipeline_id:
            continue
        if pipeline_engine.get(pipeline_id) != core_loop_type:
            continue
        related_pipeline_ids.add(pipeline_id)

        metadata = log.metadata if isinstance(log.metadata, dict) else {}
        if log.stage == PipelineStage.BUILD and log.status == PipelineStatus.SUCCESS:
            build_success_samples += 1
            asset_pack = str(metadata.get("asset_pack", "")).strip()
            if asset_pack:
                pack_scores[asset_pack].append(_to_float(metadata.get("final_composite_score"), 0.0))

            variant_id = str(metadata.get("asset_pipeline_selected_variant", "")).strip()
            if variant_id:
                variant_scores[variant_id].append(_to_float(metadata.get("final_composite_score"), 0.0))

            variant_theme = str(metadata.get("asset_pipeline_selected_theme", "")).strip()
            if variant_theme:
                theme_scores[variant_theme].append(_to_float(metadata.get("final_composite_score"), 0.0))

        if log.stage == PipelineStage.QA and log.status in {PipelineStatus.RETRY, PipelineStatus.ERROR}:
            qa_failure_samples += 1
            reason = str(log.reason or metadata.get("reason") or "").strip()
            if reason:
                failure_reason_counter[reason] += 1

            for key in ("failed_checks", "fatal_errors"):
                for token in _to_str_list(metadata.get(key)):
                    failure_token_counter[token] += 1

    preferred_asset_pack = max(pack_scores.items(), key=lambda row: mean(row[1]))[0] if pack_scores else None
    preferred_variant_id = max(variant_scores.items(), key=lambda row: mean(row[1]))[0] if variant_scores else None
    preferred_variant_theme = max(theme_scores.items(), key=lambda row: mean(row[1]))[0] if theme_scores else None
    top_reasons = [key for key, _ in failure_reason_counter.most_common(4)]
    top_tokens = [key for key, _ in failure_token_counter.most_common(8)]

    hint_parts: list[str] = []
    if preferred_asset_pack:
        hint_parts.append(f"Reuse proven asset pack {preferred_asset_pack}.")
    if preferred_variant_theme:
        hint_parts.append(f"Prefer visual theme {preferred_variant_theme} for continuity.")
    if preferred_variant_id:
        hint_parts.append(f"Start from variant profile {preferred_variant_id}.")
    if top_reasons:
        hint_parts.append(f"Avoid recurrent QA failures: {', '.join(top_reasons)}.")
    if top_tokens:
        hint_parts.append(f"Prioritize fixes for: {', '.join(top_tokens)}.")
    hint = " ".join(hint_parts).strip()

    retrieval_profile: dict[str, object] = {
        "source": "pipeline_logs_v1",
        "preferred_asset_pack": preferred_asset_pack,
        "preferred_variant_id": preferred_variant_id,
        "preferred_variant_theme": preferred_variant_theme,
        "failure_reasons": top_reasons,
        "failure_tokens": top_tokens,
        "sample_size": len(related_pipeline_ids),
    }
    registry_snapshot: dict[str, object] = {
        "core_loop_type": core_loop_type,
        "build_success_samples": build_success_samples,
        "qa_failure_samples": qa_failure_samples,
        "related_pipeline_count": len(related_pipeline_ids),
        "asset_pack_candidates": [
            {"asset_pack": key, "avg_composite_score": round(mean(values), 3), "sample_count": len(values)}
            for key, values in pack_scores.items()
        ],
        "variant_candidates": [
            {"variant_id": key, "avg_composite_score": round(mean(values), 3), "sample_count": len(values)}
            for key, values in variant_scores.items()
        ],
        "theme_candidates": [
            {"theme": key, "avg_composite_score": round(mean(values), 3), "sample_count": len(values)}
            for key, values in theme_scores.items()
        ],
        "failure_reasons": [{"reason": key, "count": count} for key, count in failure_reason_counter.items()],
        "failure_tokens": [{"token": key, "count": count} for key, count in failure_token_counter.items()],
    }

    return AssetMemoryContext(
        hint=hint,
        recurring_failures=[*top_reasons, *top_tokens],
        retrieval_profile=retrieval_profile,
        registry_snapshot=registry_snapshot,
    )
