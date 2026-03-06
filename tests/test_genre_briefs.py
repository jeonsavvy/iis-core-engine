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


def test_topdown_brief_selects_twinstick_archetype() -> None:
    brief = build_genre_brief(
        user_prompt="트윈스틱 이동과 에임, 대시가 있는 탑뷰 슈팅 게임",
        genre_hint="topdown shooter",
    )
    assert brief["archetype"] == "topdown_shooter_twinstick_2d"
    assert brief["scaffold_key"] == "phaser_twinstick_arena_seed"
    assert brief["first_frame_requirements"]
