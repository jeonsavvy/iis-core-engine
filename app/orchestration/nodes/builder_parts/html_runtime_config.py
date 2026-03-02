from __future__ import annotations

import json
from typing import Any, TypedDict


class RuntimeModeConfig(TypedDict):
    label: str
    objective: str
    controls: str


MODE_CONFIG_BY_LOOP: dict[str, RuntimeModeConfig] = {
    "f1_formula_circuit_3d": {
        "label": "F1 Formula Circuit",
        "objective": "브레이킹 포인트와 에이펙스를 읽어 체커 포인트를 연속 통과하며 랩 타임을 단축하세요.",
        "controls": "← → 조향 / ↑ 가속 / ↓ 브레이크 / Shift 오버테이크 부스트 / R 재시작",
    },
    "flight_sim_3d": {
        "label": "Flight Sim 3D",
        "objective": "스로틀·피치·롤·요 제어로 항로 링을 통과하며 스톨/충돌을 피하고 최고 점수를 달성하세요.",
        "controls": "W/S 피치 · A/D 롤 · Q/E 요 · ↑/↓ 스로틀 · Shift 부스트 · R 재시작",
    },
    "webgl_three_runner": {
        "label": "WebGL 3D Runner",
        "objective": "WebGL 기반 네온 하이웨이에서 드리프트 라인과 부스트 체인을 유지하며 최장 생존 점수를 노리세요.",
        "controls": "← → 조향 / ↑ 가속 / ↓ 브레이크 / Shift 부스트 / R 재시작",
    },
    "topdown_roguelike_shooter": {
        "label": "Topdown Roguelike",
        "objective": "대시와 집중 사격으로 몬스터 웨이브를 돌파하고 생존 콤보를 이어가세요.",
        "controls": "← → ↑ ↓ 이동 / Space 발사 / Shift 대시 / R 재시작",
    },
    "comic_action_brawler_3d": {
        "label": "Comic 3D Brawler",
        "objective": "파도처럼 몰려오는 적을 연속 타격으로 제압하고 콤보 보너스를 유지하세요.",
        "controls": "← → ↑ ↓ 이동 / Space 공격 / Shift 회피 / R 재시작",
    },
    "lane_dodge_racer": {
        "label": "Racing",
        "objective": "코너를 읽고 드리프트 라인을 유지하며 장애물 회피+부스트 박스를 활용해 최고 점수를 달성하세요.",
        "controls": "← → 조향 / ↑ 가속 / ↓ 브레이크 / R 재시작",
    },
    "arena_shooter": {
        "label": "Shooter",
        "objective": "적을 피하며 발사체로 처치하고 생존 시간을 늘리세요.",
        "controls": "← → ↑ ↓ 이동 / Space 발사 / R 재시작",
    },
    "duel_brawler": {
        "label": "Fighter",
        "objective": "근접전으로 적의 체력을 먼저 깎아 승리하세요.",
        "controls": "← → ↑ ↓ 이동 / Space 공격 / R 재시작",
    },
    "arcade_generic": {
        "label": "Arcade",
        "objective": "움직이며 위험 요소를 피하고 점수를 올리세요.",
        "controls": "← → ↑ ↓ 이동 / R 재시작",
    },
}


def resolve_mode_config(core_loop_type: str) -> RuntimeModeConfig:
    return MODE_CONFIG_BY_LOOP[core_loop_type]


def _coerce_int(value: Any, *, fallback: int) -> int:
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return fallback
        try:
            return int(float(text))
        except Exception:
            return fallback
    return fallback


def _coerce_float(value: Any, *, fallback: float) -> float:
    if isinstance(value, bool):
        return fallback
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return fallback
        try:
            return float(text)
        except Exception:
            return fallback
    return fallback


def _normalize_mode_balance_config(*, core_loop_type: str, raw_config: dict[str, Any]) -> dict[str, Any]:
    config = dict(raw_config)
    if core_loop_type == "f1_formula_circuit_3d":
        config["player_hp"] = max(2, min(6, _coerce_int(config.get("player_hp"), fallback=3)))
        config["time_limit_sec"] = max(90, min(360, _coerce_int(config.get("time_limit_sec"), fallback=120)))
        config["enemy_spawn_rate"] = max(0.58, min(1.8, _coerce_float(config.get("enemy_spawn_rate"), fallback=0.86)))
        config["player_speed"] = max(220, min(520, _coerce_int(config.get("player_speed"), fallback=320)))
    elif core_loop_type in {"flight_sim_3d", "webgl_three_runner", "lane_dodge_racer"}:
        config["player_hp"] = max(2, min(8, _coerce_int(config.get("player_hp"), fallback=5)))
        config["time_limit_sec"] = max(75, min(300, _coerce_int(config.get("time_limit_sec"), fallback=95)))
        config["enemy_spawn_rate"] = max(0.42, min(1.55, _coerce_float(config.get("enemy_spawn_rate"), fallback=0.68)))
    elif core_loop_type in {"comic_action_brawler_3d", "duel_brawler"}:
        config["player_hp"] = max(5, min(10, _coerce_int(config.get("player_hp"), fallback=7)))
        config["time_limit_sec"] = max(80, min(260, _coerce_int(config.get("time_limit_sec"), fallback=120)))
        config["enemy_spawn_rate"] = max(0.35, min(1.45, _coerce_float(config.get("enemy_spawn_rate"), fallback=0.6)))
        config["enemy_speed_min"] = max(55, min(180, _coerce_int(config.get("enemy_speed_min"), fallback=80)))
        config["enemy_speed_max"] = max(95, min(260, _coerce_int(config.get("enemy_speed_max"), fallback=155)))
        config["player_attack_cooldown"] = max(0.22, min(0.8, _coerce_float(config.get("player_attack_cooldown"), fallback=0.34)))
    return config


def build_runtime_config_json(
    *,
    title: str,
    genre: str,
    slug: str,
    accent_color: str,
    viewport_width: int,
    viewport_height: int,
    safe_area_padding: int,
    min_font_size_px: int,
    text_overflow_policy: str,
    core_loop_type: str,
    game_config: dict[str, Any],
    asset_pack: dict[str, str],
    asset_manifest: dict[str, object] | None = None,
) -> str:
    normalized_game_config = _normalize_mode_balance_config(
        core_loop_type=core_loop_type,
        raw_config=game_config,
    )
    config_dict: dict[str, Any] = {
        "mode": core_loop_type,
        "title": title,
        "genre": genre,
        "slug": slug,
        "accentColor": accent_color,
        "viewportWidth": viewport_width,
        "viewportHeight": viewport_height,
        "safeAreaPadding": safe_area_padding,
        "minFontSizePx": min_font_size_px,
        "textOverflowPolicy": text_overflow_policy,
        "assetPack": asset_pack,
        "assetManifest": asset_manifest or {},
    }
    config_dict.update(normalized_game_config)
    return json.dumps(config_dict, ensure_ascii=False)
