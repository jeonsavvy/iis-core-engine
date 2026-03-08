from app.agents.genre_briefs import build_genre_brief, scaffold_seed_for_brief


def test_racing_brief_selects_openwheel_circuit_archetype() -> None:
    brief = build_genre_brief(
        user_prompt="오픈휠 레이스카로 서킷을 주행하며 랩타임을 기록하는 풀 3D 레이싱 게임",
        genre_hint="racing",
    )
    assert brief["archetype"] == "racing_openwheel_circuit_3d"
    assert brief["scaffold_key"] == "three_openwheel_circuit_seed"
    assert brief["quality_target"] == "web_high_fidelity_racing"
    assert brief["first_frame_requirements"]
    scaffold = scaffold_seed_for_brief(brief)
    assert scaffold is not None
    assert scaffold["seed_name"] == "three_openwheel_circuit_seed"


def test_flight_brief_selects_space_dogfight_archetype() -> None:
    brief = build_genre_brief(
        user_prompt="우주 도그파이트에 초점을 맞춘 풀 3D 플라이트 슈팅 게임",
        genre_hint="flight",
    )
    assert brief["archetype"] == "flight_shooter_space_dogfight_3d"
    assert brief["scaffold_key"] == "three_space_dogfight_seed"
    assert brief["first_frame_requirements"]


def test_island_flight_brief_selects_lowpoly_island_archetype() -> None:
    brief = build_genre_brief(
        user_prompt="따뜻한 일몰 조명 아래 섬과 바다 위를 프로펠러 비행기로 돌아다니며 링을 통과하는 플라이트 게임",
        genre_hint="flight",
    )
    assert brief["archetype"] == "flight_lowpoly_island_3d"
    assert brief["scaffold_key"] == "three_lowpoly_island_flight_seed"
    assert brief["asset_pack_key"] == "island_flight_pack_v1"
    assert "yaw" in brief["must_have_mechanics"]


def test_topdown_brief_selects_twinstick_archetype() -> None:
    brief = build_genre_brief(
        user_prompt="트윈스틱 이동과 에임, 대시가 있는 탑뷰 슈팅 게임",
        genre_hint="topdown shooter",
    )
    assert brief["archetype"] == "topdown_shooter_twinstick_2d"
    assert brief["scaffold_key"] == "phaser_twinstick_arena_seed"
    assert brief["asset_pack_key"] == "topdown_lowpoly_pack_v1"
    assert brief["first_frame_requirements"]


def test_topdown_brief_requires_paused_upgrades_kill_xp_and_no_forced_reload() -> None:
    brief = build_genre_brief(
        user_prompt="마우스로 조준하고 클릭으로 발사하는 탑뷰 슈팅 게임",
        genre_hint="topdown shooter",
    )

    joined_contracts = " ".join(brief["structural_contracts"]).lower()
    assert "pause" in joined_contracts
    assert "xp" in joined_contracts
    assert "reload" not in joined_contracts
