from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from app.orchestration.nodes.builder_parts.production_pipeline import build_production_artifact
from app.schemas.payloads import DesignSpecPayload, GDDPayload
from app.schemas.pipeline import PipelineStatus
from app.services.quality_types import GameplayGateResult, QualityGateResult, SmokeCheckResult


def _make_state() -> Any:
    return {
        "pipeline_id": uuid4(),
        "keyword": "neon racer",
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
        "outputs": {},
    }


@dataclass
class _FakeVertexService:
    generation_source: str = "vertex"
    generated_suffix: str = "CODEGEN"
    generation_sequence: tuple[str, ...] = ()
    validation_failures: tuple[str, ...] = ()
    stub_reason: str = "vertex_not_configured"

    def __post_init__(self) -> None:
        self.calls = 0
        self.settings = SimpleNamespace(
            builder_codegen_enabled=True,
            builder_quality_floor_enforced=True,
            builder_quality_floor_score=82,
        )

    def generate_codegen_candidate_artifact(self, *, html_content: str, **_kwargs):
        self.calls += 1
        if self.generation_sequence and self.calls <= len(self.generation_sequence):
            source = self.generation_sequence[self.calls - 1]
        else:
            source = self.generation_source
        artifact_html = f"{html_content}\n<!-- {self.generated_suffix} -->"
        if source != "vertex":
            artifact_html = ""
        meta: dict[str, Any] = {
            "generation_source": source,
            "model": "gemini-test",
            "reason": "test",
        }
        if source != "vertex":
            meta["reason"] = self.stub_reason
            meta["vertex_error"] = "invalid_codegen_artifact:" + ",".join(self.validation_failures or ("unknown",))
            meta["validation_failures"] = list(self.validation_failures)
        return SimpleNamespace(
            payload={"artifact_html": artifact_html},
            meta=meta,
        )

    def generate_game_config(self, **_kwargs):
        return SimpleNamespace(
            payload={
                "player_hp": 3,
                "player_speed": 240,
                "player_attack_cooldown": 0.5,
                "enemy_hp": 1,
                "enemy_speed_min": 100,
                "enemy_speed_max": 220,
                "enemy_spawn_rate": 1.0,
                "time_limit_sec": 60,
                "base_score_value": 10,
            },
            meta={"generation_source": "stub", "reason": "config_test_fallback"},
        )


class _FakeQualityService:
    def __init__(
        self,
        *,
        quality_ok: bool = True,
        gameplay_ok: bool = True,
        visual_ok: bool = True,
        smoke_ok: bool = True,
    ) -> None:
        self.quality_ok = quality_ok
        self.gameplay_ok = gameplay_ok
        self.visual_ok = visual_ok
        self.smoke_ok = smoke_ok

    def evaluate_quality_contract(self, html: str, *, design_spec=None, **_kwargs):
        score = 90 if self.quality_ok else 40
        return QualityGateResult(
            ok=self.quality_ok,
            score=score,
            threshold=75,
            failed_checks=[] if self.quality_ok else ["quality_contract_low"],
            checks={"quality": self.quality_ok},
        )

    def evaluate_gameplay_gate(self, html: str, *, design_spec=None, genre=None, genre_engine=None, keyword=None):
        score = 88 if self.gameplay_ok else 44
        return GameplayGateResult(
            ok=self.gameplay_ok,
            score=score,
            threshold=55,
            failed_checks=[] if self.gameplay_ok else ["gameplay_depth_low"],
            checks={"gameplay": self.gameplay_ok},
        )

    def run_smoke_check(self, html: str, **_kwargs):
        if self.smoke_ok:
            return SmokeCheckResult(ok=True, reason="smoke_ok", non_fatal_warnings=[])
        return SmokeCheckResult(ok=False, reason="runtime_console_error", fatal_errors=["ReferenceError: broken"])

    def evaluate_visual_gate(self, visual_metrics, *, genre_engine=None):
        score = 80 if self.visual_ok else 30
        return QualityGateResult(
            ok=self.visual_ok,
            score=score,
            threshold=45,
            failed_checks=[] if self.visual_ok else ["visual_quality_low"],
            checks={"visual": self.visual_ok},
        )


def _build_result(*, vertex_source: str = "vertex", quality_service: _FakeQualityService | None = None):
    deps: Any = SimpleNamespace(
        vertex_service=_FakeVertexService(generation_source=vertex_source),
        quality_service=quality_service or _FakeQualityService(),
    )
    result = build_production_artifact(
        state=_make_state(),
        deps=deps,
        gdd=GDDPayload(title="Neon Racer", genre="arcade", objective="survive", visual_style="neon"),
        design_spec=DesignSpecPayload(
            visual_style="neon",
            palette=["#22C55E", "#111827"],
            hud="score-top-left",
            viewport_width=1280,
            viewport_height=720,
            safe_area_padding=24,
            min_font_size_px=14,
            text_overflow_policy="ellipsis-clamp",
        ),
        title="Neon Racer",
        genre="arcade",
        slug="neon-racer",
        accent_color="#22C55E",
        core_loop_type="arcade_generic",
        runtime_engine_mode="3d_three",
        asset_pack={"name": "arcade-pack"},
        asset_bank_files=[],
        runtime_asset_manifest={},
    )
    return result, deps


def _build_result_with_vertex(vertex_service: _FakeVertexService, *, quality_service: _FakeQualityService | None = None):
    deps: Any = SimpleNamespace(
        vertex_service=vertex_service,
        quality_service=quality_service or _FakeQualityService(),
    )
    result = build_production_artifact(
        state=_make_state(),
        deps=deps,
        gdd=GDDPayload(title="Neon Racer", genre="arcade", objective="survive", visual_style="neon"),
        design_spec=DesignSpecPayload(
            visual_style="neon",
            palette=["#22C55E", "#111827"],
            hud="score-top-left",
            viewport_width=1280,
            viewport_height=720,
            safe_area_padding=24,
            min_font_size_px=14,
            text_overflow_policy="ellipsis-clamp",
        ),
        title="Neon Racer",
        genre="arcade",
        slug="neon-racer",
        accent_color="#22C55E",
        core_loop_type="arcade_generic",
        runtime_engine_mode="3d_three",
        asset_pack={"name": "arcade-pack"},
        asset_bank_files=[],
        runtime_asset_manifest={},
    )
    return result, deps


def test_build_production_artifact_uses_scaffold_v3_single_pass() -> None:
    result, deps = _build_result()
    assert deps.vertex_service.calls == 1
    assert result.metadata["builder_strategy"] == "scaffold_first_codegen_v3"
    assert result.metadata["generation_engine_version"] == "scaffold_v3"
    assert result.metadata["effective_codegen_passes_per_candidate"] == 1
    assert result.metadata["quality_floor_passed"] is True
    assert "quality_gate_report" in result.metadata
    assert "<!-- CODEGEN -->" in result.build_artifact.artifact_html


def test_build_production_artifact_blocks_when_codegen_unavailable() -> None:
    result, _ = _build_result(vertex_source="stub")
    assert result.metadata["quality_floor_passed"] is False
    assert "codegen_generation_failed" in result.metadata["quality_floor_fail_reasons"]
    assert "codegen_recovery_failed" in result.metadata["quality_floor_fail_reasons"]
    assert "codegen_generation_failed" in result.metadata["blocking_reasons"]


def test_build_production_artifact_blocks_when_gameplay_gate_fails() -> None:
    result, _ = _build_result(quality_service=_FakeQualityService(gameplay_ok=False))
    assert result.metadata["quality_floor_passed"] is False
    assert "gameplay_gate_unmet" in result.metadata["quality_floor_fail_reasons"]


def test_build_production_artifact_blocks_when_runtime_smoke_fails() -> None:
    result, _ = _build_result(quality_service=_FakeQualityService(smoke_ok=False))
    assert result.metadata["playability_passed"] is False
    assert result.metadata["quality_floor_passed"] is False
    assert "runtime_smoke_failed" in result.metadata["quality_floor_fail_reasons"]


def test_build_production_artifact_runs_single_recovery_attempt_when_codegen_fails() -> None:
    vertex = _FakeVertexService(
        generation_sequence=("stub", "vertex"),
        stub_reason="vertex_error:ValueError",
        validation_failures=("boot_flag", "canvas_or_render_runtime"),
    )
    result, deps = _build_result_with_vertex(vertex)
    assert deps.vertex_service.calls == 2
    assert result.metadata["codegen_generation_attempts"] == 2
    assert result.metadata["codegen_recovery_attempted"] is True
    assert result.metadata["codegen_recovery_success"] is True
    assert result.metadata["quality_floor_passed"] is True


def test_build_production_artifact_uses_deterministic_fallback_on_codegen_value_error() -> None:
    vertex = _FakeVertexService(
        generation_sequence=("stub", "stub"),
        stub_reason="vertex_error:ValueError",
        validation_failures=("boot_flag", "leaderboard_contract"),
    )
    result, deps = _build_result_with_vertex(vertex)
    assert deps.vertex_service.calls == 2
    assert result.metadata["codegen_recovery_attempted"] is True
    assert result.metadata["codegen_recovery_success"] is False
    assert result.metadata["deterministic_fallback_used"] is True
    assert result.metadata["quality_floor_passed"] is True
    assert result.selected_generation_meta["generation_source"] == "deterministic_fallback"
