from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AcceptanceReport:
    ok: bool
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


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
    if "wrong way" not in lowered and "wrongwaytimer" not in lowered:
        failures.append("wrong_way_detection_missing")
    if "nearesttracksample" not in lowered:
        failures.append("track_confinement_missing")
    if any(token in lowered for token in ("mountain", "terrainheight", "grass", "tree")) and "trackcurve" not in lowered:
        failures.append("terrain_demo_regression")
    return AcceptanceReport(
        ok=not failures,
        failures=failures,
        metadata={"genre": "racing"},
    )


def validate_flight_acceptance(html: str) -> AcceptanceReport:
    lowered = html.casefold()
    failures: list[str] = []
    for token in ("pitch", "roll", "yaw", "throttle"):
        if token not in lowered:
            failures.append(f"{token}_missing")
    if "reticle" not in lowered and "target-box" not in lowered:
        failures.append("targeting_feedback_missing")
    if "enemy wave" not in lowered and "enemies.forEach" not in lowered and "fireenemylaser" not in lowered:
        failures.append("combat_loop_missing")
    if "enemylasers" not in lowered and "fireenemylaser" not in lowered:
        failures.append("enemy_attack_loop_missing")
    if "boostcharge" not in lowered:
        failures.append("boost_feedback_missing")
    if "cockpit-bars" not in lowered and "target-box" not in lowered:
        failures.append("hud_depth_missing")
    return AcceptanceReport(ok=not failures, failures=failures, metadata={"genre": "flight"})


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
    return AcceptanceReport(ok=not failures, failures=failures, metadata={"genre": "topdown"})


def validate_genre_acceptance(*, archetype: str, html: str) -> AcceptanceReport:
    if archetype == "racing_openwheel_circuit_3d":
        return validate_racing_acceptance(html)
    if archetype == "flight_shooter_space_dogfight_3d":
        return validate_flight_acceptance(html)
    if archetype == "topdown_shooter_twinstick_2d":
        return validate_topdown_acceptance(html)
    return AcceptanceReport(ok=True, metadata={"genre": "generic"})
