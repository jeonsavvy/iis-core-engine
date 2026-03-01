from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.orchestration.nodes.echo import run
from app.schemas.pipeline import PipelineStatus


def _state_with_publish_result() -> dict:
    return {
        "pipeline_id": uuid4(),
        "keyword": "아카이브 링크 검증",
        "qa_attempt": 0,
        "max_qa_loops": 3,
        "fail_qa_until": 0,
        "build_iteration": 0,
        "needs_rebuild": False,
        "status": PipelineStatus.RUNNING,
        "reason": None,
        "logs": [],
        "flushed_log_count": 0,
        "log_sink": None,
        "outputs": {
            "game_slug": "game-portal-link",
            "game_name": "Portal Link Racer",
            "game_genre": "arcade",
            "gdd": {"objective": "장애물 회피와 타이밍 기반 드리프트"},
            "publish_result": {
                "public_url": "https://storage.example.com/games/game-portal-link/index.html",
                "game_id": "11111111-1111-1111-1111-111111111111",
            },
        },
    }


def test_echo_prefers_portal_play_link_when_configured() -> None:
    state = _state_with_publish_result()
    captured = {}
    registry_rows: list[dict] = []

    def _broadcast(message: str) -> dict[str, str]:
        captured["message"] = message
        return {"status": "posted"}

    deps = SimpleNamespace(
        repository=SimpleNamespace(
            get_pipeline=lambda _pipeline_id: SimpleNamespace(
                metadata={"operator_control": {"pause_requested": False, "cancel_requested": False}}
            ),
            upsert_asset_registry_entry=lambda row: registry_rows.append(row),
        ),
        vertex_service=SimpleNamespace(
            generate_marketing_copy=lambda **_: SimpleNamespace(
                payload={"marketing_copy": "테스트 홍보 문구"},
                meta={"generation_source": "stub", "model": "stub", "latency_ms": 1, "usage": {}},
            ),
            generate_ai_review=lambda **_: SimpleNamespace(
                payload={"ai_review": "테스트 디자이너 코멘트"},
                meta={"generation_source": "stub", "model": "stub", "latency_ms": 1, "usage": {}},
            )
        ),
        telegram_service=SimpleNamespace(
            settings=SimpleNamespace(
                public_games_base_url="https://storage.example.com/games",
                public_portal_base_url="https://iis-arcade-portal.jeonsavvy.workers.dev",
            ),
            broadcast_message=_broadcast,
        ),
        publisher_service=SimpleNamespace(update_game_marketing=lambda **_: True),
    )

    next_state = run(cast(Any, state), cast(Any, deps))
    assert next_state["status"] == PipelineStatus.SUCCESS
    assert "/play/11111111-1111-1111-1111-111111111111" in captured["message"]
    assert registry_rows
    assert registry_rows[0]["game_slug"] == "game-portal-link"

    echo_log = next(log for log in next_state["logs"] if log.stage.value == "report")
    assert echo_log.metadata["resolved_public_url"].endswith("/play/11111111-1111-1111-1111-111111111111")


def test_echo_uses_storage_url_when_portal_base_is_missing() -> None:
    state = _state_with_publish_result()
    captured = {}
    registry_rows: list[dict] = []

    def _broadcast(message: str) -> dict[str, str]:
        captured["message"] = message
        return {"status": "posted"}

    deps = SimpleNamespace(
        repository=SimpleNamespace(
            get_pipeline=lambda _pipeline_id: SimpleNamespace(
                metadata={"operator_control": {"pause_requested": False, "cancel_requested": False}}
            ),
            upsert_asset_registry_entry=lambda row: registry_rows.append(row),
        ),
        vertex_service=SimpleNamespace(
            generate_marketing_copy=lambda **_: SimpleNamespace(
                payload={"marketing_copy": "테스트 홍보 문구"},
                meta={"generation_source": "stub", "model": "stub", "latency_ms": 1, "usage": {}},
            ),
            generate_ai_review=lambda **_: SimpleNamespace(
                payload={"ai_review": "테스트 디자이너 코멘트"},
                meta={"generation_source": "stub", "model": "stub", "latency_ms": 1, "usage": {}},
            )
        ),
        telegram_service=SimpleNamespace(
            settings=SimpleNamespace(
                public_games_base_url="https://storage.example.com/games",
                public_portal_base_url=None,
            ),
            broadcast_message=_broadcast,
        ),
        publisher_service=SimpleNamespace(update_game_marketing=lambda **_: True),
    )

    next_state = run(cast(Any, state), cast(Any, deps))
    assert next_state["status"] == PipelineStatus.SUCCESS
    assert "https://storage.example.com/games/game-portal-link/index.html" in captured["message"]
    assert registry_rows
