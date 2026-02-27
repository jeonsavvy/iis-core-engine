from __future__ import annotations

from app.orchestration.nodes.builder_parts.html_runtime_progression import (
    PROGRESSION_TUNING,
    UPGRADE_PICKS,
    build_progression_block_js,
)


def test_progression_tuning_has_core_thresholds() -> None:
    assert PROGRESSION_TUNING["combo_cap"] == 20
    assert PROGRESSION_TUNING["level_interval_sec"] == 12
    assert PROGRESSION_TUNING["dash_cooldown_sec"] == 1.35


def test_upgrade_picks_include_required_tokens() -> None:
    assert "attack_speed" in UPGRADE_PICKS
    assert "mobility" in UPGRADE_PICKS
    assert "burst" in UPGRADE_PICKS


def test_build_progression_block_js_contains_expected_consts() -> None:
    block = build_progression_block_js()
    assert "const PROGRESSION_TUNING =" in block
    assert "const UPGRADE_PICKS =" in block
    assert "combo_cap" in block
