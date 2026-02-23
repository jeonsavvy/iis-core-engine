from __future__ import annotations

from app.core.config import Settings
from app.orchestration.nodes.builder import (
    _build_hybrid_engine_html,
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


def test_infer_comic_action_mode_from_keyword() -> None:
    mode = _infer_core_loop_type(keyword="코믹액션 3D 난투", title="Turbo Smash", genre="arcade")
    assert mode == "comic_action_brawler_3d"


def test_topdown_builder_html_contains_asset_pack_and_progression_hooks() -> None:
    html = _build_sample_html("topdown_roguelike_shooter").lower()
    assert "assetpack" in html
    assert "state.run.level" in html
    assert "topdown_roguelike_shooter" in html


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
