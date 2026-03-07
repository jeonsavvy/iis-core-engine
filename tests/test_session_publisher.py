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



def test_resolve_telegram_media_url_prefers_absolute_thumbnail() -> None:
    result = SessionPublisher._resolve_telegram_media_url(
        thumbnail_url="https://cdn.example.com/thumb.png",
        screenshot_url="https://cdn.example.com/screenshot.png",
    )
    assert result == "https://cdn.example.com/thumb.png"


def test_resolve_telegram_media_url_skips_relative_svg_preview_asset() -> None:
    result = SessionPublisher._resolve_telegram_media_url(
        thumbnail_url="/assets/preview/neon-drift.svg",
        screenshot_url=None,
    )
    assert result is None


def test_resolve_play_url_uses_public_portal_base_url_when_configured() -> None:
    publisher = SessionPublisher(
        Settings(
            supabase_url="",
            supabase_service_role_key="",
            google_application_credentials="",
            public_portal_base_url="https://arcade.example.com",
        )
    )

    assert publisher._resolve_play_url(slug="neon-drift") == "https://arcade.example.com/play/neon-drift"
