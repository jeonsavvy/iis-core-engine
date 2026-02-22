from pathlib import Path

from app.core.config import Settings
from app.services.http_client import ExternalCallError
from app.services.x_service import XService


def test_x_service_blocks_for_day_after_error(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        x_auto_post_enabled=True,
        x_bearer_token="token",
        x_quota_state_file=str(tmp_path / "x_state.json"),
    )

    def fail_request(*_args, **_kwargs):
        raise ExternalCallError("network fail")

    monkeypatch.setattr("app.services.x_service.request_with_retry", fail_request)
    service = XService(settings)

    first = service.publish_update("game-1", "hello")
    second = service.publish_update("game-1", "hello again")

    assert first["status"] == "error"
    assert second["status"] == "skipped"
    assert "blocked for today" in second["reason"]


def test_x_service_persists_quota_state(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        x_auto_post_enabled=True,
        x_bearer_token="token",
        x_posts_per_game_per_day=1,
        x_quota_state_file=str(tmp_path / "x_state.json"),
    )

    def ok_request(*_args, **_kwargs):
        class DummyResponse:
            status_code = 201

        return DummyResponse()

    monkeypatch.setattr("app.services.x_service.request_with_retry", ok_request)

    service = XService(settings)
    first = service.publish_update("game-2", "launch post")
    assert first["status"] == "posted"

    reloaded_service = XService(settings)
    second = reloaded_service.publish_update("game-2", "second post")
    assert second["status"] == "skipped"
    assert "daily quota reached" in second["reason"]
