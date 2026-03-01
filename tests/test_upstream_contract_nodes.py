from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.orchestration.nodes import architect, builder, stylist, trigger
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
    def __init__(self, *, contract_mode: str = "ok", enforcement: str = "warn_only") -> None:
        self._contract_mode = contract_mode
        self.settings = SimpleNamespace(
            builder_scope_guard_enabled=False,
            builder_asset_memory_enabled=False,
            pipeline_contract_enforcement=enforcement,
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
        if self._contract_mode == "weak":
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
    assert any(log.stage.value == "analyze" for log in state["logs"])
    assert any(log.stage.value == "plan" for log in state["logs"])
    assert any(log.stage.value == "design" for log in state["logs"])


def test_builder_contract_validator_blocks_weak_contracts_in_strict_mode() -> None:
    state = _base_state()
    vertex = _VertexStub(contract_mode="weak", enforcement="strict")
    deps = _deps(vertex)

    state = trigger.run(cast(Any, state), cast(Any, deps))
    state = architect.run(cast(Any, state), cast(Any, deps))
    state = stylist.run(cast(Any, state), cast(Any, deps))
    result = builder.run(cast(Any, state), cast(Any, deps))

    assert result["status"] == PipelineStatus.ERROR
    assert result["reason"] == "builder_contract_validation_failed"
    assert any(log.stage.value == "build" and log.status.value == "error" for log in result["logs"])
