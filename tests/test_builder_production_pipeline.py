from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from app.orchestration.nodes.builder_parts import production_pipeline
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
    builder_candidate_count: int = 1
    builder_codegen_passes: int = 1
    builder_codegen_enabled: bool = True
    polished_suffix: str = "POLISHED"

    def __post_init__(self) -> None:
        self.generate_variation_hints: list[str] = []
        self.codegen_inputs: list[str] = []
        self.settings = SimpleNamespace(
            builder_candidate_count=self.builder_candidate_count,
            builder_codegen_passes=self.builder_codegen_passes,
            builder_codegen_enabled=self.builder_codegen_enabled,
        )

    def generate_game_config(self, **_kwargs):
        self.generate_variation_hints.append(str(_kwargs.get("variation_hint", "")))
        return SimpleNamespace(payload={"difficulty": "normal"}, meta={"generation_source": "stub"})

    def generate_codegen_candidate_artifact(self, *, html_content: str, **_kwargs):
        self.codegen_inputs.append(html_content)
        return SimpleNamespace(
            payload={"artifact_html": f"{html_content}\n<!-- CODEGEN -->"},
            meta={"generation_source": "vertex", "model": "gemini-test"},
        )

    def polish_hybrid_artifact(self, *, html_content: str, **_kwargs):
        return SimpleNamespace(
            payload={"artifact_html": f"{html_content}\n<!-- {self.polished_suffix} -->"},
            meta={"generation_source": "vertex", "model": "gemini-test"},
        )


class _FakeQualityService:
    def __init__(self, *, smoke_ok: bool):
        self._smoke_ok = smoke_ok

    def evaluate_quality_contract(self, html: str, *, design_spec=None):
        score = 86 if "POLISHED" in html else 80
        return QualityGateResult(ok=True, score=score, threshold=75, failed_checks=[], checks={"quality": True})

    def evaluate_gameplay_gate(self, html: str, *, design_spec=None, genre=None, genre_engine=None, keyword=None):
        score = 84 if "POLISHED" in html else 79
        return GameplayGateResult(ok=True, score=score, threshold=55, failed_checks=[], checks={"gameplay": True})

    def run_smoke_check(self, html: str, **_kwargs):
        if self._smoke_ok:
            return SmokeCheckResult(ok=True, reason="smoke_ok")
        return SmokeCheckResult(ok=False, reason=f"smoke_failed:{'POLISHED' if 'POLISHED' in html else 'BASE'}")


class _LowQualityService(_FakeQualityService):
    def evaluate_quality_contract(self, html: str, *, design_spec=None):
        return QualityGateResult(ok=False, score=28, threshold=75, failed_checks=["quality_contract_low"], checks={"quality": False})

    def evaluate_gameplay_gate(self, html: str, *, design_spec=None, genre=None, genre_engine=None, keyword=None):
        return GameplayGateResult(ok=False, score=32, threshold=55, failed_checks=["gameplay_depth_low"], checks={"gameplay": False})


def _patch_runtime_builders(monkeypatch) -> None:
    def _build_hybrid_engine_html(**_kwargs) -> str:
        return "<!doctype html><html><body>BASELINE LOOP RUNTIME HTML PAYLOAD FOR TESTS</body></html>"

    def _extract_hybrid_bundle_from_inline_html(*, slug: str, inline_html: str, asset_bank_files=None, runtime_asset_manifest=None):
        return (
            [
                {
                    "path": f"games/{slug}/index.html",
                    "content": inline_html,
                    "content_type": "text/html; charset=utf-8",
                }
            ],
            {"schema_version": 1, "bundle_kind": "hybrid_engine"},
        )

    monkeypatch.setattr(production_pipeline, "_build_hybrid_engine_html", _build_hybrid_engine_html)
    monkeypatch.setattr(production_pipeline, "_extract_hybrid_bundle_from_inline_html", _extract_hybrid_bundle_from_inline_html)


def test_build_production_artifact_prefers_polished_candidate_when_smoke_passes(monkeypatch) -> None:
    _patch_runtime_builders(monkeypatch)

    deps: Any = SimpleNamespace(
        vertex_service=_FakeVertexService(polished_suffix="POLISHED"),
        quality_service=_FakeQualityService(smoke_ok=True),
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
        asset_pack={"name": "arcade-pack"},
        asset_bank_files=[],
        runtime_asset_manifest={},
    )

    assert "<!-- POLISHED -->" in result.build_artifact.artifact_html
    assert result.metadata["candidate_count"] == 1
    assert result.metadata["selected_candidate_index"] == 1
    runtime_guard = result.metadata["runtime_guard"]
    assert isinstance(runtime_guard, dict)
    assert runtime_guard.get("chosen") == "polished"
    assert result.build_artifact.artifact_manifest is not None
    assert result.build_artifact.artifact_manifest.get("genre_engine") == "arcade_generic"
    assert result.build_artifact.artifact_manifest.get("asset_pack") == "arcade-pack"


def test_build_production_artifact_forces_baseline_when_smoke_fails(monkeypatch) -> None:
    _patch_runtime_builders(monkeypatch)

    deps: Any = SimpleNamespace(
        vertex_service=_FakeVertexService(polished_suffix="POLISHED"),
        quality_service=_FakeQualityService(smoke_ok=False),
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
        asset_pack={"name": "arcade-pack"},
        asset_bank_files=[],
        runtime_asset_manifest={},
    )

    assert "<!-- POLISHED -->" not in result.build_artifact.artifact_html
    assert "<!-- CODEGEN -->" not in result.build_artifact.artifact_html
    runtime_guard = result.metadata["runtime_guard"]
    assert isinstance(runtime_guard, dict)
    assert runtime_guard.get("chosen") == "baseline_force"


def test_build_production_artifact_enforces_single_candidate_even_when_configured_higher(monkeypatch) -> None:
    _patch_runtime_builders(monkeypatch)

    deps: Any = SimpleNamespace(
        vertex_service=_FakeVertexService(builder_candidate_count=4, polished_suffix="POLISHED"),
        quality_service=_FakeQualityService(smoke_ok=True),
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
        asset_pack={"name": "arcade-pack"},
        asset_bank_files=[],
        runtime_asset_manifest={},
    )

    assert result.metadata["configured_candidate_count"] == 4
    assert result.metadata["candidate_count"] == 1


def test_build_production_artifact_applies_visual_feedback_hint(monkeypatch) -> None:
    _patch_runtime_builders(monkeypatch)

    vertex = _FakeVertexService(polished_suffix="POLISHED")
    deps: Any = SimpleNamespace(
        vertex_service=vertex,
        quality_service=_FakeQualityService(smoke_ok=True),
    )
    state = _make_state()
    state["outputs"]["qa_visual_feedback"] = {
        "failed_checks": ["contrast", "color_diversity"],
    }
    result = build_production_artifact(
        state=state,
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
        asset_pack={"name": "arcade-pack"},
        asset_bank_files=[],
        runtime_asset_manifest={},
    )

    assert result.metadata["candidate_count"] == 1
    assert vertex.generate_variation_hints
    assert "Prior QA visual issues" in vertex.generate_variation_hints[0]
    assert "contrast" in vertex.generate_variation_hints[0]
    assert "color_diversity" in vertex.generate_variation_hints[0]


def test_build_production_artifact_applies_rebuild_feedback_hint(monkeypatch) -> None:
    _patch_runtime_builders(monkeypatch)

    vertex = _FakeVertexService(polished_suffix="POLISHED")
    deps: Any = SimpleNamespace(
        vertex_service=vertex,
        quality_service=_FakeQualityService(smoke_ok=True),
    )
    state = _make_state()
    state["outputs"]["qa_rebuild_feedback"] = {
        "gate": "runtime",
        "reason": "runtime_console_error",
        "fatal_errors": ["immediate_game_over_overlay"],
        "failed_checks": [],
        "non_fatal_warnings": [],
    }
    result = build_production_artifact(
        state=state,
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
        asset_pack={"name": "arcade-pack"},
        asset_bank_files=[],
        runtime_asset_manifest={},
    )

    assert result.metadata["candidate_count"] == 1
    assert result.metadata["rebuild_feedback_hint_applied"] is True
    assert "immediate_game_over_overlay" in result.metadata["rebuild_feedback_tokens"]
    assert vertex.generate_variation_hints
    assert "Prior QA runtime failure detected" in vertex.generate_variation_hints[0]
    assert "immediate_game_over_overlay" in vertex.generate_variation_hints[0]
    assert result.metadata["effective_codegen_passes_per_candidate"] == 2


def test_build_production_artifact_reuses_previous_artifact_when_refining(monkeypatch) -> None:
    _patch_runtime_builders(monkeypatch)

    vertex = _FakeVertexService(polished_suffix="POLISHED")
    deps: Any = SimpleNamespace(
        vertex_service=vertex,
        quality_service=_FakeQualityService(smoke_ok=True),
    )
    state = _make_state()
    state["build_iteration"] = 2
    state["outputs"]["artifact_html"] = "<html><body>PREVIOUS_ARTIFACT_SEED</body></html>"
    state["outputs"]["qa_rebuild_feedback"] = {
        "gate": "gameplay",
        "reason": "gameplay_depth_below_threshold",
        "fatal_errors": [],
        "failed_checks": ["missing_realtime_loop"],
        "non_fatal_warnings": [],
    }

    result = build_production_artifact(
        state=state,
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
        asset_pack={"name": "arcade-pack"},
        asset_bank_files=[],
        runtime_asset_manifest={},
    )

    assert result.metadata["reuse_previous_artifact_seed"] is True
    assert result.metadata["effective_codegen_passes_per_candidate"] == 2
    assert vertex.codegen_inputs
    assert "PREVIOUS_ARTIFACT_SEED" in vertex.codegen_inputs[0]
    scoreboard = result.metadata["candidate_scoreboard"]
    assert isinstance(scoreboard, list)
    assert scoreboard and scoreboard[0]["codegen_passes"][0]["reason"] == "feedback_refinement_seed"


def test_build_production_artifact_applies_asset_memory_hint(monkeypatch) -> None:
    _patch_runtime_builders(monkeypatch)

    vertex = _FakeVertexService(polished_suffix="POLISHED")
    deps: Any = SimpleNamespace(
        vertex_service=vertex,
        quality_service=_FakeQualityService(smoke_ok=True),
    )
    state = _make_state()
    result = build_production_artifact(
        state=state,
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
        asset_pack={"name": "arcade-pack"},
        asset_bank_files=[],
        runtime_asset_manifest={},
        memory_hint="Reuse proven asset pack arcade-pack. Avoid recurrent QA failures: visual_quality_below_threshold.",
        memory_tokens=["visual_quality_below_threshold", "contrast"],
    )

    assert result.metadata["memory_hint_applied"] is True
    assert "visual_quality_below_threshold" in result.metadata["memory_tokens"]
    assert vertex.generate_variation_hints
    assert "Reuse proven asset pack arcade-pack." in vertex.generate_variation_hints[0]


def test_build_production_artifact_records_builder_refinement_attempts(monkeypatch) -> None:
    _patch_runtime_builders(monkeypatch)

    vertex = _FakeVertexService(polished_suffix="POLISHED")
    vertex.settings.builder_refinement_rounds = 2
    vertex.settings.builder_refinement_target_score = 90
    deps: Any = SimpleNamespace(
        vertex_service=vertex,
        quality_service=_FakeQualityService(smoke_ok=True),
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
        asset_pack={"name": "arcade-pack"},
        asset_bank_files=[],
        runtime_asset_manifest={},
    )

    assert result.metadata["refinement_rounds_executed"] == 2
    runtime_guard = result.metadata["runtime_guard"]
    assert isinstance(runtime_guard, dict)
    refinement_rows = runtime_guard.get("refinement")
    assert isinstance(refinement_rows, list)
    assert len(refinement_rows) == 2
    scoreboard = result.metadata["candidate_scoreboard"]
    assert isinstance(scoreboard, list)
    assert scoreboard and "builder_quality_score" in scoreboard[0]


def test_build_production_artifact_reports_quality_floor_fail_metadata(monkeypatch) -> None:
    _patch_runtime_builders(monkeypatch)

    vertex = _FakeVertexService(polished_suffix="POLISHED")
    vertex.settings.builder_quality_floor_enforced = True
    vertex.settings.builder_quality_floor_score = 92
    deps: Any = SimpleNamespace(
        vertex_service=vertex,
        quality_service=_LowQualityService(smoke_ok=True),
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
        asset_pack={"name": "arcade-pack"},
        asset_bank_files=[],
        runtime_asset_manifest={},
    )

    assert result.metadata["quality_floor_enforced"] is True
    assert result.metadata["quality_floor_passed"] is False
    assert "builder_quality_floor_unmet" in result.metadata["quality_floor_fail_reasons"]
