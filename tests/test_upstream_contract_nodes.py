from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.orchestration.nodes import architect, builder, stylist, trigger
from app.orchestration.nodes.builder_parts.production_pipeline import ProductionBuildResult
from app.schemas.payloads import BuildArtifactPayload, IntentContractPayload
from app.schemas.pipeline import PipelineStatus
from app.services.vertex_types import VertexGenerationResult


class _RepoStub:
    def get_pipeline(self, _pipeline_id):
        return SimpleNamespace(metadata={})


def _base_state() -> dict[str, Any]:
    return {
        "pipeline_id": uuid4(),
        "keyword": "arena shooter",
        "qa_attempt": 0,
        "max_qa_loops": 3,
        "fail_qa_until": 0,
        "build_iteration": 0,
        "needs_rebuild": False,
        "status": PipelineStatus.RUNNING,
        "reason": None,
        "logs": [],
        "flushed_log_count": 0,
        "log_sink": None,
        "outputs": {"pipeline_version": "forgeflow-v1"},
    }


class _VertexStub:
    def __init__(self, *, contract_mode: str = "ok", strict_vertex_only: bool = False) -> None:
        self._contract_mode = contract_mode
        self.settings = SimpleNamespace(
            builder_scope_guard_enabled=False,
            builder_asset_memory_enabled=False,
            strict_vertex_only=strict_vertex_only,
            allow_stub_fallback=False,
            pipeline_contract_enforcement="strict",
        )

    def generate_analyze_contract(self, *, keyword: str) -> VertexGenerationResult:
        payload = {
            "intent": f"{keyword} intent",
            "scope_in": ["browser runtime", "deployable artifact"],
            "scope_out": ["manual approval"],
            "hard_constraints": ["no secret leakage"],
            "forbidden_patterns": ["placeholder-only visuals"],
            "success_outcome": "playable output",
        }
        return VertexGenerationResult(payload=payload, meta={"generation_source": "stub"})

    def generate_gdd_bundle(self, _keyword: str) -> VertexGenerationResult:
        payload = {
            "gdd": {
                "title": "Arena Pulse",
                "genre": "shooter",
                "objective": "Defeat waves and survive.",
                "visual_style": "neon",
            },
            "research_summary": {"intent": "find references", "references": ["a", "b", "c"]},
        }
        return VertexGenerationResult(payload=payload, meta={"generation_source": "stub"})

    def generate_plan_contract(self, *, keyword: str, gdd: dict[str, Any], research_summary: dict[str, Any] | None = None) -> VertexGenerationResult:
        _ = (keyword, gdd, research_summary)
        if self._contract_mode == "invalid":
            payload = {
                "core_mechanics": [],
                "progression_plan": [],
                "encounter_plan": ["wave"],
                "risk_reward_plan": ["safe"],
                "control_model": "",
                "balance_baseline": {"base_hp": 3.0},
            }
        elif self._contract_mode == "weak":
            payload = {
                "core_mechanics": ["move"],
                "progression_plan": ["intro"],
                "encounter_plan": ["wave"],
                "risk_reward_plan": ["safe"],
                "control_model": "keyboard",
                "balance_baseline": {"base_hp": 3.0},
            }
        else:
            payload = {
                "core_mechanics": ["move", "aim", "shoot"],
                "progression_plan": ["intro", "mid", "late"],
                "encounter_plan": ["wave", "elite", "miniboss"],
                "risk_reward_plan": ["safe", "aggressive", "recovery"],
                "control_model": "keyboard analog",
                "balance_baseline": {"base_hp": 3.0, "spawn_rate": 1.0, "difficulty": 1.2},
            }
        return VertexGenerationResult(payload=payload, meta={"generation_source": "stub"})

    def generate_design_spec(self, *, keyword: str, visual_style: str, genre: str) -> VertexGenerationResult:
        _ = (keyword, visual_style, genre)
        payload = {
            "visual_style": "neon",
            "palette": ["#00FFEE", "#111111", "#FF3366", "#F2F2F2"],
            "hud": "score/time/hp",
            "viewport_width": 1280,
            "viewport_height": 720,
            "safe_area_padding": 24,
            "min_font_size_px": 14,
            "text_overflow_policy": "ellipsis-clamp",
            "typography": "inter-bold-hud",
            "thumbnail_concept": "arena burst",
        }
        return VertexGenerationResult(payload=payload, meta={"generation_source": "stub"})

    def generate_design_contract(
        self,
        *,
        keyword: str,
        genre: str,
        visual_style: str,
        design_spec: dict[str, Any],
    ) -> VertexGenerationResult:
        _ = (keyword, genre, visual_style, design_spec)
        if self._contract_mode == "weak":
            payload = {
                "camera_ui_contract": ["stable camera"],
                "asset_blueprint_2d3d": ["player"],
                "scene_layers": ["foreground"],
                "feedback_fx_contract": ["hit flash"],
                "readability_contract": ["contrast"],
            }
        else:
            payload = {
                "camera_ui_contract": ["stable camera", "glanceable HUD"],
                "asset_blueprint_2d3d": ["player", "enemy set", "vfx pack", "props"],
                "scene_layers": ["foreground", "midground", "background", "postfx"],
                "feedback_fx_contract": ["hit flash", "danger telegraph", "combo feedback"],
                "readability_contract": ["silhouette separation", "projectile visibility"],
            }
        return VertexGenerationResult(payload=payload, meta={"generation_source": "stub"})


def _deps(vertex: _VertexStub) -> SimpleNamespace:
    return SimpleNamespace(
        repository=_RepoStub(),
        telegram_service=object(),
        quality_service=object(),
        publisher_service=object(),
        github_archive_service=object(),
        vertex_service=vertex,
    )


def test_trigger_architect_stylist_populate_contract_outputs() -> None:
    state = _base_state()
    deps = _deps(_VertexStub())

    state = trigger.run(cast(Any, state), cast(Any, deps))
    state = architect.run(cast(Any, state), cast(Any, deps))
    state = stylist.run(cast(Any, state), cast(Any, deps))

    outputs = state["outputs"]
    assert isinstance(outputs.get("analyze_contract"), dict)
    assert isinstance(outputs.get("plan_contract"), dict)
    assert isinstance(outputs.get("design_contract"), dict)
    assert isinstance(outputs.get("shared_generation_contract"), dict)
    assert isinstance(outputs.get("shared_generation_contract_hash"), str)
    assert any(log.stage.value == "analyze" for log in state["logs"])
    assert any(log.stage.value == "plan" for log in state["logs"])
    assert any(log.stage.value == "design" for log in state["logs"])


def test_trigger_reuses_cached_analyze_contract_on_build_resume(monkeypatch) -> None:
    state = _base_state()
    state["outputs"]["resume_stage"] = "build"
    state["outputs"]["analyze_contract"] = {"intent": "cached"}
    deps = _deps(_VertexStub())
    monkeypatch.setattr(
        deps.vertex_service,
        "generate_analyze_contract",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("generate_analyze_contract should not be called")),
    )

    result = trigger.run(cast(Any, state), cast(Any, deps))
    assert result["status"] == PipelineStatus.RUNNING
    analyze_logs = [log for log in result["logs"] if log.stage.value == "analyze"]
    assert analyze_logs
    assert "재개" in analyze_logs[-1].message


def test_architect_reuses_cached_plan_contract_on_build_resume(monkeypatch) -> None:
    state = _base_state()
    state["outputs"]["resume_stage"] = "build"
    state["outputs"]["gdd"] = {"title": "cached", "genre": "arcade", "objective": "survive", "visual_style": "neon"}
    state["outputs"]["plan_contract"] = {
        "core_mechanics": ["move"],
        "progression_plan": ["intro"],
        "encounter_plan": ["wave"],
        "risk_reward_plan": ["safe"],
        "control_model": "keyboard",
        "balance_baseline": {"base_hp": 3.0},
    }
    deps = _deps(_VertexStub())
    monkeypatch.setattr(
        deps.vertex_service,
        "generate_gdd_bundle",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("generate_gdd_bundle should not be called")),
    )

    result = architect.run(cast(Any, state), cast(Any, deps))
    assert result["status"] == PipelineStatus.RUNNING
    plan_logs = [log for log in result["logs"] if log.stage.value == "plan"]
    assert plan_logs
    assert "재개" in plan_logs[-1].message


def test_stylist_reuses_cached_design_contract_on_build_resume(monkeypatch) -> None:
    state = _base_state()
    state["outputs"]["resume_stage"] = "build"
    state["outputs"]["gdd"] = {"genre": "arcade"}
    state["outputs"]["design_spec"] = {
        "visual_style": "neon",
        "palette": ["#00FFEE", "#111111", "#FF3366", "#F2F2F2"],
        "hud": "score/time/hp",
        "viewport_width": 1280,
        "viewport_height": 720,
        "safe_area_padding": 24,
        "min_font_size_px": 14,
        "text_overflow_policy": "ellipsis-clamp",
        "typography": "inter-bold-hud",
        "thumbnail_concept": "arena burst",
    }
    state["outputs"]["design_contract"] = {
        "camera_ui_contract": ["stable camera", "hud"],
        "asset_blueprint_2d3d": ["player", "enemy", "bg"],
        "scene_layers": ["fg", "bg"],
        "feedback_fx_contract": ["hit flash"],
        "readability_contract": ["contrast"],
    }
    deps = _deps(_VertexStub())
    monkeypatch.setattr(
        deps.vertex_service,
        "generate_design_spec",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("generate_design_spec should not be called")),
    )

    result = stylist.run(cast(Any, state), cast(Any, deps))
    assert result["status"] == PipelineStatus.RUNNING
    design_logs = [log for log in result["logs"] if log.stage.value == "design"]
    assert design_logs
    assert "재개" in design_logs[-1].message


def test_dual_agent_mode_architect_synthesizes_plan_without_vertex_calls(monkeypatch) -> None:
    state = _base_state()
    vertex = _VertexStub()
    vertex.settings.pipeline_dual_agent_mode = True
    deps = _deps(vertex)

    state = trigger.run(cast(Any, state), cast(Any, deps))
    monkeypatch.setattr(
        deps.vertex_service,
        "generate_gdd_bundle",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("generate_gdd_bundle should not be called")),
    )
    monkeypatch.setattr(
        deps.vertex_service,
        "generate_plan_contract",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("generate_plan_contract should not be called")),
    )

    result = architect.run(cast(Any, state), cast(Any, deps))
    assert result["status"] == PipelineStatus.RUNNING
    assert result["outputs"]["gdd_source"] == "dual_agent_synth"
    assert result["outputs"]["plan_contract_source"] == "dual_agent_synth"
    assert isinstance(result["outputs"].get("gdd"), dict)
    assert isinstance(result["outputs"].get("plan_contract"), dict)


def test_dual_agent_mode_stylist_synthesizes_design_without_vertex_calls(monkeypatch) -> None:
    state = _base_state()
    vertex = _VertexStub()
    vertex.settings.pipeline_dual_agent_mode = True
    deps = _deps(vertex)

    state = trigger.run(cast(Any, state), cast(Any, deps))
    state = architect.run(cast(Any, state), cast(Any, deps))
    monkeypatch.setattr(
        deps.vertex_service,
        "generate_design_spec",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("generate_design_spec should not be called")),
    )
    monkeypatch.setattr(
        deps.vertex_service,
        "generate_design_contract",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("generate_design_contract should not be called")),
    )

    result = stylist.run(cast(Any, state), cast(Any, deps))
    assert result["status"] == PipelineStatus.RUNNING
    assert result["outputs"]["design_spec_source"] == "dual_agent_synth"
    assert result["outputs"]["design_contract_source"] == "dual_agent_synth"
    assert isinstance(result["outputs"].get("design_spec"), dict)
    assert isinstance(result["outputs"].get("design_contract"), dict)


def test_builder_accepts_dual_agent_sources_when_strict_vertex_only(monkeypatch) -> None:
    state = _base_state()
    vertex = _VertexStub(strict_vertex_only=True)
    vertex.settings.pipeline_dual_agent_mode = True
    deps = _deps(vertex)

    def _vertex_analyze_contract(*, keyword: str) -> VertexGenerationResult:
        return VertexGenerationResult(
            payload={
                "intent": f"{keyword} intent",
                "scope_in": ["browser runtime", "deployable artifact"],
                "scope_out": ["manual approval"],
                "hard_constraints": ["no secret leakage"],
                "forbidden_patterns": ["placeholder-only visuals"],
                "success_outcome": "playable output",
            },
            meta={"generation_source": "vertex"},
        )

    monkeypatch.setattr(deps.vertex_service, "generate_analyze_contract", _vertex_analyze_contract)

    state = trigger.run(cast(Any, state), cast(Any, deps))
    state = architect.run(cast(Any, state), cast(Any, deps))
    state = stylist.run(cast(Any, state), cast(Any, deps))

    def _fake_production_artifact(**_kwargs: Any) -> ProductionBuildResult:
        build_artifact = BuildArtifactPayload(
            game_slug="arena-pulse",
            game_name="Arena Pulse",
            game_genre="shooter",
            artifact_path="games/arena-pulse/index.html",
            artifact_html="<!doctype html><html><body><main><canvas id='game'></canvas><script>window.__iis_game_boot_ok=true;function restartGame(){}</script></main></body></html>",
        )
        return ProductionBuildResult(
            build_artifact=build_artifact,
            selected_generation_meta={"generation_source": "vertex"},
            metadata={
                "quality_floor_enforced": True,
                "quality_floor_passed": True,
                "playability_passed": True,
                "playability_score": 100,
            },
        )

    monkeypatch.setattr(builder, "build_production_artifact", _fake_production_artifact)
    result = builder.run(cast(Any, state), cast(Any, deps))
    assert result["status"] == PipelineStatus.RUNNING
    assert isinstance(result["outputs"].get("build_artifact"), dict)


def test_builder_contract_validator_blocks_weak_contracts_in_strict_mode() -> None:
    state = _base_state()
    vertex = _VertexStub(contract_mode="weak")
    deps = _deps(vertex)

    state = trigger.run(cast(Any, state), cast(Any, deps))
    state = architect.run(cast(Any, state), cast(Any, deps))
    state = stylist.run(cast(Any, state), cast(Any, deps))
    result = builder.run(cast(Any, state), cast(Any, deps))

    assert result["status"] == PipelineStatus.ERROR
    assert result["reason"] == "builder_contract_validation_failed"
    assert any(log.stage.value == "build" and log.status.value == "error" for log in result["logs"])


def test_builder_stops_when_quality_floor_unmet(monkeypatch) -> None:
    state = _base_state()
    vertex = _VertexStub(contract_mode="ok")
    deps = _deps(vertex)

    state = trigger.run(cast(Any, state), cast(Any, deps))
    state = architect.run(cast(Any, state), cast(Any, deps))
    state = stylist.run(cast(Any, state), cast(Any, deps))

    def _fake_production_artifact(**_kwargs: Any) -> ProductionBuildResult:
        build_artifact = BuildArtifactPayload(
            game_slug="arena-pulse",
            game_name="Arena Pulse",
            game_genre="shooter",
            artifact_path="games/arena-pulse/index.html",
            artifact_html="<!doctype html><html><body><main><canvas id='game'></canvas><script>window.__iis_game_boot_ok=true;</script></main></body></html>",
        )
        return ProductionBuildResult(
            build_artifact=build_artifact,
            selected_generation_meta={"generation_source": "stub"},
            metadata={
                "quality_floor_enforced": True,
                "quality_floor_passed": False,
                "quality_floor_score": 80,
                "quality_floor_fail_reasons": ["builder_quality_floor_unmet"],
                "final_builder_quality_score": 42,
                "final_placeholder_heavy": True,
            },
        )

    monkeypatch.setattr(builder, "build_production_artifact", _fake_production_artifact)
    result = builder.run(cast(Any, state), cast(Any, deps))
    assert result["status"] == PipelineStatus.ERROR
    assert result["reason"] == "builder_quality_floor_unmet"
    assert any(log.stage.value == "build" and log.status.value == "error" for log in result["logs"])


def test_builder_sets_retry_when_codegen_vertex_quota_is_exhausted(monkeypatch) -> None:
    state = _base_state()
    vertex = _VertexStub(contract_mode="ok")
    deps = _deps(vertex)

    state = trigger.run(cast(Any, state), cast(Any, deps))
    state = architect.run(cast(Any, state), cast(Any, deps))
    state = stylist.run(cast(Any, state), cast(Any, deps))

    def _retryable_production_artifact(**_kwargs: Any) -> ProductionBuildResult:
        build_artifact = BuildArtifactPayload(
            game_slug="arena-pulse",
            game_name="Arena Pulse",
            game_genre="shooter",
            artifact_path="games/arena-pulse/index.html",
            artifact_html="<!doctype html><html><body><main><canvas id='game'></canvas><script>window.__iis_game_boot_ok=true;</script></main></body></html>",
        )
        return ProductionBuildResult(
            build_artifact=build_artifact,
            selected_generation_meta={"generation_source": "stub"},
            metadata={
                "vertex_resource_exhausted_retryable": True,
                "codegen_generation_attempts": 1,
                "codegen_initial_reason": "vertex_error:ResourceExhausted",
                "codegen_initial_error": "429 RESOURCE_EXHAUSTED",
            },
        )

    monkeypatch.setattr(builder, "build_production_artifact", _retryable_production_artifact)
    result = builder.run(cast(Any, state), cast(Any, deps))

    assert result["status"] == PipelineStatus.RETRY
    assert result["reason"] == "build_vertex_resource_exhausted"
    retry_logs = [log for log in result["logs"] if log.stage.value == "build" and log.status.value == "retry"]
    assert retry_logs


def test_builder_stops_when_playability_hard_gate_unmet(monkeypatch) -> None:
    state = _base_state()
    vertex = _VertexStub(contract_mode="ok")
    vertex.settings.builder_playability_hard_gate = True
    deps = _deps(vertex)

    state = trigger.run(cast(Any, state), cast(Any, deps))
    state = architect.run(cast(Any, state), cast(Any, deps))
    state = stylist.run(cast(Any, state), cast(Any, deps))

    def _fake_production_artifact(**_kwargs: Any) -> ProductionBuildResult:
        build_artifact = BuildArtifactPayload(
            game_slug="arena-pulse",
            game_name="Arena Pulse",
            game_genre="shooter",
            artifact_path="games/arena-pulse/index.html",
            artifact_html="<!doctype html><html><body><main><canvas id='game'></canvas><script>window.__iis_game_boot_ok=true;</script></main></body></html>",
        )
        return ProductionBuildResult(
            build_artifact=build_artifact,
            selected_generation_meta={"generation_source": "stub"},
            metadata={
                "playability_passed": False,
                "playability_score": 36,
                "playability_fail_reasons": ["overlay_game_over_visible", "immediate_zero_hp_state"],
                "quality_floor_enforced": False,
                "quality_floor_passed": True,
            },
        )

    monkeypatch.setattr(builder, "build_production_artifact", _fake_production_artifact)
    result = builder.run(cast(Any, state), cast(Any, deps))
    assert result["status"] == PipelineStatus.ERROR
    assert result["reason"] == "builder_playability_unmet"
    assert any(log.stage.value == "build" and log.status.value == "error" for log in result["logs"])


def test_builder_handles_intent_contract_validation_error(monkeypatch) -> None:
    state = _base_state()
    vertex = _VertexStub(contract_mode="ok")
    deps = _deps(vertex)

    state = trigger.run(cast(Any, state), cast(Any, deps))
    state = architect.run(cast(Any, state), cast(Any, deps))
    state = stylist.run(cast(Any, state), cast(Any, deps))

    def _invalid_intent_contract(**_kwargs: Any):
        return IntentContractPayload.model_validate({})

    monkeypatch.setattr(builder, "build_intent_contract", _invalid_intent_contract)
    result = builder.run(cast(Any, state), cast(Any, deps))

    assert result["status"] == PipelineStatus.ERROR
    assert result["reason"] == "intent_contract_invalid"
    build_error_logs = [log for log in result["logs"] if log.stage.value == "build" and log.status.value == "error"]
    assert build_error_logs
    assert "validation_error" in build_error_logs[-1].metadata


def test_trigger_blocks_when_strict_vertex_only_and_source_is_stub() -> None:
    state = _base_state()
    deps = _deps(_VertexStub(strict_vertex_only=True))

    result = trigger.run(cast(Any, state), cast(Any, deps))

    assert result["status"] == PipelineStatus.ERROR
    assert result["reason"] == "analyze_contract_unavailable"


def test_architect_sets_retry_when_vertex_resource_exhausted() -> None:
    state = _base_state()
    deps = _deps(_VertexStub(contract_mode="ok", strict_vertex_only=False))

    state = trigger.run(cast(Any, state), cast(Any, deps))
    deps.vertex_service.settings.strict_vertex_only = True

    def _resource_exhausted_gdd_bundle(_keyword: str) -> VertexGenerationResult:
        return VertexGenerationResult(
            payload={"gdd": {}, "research_summary": {}},
            meta={
                "generation_source": "stub",
                "reason": "vertex_error:ResourceExhausted",
                "vertex_error": "429 RESOURCE_EXHAUSTED",
            },
        )

    deps.vertex_service.generate_gdd_bundle = _resource_exhausted_gdd_bundle
    result = architect.run(cast(Any, state), cast(Any, deps))

    assert result["status"] == PipelineStatus.RETRY
    assert result["reason"] == "gdd_unavailable_vertex_resource_exhausted"
    plan_logs = [log for log in result["logs"] if log.stage.value == "plan"]
    assert plan_logs
    assert plan_logs[-1].status == PipelineStatus.RETRY


def test_architect_plan_invalid_logs_validation_error_details() -> None:
    state = _base_state()
    deps = _deps(_VertexStub(contract_mode="invalid"))

    state = trigger.run(cast(Any, state), cast(Any, deps))
    result = architect.run(cast(Any, state), cast(Any, deps))

    assert result["status"] == PipelineStatus.ERROR
    assert result["reason"] == "plan_contract_invalid"
    plan_error_logs = [log for log in result["logs"] if log.stage.value == "plan" and log.status.value == "error"]
    assert plan_error_logs
    assert "validation_error" in plan_error_logs[-1].metadata
