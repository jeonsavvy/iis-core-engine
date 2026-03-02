from __future__ import annotations

from app.orchestration.nodes.builder_parts.html_runtime_balance import (
    CONTROL_PRESETS,
    DEPTH_PACKS,
    RELIC_SYNERGY_RULES,
    build_runtime_balance_block_js,
)


def test_balance_tables_cover_known_modes() -> None:
    expected_modes = {
        "f1_formula_circuit_3d",
        "flight_sim_3d",
        "webgl_three_runner",
        "lane_dodge_racer",
        "topdown_roguelike_shooter",
        "arena_shooter",
        "comic_action_brawler_3d",
        "duel_brawler",
        "request_faithful_generic",
        "arcade_generic",
    }
    assert expected_modes.issubset(CONTROL_PRESETS.keys())
    assert expected_modes.issubset(DEPTH_PACKS.keys())


def test_relic_synergy_rules_exist() -> None:
    assert len(RELIC_SYNERGY_RULES) >= 3
    assert any(rule.get("id") == "velocity-chain" for rule in RELIC_SYNERGY_RULES)


def test_runtime_balance_block_contains_required_js_symbols() -> None:
    block = build_runtime_balance_block_js()
    assert "const CONTROL_PRESETS =" in block
    assert "const DEPTH_PACKS =" in block
    assert "const RELIC_SYNERGY_RULES =" in block
    assert "const CONTROL = CONTROL_PRESETS[CONFIG.mode] || CONTROL_PRESETS.request_faithful_generic || CONTROL_PRESETS.arcade_generic;" in block
    assert "const ACTIVE_DEPTH_PACK = DEPTH_PACKS[CONFIG.mode] || DEPTH_PACKS.request_faithful_generic || DEPTH_PACKS.arcade_generic;" in block
