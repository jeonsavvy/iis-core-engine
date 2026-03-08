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


def test_flight_scaffold_contains_depth_landmarks() -> None:
    seed = get_scaffold_seed("three_space_dogfight_seed")
    assert seed is not None
    html = seed.html.lower()
    assert "carriercore" in html
    assert "asteroidfield" in html
    assert "shieldflash" in html


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
    assert "yaw" in html
    assert "stabilize" in html
    assert "lastsafepoint" in html or "respawn(" in html
    assert "requestanimationframe" in html
    assert "__iis_game_boot_ok" in html


def test_island_flight_scaffold_contains_environment_landmarks() -> None:
    seed = get_scaffold_seed("three_lowpoly_island_flight_seed")
    assert seed is not None
    html = seed.html.lower()
    assert "cloudgroup" in html
    assert "sunhalo" in html
    assert "lighthousetower" in html
    assert "chain" in html
    assert "medal" in html or "rating" in html


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
    assert "xp" in html
    assert "level" in html
    assert "upgrade" in html
    assert "resolvedashtarget" in html
    assert "enemytype" in html or "kind:" in html


def test_topdown_scaffold_contains_resilient_start_flow() -> None:
    seed = get_scaffold_seed("phaser_twinstick_arena_seed")
    assert seed is not None
    html = seed.html.lower()
    assert "const beginrun" in html or "function beginrun" in html
    assert 'startbutton?.addeventlistener("pointerdown"' in html or "startbutton?.addeventlistener('pointerdown'" in html
    assert "delayedcall(480, beginrun)" in html or "settimeout(beginrun" in html
    assert "if (!gamestate.started)" in html


def test_topdown_scaffold_contains_pause_game_over_and_enemy_variety_guards() -> None:
    seed = get_scaffold_seed("phaser_twinstick_arena_seed")
    assert seed is not None
    html = seed.html.lower()
    assert "hp: 5" in html
    assert "maxhp: 5" in html
    assert "triggergameover" in html
    assert "physics.world.pause()" in html
    assert "physics.world.resume()" in html
    assert "flanker" in html
    assert "bruiser" in html
