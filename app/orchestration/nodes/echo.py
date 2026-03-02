from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log, apply_operator_control_gate
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


def _latest_stage_log_metadata(state: PipelineState, stage: PipelineStage) -> dict[str, object]:
    for log in reversed(state["logs"]):
        if log.stage == stage and isinstance(log.metadata, dict):
            return dict(log.metadata)
    return {}


def _latest_stage_log(state: PipelineState, stage: PipelineStage):
    for log in reversed(state["logs"]):
        if log.stage == stage:
            return log
    return None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            rows.append(text)
    return rows


def run(state: PipelineState, deps: NodeDependencies) -> PipelineState:
    gated_state = apply_operator_control_gate(
        state,
        deps,
        stage=PipelineStage.REPORT,
        agent_name=PipelineAgentName.REPORTER,
    )
    if gated_state is not None:
        return gated_state

    slug = state["outputs"].get("game_slug", "unknown-game")
    game_name = state["outputs"].get("game_name", slug)
    genre = state["outputs"].get("game_genre", "arcade")
    genre_engine = str(state["outputs"].get("genre_engine", "arcade_generic"))
    keyword = state.get("keyword", "unknown")
    objective = ""
    gdd_payload = state["outputs"].get("gdd")
    if isinstance(gdd_payload, dict):
        raw_objective = gdd_payload.get("objective")
        if isinstance(raw_objective, str):
            objective = raw_objective.strip()
    
    build_metadata = _latest_stage_log_metadata(state, PipelineStage.BUILD)
    runtime_qa_metadata = _latest_stage_log_metadata(state, PipelineStage.QA_RUNTIME)
    quality_qa_metadata = _latest_stage_log_metadata(state, PipelineStage.QA_QUALITY)
    analyze_metadata = _latest_stage_log_metadata(state, PipelineStage.ANALYZE)
    plan_metadata = _latest_stage_log_metadata(state, PipelineStage.PLAN)
    design_metadata = _latest_stage_log_metadata(state, PipelineStage.DESIGN)
    qa_quality_log = _latest_stage_log(state, PipelineStage.QA_QUALITY)
    stage_contribution_summary = {
        "analyze": {
            "contract_status": analyze_metadata.get("contract_status"),
            "contribution_score": analyze_metadata.get("contribution_score"),
            "deliverables": _string_list(analyze_metadata.get("deliverables")),
        },
        "plan": {
            "contract_status": plan_metadata.get("contract_status"),
            "contribution_score": plan_metadata.get("contribution_score"),
            "deliverables": _string_list(plan_metadata.get("deliverables")),
        },
        "design": {
            "contract_status": design_metadata.get("contract_status"),
            "contribution_score": design_metadata.get("contribution_score"),
            "deliverables": _string_list(design_metadata.get("deliverables")),
        },
        "build": {
            "contract_status": build_metadata.get("contract_status"),
            "contribution_score": build_metadata.get("contribution_score"),
            "deliverables": _string_list(build_metadata.get("deliverables")),
        },
        "qa_runtime": {
            "contract_status": runtime_qa_metadata.get("contract_status"),
            "contribution_score": runtime_qa_metadata.get("contribution_score"),
            "deliverables": _string_list(runtime_qa_metadata.get("deliverables")),
        },
        "qa_quality": {
            "contract_status": quality_qa_metadata.get("contract_status"),
            "contribution_score": quality_qa_metadata.get("contribution_score"),
            "deliverables": _string_list(quality_qa_metadata.get("deliverables")),
        },
    }
    grounded_evidence = {
        "slug": slug,
        "genre_engine": genre_engine,
        "candidate_count": build_metadata.get("candidate_count"),
        "final_quality_score": build_metadata.get("final_quality_score") or quality_qa_metadata.get("quality_score"),
        "final_gameplay_score": build_metadata.get("final_gameplay_score") or quality_qa_metadata.get("gameplay_score"),
        "artifact_file_count": build_metadata.get("artifact_file_count"),
        "asset_pack": build_metadata.get("asset_pack") or state["outputs"].get("asset_pack"),
        "qa_message": quality_qa_metadata.get("message") if isinstance(quality_qa_metadata.get("message"), str) else None,
    }

    marketing_result = deps.vertex_service.generate_marketing_copy(
        keyword=keyword, slug=slug, genre=genre, game_name=game_name
    )
    marketing_text = marketing_result.payload.get("marketing_copy", "")
    review_generator = getattr(deps.vertex_service, "generate_grounded_ai_review", None)
    if callable(review_generator):
        review_result = review_generator(
            keyword=keyword,
            game_name=game_name,
            genre=genre,
            objective=objective or "플레이어가 즉시 이해하고 반복 도전할 수 있는 아케이드 루프",
            evidence=grounded_evidence,
        )
    else:
        review_result = deps.vertex_service.generate_ai_review(
            keyword=keyword,
            game_name=game_name,
            genre=genre,
            objective=objective or "플레이어가 즉시 이해하고 반복 도전할 수 있는 아케이드 루프",
        )
    ai_review_text = str(review_result.payload.get("ai_review", "")).strip()
    if not ai_review_text:
        ai_review_text = "리뷰 생성에 실패했습니다. 최신 파이프라인 로그에서 BUILD/QA 근거 데이터를 확인해주세요."

    resolved_public_url = ""
    portal_link_candidate = ""
    publish_result = state["outputs"].get("publish_result")
    if isinstance(publish_result, dict):
        maybe_game_id = publish_result.get("game_id")
        if maybe_game_id and deps.telegram_service.settings.public_portal_base_url:
            base = deps.telegram_service.settings.public_portal_base_url.rstrip("/")
            portal_link_candidate = f"{base}/play/{maybe_game_id}"
        maybe_public_url = publish_result.get("public_url")
        if isinstance(maybe_public_url, str):
            resolved_public_url = maybe_public_url.strip()
    if portal_link_candidate:
        resolved_public_url = portal_link_candidate
    if not resolved_public_url:
        raw_public_url = state["outputs"].get("public_url")
        if isinstance(raw_public_url, str):
            resolved_public_url = raw_public_url.strip()
    if not resolved_public_url:
        base_url = deps.telegram_service.settings.public_games_base_url.rstrip("/")
        resolved_public_url = f"{base_url}/{slug}/index.html"

    telegram_text = f"🎮 신규 게임 게시됨\n\n{marketing_text}\n\n🕹️ 플레이: {resolved_public_url}"
    
    result = deps.telegram_service.broadcast_message(telegram_text)
    
    screenshot_url = state["outputs"].get("screenshot_url")
    marketing_updated = deps.publisher_service.update_game_marketing(
        slug=slug,
        ai_review=ai_review_text,
        screenshot_url=screenshot_url
    )

    status = PipelineStatus.SUCCESS if result.get("status") in ("posted", "skipped") else PipelineStatus.SKIPPED
    reason = result.get("reason")

    state = append_log(
        state,
        stage=PipelineStage.REPORT,
        status=status,
        agent_name=PipelineAgentName.REPORTER,
        message=f"Telegram broadcast result: {result.get('status', 'unknown')}",
        metadata={
            "generation_source": marketing_result.meta.get("generation_source"),
            "model": marketing_result.meta.get("model"),
            "latency_ms": marketing_result.meta.get("latency_ms"),
            "usage": marketing_result.meta.get("usage", {}),
            "slug": slug,
            "game_name": game_name,
            "ai_review_text": ai_review_text,
            "review_generation_source": review_result.meta.get("generation_source"),
            "review_model": review_result.meta.get("model"),
            "review_usage": review_result.meta.get("usage", {}),
            "review_grounded_evidence": grounded_evidence,
            "marketing_updated": bool(marketing_updated),
            "marketing_language": "ko-KR",
            "resolved_public_url": resolved_public_url,
            "deliverables": ["telegram_broadcast", "ai_review_update", "asset_registry_sync"],
            "contract_status": "pass",
            "contract_summary": "final reporting and persistence completed",
            "contribution_score": 4.4,
            "stage_contribution_summary": stage_contribution_summary,
        },
        reason=reason,
    )

    upsert_registry = getattr(deps.repository, "upsert_asset_registry_entry", None)
    if callable(upsert_registry):
        failure_reasons: list[str] = []
        if qa_quality_log and isinstance(qa_quality_log.reason, str) and qa_quality_log.reason.strip():
            failure_reasons.append(qa_quality_log.reason.strip())
        failure_reasons.extend(_string_list(quality_qa_metadata.get("failed_checks")))

        failure_tokens = _string_list(runtime_qa_metadata.get("fatal_errors")) + _string_list(runtime_qa_metadata.get("non_fatal_warnings"))

        try:
            upsert_registry(
                {
                    "pipeline_id": str(state["pipeline_id"]),
                    "game_slug": str(slug),
                    "game_name": str(game_name),
                    "keyword": str(keyword),
                    "core_loop_type": genre_engine,
                    "asset_pack": str(build_metadata.get("asset_pack") or state["outputs"].get("asset_pack") or ""),
                    "variant_id": str(build_metadata.get("asset_pipeline_selected_variant") or ""),
                    "variant_theme": str(build_metadata.get("asset_pipeline_selected_theme") or ""),
                    "final_composite_score": build_metadata.get("final_composite_score"),
                    "final_quality_score": build_metadata.get("final_quality_score") or quality_qa_metadata.get("quality_score"),
                    "final_gameplay_score": build_metadata.get("final_gameplay_score") or quality_qa_metadata.get("gameplay_score"),
                    "qa_status": qa_quality_log.status.value if qa_quality_log else "",
                    "qa_reason": qa_quality_log.reason if qa_quality_log else None,
                    "failure_reasons": failure_reasons,
                    "failure_tokens": failure_tokens,
                    "artifact_manifest": state["outputs"].get("artifact_manifest")
                    if isinstance(state["outputs"].get("artifact_manifest"), dict)
                    else {},
                    "metadata": {
                        "resolved_public_url": resolved_public_url,
                        "review_generation_source": review_result.meta.get("generation_source"),
                        "runtime_structure_signature": build_metadata.get("runtime_structure_signature"),
                        "final_runtime_warning_codes": build_metadata.get("final_runtime_warning_codes"),
                        "final_runtime_warning_penalty": build_metadata.get("final_runtime_warning_penalty"),
                        "duplicate_runtime_signature": build_metadata.get("duplicate_runtime_signature"),
                    },
                }
            )
            state["outputs"]["asset_registry_synced"] = True
        except Exception:
            state["outputs"]["asset_registry_synced"] = False

    append_improvements = getattr(deps.repository, "append_qa_improvement_entries", None)
    improvement_items = state["outputs"].get("qa_improvement_items")
    if callable(append_improvements) and isinstance(improvement_items, list):
        typed_items = [item for item in improvement_items if isinstance(item, dict)]
        try:
            append_improvements(
                pipeline_id=str(state["pipeline_id"]),
                game_slug=str(slug),
                core_loop_type=genre_engine,
                keyword=str(keyword),
                entries=typed_items,
            )
            state["outputs"]["qa_improvement_synced"] = True
        except Exception:
            state["outputs"]["qa_improvement_synced"] = False

    if state["status"] != PipelineStatus.ERROR:
        state["status"] = PipelineStatus.SUCCESS
        append_log(
            state,
            stage=PipelineStage.DONE,
            status=PipelineStatus.SUCCESS,
            agent_name=PipelineAgentName.REPORTER,
            message="Pipeline finished.",
        )
    return state
