from __future__ import annotations

from app.core.config import Settings
from app.orchestration.nodes.builder import (
    _build_hybrid_asset_bank,
    _build_hybrid_engine_html,
    _extract_hybrid_bundle_from_inline_html,
    _infer_core_loop_type,
    _resolve_asset_pack,
)
from app.services.quality_service import QualityService


def _build_sample_html(mode: str) -> str:
    asset_pack = _resolve_asset_pack(core_loop_type=mode, palette=["#22c55e", "#10162c", "#60a5fa", "#f43f5e"])
    return _build_hybrid_engine_html(
        title="Sample",
        genre="arcade",
        slug="sample-game",
        accent_color="#22c55e",
        viewport_width=1280,
        viewport_height=720,
        safe_area_padding=24,
        min_font_size_px=14,
        text_overflow_policy="ellipsis-clamp",
        core_loop_type=mode,
        game_config={
            "player_hp": 3,
            "player_speed": 260,
            "player_attack_cooldown": 0.5,
            "enemy_hp": 1,
            "enemy_speed_min": 100,
            "enemy_speed_max": 220,
            "enemy_spawn_rate": 0.8,
            "time_limit_sec": 60,
            "base_score_value": 12,
        },
        asset_pack=asset_pack,
    )


def test_infer_topdown_roguelike_mode_from_keyword() -> None:
    mode = _infer_core_loop_type(keyword="탑뷰 판타지 슈팅 로그라이크", title="Rune Rush", genre="arcade")
    assert mode == "topdown_roguelike_shooter"


def test_infer_flight_mode_from_keyword() -> None:
    mode = _infer_core_loop_type(keyword="풀3D 비행기 조종 시뮬레이터", title="Sky Ace", genre="sim")
    assert mode == "flight_sim_3d"


def test_infer_formula_mode_from_keyword() -> None:
    mode = _infer_core_loop_type(keyword="F1 스타일 풀3D 레이싱", title="Grand Prix Neon", genre="racing")
    assert mode == "f1_formula_circuit_3d"


def test_infer_webgl_runner_mode_from_keyword() -> None:
    mode = _infer_core_loop_type(keyword="웹글 3D 드리프트 레이싱", title="Neon Outrun", genre="arcade")
    assert mode == "webgl_three_runner"


def test_infer_comic_action_mode_from_keyword() -> None:
    mode = _infer_core_loop_type(keyword="코믹액션 3D 난투", title="Turbo Smash", genre="arcade")
    assert mode == "comic_action_brawler_3d"


def test_topdown_builder_html_contains_asset_pack_and_progression_hooks() -> None:
    html = _build_sample_html("topdown_roguelike_shooter").lower()
    assert "assetpack" in html
    assert "state.run.level" in html
    assert "topdown_roguelike_shooter" in html
    assert "depth_packs" in html
    assert "spawnminiboss" in html
    assert "relic_synergy_rules" in html


def test_gameplay_gate_passes_for_topdown_candidate() -> None:
    html = _build_sample_html("topdown_roguelike_shooter")
    quality = QualityService(Settings(qa_min_gameplay_score=55))
    gate = quality.evaluate_gameplay_gate(
        html,
        design_spec={"text_overflow_policy": "ellipsis-clamp"},
        genre="탑다운 로그라이크 슈팅",
    )
    assert gate.ok is True
    assert gate.score >= gate.threshold


def test_webgl_builder_html_contains_webgl_audio_and_relic_hooks() -> None:
    html = _build_sample_html("webgl_three_runner").lower()
    assert "getcontext(\"webgl\"" in html
    assert "renderwebglbackground(" in html
    assert "playsfx(" in html
    assert "state.run.relics" in html
    assert "steervelocity" in html
    assert "math.round(state.player.lane)" not in html
    assert "control_presets" in html
    assert "const control =" in html
    assert "active_depth_pack" in html
    assert "applyrelicsynergy" in html
    assert "drawpostfx" in html


def test_flight_builder_html_contains_flight_controls_and_progression_hooks() -> None:
    html = _build_sample_html("flight_sim_3d").lower()
    assert "state.flight" in html
    assert "checkpointcombo" in html
    assert "throttle" in html
    assert "pitch" in html and "roll" in html and "yaw" in html


def test_formula_builder_html_contains_lap_and_overtake_hooks() -> None:
    html = _build_sample_html("f1_formula_circuit_3d").lower()
    assert "state.formula" in html
    assert "checkpoint" in html
    assert "overtakechain" in html
    assert "accel_rate" in html and "brake_rate" in html


def test_gameplay_gate_rejects_when_keyword_requires_flight_but_mode_mismatches() -> None:
    html = _build_sample_html("topdown_roguelike_shooter").replace("state.flight", "state.airframe")
    quality = QualityService(Settings(qa_min_gameplay_score=55))
    gate = quality.evaluate_gameplay_gate(
        html,
        design_spec={"text_overflow_policy": "ellipsis-clamp"},
        genre="simulation",
        genre_engine="flight_sim_3d",
        keyword="full 3d flight simulator",
    )
    assert gate.ok is False
    assert "flight_mechanics_not_found" in gate.failed_checks or "genre_engine_mismatch" in gate.failed_checks


def test_gameplay_gate_rejects_quantized_webgl_lane_steering() -> None:
    html = _build_sample_html("webgl_three_runner") + "\n// Math.round(state.player.lane)"
    quality = QualityService(Settings(qa_min_gameplay_score=55))
    gate = quality.evaluate_gameplay_gate(
        html,
        design_spec={"text_overflow_policy": "ellipsis-clamp"},
        genre="webgl racing",
        genre_engine="webgl_three_runner",
        keyword="neon outrun",
    )
    assert gate.ok is False
    assert "quantized_lane_steering" in gate.failed_checks


def test_gameplay_gate_passes_for_formula_mode() -> None:
    html = _build_sample_html("f1_formula_circuit_3d")
    quality = QualityService(Settings(qa_min_gameplay_score=55))
    gate = quality.evaluate_gameplay_gate(
        html,
        design_spec={"text_overflow_policy": "ellipsis-clamp"},
        genre="formula racing",
        genre_engine="f1_formula_circuit_3d",
        keyword="f1 style full 3d racing",
    )
    assert gate.ok is True
    assert gate.score >= gate.threshold


def test_hybrid_bundle_extract_includes_asset_bank_and_runtime_contract() -> None:
    mode = "webgl_three_runner"
    slug = "asset-contract-sample"
    asset_pack = _resolve_asset_pack(core_loop_type=mode, palette=["#22c55e", "#10162c", "#60a5fa", "#f43f5e"])
    asset_files, runtime_manifest = _build_hybrid_asset_bank(
        slug=slug,
        core_loop_type=mode,
        asset_pack=asset_pack,
    )
    html = _build_hybrid_engine_html(
        title="Asset Sample",
        genre="arcade",
        slug=slug,
        accent_color="#22c55e",
        viewport_width=1280,
        viewport_height=720,
        safe_area_padding=24,
        min_font_size_px=14,
        text_overflow_policy="ellipsis-clamp",
        core_loop_type=mode,
        game_config={"time_limit_sec": 60},
        asset_pack=asset_pack,
        asset_manifest=runtime_manifest,
    )
    bundle = _extract_hybrid_bundle_from_inline_html(
        slug=slug,
        inline_html=html,
        asset_bank_files=asset_files,
        runtime_asset_manifest=runtime_manifest,
    )
    assert bundle is not None
    artifact_files, artifact_manifest = bundle
    assert any(row["path"].endswith("/player.svg") for row in artifact_files)
    assert any(row["path"].endswith("/ring.svg") for row in artifact_files)
    runtime_hooks = artifact_manifest.get("runtime_hooks")
    assert isinstance(runtime_hooks, list)
    assert len(runtime_hooks) >= 4
    asset_manifest = artifact_manifest.get("asset_manifest")
    assert isinstance(asset_manifest, dict)
    images = asset_manifest.get("images")
    assert isinstance(images, dict)
    assert images.get("player") == "./player.svg"
    asset_policy = asset_manifest.get("asset_policy")
    assert isinstance(asset_policy, dict)
    assert asset_policy.get("mode") == "procedural_threejs_first"
    assert asset_policy.get("external_image_generation") is False
    procedural_layers = asset_manifest.get("procedural_layers")
    assert isinstance(procedural_layers, list)
    assert len(procedural_layers) >= 3

    quality = QualityService(Settings(qa_min_artifact_contract_score=70))
    contract_result = quality.evaluate_artifact_contract(
        artifact_manifest,
        art_direction_contract={
            "min_image_assets": 5,
            "min_render_layers": 4,
            "min_animation_hooks": 3,
            "min_procedural_layers": 3,
        },
    )
    assert contract_result.ok is True
