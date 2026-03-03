from __future__ import annotations

import json
from typing import Any

CONTROL_PRESETS: dict[str, dict[str, Any]] = {
    "f1_formula_circuit_3d": {
        "steer_accel": 11.6,
        "steer_drag": 8.8,
        "steer_return": 9.4,
        "accel_rate": 340,
        "brake_rate": 420,
        "drag_rate": 120,
        "speed_min": 185,
        "speed_max": 640,
        "lane_lerp": 11.2,
        "curve_response": 1.9,
        "curve_interval_min": 0.6,
        "curve_interval_max": 1.8,
        "apex_window": 0.36,
        "overtake_boost_floor": 460,
        "checkpoint_bonus_sec": 2.2,
    },
    "flight_sim_3d": {
        "throttle_response": 0.62,
        "pitch_response": 2.7,
        "roll_response": 2.9,
        "yaw_response": 2.0,
        "damping_pitch": 2.9,
        "damping_roll": 3.3,
        "damping_yaw": 3.6,
        "lateral_sensitivity": 362,
        "vertical_sensitivity": 248,
        "cruise_speed_min": 190,
        "cruise_speed_max": 438,
        "camera_sensitivity": 1.18,
        "boost_floor_speed": 452,
    },
    "webgl_three_runner": {
        "steer_accel": 10.2,
        "steer_drag": 7.6,
        "steer_return": 10.4,
        "accel_rate": 268,
        "brake_rate": 304,
        "drag_rate": 126,
        "speed_min": 185,
        "speed_max": 548,
        "lane_lerp": 13.5,
        "curve_response": 1.55,
        "curve_interval_min": 0.85,
        "curve_interval_max": 2.25,
    },
    "lane_dodge_racer": {
        "steer_accel": 9.2,
        "steer_drag": 7.2,
        "steer_return": 9.6,
        "accel_rate": 238,
        "brake_rate": 278,
        "drag_rate": 122,
        "speed_min": 180,
        "speed_max": 520,
        "lane_lerp": 12.2,
        "curve_response": 1.42,
        "curve_interval_min": 1.0,
        "curve_interval_max": 2.4,
    },
    "topdown_roguelike_shooter": {
        "move_speed": 262,
        "dash_multiplier": 1.92,
        "orbit_speed": 2.05,
    },
    "arena_shooter": {
        "move_speed": 268,
    },
    "comic_action_brawler_3d": {
        "move_speed": 232,
        "dash_multiplier": 1.85,
    },
    "duel_brawler": {
        "move_speed": 220,
        "dash_multiplier": 1.75,
    },
    "arcade_generic": {
        "move_speed": 240,
    },
}

DEPTH_PACKS: dict[str, dict[str, Any]] = {
    "f1_formula_circuit_3d": {
        "wave_interval_sec": 6.4,
        "miniboss_interval_sec": 20.0,
        "wave_modifiers": [1.0, 1.12, 1.26, 1.42],
        "pattern": [["checkpoint", 0.3], ["opponent", 0.44], ["boost", 0.18], ["hazard", 0.08]],
    },
    "flight_sim_3d": {
        "wave_interval_sec": 8.0,
        "miniboss_interval_sec": 24.0,
        "wave_modifiers": [1.0, 1.12, 1.25, 1.4],
        "pattern": [["ring", 0.24], ["hazard", 0.6], ["turbulence", 0.16]],
    },
    "webgl_three_runner": {
        "wave_interval_sec": 7.0,
        "miniboss_interval_sec": 22.0,
        "wave_modifiers": [1.0, 1.1, 1.23, 1.36],
        "pattern": [["boost", 0.2], ["obstacle", 0.64], ["elite", 0.16]],
    },
    "lane_dodge_racer": {
        "wave_interval_sec": 7.5,
        "miniboss_interval_sec": 24.0,
        "wave_modifiers": [1.0, 1.08, 1.18, 1.28],
        "pattern": [["boost", 0.18], ["obstacle", 0.72], ["elite", 0.1]],
    },
    "topdown_roguelike_shooter": {
        "wave_interval_sec": 8.5,
        "miniboss_interval_sec": 26.0,
        "wave_modifiers": [1.0, 1.15, 1.3, 1.45],
        "pattern": [["grunt", 0.5], ["charger", 0.28], ["elite", 0.22]],
    },
    "arena_shooter": {
        "wave_interval_sec": 9.0,
        "miniboss_interval_sec": 27.0,
        "wave_modifiers": [1.0, 1.12, 1.24, 1.36],
        "pattern": [["grunt", 0.66], ["elite", 0.34]],
    },
    "comic_action_brawler_3d": {
        "wave_interval_sec": 8.0,
        "miniboss_interval_sec": 23.0,
        "wave_modifiers": [1.0, 1.14, 1.28, 1.44],
        "pattern": [["grunt", 0.62], ["elite", 0.38]],
    },
    "duel_brawler": {
        "wave_interval_sec": 9.0,
        "miniboss_interval_sec": 24.0,
        "wave_modifiers": [1.0, 1.1, 1.22, 1.32],
        "pattern": [["grunt", 0.72], ["elite", 0.28]],
    },
    "arcade_generic": {
        "wave_interval_sec": 9.0,
        "miniboss_interval_sec": 28.0,
        "wave_modifiers": [1.0, 1.08, 1.16, 1.24],
        "pattern": [["grunt", 0.82], ["elite", 0.18]],
    },
}

RELIC_SYNERGY_RULES: list[dict[str, Any]] = [
    {"id": "velocity-chain", "requires": ["mobility", "burst"], "score_mul": 1.14, "boost_bonus": 0.45, "spawn_ease": 0.94},
    {"id": "precision-overdrive", "requires": ["attack_speed", "damage"], "score_mul": 1.2, "damage_bonus": 0.28, "spawn_ease": 0.92},
    {"id": "endurance-loop", "requires": ["sustain", "mobility"], "score_mul": 1.08, "hp_regen_tick": 0.08, "spawn_ease": 0.95},
]


def _format_js_const(name: str, value: Any) -> str:
    payload_lines = json.dumps(value, ensure_ascii=False, indent=2).splitlines()
    if not payload_lines:
        return f"      const {name} = null;"

    header = f"      const {name} = {payload_lines[0]}"
    if len(payload_lines) == 1:
        return f"{header};"

    body = "\n".join(f"      {line}" for line in payload_lines[1:])
    return f"{header}\n{body};"


def build_runtime_balance_block_js() -> str:
    return "\n".join(
        [
            _format_js_const("CONTROL_PRESETS", CONTROL_PRESETS),
            _format_js_const("DEPTH_PACKS", DEPTH_PACKS),
            _format_js_const("RELIC_SYNERGY_RULES", RELIC_SYNERGY_RULES),
            "      const CONTROL = CONTROL_PRESETS[CONFIG.mode] || CONTROL_PRESETS.comic_action_brawler_3d || CONTROL_PRESETS.arcade_generic;",
            "      const ACTIVE_DEPTH_PACK = DEPTH_PACKS[CONFIG.mode] || DEPTH_PACKS.comic_action_brawler_3d || DEPTH_PACKS.arcade_generic;",
        ]
    )
