from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.builder_parts.bundle import _extract_hybrid_bundle_from_inline_html
from app.orchestration.nodes.builder_parts.html_runtime import _build_hybrid_engine_html
from app.orchestration.nodes.builder_parts.mode import _candidate_composite_score, _candidate_variation_hints
from app.orchestration.nodes.common import append_log
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.payloads import BuildArtifactPayload, DesignSpecPayload, GDDPayload
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


@dataclass(frozen=True)
class ProductionBuildResult:
    build_artifact: BuildArtifactPayload
    selected_generation_meta: dict[str, Any]
    metadata: dict[str, Any]


def build_production_artifact(
    *,
    state: PipelineState,
    deps: NodeDependencies,
    gdd: GDDPayload,
    design_spec: DesignSpecPayload,
    title: str,
    genre: str,
    slug: str,
    accent_color: str,
    core_loop_type: str,
    asset_pack: dict[str, Any],
    asset_bank_files: list[dict[str, str]],
    runtime_asset_manifest: dict[str, Any],
) -> ProductionBuildResult:
    configured_candidate_count = max(1, int(deps.vertex_service.settings.builder_candidate_count))
    candidate_count = 1
    variation_hints = _candidate_variation_hints(core_loop_type=core_loop_type, candidate_count=candidate_count)
    design_spec_dump = design_spec.model_dump()

    append_log(
        state,
        stage=PipelineStage.BUILD,
        status=PipelineStatus.RUNNING,
        agent_name=PipelineAgentName.BUILDER,
        message=f"Production V2 generation started (iteration={state['build_iteration']}).",
        metadata={
            "iteration": state["build_iteration"],
            "core_loop_type": core_loop_type,
            "asset_pack": asset_pack["name"],
            "configured_candidate_count": configured_candidate_count,
            "candidate_count": candidate_count,
        },
    )

    candidate_rows: list[dict[str, Any]] = []
    for index, variation_hint in enumerate(variation_hints, start=1):
        generated_config = deps.vertex_service.generate_game_config(
            keyword=state["keyword"],
            title=title,
            genre=genre,
            objective=gdd.objective,
            design_spec=design_spec_dump,
            variation_hint=variation_hint,
        )
        base_candidate_html = _build_hybrid_engine_html(
            title=title,
            genre=genre,
            slug=slug,
            accent_color=accent_color,
            viewport_width=design_spec.viewport_width,
            viewport_height=design_spec.viewport_height,
            safe_area_padding=design_spec.safe_area_padding,
            min_font_size_px=design_spec.min_font_size_px,
            text_overflow_policy=design_spec.text_overflow_policy,
            core_loop_type=core_loop_type,
            game_config=generated_config.payload,
            asset_pack=asset_pack,
            asset_manifest=runtime_asset_manifest,
        )
        candidate_html = base_candidate_html
        codegen_meta_rows: list[dict[str, Any]] = []
        for pass_index in range(max(0, int(deps.vertex_service.settings.builder_codegen_passes))):
            codegen_result = deps.vertex_service.generate_codegen_candidate_artifact(
                keyword=state["keyword"],
                title=title,
                genre=genre,
                objective=gdd.objective,
                core_loop_type=core_loop_type,
                variation_hint=variation_hint,
                design_spec=design_spec_dump,
                asset_pack=asset_pack,
                html_content=candidate_html,
            )
            generated_candidate_html = str(codegen_result.payload.get("artifact_html", "")).strip()
            if generated_candidate_html:
                candidate_html = generated_candidate_html
            codegen_meta_rows.append(
                {
                    "pass": pass_index + 1,
                    "generation_source": codegen_result.meta.get("generation_source", "stub"),
                    "model": codegen_result.meta.get("model"),
                    "reason": codegen_result.meta.get("reason"),
                }
            )
        base_quality_probe = deps.quality_service.evaluate_quality_contract(base_candidate_html, design_spec=design_spec_dump)
        base_gameplay_probe = deps.quality_service.evaluate_gameplay_gate(
            base_candidate_html,
            design_spec=design_spec_dump,
            genre=genre,
            genre_engine=core_loop_type,
            keyword=state["keyword"],
        )
        base_composite_score = _candidate_composite_score(
            quality_score=base_quality_probe.score,
            gameplay_score=base_gameplay_probe.score,
            quality_ok=base_quality_probe.ok,
            gameplay_ok=base_gameplay_probe.ok,
        )
        quality_probe = deps.quality_service.evaluate_quality_contract(candidate_html, design_spec=design_spec_dump)
        gameplay_probe = deps.quality_service.evaluate_gameplay_gate(
            candidate_html,
            design_spec=design_spec_dump,
            genre=genre,
            genre_engine=core_loop_type,
            keyword=state["keyword"],
        )
        composite_score = _candidate_composite_score(
            quality_score=quality_probe.score,
            gameplay_score=gameplay_probe.score,
            quality_ok=quality_probe.ok,
            gameplay_ok=gameplay_probe.ok,
        )
        if base_composite_score > composite_score:
            candidate_html = base_candidate_html
            quality_probe = base_quality_probe
            gameplay_probe = base_gameplay_probe
            composite_score = base_composite_score
            codegen_meta_rows.append(
                {
                    "pass": 0,
                    "generation_source": "template_baseline",
                    "model": None,
                    "reason": "codegen_regression_guard",
                    "baseline_composite_score": base_composite_score,
                }
            )

        candidate_row = {
            "index": index,
            "variation_hint": variation_hint,
            "artifact_html": candidate_html,
            "baseline_artifact_html": base_candidate_html,
            "generation_meta": generated_config.meta,
            "quality_ok": quality_probe.ok,
            "quality_score": quality_probe.score,
            "gameplay_ok": gameplay_probe.ok,
            "gameplay_score": gameplay_probe.score,
            "composite_score": composite_score,
            "asset_pack": asset_pack["name"],
            "codegen_passes": codegen_meta_rows,
        }
        candidate_rows.append(candidate_row)

        append_log(
            state,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.RUNNING,
            agent_name=PipelineAgentName.BUILDER,
            message=f"Candidate {index}/{candidate_count} evaluated.",
            metadata={
                "iteration": state["build_iteration"],
                "candidate_index": index,
                "quality_score": quality_probe.score,
                "gameplay_score": gameplay_probe.score,
                "composite_score": composite_score,
                "generation_source": generated_config.meta.get("generation_source", "stub"),
                "model": generated_config.meta.get("model"),
                "asset_pack": asset_pack["name"],
                "codegen_passes": codegen_meta_rows,
            },
        )

    best_candidate = max(
        candidate_rows,
        key=lambda row: (float(row["composite_score"]), int(row["gameplay_score"]), int(row["quality_score"])),
    )
    selected_generation_meta = dict(best_candidate.get("generation_meta", {}))
    selected_html = str(best_candidate["artifact_html"])
    selected_baseline_html = str(best_candidate.get("baseline_artifact_html", selected_html))

    append_log(
        state,
        stage=PipelineStage.BUILD,
        status=PipelineStatus.RUNNING,
        agent_name=PipelineAgentName.BUILDER,
        message="Final polish pass started for selected candidate.",
        metadata={
            "iteration": state["build_iteration"],
            "selected_candidate": best_candidate["index"],
            "selected_composite_score": best_candidate["composite_score"],
        },
    )

    polish_result = deps.vertex_service.polish_hybrid_artifact(
        keyword=state["keyword"],
        title=title,
        genre=genre,
        html_content=selected_html,
    )
    polished_html = str(polish_result.payload.get("artifact_html", "")).strip() or selected_html
    polished_quality = deps.quality_service.evaluate_quality_contract(polished_html, design_spec=design_spec_dump)
    polished_gameplay = deps.quality_service.evaluate_gameplay_gate(
        polished_html,
        design_spec=design_spec_dump,
        genre=genre,
        genre_engine=core_loop_type,
        keyword=state["keyword"],
    )
    polished_composite = _candidate_composite_score(
        quality_score=polished_quality.score,
        gameplay_score=polished_gameplay.score,
        quality_ok=polished_quality.ok,
        gameplay_ok=polished_gameplay.ok,
    )
    selected_composite = float(best_candidate["composite_score"])
    use_polished = polished_composite >= (selected_composite - 2.0)
    if polished_quality.ok and polished_gameplay.ok:
        use_polished = True
    artifact_html = polished_html if use_polished else selected_html

    final_quality_score = polished_quality.score if use_polished else int(best_candidate["quality_score"])
    final_gameplay_score = polished_gameplay.score if use_polished else int(best_candidate["gameplay_score"])
    final_composite_score = polished_composite if use_polished else selected_composite

    runtime_guard_candidates = [
        ("polished", artifact_html),
        ("selected", selected_html),
        ("baseline", selected_baseline_html),
    ]
    runtime_guard_result: dict[str, object] = {"chosen": None, "reason": None, "probes": []}
    for label, candidate_html in runtime_guard_candidates:
        smoke_probe = deps.quality_service.run_smoke_check(
            candidate_html,
            artifact_files=asset_bank_files,
            entrypoint_path=f"games/{slug}/index.html",
        )
        runtime_guard_result["probes"].append(
            {
                "label": label,
                "ok": bool(smoke_probe.ok),
                "reason": smoke_probe.reason,
                "console_errors": smoke_probe.console_errors or [],
                "fatal_errors": smoke_probe.fatal_errors or [],
                "non_fatal_warnings": smoke_probe.non_fatal_warnings or [],
            }
        )
        if smoke_probe.ok:
            artifact_html = candidate_html
            runtime_guard_result["chosen"] = label
            runtime_guard_result["reason"] = smoke_probe.reason
            break

    if runtime_guard_result["chosen"] is None:
        artifact_html = selected_baseline_html
        runtime_guard_result["chosen"] = "baseline_force"
        runtime_guard_result["reason"] = "builder_runtime_guard_all_failed"

    builder_strategy = "production_v3_candidates_codegen_qa_polish"
    candidate_scoreboard = [
        {
            "index": int(row["index"]),
            "quality_score": int(row["quality_score"]),
            "gameplay_score": int(row["gameplay_score"]),
            "composite_score": float(row["composite_score"]),
            "quality_ok": bool(row["quality_ok"]),
            "gameplay_ok": bool(row["gameplay_ok"]),
            "generation_source": row["generation_meta"].get("generation_source", "stub"),
            "model": row["generation_meta"].get("model"),
            "asset_pack": row.get("asset_pack"),
            "codegen_passes": row.get("codegen_passes", []),
        }
        for row in candidate_rows
    ]

    artifact_files: list[dict[str, str]] | None = None
    artifact_manifest: dict[str, object] | None = None

    hybrid_bundle = _extract_hybrid_bundle_from_inline_html(
        slug=slug,
        inline_html=artifact_html,
        asset_bank_files=asset_bank_files,
        runtime_asset_manifest=runtime_asset_manifest,
    )
    if not hybrid_bundle:
        fallback_files = [
            {
                "path": f"games/{slug}/index.html",
                "content": artifact_html,
                "content_type": "text/html; charset=utf-8",
            },
            *asset_bank_files,
        ]
        fallback_asset_manifest = runtime_asset_manifest if isinstance(runtime_asset_manifest, dict) else {}
        fallback_manifest = {
            "schema_version": 1,
            "entrypoint": f"games/{slug}/index.html",
            "files": [row["path"] for row in fallback_files],
            "bundle_kind": "hybrid_engine",
            "modules": [
                "runtime_bootstrap",
                "input_controls",
                "spawn_system",
                "combat_or_navigation_loop",
                "render_pipeline",
                "hud_overlay",
                "audio_feedback",
            ],
            "runtime_hooks": [
                "requestAnimationFrame",
                "pickWeighted",
                "applyRelicSynergy",
                "spawnMiniBoss",
                "drawPostFx",
                "update",
                "draw",
                "playSfx",
            ],
            "asset_manifest": fallback_asset_manifest,
        }
        hybrid_bundle = (fallback_files, fallback_manifest)
    if hybrid_bundle:
        artifact_files, artifact_manifest = hybrid_bundle
        artifact_manifest["genre_engine"] = core_loop_type
        artifact_manifest["asset_pack"] = asset_pack["name"]

    build_artifact = BuildArtifactPayload(
        game_slug=slug,
        game_name=title,
        game_genre=genre,
        artifact_path=f"games/{slug}/index.html",
        artifact_html=artifact_html,
        entrypoint_path=f"games/{slug}/index.html",
        artifact_files=artifact_files,
        artifact_manifest=artifact_manifest,
    )

    metadata = {
        "builder_strategy": builder_strategy,
        "genre_engine_selected": core_loop_type,
        "asset_pack": asset_pack["name"],
        "artifact_file_count": len(build_artifact.artifact_files or []),
        "configured_candidate_count": configured_candidate_count,
        "candidate_count": candidate_count,
        "codegen_enabled": bool(deps.vertex_service.settings.builder_codegen_enabled),
        "codegen_passes_per_candidate": int(deps.vertex_service.settings.builder_codegen_passes),
        "selected_candidate_index": int(best_candidate["index"]),
        "selected_candidate_score": selected_composite,
        "final_quality_score": final_quality_score,
        "final_gameplay_score": final_gameplay_score,
        "final_composite_score": final_composite_score,
        "polish_applied": use_polished,
        "polish_generation_source": polish_result.meta.get("generation_source", "stub"),
        "polish_model": polish_result.meta.get("model"),
        "polish_reason": polish_result.meta.get("reason"),
        "runtime_guard": runtime_guard_result,
        "candidate_scoreboard": candidate_scoreboard,
    }
    return ProductionBuildResult(
        build_artifact=build_artifact,
        selected_generation_meta=selected_generation_meta,
        metadata=metadata,
    )
