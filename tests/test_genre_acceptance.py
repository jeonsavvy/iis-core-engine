from app.agents.genre_acceptance import (
    validate_flight_acceptance,
    validate_island_flight_acceptance,
    validate_racing_acceptance,
    validate_topdown_acceptance,
)
from app.agents.scaffolds import get_scaffold_seed


def test_racing_seed_passes_acceptance() -> None:
    seed = get_scaffold_seed("three_openwheel_circuit_seed")
    assert seed is not None
    report = validate_racing_acceptance(seed.html)
    assert report.ok is True


def test_flight_seed_passes_acceptance() -> None:
    seed = get_scaffold_seed("three_space_dogfight_seed")
    assert seed is not None
    report = validate_flight_acceptance(seed.html)
    assert report.ok is True


def test_island_flight_seed_passes_acceptance() -> None:
    seed = get_scaffold_seed("three_lowpoly_island_flight_seed")
    assert seed is not None
    report = validate_island_flight_acceptance(seed.html)
    assert report.ok is True


def test_topdown_seed_passes_acceptance() -> None:
    seed = get_scaffold_seed("phaser_twinstick_arena_seed")
    assert seed is not None
    report = validate_topdown_acceptance(seed.html)
    assert report.ok is True


def test_racing_terrain_demo_fails_acceptance() -> None:
    report = validate_racing_acceptance("<html><body>mountain grass sky requestAnimationFrame throttle brake</body></html>")
    assert report.ok is False
    assert "terrain_demo_regression" in report.failures


def test_flight_corridor_demo_fails_acceptance() -> None:
    report = validate_flight_acceptance(
        "<html><body>pitch roll yaw throttle requestAnimationFrame corridor shooter autoscroll reticle</body></html>"
    )
    assert report.ok is False
    assert "corridor_regression" in report.failures


def test_island_flight_void_demo_fails_acceptance() -> None:
    report = validate_island_flight_acceptance(
        "<html><body>flight void propeller requestAnimationFrame dark empty void</body></html>"
    )
    assert report.ok is False
    assert "ring_collect_missing" in report.failures


def test_topdown_flat_shooter_fails_acceptance() -> None:
    report = validate_topdown_acceptance(
        "<html><body>phaser dash firebullet requestAnimationFrame crosshair 8-way shooter</body></html>"
    )
    assert report.ok is False
    assert "flat_shooter_regression" in report.failures
