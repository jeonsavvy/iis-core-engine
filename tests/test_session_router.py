from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.agent_loop import AgentActivity, AgentLoopResult
from app.agents.codegen_agent import CodegenResult
from app.api.v1.session_router import router as session_router
from app.services.vertex_service import BuilderRoute, VertexCapacityExhausted


class FakeSessionStore:
    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}
        self.histories: dict[str, list[dict[str, Any]]] = {}
        self.events: dict[str, list[dict[str, Any]]] = {}
        self.publish_rows: list[dict[str, Any]] = []
        self.runs: dict[str, dict[str, Any]] = {}
        self.issues: dict[str, dict[str, Any]] = {}
        self.issue_proposals: dict[str, dict[str, Any]] = {}
        self.publish_approvals: dict[str, list[dict[str, Any]]] = {}
        self._counter = 0

    def _id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter}"

    def create_session(self, *, user_id: str | None = None, title: str = "", genre: str = "") -> dict[str, Any]:
        sid = self._id("s")
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
        self.publish_approvals[sid] = []
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

    def update_session(self, session_id: str, **fields: Any) -> None:
        self.sessions[session_id].update(fields)

    def delete_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)
        self.histories.pop(session_id, None)
        self.events.pop(session_id, None)
        self.publish_approvals.pop(session_id, None)

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
            "id": self._id("e"),
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

    def create_session_run(self, *, session_id: str, prompt: str, auto_qa: bool, status: str = "queued") -> dict[str, Any]:
        run_id = self._id("run")
        row = {
            "id": run_id,
            "session_id": session_id,
            "prompt": prompt,
            "auto_qa": auto_qa,
            "status": status,
            "error_code": None,
            "error_detail": "",
            "final_score": 0,
            "activities": [],
            "created_at": "2026-03-05T00:00:00Z",
            "started_at": None,
            "finished_at": None,
            "attempt_count": 0,
            "retry_after_seconds": None,
            "model_name": None,
            "model_location": None,
            "fallback_used": False,
            "capacity_error": None,
            "updated_at": "2026-03-05T00:00:00Z",
        }
        self.runs[run_id] = row
        return row

    def get_session_run(self, session_id: str, run_id: str) -> dict[str, Any] | None:
        run = self.runs.get(run_id)
        if run and run.get("session_id") == session_id:
            return run
        return None

    def update_session_run(self, session_id: str, run_id: str, **fields: Any) -> None:
        run = self.runs[run_id]
        if run["session_id"] != session_id:
            return
        run.update(fields)

    def create_session_issue(
        self,
        *,
        session_id: str,
        title: str,
        details: str,
        category: str,
        created_by: str = "master_admin",
    ) -> dict[str, Any]:
        row = {
            "id": self._id("issue"),
            "session_id": session_id,
            "title": title,
            "details": details,
            "category": category,
            "status": "open",
            "created_by": created_by,
            "created_at": "2026-03-05T00:00:00Z",
            "updated_at": "2026-03-05T00:00:00Z",
        }
        self.issues[row["id"]] = row
        return row

    def get_session_issue(self, session_id: str, issue_id: str) -> dict[str, Any] | None:
        issue = self.issues.get(issue_id)
        if issue and issue.get("session_id") == session_id:
            return issue
        return None

    def update_session_issue(self, session_id: str, issue_id: str, **fields: Any) -> None:
        issue = self.issues[issue_id]
        if issue["session_id"] != session_id:
            return
        issue.update(fields)

    def create_issue_proposal(
        self,
        *,
        session_id: str,
        issue_id: str,
        summary: str,
        proposal_prompt: str,
        preview_html: str,
        proposed_by: str = "codegen",
    ) -> dict[str, Any]:
        row = {
            "id": self._id("proposal"),
            "session_id": session_id,
            "issue_id": issue_id,
            "summary": summary,
            "proposal_prompt": proposal_prompt,
            "preview_html": preview_html,
            "status": "proposed",
            "proposed_by": proposed_by,
            "created_at": "2026-03-05T00:00:00Z",
            "updated_at": "2026-03-05T00:00:00Z",
        }
        self.issue_proposals[row["id"]] = row
        return row

    def get_issue_proposal(self, session_id: str, issue_id: str, proposal_id: str) -> dict[str, Any] | None:
        proposal = self.issue_proposals.get(proposal_id)
        if proposal and proposal.get("session_id") == session_id and proposal.get("issue_id") == issue_id:
            return proposal
        return None

    def get_latest_issue_proposal(self, session_id: str, issue_id: str) -> dict[str, Any] | None:
        proposals = [
            proposal
            for proposal in self.issue_proposals.values()
            if proposal.get("session_id") == session_id and proposal.get("issue_id") == issue_id
        ]
        return proposals[-1] if proposals else None

    def update_issue_proposal(self, session_id: str, issue_id: str, proposal_id: str, **fields: Any) -> None:
        proposal = self.issue_proposals[proposal_id]
        if proposal["session_id"] != session_id or proposal["issue_id"] != issue_id:
            return
        proposal.update(fields)

    def create_publish_approval(
        self,
        *,
        session_id: str,
        approved_by: str = "master_admin",
        note: str = "",
    ) -> dict[str, Any]:
        row = {
            "id": self._id("approval"),
            "session_id": session_id,
            "approved_by": approved_by,
            "note": note,
            "approved_at": "2026-03-05T00:00:00Z",
        }
        self.publish_approvals.setdefault(session_id, []).append(row)
        return row

    def get_latest_publish_approval(self, session_id: str) -> dict[str, Any] | None:
        rows = self.publish_approvals.get(session_id, [])
        return rows[-1] if rows else None

    def clear_publish_approvals(self, session_id: str) -> None:
        self.publish_approvals[session_id] = []


@dataclass
class FakeLoop:
    result: AgentLoopResult
    delay_seconds: float = 0.0
    error: Exception | None = None

    async def run(self, **_: Any) -> AgentLoopResult:
        if self.delay_seconds > 0:
            await asyncio.sleep(self.delay_seconds)
        if self.error is not None:
            raise self.error
        return self.result


class FakeCodegen:
    async def generate(self, **_: Any) -> CodegenResult:
        return CodegenResult(html="<html>patched</html>", generation_source="vertex")


class FakePlaytester:
    def __init__(self, *, boots_ok: bool = True, issues: list[str] | None = None) -> None:
        self.boots_ok = boots_ok
        self.issues = issues or []

    async def test(self, *, html_content: str) -> Any:
        return type(
            "FakePlaytestResult",
            (),
            {
                "boots_ok": self.boots_ok,
                "has_errors": bool(self.issues),
                "console_errors": list(self.issues),
                "issues": list(self.issues),
                "fatal_issues": list(self.issues if not self.boots_ok else []),
                "feedback": "\n".join(self.issues) if self.issues else "ok",
                "score": 0,
            },
        )()


class FakePublisher:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.presentation_ok = True
        self.presentation_issues: list[str] = []

    async def publish(
        self,
        *,
        slug: str,
        game_name: str,
        genre: str,
        html_content: str,
        recent_history: list[dict[str, Any]] | None = None,
        recent_events: list[dict[str, Any]] | None = None,
        genre_brief: dict[str, Any] | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "slug": slug,
                "game_name": game_name,
                "genre": genre,
                "html_content": html_content,
                "recent_history": recent_history or [],
                "recent_events": recent_events or [],
                "genre_brief": genre_brief or {},
                "created_by": created_by,
            }
        )
        return {
            "success": True,
            "public_url": f"https://cdn.example.com/games/{slug}/index.html",
            "game_id": "game-1",
            "game_slug": slug,
            "play_url": f"/play/{slug}",
            "presentation_status": "ready",
            "thumbnail_url": f"https://cdn.example.com/games/{slug}/canonical.png",
            "marketing_summary": f"{game_name} summary",
            "play_overview": ["overview"],
            "controls_guide": ["controls"],
        }

    def validate_presentation_contract(self, *, html_content: str) -> tuple[bool, list[str]]:
        return self.presentation_ok, list(self.presentation_issues)


def make_client(
    *,
    loop_result: AgentLoopResult | None = None,
    delay_seconds: float = 0.0,
    playtester: FakePlaytester | None = None,
) -> tuple[TestClient, FakeSessionStore]:
    app = FastAPI()
    app.include_router(session_router, prefix="/api/v1")

    store = FakeSessionStore()
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
        ),
        delay_seconds=delay_seconds,
    )
    app.state.codegen_agent = FakeCodegen()
    app.state.playtester_agent = playtester or FakePlaytester()
    app.state.publisher_service = FakePublisher()
    app.state.session_run_tasks = {}
    app.state.prompt_run_semaphore = asyncio.Semaphore(1)
    return TestClient(app), store


def wait_run_terminal(client: TestClient, session_id: str, run_id: str) -> dict[str, Any]:
    deadline = time.time() + 2.0
    latest: dict[str, Any] = {}
    while time.time() < deadline:
        response = client.get(f"/api/v1/sessions/{session_id}/runs/{run_id}")
        assert response.status_code == 200
        latest = response.json()
        if latest["status"] in {"succeeded", "failed", "cancelled"}:
            return latest
        time.sleep(0.05)
    return latest


def create_session(client: TestClient) -> str:
    created = client.post("/api/v1/sessions", json={"title": "T", "genre_hint": "arcade"})
    assert created.status_code == 200
    payload = cast(dict[str, Any], created.json())
    return str(payload["session_id"])


def create_named_session(client: TestClient, title: str, genre_hint: str = "arcade") -> str:
    created = client.post("/api/v1/sessions", json={"title": title, "genre_hint": genre_hint})
    assert created.status_code == 200
    payload = cast(dict[str, Any], created.json())
    return str(payload["session_id"])


def test_prompt_is_async_and_run_succeeds() -> None:
    client, store = make_client()
    session_id = create_session(client)

    response = client.post(f"/api/v1/sessions/{session_id}/prompt", json={"prompt": "make game", "auto_qa": True})
    assert response.status_code == 202
    payload = response.json()
    run_id = payload["run_id"]
    assert payload["status"] == "queued"

    run = wait_run_terminal(client, session_id, run_id)
    assert run["status"] == "succeeded"
    assert run["final_score"] == 0
    assert run["current_html"] == "<html>ok</html>"

    session = store.get_session(session_id)
    assert session is not None
    assert session["current_html"] == "<html>ok</html>"


def test_generic_session_title_is_replaced_for_publish_name() -> None:
    client, store = make_client()
    session_id = create_named_session(client, "New Session", "flight")

    queued = client.post(
        f"/api/v1/sessions/{session_id}/prompt",
        json={"prompt": "따뜻한 일몰 조명 아래 섬과 바다 위를 프로펠러 비행기로 돌아다니며 링을 통과하는 플라이트 게임"},
    )
    run_id = queued.json()["run_id"]
    run = wait_run_terminal(client, session_id, run_id)
    assert run["status"] == "succeeded"

    approved = client.post(f"/api/v1/sessions/{session_id}/approve-publish", json={"note": "looks good"})
    assert approved.status_code == 200
    published = client.post(f"/api/v1/sessions/{session_id}/publish", json={"slug": "golden-isles-flight"})
    assert published.status_code == 200
    publisher_calls = client.app.state.publisher_service.calls
    assert publisher_calls[-1]["game_name"] == "Golden Isles Flight"


def test_create_session_tracks_actor_id_from_headers() -> None:
    client, store = make_client()

    created = client.post(
        "/api/v1/sessions",
        json={"title": "Creator Session", "genre_hint": "arcade"},
        headers={"X-IIS-Actor-Id": "creator-1", "X-IIS-Actor-Role": "creator"},
    )

    assert created.status_code == 200
    session_id = created.json()["session_id"]
    assert store.sessions[session_id]["user_id"] == "creator-1"


def test_issue_and_approval_store_actor_id_from_headers() -> None:
    client, store = make_client()
    session_id = create_session(client)

    issue_response = client.post(
        f"/api/v1/sessions/{session_id}/issues",
        json={"title": "버그", "details": "충돌 판정 이상"},
        headers={"X-IIS-Actor-Id": "creator-1", "X-IIS-Actor-Role": "creator"},
    )
    assert issue_response.status_code == 200
    issue_id = issue_response.json()["issue_id"]
    assert store.issues[issue_id]["created_by"] == "creator-1"

    approve_response = client.post(
        f"/api/v1/sessions/{session_id}/approve-publish",
        json={"note": "ship it"},
        headers={"X-IIS-Actor-Id": "admin-1", "X-IIS-Actor-Role": "master_admin"},
    )
    assert approve_response.status_code == 200
    assert store.publish_approvals[session_id][-1]["approved_by"] == "admin-1"


def test_prompt_run_failure_exposes_error_code() -> None:
    client, _ = make_client(
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
    session_id = create_session(client)

    queued = client.post(f"/api/v1/sessions/{session_id}/prompt", json={"prompt": "make game"})
    assert queued.status_code == 202
    run_id = queued.json()["run_id"]

    run = wait_run_terminal(client, session_id, run_id)
    assert run["status"] == "failed"
    assert run["error_code"] == "vertex_not_configured"


def test_run_cancel_marks_cancelled() -> None:
    client, _ = make_client(delay_seconds=0.8)
    session_id = create_session(client)

    queued = client.post(f"/api/v1/sessions/{session_id}/prompt", json={"prompt": "slow prompt"})
    run_id = queued.json()["run_id"]
    cancelled = client.post(f"/api/v1/sessions/{session_id}/runs/{run_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_publish_succeeds_without_manual_approval() -> None:
    client, _ = make_client()
    session_id = create_session(client)

    queued = client.post(f"/api/v1/sessions/{session_id}/prompt", json={"prompt": "build racing game"})
    run_id = queued.json()["run_id"]
    run = wait_run_terminal(client, session_id, run_id)
    assert run["status"] == "succeeded"

    published = client.post(f"/api/v1/sessions/{session_id}/publish", json={"slug": "road-rush"})
    assert published.status_code == 200
    assert published.json()["game_url"] == "/play/road-rush"
    assert published.json()["presentation_status"] == "ready"
    assert published.json()["thumbnail_url"] == "https://cdn.example.com/games/road-rush/canonical.png"
    assert published.json()["marketing_summary"] == "T summary"
    assert published.json()["play_overview"] == ["overview"]
    assert published.json()["controls_guide"] == ["controls"]


def test_publish_blocks_when_runtime_fatal_exists() -> None:
    client, store = make_client(playtester=FakePlaytester(boots_ok=False, issues=["Missing animation loop (requestAnimationFrame)"]))
    session_id = create_session(client)
    store.update_session_html(session_id, "<html>draft</html>", score=0)

    approved = client.post(f"/api/v1/sessions/{session_id}/approve-publish", json={"note": "looks good"})
    assert approved.status_code == 200

    published = client.post(f"/api/v1/sessions/{session_id}/publish", json={"slug": "road-rush"})
    assert published.status_code == 409
    assert published.json()["detail"]["code"] == "publish_runtime_blocked"


def test_publish_blocks_when_presentation_contract_is_missing() -> None:
    client, store = make_client()
    client.app.state.publisher_service.presentation_ok = False
    client.app.state.publisher_service.presentation_issues = ["presentation_capture_hook", "presentation_ready_flag"]
    session_id = create_session(client)
    store.update_session_html(
        session_id,
        "<html><body><canvas></canvas><script>window.__iis_game_boot_ok=true;window.IISLeaderboard={};requestAnimationFrame(()=>{});</script></body></html>",
        score=0,
    )

    published = client.post(f"/api/v1/sessions/{session_id}/publish", json={"slug": "road-rush"})
    assert published.status_code == 409
    assert published.json()["detail"]["code"] == "publish_presentation_blocked"
    assert "presentation_capture_hook" in published.json()["detail"]["issues"]


def test_issue_propose_apply_flow() -> None:
    client, store = make_client()
    session_id = create_session(client)
    store.update_session_html(session_id, "<html>old</html>", score=70)

    issue_res = client.post(
        f"/api/v1/sessions/{session_id}/issues",
        json={"title": "코너링 감각 이상", "details": "드리프트가 너무 급함", "category": "physics"},
    )
    assert issue_res.status_code == 200
    issue_id = issue_res.json()["issue_id"]
    assert issue_res.json()["category"] == "gameplay_bug"

    propose = client.post(
        f"/api/v1/sessions/{session_id}/issues/{issue_id}/propose-fix",
        json={"instruction": "핸들링을 더 안정적으로"},
    )
    assert propose.status_code == 200
    proposal_id = propose.json()["proposal_id"]
    assert propose.json()["preview_html"] == "<html>patched</html>"

    apply_res = client.post(
        f"/api/v1/sessions/{session_id}/issues/{issue_id}/apply-fix",
        json={"proposal_id": proposal_id},
    )
    assert apply_res.status_code == 200
    assert apply_res.json()["status"] == "applied"
    assert apply_res.json()["html"] == "<html>patched</html>"

    session_row = store.get_session(session_id)
    assert session_row is not None
    assert session_row["current_html"] == "<html>patched</html>"


def test_issue_auto_classifies_visual_feedback_with_attachment() -> None:
    client, store = make_client()
    session_id = create_session(client)

    issue_res = client.post(
        f"/api/v1/sessions/{session_id}/issues",
        json={
            "title": "이 화면 느낌을 바꿔줘",
            "details": "첨부 이미지처럼 더 공격적인 비주얼로 바꿔줘",
            "image_attachment": {
                "name": "reference.png",
                "mime_type": "image/png",
                "data_url": "data:image/png;base64,aGVsbG8=",
            },
        },
    )
    assert issue_res.status_code == 200
    assert issue_res.json()["category"] == "visual_polish"
    assert store.histories[session_id][-1]["metadata"]["attachment"]["has_image"] is True


def test_prompt_accepts_image_attachment_metadata() -> None:
    client, store = make_client()
    session_id = create_session(client)

    queued = client.post(
        f"/api/v1/sessions/{session_id}/prompt",
        json={
            "prompt": "첨부 이미지 같은 컬러감의 레이싱 게임 만들어줘",
            "image_attachment": {
                "name": "reference.webp",
                "mime_type": "image/webp",
                "data_url": "data:image/webp;base64,aGVsbG8=",
            },
        },
    )
    assert queued.status_code == 202
    user_rows = [row for row in store.histories[session_id] if row["role"] == "user"]
    assert user_rows[-1]["metadata"]["attachment"]["mime_type"] == "image/webp"


def test_prompt_run_schedules_retry_on_capacity_exhaustion() -> None:
    client, store = make_client()
    client.app.state.agent_loop = FakeLoop(
        result=AgentLoopResult(html="", activities=[]),
        error=VertexCapacityExhausted(
            retry_after_seconds=10,
            attempted_routes=[
                BuilderRoute(model_name="gemini-3-pro-preview", location="global", tier="preview", fallback_rank=0),
                BuilderRoute(model_name="gemini-2.5-pro", location="global", tier="stable-pro", fallback_rank=1),
            ],
            last_error="429 RESOURCE_EXHAUSTED",
        ),
    )
    session_id = create_session(client)

    queued = client.post(f"/api/v1/sessions/{session_id}/prompt", json={"prompt": "build flight game"})
    assert queued.status_code == 202
    run_id = queued.json()["run_id"]

    response = client.get(f"/api/v1/sessions/{session_id}/runs/{run_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"retrying", "queued"}
    assert payload["error_code"] == "resource_exhausted_retrying"

    event_types = [row["event_type"] for row in store.events[session_id]]
    assert "prompt_run_retry_scheduled" in event_types


def test_session_snapshot_conversation_and_latest_issue_endpoints() -> None:
    client, store = make_client()
    session_id = create_session(client)

    queued = client.post(f"/api/v1/sessions/{session_id}/prompt", json={"prompt": "build racing game"})
    run_id = queued.json()["run_id"]
    run = wait_run_terminal(client, session_id, run_id)
    assert run["status"] == "succeeded"

    issue_res = client.post(
        f"/api/v1/sessions/{session_id}/issues",
        json={"title": "랩타이머 강화", "details": "랩타임이 더 잘 보였으면 함", "category": "ux_copy"},
    )
    issue_id = issue_res.json()["issue_id"]
    propose = client.post(
        f"/api/v1/sessions/{session_id}/issues/{issue_id}/propose-fix",
        json={"instruction": "랩타임 표시를 더 크게"},
    )
    proposal_id = propose.json()["proposal_id"]

    snapshot = client.get(f"/api/v1/sessions/{session_id}")
    assert snapshot.status_code == 200
    assert snapshot.json()["current_run_id"] == run_id
    assert snapshot.json()["current_run_status"] == "succeeded"
    assert snapshot.json()["last_issue_id"] == issue_id
    assert snapshot.json()["last_proposal_id"] == proposal_id

    conversation = client.get(f"/api/v1/sessions/{session_id}/conversation?limit=20")
    assert conversation.status_code == 200
    assert any(row["role"] == "user" for row in conversation.json()["messages"])

    latest_issue = client.get(f"/api/v1/sessions/{session_id}/issues/latest")
    assert latest_issue.status_code == 200
    assert latest_issue.json()["issue"]["issue_id"] == issue_id
    assert latest_issue.json()["proposal_id"] == proposal_id
