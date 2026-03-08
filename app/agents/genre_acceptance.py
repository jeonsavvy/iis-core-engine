from __future__ import annotations

import re

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AcceptanceReport:
    ok: bool
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def _report(*, genre: str, failures: list[str], warnings: list[str] | None = None, heuristics: dict[str, Any] | None = None) -> AcceptanceReport:
    warnings = warnings or []
    heuristics = heuristics or {}
    return AcceptanceReport(
        ok=not failures,
        failures=failures,
        warnings=warnings,
        metadata={
            "genre": genre,
            "failed_checks": failures,
            "warnings": warnings,
            "heuristics": heuristics,
            "revert_recommended": bool(failures),
        },
    )


def validate_racing_acceptance(html: str) -> AcceptanceReport:
    lowered = html.casefold()
    failures: list[str] = []
    if "trackcurve" not in lowered and "checkpointstate" not in lowered:
        failures.append("circuit_runtime_missing")
    if "laptimer" not in lowered and "lap-state" not in lowered:
        failures.append("lap_timer_missing")
    if "throttle" not in lowered or "brake" not in lowered:
        failures.append("vehicle_control_missing")
    if "requestanimationframe" not in lowered:
        failures.append("animation_loop_missing")
    if "offtracktimer" not in lowered and "off track" not in lowered:
        failures.append("off_track_penalty_missing")
    if "respawntocheckpoint" not in lowered:
        failures.append("checkpoint_respawn_missing")
    if "wrong way" not in lowered and "wrongwaytimer" not in lowered:
        failures.append("wrong_way_detection_missing")
    if "nearesttracksample" not in lowered:
        failures.append("track_confinement_missing")
    if "guard rail" not in lowered and "railmaterial" not in lowered:
        failures.append("circuit_barrier_missing")
    if any(token in lowered for token in ("mountain", "terrainheight", "grass", "tree")) and "trackcurve" not in lowered:
        failures.append("terrain_demo_regression")
    return _report(
        genre="racing",
        failures=failures,
        heuristics={
            "has_track_curve": "trackcurve" in lowered,
            "has_off_track_penalty": "offtracktimer" in lowered or "off track" in lowered,
            "has_wrong_way": "wrongwaytimer" in lowered or "wrong way" in lowered,
        },
    )


def validate_flight_acceptance(html: str) -> AcceptanceReport:
    lowered = html.casefold()
    failures: list[str] = []
    for token in ("pitch", "roll", "yaw", "throttle"):
        if token not in lowered:
            failures.append(f"{token}_missing")
    if "reticle" not in lowered and "target-box" not in lowered:
        failures.append("targeting_feedback_missing")
    if "target locked" not in lowered and "lockstrength" not in lowered:
        failures.append("target_lock_feedback_missing")
    if "enemy wave" not in lowered and "enemies.forEach" not in lowered and "fireenemylaser" not in lowered:
        failures.append("combat_loop_missing")
    if "enemylasers" not in lowered and "fireenemylaser" not in lowered:
        failures.append("enemy_attack_loop_missing")
    if "boostcharge" not in lowered:
        failures.append("boost_feedback_missing")
    if "cockpit-bars" not in lowered and "target-box" not in lowered:
        failures.append("hud_depth_missing")
    if "enginetrail" not in lowered:
        failures.append("engine_trail_missing")
    if "requestanimationframe" not in lowered:
        failures.append("animation_loop_missing")
    if any(token in lowered for token in ("autoscroll", "corridor shooter", "lane shooter", "side-scroll")):
        failures.append("corridor_regression")
    return _report(
        genre="flight",
        failures=failures,
        heuristics={
            "has_target_box": "target-box" in lowered,
            "has_enemy_lasers": "enemylasers" in lowered or "fireenemylaser" in lowered,
            "has_space_depth": "nebula" in lowered and "stars" in lowered,
        },
    )


def validate_island_flight_acceptance(html: str) -> AcceptanceReport:
    lowered = html.casefold()
    failures: list[str] = []
    for token in ("pitch", "yaw", "bank", "throttle"):
        if token not in lowered:
            failures.append(f"{token}_missing")
    if "propeller" not in lowered:
        failures.append("propeller_missing")
    if "stabilize" not in lowered:
        failures.append("stabilize_missing")
    if "ring" not in lowered:
        failures.append("ring_collect_missing")
    if "fog" not in lowered:
        failures.append("fog_missing")
    if "directionallight" not in lowered:
        failures.append("warm_light_missing")
    if "chain" not in lowered:
        failures.append("chain_progression_missing")
    if "medal" not in lowered and "rating" not in lowered:
        failures.append("rating_loop_missing")
    if "lastsafepoint" not in lowered and "respawn(" not in lowered:
        failures.append("altitude_guard_missing")
    if "island" not in lowered and "sea" not in lowered:
        failures.append("island_landmark_missing")
    if "requestanimationframe" not in lowered:
        failures.append("animation_loop_missing")
    if any(token in lowered for token in ("dogfight", "enemylaser", "target locked")):
        failures.append("dogfight_regression")
    if "yawvelocity" not in lowered and "yawinput" not in lowered:
        failures.append("yaw_authority_missing")
    return _report(
        genre="island_flight",
        failures=failures,
        heuristics={
            "has_propeller": "propeller" in lowered,
            "has_ring_loop": "ring" in lowered,
            "has_island_depth": "island" in lowered and "fog" in lowered,
            "has_respawn": "lastsafepoint" in lowered or "respawn(" in lowered,
        },
    )


def validate_topdown_acceptance(html: str) -> AcceptanceReport:
    lowered = html.casefold()
    failures: list[str] = []
    if "pointeraim" not in lowered and "crosshair" not in lowered:
        failures.append("aim_loop_missing")
    if "dash" not in lowered:
        failures.append("dash_missing")
    if "spawnwave" not in lowered:
        failures.append("wave_loop_missing")
    if "firebullet" not in lowered:
        failures.append("fire_loop_missing")
    if "dashghosts" not in lowered and "dash committed" not in lowered:
        failures.append("dash_feedback_missing")
    if "crosshair" not in lowered:
        failures.append("crosshair_missing")
    if "comboreadout" not in lowered:
        failures.append("arena_hud_missing")
    if "title-screen" not in lowered and "start run" not in lowered:
        failures.append("state_flow_missing")
    if "enemybullets" not in lowered and "fireenemybullet" not in lowered:
        failures.append("enemy_pressure_missing")
    if "xp" not in lowered:
        failures.append("xp_loop_missing")
    if "gainxp(" not in lowered:
        failures.append("kill_xp_loop_missing")
    if "level" not in lowered:
        failures.append("level_loop_missing")
    if "upgrade" not in lowered:
        failures.append("upgrade_loop_missing")
    if "physics.world.pause()" not in lowered or "physics.world.resume()" not in lowered:
        failures.append("upgrade_pause_missing")
    if "resolvedashtarget" not in lowered:
        failures.append("dash_targeting_missing")
    if "setcollideworldbounds(true)" not in lowered or "world.setbounds" not in lowered:
        failures.append("arena_lock_missing")
    if "coverblocks" not in lowered and "arena cover" not in lowered:
        failures.append("arena_landmark_missing")
    if "triggergameover" not in lowered and "game over" not in lowered:
        failures.append("game_over_flow_missing")
    if "flanker" not in lowered or "bruiser" not in lowered:
        failures.append("enemy_variety_missing")
    if "shake(" not in lowered:
        failures.append("screen_shake_missing")
    if "requestanimationframe" not in lowered:
        failures.append("animation_loop_missing")
    if re.search(r"\breload\b", lowered) and "ammo" not in lowered:
        failures.append("forced_reload_regression")
    if any(token in lowered for token in ("clicker", "auto click", "8-way shooter")):
        failures.append("flat_shooter_regression")
    return _report(
        genre="topdown",
        failures=failures,
        heuristics={
            "has_crosshair": "crosshair" in lowered,
            "has_enemy_bullets": "enemybullets" in lowered or "fireenemybullet" in lowered,
            "has_cover": "coverblocks" in lowered or "arena cover" in lowered,
            "has_upgrades": "upgrade" in lowered,
            "has_enemy_variety": "flanker" in lowered and "bruiser" in lowered,
        },
    )


def validate_genre_acceptance(*, archetype: str, html: str) -> AcceptanceReport:
    if archetype == "racing_openwheel_circuit_3d":
        return validate_racing_acceptance(html)
    if archetype == "flight_lowpoly_island_3d":
        return validate_island_flight_acceptance(html)
    if archetype == "flight_shooter_space_dogfight_3d":
        return validate_flight_acceptance(html)
    if archetype == "topdown_shooter_twinstick_2d":
        return validate_topdown_acceptance(html)
    return AcceptanceReport(ok=True, metadata={"genre": "generic"})
