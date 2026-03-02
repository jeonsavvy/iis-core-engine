from app.orchestration.nodes.builder_parts.production_pipeline import _evaluate_playability_gate
from app.services.quality_types import SmokeCheckResult


def test_playability_gate_fails_on_runtime_warning_codes() -> None:
    result = _evaluate_playability_gate(
        smoke=SmokeCheckResult(
            ok=True,
            reason="smoke_ok",
            non_fatal_warnings=["overlay_game_over_visible", "runtime_layout_scroll_overflow"],
        )
    )
    assert result.ok is False
    assert "overlay_game_over_visible" in result.fail_reasons
    assert result.score < 100


def test_playability_gate_passes_when_runtime_is_clean() -> None:
    result = _evaluate_playability_gate(
        smoke=SmokeCheckResult(
            ok=True,
            reason="smoke_ok",
            non_fatal_warnings=[],
        )
    )
    assert result.ok is True
    assert result.fail_reasons == []
    assert result.score == 100
