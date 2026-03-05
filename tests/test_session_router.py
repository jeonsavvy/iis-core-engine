from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.agent_loop import AgentActivity, AgentLoopResult
from app.api.v1.session_router import router as session_router


class FakeSessionStore:
    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}
        self.histories: dict[str, list[dict[str, Any]]] = {}
        self.events: dict[str, list[dict[str, Any]]] = {}
        self.publish_rows: list[dict[str, Any]] = []
        self._counter = 0

    def _id(self) -> str:
        self._counter += 1
        return f"s-{self._counter}"

    def create_session(self, *, user_id: str | None = None, title: str = "", genre: str = "") -> dict[str, Any]:
        sid = self._id()
        row = {
            "id": sid,
            "user_id": user_id,
            "title": title or f"Game #{sid}",
            "genre": genre,
            "status": "active",
            "current_html": "",
            "score": 0,
            "created_at": "2026-03-05T00:00:00Z",
            "updated_at": "2026-03-05T00:00:00Z",
        }
        self.sessions[sid] = row
        self.histories[sid] = []
        self.events[sid] = []
        return row

    def list_sessions(self, *, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        rows = list(self.sessions.values())
        if status:
            rows = [r for r in rows if r.get("status") == status]
        return rows[:limit]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        return self.sessions.get(session_id)

    def update_session_html(self, session_id: str, html: str, score: int = 0) -> None:
        row = self.sessions[session_id]
        row["current_html"] = html
        row["score"] = score

    def update_session_status(self, session_id: str, status: str) -> None:
        self.sessions[session_id]["status"] = status

    def delete_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)
        self.histories.pop(session_id, None)
        self.events.pop(session_id, None)

    def add_conversation_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.histories[session_id].append(
            {
                "role": role,
                "content": content,
                "metadata": metadata or {},
                "created_at": "2026-03-05T00:00:00Z",
            }
        )

    def get_conversation_history(self, session_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        return self.histories.get(session_id, [])[:limit]

    def add_session_event(
        self,
        *,
        session_id: str,
        event_type: str,
        agent: str | None = None,
        action: str | None = None,
        summary: str = "",
        score: int | None = None,
        before_score: int | None = None,
        after_score: int | None = None,
        decision_reason: str = "",
        input_signal: str = "",
        change_impact: str = "",
        confidence: float | None = None,
        error_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = {
            "id": f"e-{len(self.events[session_id]) + 1}",
            "session_id": session_id,
            "event_type": event_type,
            "agent": agent,
            "action": action,
            "summary": summary,
            "score": score,
            "before_score": before_score,
            "after_score": after_score,
            "decision_reason": decision_reason,
            "input_signal": input_signal,
            "change_impact": change_impact,
            "confidence": confidence,
            "error_code": error_code,
            "metadata": metadata or {},
            "created_at": f"2026-03-05T00:00:{len(self.events[session_id]) + 1:02d}Z",
        }
        self.events[session_id].append(row)
        return row

    def get_session_events(self, session_id: str, *, limit: int = 50, cursor: str | None = None) -> list[dict[str, Any]]:
        rows = list(self.events.get(session_id, []))
        if cursor:
            rows = [row for row in rows if str(row["created_at"]) < cursor]
        rows.reverse()
        return rows[:limit]

    def record_publish(
        self,
        *,
        session_id: str,
        game_id: str | None,
        game_slug: str,
        play_url: str,
        public_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.publish_rows.append(
            {
                "session_id": session_id,
                "game_id": game_id,
                "game_slug": game_slug,
                "play_url": play_url,
                "public_url": public_url,
                "metadata": metadata or {},
            }
        )


@dataclass
class FakeLoop:
    result: AgentLoopResult

    async def run(self, **_: Any) -> AgentLoopResult:
        return self.result


class FakePublisher:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def publish(self, *, slug: str, game_name: str, genre: str, html_content: str) -> dict[str, Any]:
        self.calls.append({"slug": slug, "game_name": game_name, "genre": genre, "html_content": html_content})
        return {
            "success": True,
            "public_url": f"https://cdn.example.com/games/{slug}/index.html",
            "game_id": "game-1",
            "game_slug": slug,
            "play_url": f"/play/{slug}",
        }


def make_client(*, with_store: bool = True, loop_result: AgentLoopResult | None = None) -> tuple[TestClient, FakeSessionStore | None]:
    app = FastAPI()
    app.include_router(session_router, prefix="/api/v1")

    store = FakeSessionStore() if with_store else None
    if store is not None:
        app.state.session_store = store

    app.state.agent_loop = FakeLoop(
        loop_result
        or AgentLoopResult(
            html="<html>ok</html>",
            final_score=88,
            generation_source="vertex",
            activities=[
                AgentActivity(
                    agent="visual_qa",
                    action="evaluate",
                    summary="looks good",
                    score=80,
                    decision_reason="visual_metrics_assessment",
                    input_signal="genre=arcade",
                    change_impact="quality_pass",
                    confidence=0.8,
                    before_score=0,
                    after_score=80,
                )
            ],
        )
    )
    app.state.publisher_service = FakePublisher()
    return TestClient(app), store


def test_session_requires_store() -> None:
    client, _ = make_client(with_store=False)
    response = client.post("/api/v1/sessions", json={"title": "A"})
    assert response.status_code == 503
    assert "Session store unavailable" in response.text


def test_prompt_fail_fast_when_agent_loop_errors() -> None:
    client, store = make_client(
        loop_result=AgentLoopResult(
            html="",
            final_score=0,
            generation_source="error",
            auto_refined=False,
            refinement_rounds=0,
            error="vertex_not_configured",
            activities=[],
        )
    )
    assert store is not None

    created = client.post("/api/v1/sessions", json={"title": "T", "genre_hint": "arcade"})
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/prompt",
        json={"prompt": "make game", "auto_qa": True, "stream": False},
    )
    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "prompt_failed"
    session_row = store.get_session(session_id)
    assert session_row is not None
    assert session_row["current_html"] == ""


def test_prompt_records_event_when_agent_loop_raises_exception() -> None:
    client, store = make_client()
    assert store is not None

    class RaisingLoop:
        async def run(self, **_: Any) -> AgentLoopResult:  # pragma: no cover - exercised by test
            raise RuntimeError("loop_crashed")

    client.app.state.agent_loop = RaisingLoop()

    created = client.post("/api/v1/sessions", json={"title": "T", "genre_hint": "arcade"})
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/prompt",
        json={"prompt": "make game", "auto_qa": True, "stream": False},
    )
    assert response.status_code == 502
    payload = response.json()
    assert payload["detail"]["error"] == "prompt_failed"
    assert payload["detail"]["code"] == "agent_loop_exception"

    events = store.get_session_events(session_id, limit=20)
    assert any(event.get("error_code") == "agent_loop_exception" for event in events)


def test_prompt_response_contains_activity_contract_and_events() -> None:
    client, _ = make_client()

    created = client.post("/api/v1/sessions", json={"title": "T", "genre_hint": "arcade"})
    session_id = created.json()["session_id"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/prompt",
        json={"prompt": "add enemies", "auto_qa": True, "stream": False},
    )
    assert response.status_code == 200
    payload = response.json()

    activity = payload["activities"][0]
    assert activity["agent"] == "visual_qa"
    assert "decision_reason" in activity
    assert "input_signal" in activity
    assert "change_impact" in activity
    assert "confidence" in activity
    assert "error_code" in activity

    events_res = client.get(f"/api/v1/sessions/{session_id}/events")
    assert events_res.status_code == 200
    events_payload = events_res.json()
    assert len(events_payload["events"]) >= 3


def test_cancel_blocks_prompt_and_publish_returns_play_slug_url() -> None:
    client, store = make_client()
    assert store is not None

    created = client.post("/api/v1/sessions", json={"title": "Road Rush", "genre_hint": "racing"})
    session_id = created.json()["session_id"]

    prompt = client.post(
        f"/api/v1/sessions/{session_id}/prompt",
        json={"prompt": "build racing game", "auto_qa": True, "stream": False},
    )
    assert prompt.status_code == 200

    publish = client.post(
        f"/api/v1/sessions/{session_id}/publish",
        json={"slug": "road-rush"},
    )
    assert publish.status_code == 200
    assert publish.json()["game_url"] == "/play/road-rush"

    cancel = client.post(f"/api/v1/sessions/{session_id}/cancel")
    assert cancel.status_code == 200

    second_prompt = client.post(
        f"/api/v1/sessions/{session_id}/prompt",
        json={"prompt": "more effects", "auto_qa": True, "stream": False},
    )
    assert second_prompt.status_code == 409
