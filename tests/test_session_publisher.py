from __future__ import annotations

from app.core.config import Settings
from app.services.session_publisher import SessionPublisher


def test_session_publisher_initializes_without_archive_repo_local_path_setting() -> None:
    publisher = SessionPublisher(
        Settings(
            supabase_url="",
            supabase_service_role_key="",
            google_application_credentials="",
        )
    )

    assert publisher is not None


def test_fallback_preview_asset_maps_known_genre_packs() -> None:
    assert SessionPublisher._fallback_preview_asset(genre_brief={"asset_pack_key": "racing_synthwave_pack_v1"}) == "/assets/preview/neon-drift.svg"
    assert SessionPublisher._fallback_preview_asset(genre_brief={"asset_pack_key": "island_flight_pack_v1"}) == "/assets/preview/aether-courier.svg"
    assert SessionPublisher._fallback_preview_asset(genre_brief={"asset_pack_key": "space_dogfight_pack_v1"}) == "/assets/preview/skyline-jet.svg"
    assert SessionPublisher._fallback_preview_asset(genre_brief={"asset_pack_key": "topdown_lowpoly_pack_v1"}) == "/assets/preview/timebreakers.svg"
