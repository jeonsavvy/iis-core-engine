from __future__ import annotations

import base64
from datetime import datetime

import pytest

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
    monkeypatch.setattr(publisher._quality, "capture_presentation_screenshot", lambda *_args, **_kwargs: b"png")
    monkeypatch.setattr(publisher._publisher, "upload_screenshot", lambda **_: "https://cdn.example.com/games/neon-drift/canonical.png")
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


def test_publish_uses_selected_thumbnail_without_runtime_capture(monkeypatch) -> None:
    publisher = SessionPublisher(
        Settings(
            supabase_url="",
            supabase_service_role_key="",
            google_application_credentials="",
        )
    )

    uploaded: dict[str, object] = {}

    monkeypatch.setattr(
        publisher._publisher,
        "publish_game",
        lambda **_: {
            "status": "published",
            "public_url": "https://cdn.example.com/games/neon-drift/index.html",
            "game_id": "game-1",
        },
    )
    monkeypatch.setattr(
        publisher._publisher,
        "upload_screenshot",
        lambda **kwargs: uploaded.update(kwargs) or "https://cdn.example.com/games/neon-drift/manual.webp",
    )
    monkeypatch.setattr(publisher._publisher, "update_game_marketing", lambda **_: True)
    monkeypatch.setattr(
        publisher._quality,
        "capture_presentation_screenshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("runtime capture should not run")),
    )
    monkeypatch.setattr(publisher._telegram, "broadcast_launch_announcement", lambda **_: None)
    publisher._archiver = None

    result = __import__("asyncio").run(
        publisher.publish(
            slug="neon-drift",
            game_name="Neon Drift",
            genre="racing",
            html_content="<html>ok</html>",
            selected_thumbnail_bytes=b"manual-image",
            selected_thumbnail_mime_type="image/webp",
            selected_thumbnail_name="manual.webp",
        )
    )

    assert result["thumbnail_url"] == "https://cdn.example.com/games/neon-drift/manual.webp"
    assert uploaded["screenshot_bytes"] == b"manual-image"
    assert uploaded["mime_type"] == "image/webp"


def test_generate_publish_thumbnail_candidates_returns_data_urls(monkeypatch) -> None:
    publisher = SessionPublisher(
        Settings(
            supabase_url="",
            supabase_service_role_key="",
            google_application_credentials="",
        )
    )
    monkeypatch.setattr(
        publisher._quality,
        "capture_publish_thumbnail_candidates",
        lambda *_args, **_kwargs: [
            {"label": "자동 캡처 1", "reason": "auto", "bytes": b"candidate-1"},
            {"label": "자동 캡처 2", "reason": "auto", "bytes": b"candidate-2"},
        ],
    )

    result = publisher.generate_publish_thumbnail_candidates(html_content="<html>ok</html>")

    assert len(result) == 2
    assert result[0]["data_url"] == f"data:image/png;base64,{base64.b64encode(b'candidate-1').decode('ascii')}"
    assert result[0]["source"] == "auto"


def test_publish_fails_fast_when_actual_runtime_capture_is_missing(monkeypatch) -> None:
    publisher = SessionPublisher(
        Settings(
            supabase_url="",
            supabase_service_role_key="",
            google_application_credentials="",
        )
    )

    publish_calls: list[dict[str, object]] = []
    sent_payload: dict[str, object] = {}
    update_calls: list[dict[str, object]] = []

    def fake_publish_game(**kwargs: object) -> dict[str, object]:
        publish_calls.append(dict(kwargs))
        return {
            "status": "published",
            "public_url": "https://cdn.example.com/games/golden-isles-flight/index.html",
            "game_id": "game-1",
        }

    monkeypatch.setattr(publisher._publisher, "publish_game", fake_publish_game)

    def fake_update_game_marketing(**kwargs: object) -> bool:
        update_calls.append(dict(kwargs))
        return True

    monkeypatch.setattr(publisher._publisher, "update_game_marketing", fake_update_game_marketing)
    monkeypatch.setattr(publisher._quality, "capture_presentation_screenshot", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(publisher._telegram, "broadcast_launch_announcement", lambda **kwargs: sent_payload.update(kwargs))
    publisher._archiver = None

    with pytest.raises(RuntimeError, match="actual_presentation_screenshot_missing"):
        __import__("asyncio").run(
            publisher.publish(
                slug="golden-isles-flight",
                game_name="Golden Isles Flight",
                genre="flight",
                html_content="<html>ok</html>",
                genre_brief={"asset_pack_key": "island_flight_pack_v1"},
            )
        )

    assert publish_calls == []
    assert update_calls == []
    assert sent_payload == {}


def test_publish_marks_game_hidden_when_actual_screenshot_upload_fails(monkeypatch) -> None:
    publisher = SessionPublisher(
        Settings(
            supabase_url="",
            supabase_service_role_key="",
            google_application_credentials="",
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
    monkeypatch.setattr(publisher._quality, "capture_presentation_screenshot", lambda *_args, **_kwargs: b"png")
    monkeypatch.setattr(publisher._publisher, "upload_screenshot", lambda **_: None)
    monkeypatch.setattr(publisher._telegram, "broadcast_launch_announcement", lambda **kwargs: sent_payload.update(kwargs))
    publisher._archiver = None

    with pytest.raises(RuntimeError, match="actual_presentation_screenshot_upload_failed"):
        __import__("asyncio").run(
            publisher.publish(
                slug="lowpoly-siege",
                game_name="Lowpoly Siege",
                genre="unknown",
                html_content="<html>ok</html>",
                genre_brief={"asset_pack_key": "unknown_pack"},
            )
        )

    assert update_calls[-1]["visibility"] == "hidden"
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
            slug="golden-isles-flight",
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


def test_repair_presentation_contract_html_appends_publish_override_hook() -> None:
    publisher = SessionPublisher(
        Settings(
            supabase_url="",
            supabase_service_role_key="",
            google_application_credentials="",
        )
    )

    repaired, transforms = publisher.repair_presentation_contract_html(
        html_content="<html><body><canvas></canvas><script>window.__iis_game_boot_ok=true;window.IISLeaderboard={};requestAnimationFrame(()=>{});</script></body></html>"
    )

    assert "iis-publish-presentation-repair" in repaired
    assert "__iisPreparePresentationCapture" in repaired
    assert "inject_publish_presentation_repair" in transforms


def test_repair_presentation_contract_html_does_not_inject_visual_overlay_shim() -> None:
    publisher = SessionPublisher(
        Settings(
            supabase_url="",
            supabase_service_role_key="",
            google_application_credentials="",
        )
    )

    repaired, _transforms = publisher.repair_presentation_contract_html(
        html_content="<html><body><canvas></canvas><script>window.__iis_game_boot_ok=true;window.IISLeaderboard={};requestAnimationFrame(()=>{});</script></body></html>"
    )

    assert "iis-visual-contract-shim" not in repaired
