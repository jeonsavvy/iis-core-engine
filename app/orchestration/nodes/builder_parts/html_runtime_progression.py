from __future__ import annotations

import json

UPGRADE_PICKS = [
    "attack_speed",
    "mobility",
    "damage",
    "sustain",
    "burst",
]

PROGRESSION_TUNING = {
    "next_xp_multiplier": 1.2,
    "combo_cap": 20,
    "attack_speed_cooldown_floor": 0.16,
    "attack_speed_cooldown_multiplier": 0.88,
    "mobility_speed_cap": 460,
    "mobility_speed_add": 20,
    "damage_score_cap": 220,
    "damage_score_add": 5,
    "burst_combo_add": 1.8,
    "level_interval_sec": 12,
    "level_difficulty_step": 0.11,
    "level_xp_base": 30,
    "level_xp_step": 6,
    "combo_decay_per_sec": 2.2,
    "wave_interval_sec_default": 8.0,
    "miniboss_interval_sec_default": 24.0,
    "wave_shake_floor": 0.12,
    "wave_fx_pulse_floor": 0.24,
    "level_fx_pulse_floor": 0.35,
    "combo_timer_window_sec": 2.3,
    "dash_cooldown_sec": 1.35,
    "dash_shake_value": 0.2,
    "shake_decay_per_sec": 1.8,
    "fx_pulse_decay_per_sec": 0.8,
}


def build_progression_block_js() -> str:
    tuning_json = json.dumps(PROGRESSION_TUNING, ensure_ascii=False, indent=2)
    picks_json = json.dumps(UPGRADE_PICKS, ensure_ascii=False, indent=2)
    return "\n".join(
        [
            f"      const PROGRESSION_TUNING = {tuning_json};",
            f"      const UPGRADE_PICKS = {picks_json};",
        ]
    )
