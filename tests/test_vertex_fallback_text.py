from app.services.vertex_fallback_text import build_marketing_fallback_copy, build_publish_copy_fallback


def test_publish_copy_fallback_uses_genre_specific_flight_copy() -> None:
    payload = build_publish_copy_fallback(display_name="Golden Isles Flight", genre="flight_lowpoly_island_3d")
    assert "링" in payload["play_overview"][0]
    assert "피치" in payload["controls_guide"][0]
    assert "flight_lowpoly_island_3d" not in payload["marketing_summary"]


def test_marketing_fallback_copy_avoids_sluggy_machine_text() -> None:
    text = build_marketing_fallback_copy(
        display_name="Neon Grid Grand Prix",
        keyword="neon racing",
        genre="racing_openwheel_circuit_3d",
    )
    assert "racing_openwheel_circuit_3d" not in text
