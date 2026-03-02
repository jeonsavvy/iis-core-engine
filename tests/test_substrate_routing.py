from app.orchestration.nodes.builder_parts.substrates import resolve_substrate_profile


def test_substrate_routes_fighter_3d_modes() -> None:
    profile = resolve_substrate_profile("comic_action_brawler_3d")
    assert profile.substrate_id == "fighter_3d"
    assert profile.camera_model == "third_person_close"


def test_substrate_routes_racer_modes() -> None:
    profile = resolve_substrate_profile("f1_formula_circuit_3d")
    assert profile.substrate_id == "racer_3d"
    assert profile.interaction_model == "vehicle_control"


def test_substrate_routes_flight_mode() -> None:
    profile = resolve_substrate_profile("flight_sim_3d")
    assert profile.substrate_id == "flight_3d"
    assert profile.camera_model == "cockpit_or_chase"


def test_substrate_falls_back_to_hybrid_dynamic_for_unknown_mode() -> None:
    profile = resolve_substrate_profile("experimental_custom_mode")
    assert profile.substrate_id == "hybrid_dynamic"
    assert profile.camera_model == "request_driven"
