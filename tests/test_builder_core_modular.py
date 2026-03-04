from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from app.orchestration.nodes.builder_core import build_modular_artifact
from app.orchestration.nodes.builder_parts.production_pipeline import build_production_artifact
from app.schemas.payloads import DesignSpecPayload, GDDPayload
from app.schemas.pipeline import PipelineStatus
from app.services.quality_types import GameplayGateResult, QualityGateResult, SmokeCheckResult


def _state() -> Any:
    return {
        "pipeline_id": uuid4(),
        "keyword": "풀3d 격투 게임",
        "qa_attempt": 0,
        "max_qa_loops": 3,
        "fail_qa_until": 0,
        "build_iteration": 1,
        "needs_rebuild": False,
        "status": PipelineStatus.RUNNING,
        "reason": None,
        "logs": [],
        "flushed_log_count": 0,
        "log_sink": None,
        "outputs": {
            "analyze_contract": {"scope_in": ["runtime", "artifact"], "hard_constraints": ["boot"]},
            "plan_contract": {"core_mechanics": ["movement", "attack"], "progression_plan": ["wave"]},
            "design_contract": {"scene_layers": ["fg", "mg", "bg"], "asset_blueprint_2d3d": ["player", "enemy"]},
        },
    }


class _QualityService:
    def evaluate_quality_contract(self, html: str, *, design_spec=None):
        return QualityGateResult(ok=True, score=88, threshold=70, failed_checks=[], checks={"ok": True})

    def evaluate_gameplay_gate(self, html: str, *, design_spec=None, genre=None, genre_engine=None, keyword=None):
        return GameplayGateResult(ok=True, score=86, threshold=70, failed_checks=[], checks={"ok": True})

    def run_smoke_check(self, html: str, **_kwargs):
        return SmokeCheckResult(ok=True, reason="smoke_ok", non_fatal_warnings=[])


class _VertexServiceWithCodegen:
    def __init__(self) -> None:
        self.settings = SimpleNamespace(
            rqc_version="rqc-1",
            builder_codegen_enabled=True,
            builder_codegen_passes=1,
            builder_codegen_recovery_enabled=False,
            strict_vertex_only=True,
            allow_stub_fallback=False,
        )
        self.calls = 0

    def generate_codegen_candidate_artifact(
        self,
        *,
        keyword: str,
        title: str,
        genre: str,
        objective: str,
        core_loop_type: str,
        runtime_engine_mode: str,
        variation_hint: str,
        design_spec: dict[str, Any],
        asset_pack: dict[str, Any],
        intent_contract: dict[str, Any] | None,
        synapse_contract: dict[str, Any] | None,
        shared_generation_contract: dict[str, Any] | None,
        html_content: str,
    ) -> Any:
        _ = (intent_contract, synapse_contract, shared_generation_contract)
        self.calls += 1
        refined_html = f"{html_content}\n<!-- codegen-refined -->"
        return SimpleNamespace(
            payload={"artifact_html": refined_html},
            meta={"generation_source": "vertex", "model": "stub-model", "reason": "test"},
        )


def test_build_modular_artifact_produces_rqc_ready_runtime() -> None:
    result = build_modular_artifact(
        keyword="풀3d 격투 게임",
        title="Arena Clash",
        genre="action",
        slug="arena-clash",
        accent_color="#22C55E",
        viewport_width=1280,
        viewport_height=720,
        safe_area_padding=24,
        text_overflow_policy="ellipsis-clamp",
        core_loop_type="comic_action_brawler_3d",
        analyze_contract={"scope_in": ["runtime"]},
        plan_contract={"core_mechanics": ["movement", "combat"]},
        design_contract={"scene_layers": ["fg", "mg", "bg"]},
        rqc_version="rqc-1",
    )
    assert "new THREE.WebGLRenderer" in result.artifact_html
    assert result.selfcheck_result["passed"] is True
    assert result.module_signature
    assert result.module_plan["primary_modules"]


def test_build_modular_artifact_resolves_vehicle_capability_for_korean_car_prompt() -> None:
    result = build_modular_artifact(
        keyword="자동차 조종 시뮬레이터",
        title="AeroFront: Flight Simulator",
        genre="arcade",
        slug="car-sim",
        accent_color="#38BDF8",
        viewport_width=1280,
        viewport_height=720,
        safe_area_padding=20,
        text_overflow_policy="ellipsis-clamp",
        core_loop_type="arcade",
        rqc_version="rqc-1",
    )
    assert result.capability_profile["locomotion_model"] == "vehicle"
    assert result.capability_profile["interaction_model"] == "navigation"
    assert result.capability_profile["camera_model"] == "chase"
    assert "조향:" in result.artifact_html
    assert "피치" not in result.artifact_html


def test_build_modular_artifact_resolves_vehicle_capability_for_compact_korean_prompt() -> None:
    result = build_modular_artifact(
        keyword="자동차조종시뮬레이터",
        title="자동차조종시뮬레이터 Infinite",
        genre="arcade",
        slug="car-sim-compact",
        accent_color="#38BDF8",
        viewport_width=1280,
        viewport_height=720,
        safe_area_padding=20,
        text_overflow_policy="ellipsis-clamp",
        core_loop_type="arcade",
        rqc_version="rqc-1",
    )
    assert result.capability_profile["locomotion_model"] == "vehicle"
    assert result.capability_profile["interaction_model"] == "navigation"


def test_build_modular_artifact_defaults_to_3d_render_for_generic_prompt() -> None:
    result = build_modular_artifact(
        keyword="게임 만들어줘",
        title="Generic Quest",
        genre="arcade",
        slug="generic-quest",
        accent_color="#38BDF8",
        viewport_width=1280,
        viewport_height=720,
        safe_area_padding=20,
        text_overflow_policy="ellipsis-clamp",
        core_loop_type="arcade",
        rqc_version="rqc-1",
    )
    assert "render:3d" in result.capability_profile["capability_tags"]


def test_build_modular_artifact_enforces_phaser_for_explicit_2d_prompt() -> None:
    result = build_modular_artifact(
        keyword="2d 픽셀 로그라이크 액션 게임",
        title="Pixel Frontier",
        genre="arcade",
        slug="pixel-frontier",
        accent_color="#F59E0B",
        viewport_width=1280,
        viewport_height=720,
        safe_area_padding=20,
        text_overflow_policy="ellipsis-clamp",
        core_loop_type="topdown_roguelike_shooter",
        rqc_version="rqc-1",
    )
    assert "render:2d" in result.capability_profile["capability_tags"]
    assert "new Phaser.Game" in result.artifact_html
    assert "new THREE.WebGLRenderer" not in result.artifact_html
    assert result.selfcheck_result["passed"] is True


def test_build_modular_artifact_uses_readable_objective_and_hides_slug_like_genre() -> None:
    result = build_modular_artifact(
        keyword="오토바이 서킷 레이싱",
        title="Apex Rider: Moto Simulator",
        genre="motorcycle-circuit-sim",
        slug="apex-rider-moto-sim",
        accent_color="#38BDF8",
        viewport_width=1280,
        viewport_height=720,
        safe_area_padding=20,
        text_overflow_policy="ellipsis-clamp",
        core_loop_type="lane_dodge_racer",
        rqc_version="rqc-1",
    )
    assert "목표: directional movement + timing" not in result.artifact_html
    assert '<div class="subtitle">3D 레이싱 주행</div>' in result.artifact_html
    assert result.selfcheck_result["checks"]["objective_text_quality"] is True
    assert result.selfcheck_result["checks"]["subtitle_no_slug_noise"] is True


def test_build_production_artifact_uses_scaffold_single_pass_engine() -> None:
    vertex_service = _VertexServiceWithCodegen()
    deps = SimpleNamespace(
        vertex_service=vertex_service,
        quality_service=_QualityService(),
    )
    result = build_production_artifact(
        state=_state(),
        deps=deps,
        gdd=GDDPayload(title="Arena Clash", genre="action", objective="survive", visual_style="neon"),
        design_spec=DesignSpecPayload(
            visual_style="neon",
            palette=["#22C55E"],
            hud="score/time/hp",
            viewport_width=1280,
            viewport_height=720,
            safe_area_padding=24,
            min_font_size_px=14,
            text_overflow_policy="ellipsis-clamp",
        ),
        title="Arena Clash",
        genre="action",
        slug="arena-clash",
        accent_color="#22C55E",
        core_loop_type="comic_action_brawler_3d",
        runtime_engine_mode="3d_three",
        asset_pack={"name": "modular-pack"},
        asset_bank_files=[],
        runtime_asset_manifest={},
    )
    assert result.metadata["builder_strategy"] == "scaffold_first_codegen_v3"
    assert result.metadata["generation_engine_version"] == "scaffold_v3"
    assert result.metadata["effective_codegen_passes_per_candidate"] == 1
    assert vertex_service.calls == 1
    assert result.build_artifact.artifact_manifest is not None
    assert result.build_artifact.artifact_manifest["bundle_kind"] in {"hybrid_engine"}


def test_build_production_artifact_runs_single_codegen_pass() -> None:
    vertex_service = _VertexServiceWithCodegen()
    deps = SimpleNamespace(
        vertex_service=vertex_service,
        quality_service=_QualityService(),
    )
    result = build_production_artifact(
        state=_state(),
        deps=deps,
        gdd=GDDPayload(title="Arena Clash", genre="action", objective="survive", visual_style="neon"),
        design_spec=DesignSpecPayload(
            visual_style="neon",
            palette=["#22C55E"],
            hud="score/time/hp",
            viewport_width=1280,
            viewport_height=720,
            safe_area_padding=24,
            min_font_size_px=14,
            text_overflow_policy="ellipsis-clamp",
        ),
        title="Arena Clash",
        genre="action",
        slug="arena-clash",
        accent_color="#22C55E",
        core_loop_type="comic_action_brawler_3d",
        runtime_engine_mode="3d_three",
        asset_pack={"name": "modular-pack"},
        asset_bank_files=[],
        runtime_asset_manifest={},
    )
    assert vertex_service.calls == 1
    assert result.metadata["effective_codegen_passes_per_candidate"] == 1
    assert result.selected_generation_meta["generation_source"] == "vertex"
    assert "<!-- codegen-refined -->" in result.build_artifact.artifact_html
