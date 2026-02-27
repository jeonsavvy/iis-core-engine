from __future__ import annotations

import json

from app.orchestration.nodes.builder_parts.html_runtime_config import build_runtime_config_json, resolve_mode_config


def test_resolve_mode_config_returns_expected_values() -> None:
    resolved = resolve_mode_config("flight_sim_3d")
    assert resolved["label"] == "Flight Sim 3D"
    assert "스로틀" in resolved["objective"]
    assert "W/S" in resolved["controls"]


def test_resolve_mode_config_raises_key_error_for_unknown_mode() -> None:
    try:
        resolve_mode_config("unsupported_mode")
    except KeyError as exc:
        assert exc.args[0] == "unsupported_mode"
    else:
        raise AssertionError("expected KeyError for unsupported mode")


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
