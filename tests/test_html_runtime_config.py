from __future__ import annotations

import json

from app.orchestration.nodes.builder_parts.html_runtime_config import build_runtime_config_json, resolve_mode_config


def test_resolve_mode_config_returns_expected_values() -> None:
    resolved = resolve_mode_config("flight_sim_3d")
    assert resolved["label"] == "Flight Sim 3D"
    assert "스로틀" in resolved["objective"]
    assert "W/S" in resolved["controls"]


def test_resolve_mode_config_falls_back_to_request_faithful_mode_for_unknown_mode() -> None:
    resolved = resolve_mode_config("unsupported_mode")
    assert resolved["label"] == "Adaptive Action"
    assert "요청한 게임 판타지" in resolved["objective"]


def test_build_runtime_config_json_merges_payload_and_defaults() -> None:
    payload = json.loads(
        build_runtime_config_json(
            title="Sample",
            genre="arcade",
            slug="sample",
            accent_color="#22c55e",
            viewport_width=1280,
            viewport_height=720,
            safe_area_padding=24,
            min_font_size_px=14,
            text_overflow_policy="ellipsis-clamp",
            core_loop_type="webgl_three_runner",
            game_config={
                "player_hp": 3,
                "title": "override-allowed",
            },
            asset_pack={"bg_top": "#111", "bg_bottom": "#222", "hud_primary": "#fff", "hud_muted": "#ddd"},
            asset_manifest=None,
        )
    )

    assert payload["mode"] == "webgl_three_runner"
    assert payload["title"] == "override-allowed"
    assert payload["player_hp"] == 3
    assert payload["assetPack"]["bg_top"] == "#111"
    assert payload["assetManifest"] == {}


def test_build_runtime_config_json_enforces_f1_runtime_safety_floor() -> None:
    payload = json.loads(
        build_runtime_config_json(
            title="F1 Test",
            genre="formula-racing-3d",
            slug="f1-test",
            accent_color="#22c55e",
            viewport_width=1280,
            viewport_height=720,
            safe_area_padding=24,
            min_font_size_px=14,
            text_overflow_policy="ellipsis-clamp",
            core_loop_type="f1_formula_circuit_3d",
            game_config={
                "player_hp": 1,
                "time_limit_sec": 45,
                "enemy_spawn_rate": 0.2,
                "player_speed": 620,
            },
            asset_pack={"bg_top": "#111", "bg_bottom": "#222", "hud_primary": "#fff", "hud_muted": "#ddd"},
            asset_manifest=None,
        )
    )

    assert payload["player_hp"] == 2
    assert payload["time_limit_sec"] == 90
    assert payload["enemy_spawn_rate"] == 0.58
    assert payload["player_speed"] == 520
