from __future__ import annotations

from datetime import datetime

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


def test_fallback_preview_raster_asset_maps_known_genre_packs() -> None:
    assert SessionPublisher._fallback_preview_raster_asset(genre_brief={"asset_pack_key": "racing_synthwave_pack_v1"}) == "/assets/preview-raster/neon-drift.png"
    assert SessionPublisher._fallback_preview_raster_asset(genre_brief={"asset_pack_key": "island_flight_pack_v1"}) == "/assets/preview-raster/aether-courier.png"
    assert SessionPublisher._fallback_preview_raster_asset(genre_brief={"asset_pack_key": "space_dogfight_pack_v1"}) == "/assets/preview-raster/skyline-jet.png"
    assert SessionPublisher._fallback_preview_raster_asset(genre_brief={"asset_pack_key": "topdown_lowpoly_pack_v1"}) == "/assets/preview-raster/timebreakers.png"



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


def test_resolve_portal_asset_url_uses_public_portal_base_url() -> None:
    publisher = SessionPublisher(
        Settings(
            supabase_url="",
            supabase_service_role_key="",
            google_application_credentials="",
            public_portal_base_url="https://arcade.example.com/",
        )
    )

    assert publisher._resolve_portal_asset_url("/assets/preview-raster/neon-drift.png") == "https://arcade.example.com/assets/preview-raster/neon-drift.png"


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


def test_build_public_game_metadata_derives_catalog_fields() -> None:
    metadata = SessionPublisher._build_public_game_metadata(
        slug="golden-isles-flight",
        game_name="Golden Isles Flight",
        genre="flight",
        genre_brief={
            "archetype": "flight_lowpoly_island_3d",
            "asset_pack_key": "island_flight_pack_v1",
            "must_have_mechanics": ["pitch", "ring collect", "reset"],
        },
        screenshot_url="https://cdn.example.com/golden-isles-flight.png",
        marketing_summary="따뜻한 섬과 바다 위를 비행하며 링을 통과하는 3D 비행 게임",
        play_overview=[
            "섬 지형과 바다 위를 선회하며 링을 통과하세요.",
            "기체가 흔들릴 때는 짧게 자세를 보정하는 것이 중요합니다.",
        ],
        controls_guide=["피치/요: W/S · A/D", "가속: Shift"],
    )

    assert metadata["short_description"] == "따뜻한 섬과 바다 위를 비행하며 링을 통과하는 3D 비행 게임"
    assert "Golden Isles Flight" in metadata["description"]
    assert metadata["genre_primary"] == "flight"
    assert metadata["hero_image_url"] == "https://cdn.example.com/golden-isles-flight.png"
    assert metadata["visibility"] == "public"
    assert metadata["play_count_cached"] == 0
    assert "flight" in metadata["genre_tags"]
    assert "3d" in metadata["genre_tags"]
    assert "ring-collect" in metadata["genre_tags"]
    datetime.fromisoformat(metadata["released_at"])


def test_publish_uses_session_user_id_for_created_by(monkeypatch) -> None:
    publisher = SessionPublisher(
        Settings(
            supabase_url="",
            supabase_service_role_key="",
            google_application_credentials="",
        )
    )

    recorded: dict[str, object] = {}

    def fake_publish_game(**kwargs):  # type: ignore[no-untyped-def]
        recorded.update(kwargs)
        return {
            "status": "published",
            "public_url": "https://cdn.example.com/games/neon-drift/index.html",
            "game_id": "game-1",
        }

    monkeypatch.setattr(publisher._publisher, "publish_game", fake_publish_game)
    monkeypatch.setattr(publisher._publisher, "update_game_marketing", lambda **_: True)
    monkeypatch.setattr(publisher._telegram, "broadcast_launch_announcement", lambda **_: None)
    publisher._archiver = None

    result = __import__("asyncio").run(
        publisher.publish(
            slug="neon-drift",
            game_name="Neon Drift",
            genre="racing",
            html_content="<html>ok</html>",
            genre_brief={"archetype": "racing_openwheel_circuit_3d"},
            created_by="user-1",
        )
    )

    assert result["success"] is True
    assert recorded["created_by"] == "user-1"


def test_publish_uses_text_only_telegram_alert_when_only_placeholder_media_exists(monkeypatch) -> None:
    publisher = SessionPublisher(
        Settings(
            supabase_url="",
            supabase_service_role_key="",
            google_application_credentials="",
            public_portal_base_url="https://arcade.example.com",
        )
    )

    sent_payload: dict[str, object] = {}

    monkeypatch.setattr(
        publisher._publisher,
        "publish_game",
        lambda **_: {
            "status": "published",
            "public_url": "https://cdn.example.com/games/golden-isles-flight/index.html",
            "game_id": "game-1",
        },
    )
    monkeypatch.setattr(publisher._publisher, "update_game_marketing", lambda **_: True)
    monkeypatch.setattr(publisher._quality, "capture_presentation_screenshot", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(publisher._telegram, "broadcast_launch_announcement", lambda **kwargs: sent_payload.update(kwargs))
    publisher._archiver = None

    __import__("asyncio").run(
        publisher.publish(
            slug="golden-isles-flight",
            game_name="Golden Isles Flight",
            genre="flight",
            html_content="<html>ok</html>",
            genre_brief={"asset_pack_key": "island_flight_pack_v1"},
        )
    )

    assert sent_payload == {}


def test_publish_marks_game_hidden_when_canonical_thumbnail_is_missing(monkeypatch) -> None:
    publisher = SessionPublisher(
        Settings(
            supabase_url="",
            supabase_service_role_key="",
            google_application_credentials="",
            public_portal_base_url="https://arcade.example.com",
        )
    )

    update_calls: list[dict[str, object]] = []
    sent_payload: dict[str, object] = {}

    def fake_update_game_marketing(**kwargs: object) -> bool:
        update_calls.append(dict(kwargs))
        return True

    monkeypatch.setattr(
        publisher._publisher,
        "publish_game",
        lambda **_: {
            "status": "published",
            "public_url": "https://cdn.example.com/games/lowpoly-siege/index.html",
            "game_id": "game-1",
        },
    )
    monkeypatch.setattr(publisher._publisher, "update_game_marketing", fake_update_game_marketing)
    monkeypatch.setattr(publisher._quality, "capture_presentation_screenshot", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(publisher._telegram, "broadcast_launch_announcement", lambda **kwargs: sent_payload.update(kwargs))
    publisher._archiver = None

    result = __import__("asyncio").run(
        publisher.publish(
            slug="lowpoly-siege",
            game_name="Lowpoly Siege",
            genre="topdown shooter",
            html_content="<html>ok</html>",
            genre_brief={"asset_pack_key": "topdown_lowpoly_pack_v1"},
        )
    )

    assert result["presentation_status"] == "repair_pending"
    assert result["thumbnail_url"] is None
    assert update_calls[-1]["visibility"] == "public"
    assert update_calls[-1]["thumbnail_url"] is None
    assert update_calls[-1]["hero_image_url"] is None
    assert sent_payload == {}


def test_publish_synchronizes_canonical_thumbnail_fields_when_screenshot_exists(monkeypatch) -> None:
    publisher = SessionPublisher(
        Settings(
            supabase_url="",
            supabase_service_role_key="",
            google_application_credentials="",
            public_portal_base_url="https://arcade.example.com",
        )
    )

    update_calls: list[dict[str, object]] = []
    screenshot_url = "https://cdn.example.com/games/lowpoly-siege/canonical.png"

    def fake_update_game_marketing(**kwargs: object) -> bool:
        update_calls.append(dict(kwargs))
        return True

    monkeypatch.setattr(
        publisher._publisher,
        "publish_game",
        lambda **_: {
            "status": "published",
            "public_url": "https://cdn.example.com/games/lowpoly-siege/index.html",
            "game_id": "game-1",
        },
    )
    monkeypatch.setattr(publisher._publisher, "upload_screenshot", lambda **_: screenshot_url)
    monkeypatch.setattr(publisher._publisher, "update_game_marketing", fake_update_game_marketing)
    monkeypatch.setattr(publisher._quality, "capture_presentation_screenshot", lambda *_args, **_kwargs: b"png")
    monkeypatch.setattr(publisher._telegram, "broadcast_launch_announcement", lambda **_: None)
    publisher._archiver = None

    result = __import__("asyncio").run(
        publisher.publish(
            slug="lowpoly-siege",
            game_name="Lowpoly Siege",
            genre="topdown shooter",
            html_content="<html>ok</html>",
            genre_brief={"asset_pack_key": "topdown_lowpoly_pack_v1"},
        )
    )

    assert result["presentation_status"] == "ready"
    assert result["thumbnail_url"] == screenshot_url
    assert update_calls[-1]["visibility"] == "public"
    assert update_calls[-1]["screenshot_url"] == screenshot_url
    assert update_calls[-1]["thumbnail_url"] == screenshot_url
    assert update_calls[-1]["hero_image_url"] == screenshot_url
