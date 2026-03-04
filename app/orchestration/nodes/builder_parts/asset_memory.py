from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import re
from statistics import mean

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.dependencies import NodeDependencies
from app.orchestration.nodes.builder_parts.substrates import resolve_substrate_profile
from app.schemas.pipeline import PipelineLogRecord, PipelineStage, PipelineStatus
from app.services.visual_contract import canonicalize_visual_token


@dataclass(frozen=True)
class AssetMemoryContext:
    hint: str
    recurring_failures: list[str]
    retrieval_profile: dict[str, object]
    registry_snapshot: dict[str, object]


def _to_float(value: object, fallback: float = 0.0) -> float:
    if isinstance(value, bool):
        return fallback
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return fallback
        try:
            return float(text)
        except ValueError:
            return fallback
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


def _tokenize_keyword(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", value.lower()) if len(token) >= 2}


def _row_effective_quality(row: dict[str, object]) -> float:
    metadata = row.get("metadata")
    typed_metadata = metadata if isinstance(metadata, dict) else {}
    for key in (
        "final_composite_score",
        "final_quality_score",
        "final_gameplay_score",
        "playability_score",
        "asset_complexity_score",
    ):
        score = _to_float(row.get(key), -1.0)
        if score < 0:
            score = _to_float(typed_metadata.get(key), -1.0)
        if score >= 0:
            return score
    return 0.0


def _registry_row_score(
    *,
    row: dict[str, object],
    current_keyword_tokens: set[str],
    current_substrate_id: str,
    rank: int,
) -> tuple[float, float]:
    row_keyword_tokens = _tokenize_keyword(str(row.get("keyword", "")).strip())
    shared_tokens = len(current_keyword_tokens & row_keyword_tokens)
    keyword_overlap = (
        shared_tokens / max(len(current_keyword_tokens), 1)
        if current_keyword_tokens
        else 0.0
    )

    qa_status = str(row.get("qa_status", "")).strip().lower()
    qa_bonus = 0.0
    if qa_status == "success":
        qa_bonus = 8.0
    elif qa_status in {"retry", "error"}:
        qa_bonus = -14.0

    failure_penalty = min(len(_to_str_list(row.get("failure_reasons"))) * 2.5, 12.0)
    recency_bonus = max(6.0 - (rank * 0.12), 0.0)
    overlap_bonus = keyword_overlap * 16.0
    metadata = row.get("metadata")
    typed_metadata = metadata if isinstance(metadata, dict) else {}
    row_substrate_id = str(row.get("substrate_id", "")).strip() or str(typed_metadata.get("substrate_id", "")).strip()
    substrate_bonus = 6.0 if row_substrate_id and row_substrate_id == current_substrate_id else 0.0
    complexity_score = _to_float(row.get("asset_complexity_score"), -1.0)
    if complexity_score < 0:
        complexity_score = _to_float(typed_metadata.get("asset_complexity_score"), 0.0)
    playability_score = _to_float(row.get("playability_score"), -1.0)
    if playability_score < 0:
        playability_score = _to_float(typed_metadata.get("playability_score"), 0.0)
    complexity_bonus = max(0.0, min(12.0, complexity_score * 0.12))
    playability_bonus = max(0.0, min(10.0, playability_score * 0.1))
    base_quality = _row_effective_quality(row)
    composed_score = (
        base_quality
        + qa_bonus
        + overlap_bonus
        + recency_bonus
        + substrate_bonus
        + complexity_bonus
        + playability_bonus
        - failure_penalty
    )
    return max(composed_score, 0.0), keyword_overlap


def _build_context_from_registry_entries(
    *,
    entries: list[dict[str, object]],
    core_loop_type: str,
    keyword: str,
) -> AssetMemoryContext | None:
    if not entries:
        return None

    current_keyword_tokens = _tokenize_keyword(keyword)
    pack_scores: dict[str, list[float]] = defaultdict(list)
    variant_scores: dict[str, list[float]] = defaultdict(list)
    theme_scores: dict[str, list[float]] = defaultdict(list)
    failure_reason_counter: Counter[str] = Counter()
    failure_token_counter: Counter[str] = Counter()
    keyword_match_count = 0

    substrate_id = resolve_substrate_profile(core_loop_type).substrate_id
    for index, row in enumerate(entries):
        row_score, overlap = _registry_row_score(
            row=row,
            current_keyword_tokens=current_keyword_tokens,
            current_substrate_id=substrate_id,
            rank=index,
        )
        if overlap > 0:
            keyword_match_count += 1

        asset_pack = str(row.get("asset_pack", "")).strip()
        if asset_pack:
            pack_scores[asset_pack].append(row_score)

        variant_id = str(row.get("variant_id", "")).strip()
        if variant_id:
            variant_scores[variant_id].append(row_score)

        variant_theme = str(row.get("variant_theme", "")).strip()
        if variant_theme:
            theme_scores[variant_theme].append(row_score)

        for reason in _to_str_list(row.get("failure_reasons")):
            failure_reason_counter[reason] += 1
        for token in _to_str_list(row.get("failure_tokens")):
            normalized_token = canonicalize_visual_token(token)
            if normalized_token:
                failure_token_counter[normalized_token] += 1

    preferred_asset_pack = max(pack_scores.items(), key=lambda item: mean(item[1]))[0] if pack_scores else None
    preferred_variant_id = max(variant_scores.items(), key=lambda item: mean(item[1]))[0] if variant_scores else None
    preferred_variant_theme = max(theme_scores.items(), key=lambda item: mean(item[1]))[0] if theme_scores else None
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

    retrieval_profile: dict[str, object] = {
        "source": "asset_registry_v1",
        "substrate_id": substrate_id,
        "preferred_asset_pack": preferred_asset_pack,
        "preferred_variant_id": preferred_variant_id,
        "preferred_variant_theme": preferred_variant_theme,
        "failure_reasons": top_reasons,
        "failure_tokens": top_tokens,
        "sample_size": len(entries),
        "keyword_match_count": keyword_match_count,
        "keyword_query_tokens": sorted(current_keyword_tokens),
        "scoring_profile": "quality+qa_status+keyword_overlap+substrate+complexity+playability+recency-failure_penalty",
    }
    registry_snapshot: dict[str, object] = {
        "core_loop_type": core_loop_type,
        "registry_source": "asset_registry_v1",
        "build_success_samples": len(entries),
        "qa_failure_samples": sum(1 for row in entries if _to_str_list(row.get("failure_reasons"))),
        "related_pipeline_count": len(entries),
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
        "keyword_match_count": keyword_match_count,
    }
    return AssetMemoryContext(
        hint=" ".join(hint_parts).strip(),
        recurring_failures=[*top_reasons, *top_tokens],
        retrieval_profile=retrieval_profile,
        registry_snapshot=registry_snapshot,
    )


def _merge_improvement_queue_signals(
    context: AssetMemoryContext,
    improvement_rows: list[dict[str, object]],
) -> AssetMemoryContext:
    if not improvement_rows:
        return context

    reason_counter: Counter[str] = Counter()
    token_counter: Counter[str] = Counter()
    for row in improvement_rows:
        reason = str(row.get("reason", "")).strip()
        if reason:
            reason_counter[reason] += 1
        for token in _to_str_list(row.get("tokens")):
            normalized_token = canonicalize_visual_token(token)
            if normalized_token:
                token_counter[normalized_token] += 1

    top_reasons = [key for key, _ in reason_counter.most_common(4)]
    top_tokens = [key for key, _ in token_counter.most_common(8)]
    if not top_reasons and not top_tokens:
        return context

    hint = context.hint
    queue_hint_parts: list[str] = []
    if top_reasons:
        queue_hint_parts.append(f"Reflect queued QA improvements: {', '.join(top_reasons)}.")
    if top_tokens:
        queue_hint_parts.append(f"Focus queued fix tokens: {', '.join(top_tokens)}.")
    if queue_hint_parts:
        hint = f"{hint} {' '.join(queue_hint_parts)}".strip()

    retrieval_profile = dict(context.retrieval_profile)
    retrieval_profile["improvement_queue_reason_top"] = top_reasons
    retrieval_profile["improvement_queue_token_top"] = top_tokens
    retrieval_profile["improvement_queue_count"] = len(improvement_rows)

    registry_snapshot = dict(context.registry_snapshot)
    registry_snapshot["improvement_queue_reason_top"] = top_reasons
    registry_snapshot["improvement_queue_token_top"] = top_tokens
    registry_snapshot["improvement_queue_count"] = len(improvement_rows)

    recurring_failures = list(dict.fromkeys([*context.recurring_failures, *top_reasons, *top_tokens]))

    return AssetMemoryContext(
        hint=hint,
        recurring_failures=recurring_failures,
        retrieval_profile=retrieval_profile,
        registry_snapshot=registry_snapshot,
    )


def collect_asset_memory_context(
    *,
    state: PipelineState,
    deps: NodeDependencies,
    core_loop_type: str,
    limit: int = 240,
) -> AssetMemoryContext:
    list_registry = getattr(deps.repository, "list_asset_registry", None)
    list_improvements = getattr(deps.repository, "list_qa_improvement_entries", None)
    improvement_rows: list[dict[str, object]] = []
    if callable(list_improvements):
        rows = list_improvements(core_loop_type=core_loop_type, limit=min(limit, 180))
        improvement_rows = [row for row in rows if isinstance(row, dict)]
    if callable(list_registry):
        rows = list_registry(core_loop_type=core_loop_type, limit=min(limit, 120))
        typed_rows = [row for row in rows if isinstance(row, dict)]
        registry_context = _build_context_from_registry_entries(
            entries=typed_rows,
            core_loop_type=core_loop_type,
            keyword=state.get("keyword", ""),
        )
        if registry_context is not None:
            return _merge_improvement_queue_signals(registry_context, improvement_rows)

    logs = deps.repository.list_recent_logs(limit=limit)
    if not logs:
        return empty_asset_memory_context()

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

        if log.stage in {PipelineStage.BUILD, PipelineStage.QA_RUNTIME, PipelineStage.QA_QUALITY} and log.status in {
            PipelineStatus.RETRY,
            PipelineStatus.ERROR,
        }:
            qa_failure_samples += 1
            reason = str(log.reason or metadata.get("reason") or "").strip()
            if reason:
                failure_reason_counter[reason] += 1

            for key in (
                "failed_checks",
                "fatal_errors",
                "blocking_reasons",
                "quality_floor_fail_reasons",
                "playability_fail_reasons",
            ):
                for token in _to_str_list(metadata.get(key)):
                    normalized_token = canonicalize_visual_token(token)
                    if normalized_token:
                        failure_token_counter[normalized_token] += 1

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

    context = AssetMemoryContext(
        hint=hint,
        recurring_failures=[*top_reasons, *top_tokens],
        retrieval_profile=retrieval_profile,
        registry_snapshot=registry_snapshot,
    )
    return _merge_improvement_queue_signals(context, improvement_rows)


def empty_asset_memory_context() -> AssetMemoryContext:
    empty_profile: dict[str, object] = {
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
