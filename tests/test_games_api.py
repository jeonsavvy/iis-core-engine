from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException

from app.api.v1.endpoints.games import delete_game
from app.schemas.games import DeleteGameRequest


class StubGameAdminService:
    result: dict[str, Any] = {}
    last_call: dict[str, Any] | None = None

    def __init__(self, _settings: Any) -> None:
        pass

    def delete_game(
        self,
        *,
        game_id: UUID,
        delete_storage: bool,
        delete_archive: bool,
        reason: str,
    ) -> dict[str, Any]:
        type(self).last_call = {
            "game_id": game_id,
            "delete_storage": delete_storage,
            "delete_archive": delete_archive,
            "reason": reason,
        }
        return dict(type(self).result)


def _set_stub_result(monkeypatch, result: dict[str, Any]) -> None:
    from app.api.v1.endpoints import games as games_endpoint

    StubGameAdminService.result = result
    StubGameAdminService.last_call = None
    monkeypatch.setattr(games_endpoint, "GameAdminService", StubGameAdminService)


def test_delete_game_returns_response_when_service_succeeds(monkeypatch) -> None:
    pipeline_id = uuid4()
    _set_stub_result(
        monkeypatch,
        {
            "status": "ok",
            "game_id": str(pipeline_id),
            "slug": "neon-drift",
            "deleted": {"db": True, "storage": True, "archive": True},
            "details": {"reason": "admin_manual_delete"},
        },
    )

    response = delete_game(
        game_id=pipeline_id,
        payload=DeleteGameRequest(delete_storage=True, delete_archive=True, reason="admin_manual_delete"),
    )

    assert response.status == "ok"
    assert response.game_id == pipeline_id
    assert response.slug == "neon-drift"
    assert StubGameAdminService.last_call is not None
    assert StubGameAdminService.last_call["delete_storage"] is True
    assert StubGameAdminService.last_call["delete_archive"] is True


def test_delete_game_raises_404_for_not_found(monkeypatch) -> None:
    game_id = uuid4()
    _set_stub_result(
        monkeypatch,
        {"status": "not_found", "reason": "game_not_found", "game_id": str(game_id)},
    )

    try:
        delete_game(game_id=game_id, payload=DeleteGameRequest())
    except HTTPException as exc:
        assert exc.status_code == 404
        assert isinstance(exc.detail, dict)
        assert exc.detail.get("status") == "not_found"
    else:
        raise AssertionError("expected HTTPException for not_found")


def test_delete_game_raises_500_for_service_error(monkeypatch) -> None:
    game_id = uuid4()
    _set_stub_result(
        monkeypatch,
        {"status": "error", "reason": "supabase client is not configured", "game_id": str(game_id)},
    )

    try:
        delete_game(game_id=game_id, payload=DeleteGameRequest())
    except HTTPException as exc:
        assert exc.status_code == 500
        assert isinstance(exc.detail, dict)
        assert exc.detail.get("status") == "error"
    else:
        raise AssertionError("expected HTTPException for error")


def test_delete_game_raises_409_for_partial_error(monkeypatch) -> None:
    game_id = uuid4()
    _set_stub_result(
        monkeypatch,
        {
            "status": "partial_error",
            "reason": "storage_delete_failed",
            "game_id": str(game_id),
            "slug": "neon-drift",
            "deleted": {"db": False, "storage": False, "archive": False},
            "details": {"storage": {"status": "error"}},
        },
    )

    try:
        delete_game(game_id=game_id, payload=DeleteGameRequest())
    except HTTPException as exc:
        assert exc.status_code == 409
        assert isinstance(exc.detail, dict)
        assert exc.detail.get("status") == "partial_error"
    else:
        raise AssertionError("expected HTTPException for partial_error")
