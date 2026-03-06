from app.agents.scaffolds import get_scaffold_seed, list_scaffold_keys


def test_scaffold_registry_lists_three_supported_genres() -> None:
    assert list_scaffold_keys() == [
        "phaser_twinstick_arena_seed",
        "three_lowpoly_island_flight_seed",
        "three_openwheel_circuit_seed",
        "three_space_dogfight_seed",
    ]


def test_racing_scaffold_contains_required_runtime_tokens() -> None:
    seed = get_scaffold_seed("three_openwheel_circuit_seed")
    assert seed is not None
    html = seed.html.lower()
    assert "<!doctype html>" in html
    assert "three" in html
    assert "lap timer" in html or "lap-timer" in html
    assert "checkpoint" in html
    assert "throttle" in html
    assert "brake" in html
    assert "respawntocheckpoint" in html
    assert "wrongwaytimer" in html or "wrong way" in html
    assert "requestanimationframe" in html
    assert "__iis_game_boot_ok" in html


def test_flight_scaffold_contains_required_runtime_tokens() -> None:
    seed = get_scaffold_seed("three_space_dogfight_seed")
    assert seed is not None
    html = seed.html.lower()
    assert "<!doctype html>" in html
    assert "three" in html
    assert "pitch" in html
    assert "roll" in html
    assert "yaw" in html
    assert "throttle" in html
    assert "reticle" in html
    assert "target locked" in html or "lockstrength" in html
    assert "enemylasers" in html or "fireenemylaser" in html
    assert "boostcharge" in html
    assert "requestanimationframe" in html
    assert "__iis_game_boot_ok" in html


def test_island_flight_scaffold_contains_required_runtime_tokens() -> None:
    seed = get_scaffold_seed("three_lowpoly_island_flight_seed")
    assert seed is not None
    html = seed.html.lower()
    assert "<!doctype html>" in html
    assert "three" in html
    assert "propeller" in html
    assert "ring" in html
    assert "island" in html
    assert "fog" in html
    assert "requestanimationframe" in html
    assert "__iis_game_boot_ok" in html


def test_topdown_scaffold_contains_required_runtime_tokens() -> None:
    seed = get_scaffold_seed("phaser_twinstick_arena_seed")
    assert seed is not None
    html = seed.html.lower()
    assert "<!doctype html>" in html
    assert "phaser" in html
    assert "dash" in html
    assert "wave" in html
    assert "aim" in html
    assert "fire" in html
    assert "enemybullets" in html or "fireenemybullet" in html
    assert "coverblocks" in html
    assert "title-screen" in html or "start run" in html
    assert "requestanimationframe" in html
    assert "__iis_game_boot_ok" in html
