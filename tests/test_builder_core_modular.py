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
    assert "getContext(\"webgl\"" in result.artifact_html
    assert result.selfcheck_result["passed"] is True
    assert result.module_signature
    assert result.module_plan["primary_modules"]


def test_build_production_artifact_uses_modular_core_when_enabled() -> None:
    deps = SimpleNamespace(
        vertex_service=SimpleNamespace(
            settings=SimpleNamespace(
                gen_core_mode="modular",
                rqc_version="rqc-1",
            )
        ),
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
        asset_pack={"name": "modular-pack"},
        asset_bank_files=[],
        runtime_asset_manifest={},
    )
    assert result.metadata["builder_strategy"] == "builder_core_modular_v1"
    assert result.metadata["rebuild_source"] == "builder_core"
    assert result.metadata["rqc_passed"] is True
    assert result.metadata["module_signature"]
    assert result.build_artifact.artifact_manifest is not None
    assert result.build_artifact.artifact_manifest["bundle_kind"] in {"modular_builder_core", "hybrid_engine"}
