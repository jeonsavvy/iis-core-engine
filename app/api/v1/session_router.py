"""Session API — interactive game creation sessions."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any, Protocol, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.agents.codegen_agent import ConversationMessage
from app.api.security import verify_internal_api_token
from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(
    prefix="/sessions",
    tags=["sessions"],
    dependencies=[Depends(verify_internal_api_token)],
)


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    title: str = ""
    genre_hint: str = ""


class CreateSessionResponse(BaseModel):
    session_id: str
    title: str
    status: str = "active"


class PromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    auto_qa: bool = True
    stream: bool = False


class PromptQueuedResponse(BaseModel):
    session_id: str
    run_id: str
    status: str


class ActivityResponse(BaseModel):
    agent: str
    action: str
    summary: str = ""
    score: int = 0
    decision_reason: str = ""
    input_signal: str = ""
    change_impact: str = ""
    confidence: float = 0.0
    error_code: str | None = None
    before_score: int | None = None
    after_score: int | None = None


class SessionResponse(BaseModel):
    session_id: str
    title: str
    genre: str = ""
    status: str = "active"
    current_html: str = ""
    score: int = 0
    conversation_count: int = 0


class SessionSummary(BaseModel):
    session_id: str
    title: str
    genre: str = ""
    status: str = "active"
    score: int = 0
    updated_at: str | None = None
    created_at: str | None = None


class SessionListResponse(BaseModel):
    sessions: list[SessionSummary] = Field(default_factory=list)


class SessionRunResponse(BaseModel):
    session_id: str
    run_id: str
    status: str
    prompt: str = ""
    auto_qa: bool = True
    final_score: int = 0
    error_code: str | None = None
    error_detail: str = ""
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    activities: list[ActivityResponse] = Field(default_factory=list)
    current_html: str = ""


class PlanDraftRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)


class PlanDraftResponse(BaseModel):
    mode: str
    summary: str
    checklist: list[str]
    risk_hint: str


class CreateIssueRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    details: str = Field(default="", max_length=4000)
    category: str = Field(default="gameplay", max_length=40)


class SessionIssueResponse(BaseModel):
    issue_id: str
    session_id: str
    title: str
    details: str = ""
    category: str
    status: str
    created_at: str
    updated_at: str | None = None


class ProposeFixRequest(BaseModel):
    instruction: str = Field(default="", max_length=2000)


class ProposeFixResponse(BaseModel):
    session_id: str
    issue_id: str
    proposal_id: str
    summary: str
    preview_html: str
    routed_agents: list[str]
    status: str


class ApplyFixRequest(BaseModel):
    proposal_id: str | None = None


class ApplyFixResponse(BaseModel):
    session_id: str
    issue_id: str
    proposal_id: str
    status: str
    html: str


class ApprovePublishRequest(BaseModel):
    note: str = Field(default="", max_length=1000)


class ApprovePublishResponse(BaseModel):
    session_id: str
    approval_id: str
    approved: bool = True
    approved_at: str


class PublishRequest(BaseModel):
    game_name: str = ""
    slug: str = ""


class PublishResponse(BaseModel):
    success: bool
    game_slug: str = ""
    game_url: str = ""
    error: str = ""


class SessionEventResponse(BaseModel):
    id: str
    session_id: str
    event_type: str
    agent: str | None = None
    action: str | None = None
    summary: str = ""
    score: int | None = None
    before_score: int | None = None
    after_score: int | None = None
    decision_reason: str = ""
    input_signal: str = ""
    change_impact: str = ""
    confidence: float | None = None
    error_code: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class SessionEventsListResponse(BaseModel):
    events: list[SessionEventResponse]
    next_cursor: str | None = None


class CancelSessionResponse(BaseModel):
    session_id: str
    status: str


_SLUG_PATTERN = re.compile(r"[^a-z0-9-]+")
_EVENT_SUMMARY_MAX_LEN = 200


class SessionStoreProtocol(Protocol):
    def create_session(self, *, user_id: str | None = None, title: str = "", genre: str = "") -> dict[str, Any]:
        ...

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        ...

    def list_sessions(self, *, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        ...

    def update_session_html(self, session_id: str, html: str, score: int = 0) -> None:
        ...

    def update_session_status(self, session_id: str, status: str) -> None:
        ...

    def delete_session(self, session_id: str) -> None:
        ...

    def add_conversation_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        ...

    def get_conversation_history(self, session_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        ...

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
        ...

    def get_session_events(self, session_id: str, *, limit: int = 50, cursor: str | None = None) -> list[dict[str, Any]]:
        ...

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
        ...

    def create_session_run(self, *, session_id: str, prompt: str, auto_qa: bool, status: str = "queued") -> dict[str, Any]:
        ...

    def get_session_run(self, session_id: str, run_id: str) -> dict[str, Any] | None:
        ...

    def update_session_run(self, session_id: str, run_id: str, **fields: Any) -> None:
        ...

    def create_session_issue(
        self,
        *,
        session_id: str,
        title: str,
        details: str,
        category: str,
        created_by: str = "master_admin",
    ) -> dict[str, Any]:
        ...

    def get_session_issue(self, session_id: str, issue_id: str) -> dict[str, Any] | None:
        ...

    def update_session_issue(self, session_id: str, issue_id: str, **fields: Any) -> None:
        ...

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
        ...

    def get_issue_proposal(self, session_id: str, issue_id: str, proposal_id: str) -> dict[str, Any] | None:
        ...

    def get_latest_issue_proposal(self, session_id: str, issue_id: str) -> dict[str, Any] | None:
        ...

    def update_issue_proposal(self, session_id: str, issue_id: str, proposal_id: str, **fields: Any) -> None:
        ...

    def create_publish_approval(self, *, session_id: str, approved_by: str = "master_admin", note: str = "") -> dict[str, Any]:
        ...

    def get_latest_publish_approval(self, session_id: str) -> dict[str, Any] | None:
        ...

    def clear_publish_approvals(self, session_id: str) -> None:
        ...


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_session_store(request: Request) -> SessionStoreProtocol:
    store = getattr(request.app.state, "session_store", None)
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session store unavailable. Configure Supabase persistence.",
        )
    return cast(SessionStoreProtocol, store)


def _load_session_or_404(store: SessionStoreProtocol, session_id: str) -> dict[str, Any]:
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


def _load_run_or_404(store: SessionStoreProtocol, session_id: str, run_id: str) -> dict[str, Any]:
    run = store.get_session_run(session_id, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


def _load_issue_or_404(store: SessionStoreProtocol, session_id: str, issue_id: str) -> dict[str, Any]:
    issue = store.get_session_issue(session_id, issue_id)
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    return issue


def _normalize_slug(raw: str) -> str:
    candidate = raw.strip().lower().replace("_", "-").replace(" ", "-")
    candidate = _SLUG_PATTERN.sub("-", candidate)
    candidate = candidate.strip("-")
    return candidate[:64] if candidate else ""


def _normalize_error_code(raw: str) -> str:
    code = raw.strip().lower()
    if not code:
        return "agent_loop_exception"
    if "timeout" in code:
        return "core_engine_timeout"
    return code.replace(" ", "_")[:80]


def _detect_requested_mode(prompt: str, genre_hint: str) -> str:
    text = f"{prompt} {genre_hint}".casefold()
    if any(marker in text for marker in ("3d", "three.js", "threejs", "입체", "레이싱", "racing", "fps")):
        return "3d"
    if any(marker in text for marker in ("2d", "phaser", "플랫포머", "퍼즐", "pixel", "탑다운")):
        return "2d"
    return "unknown"


def _detect_engine(html: str) -> str:
    lowered = html.casefold()
    has_three = any(token in lowered for token in ("three.module.js", "from 'three'", 'from "three"', "new three."))
    has_phaser = "phaser.min.js" in lowered or "new phaser.game" in lowered
    if has_three and has_phaser:
        return "mixed"
    if has_three:
        return "three"
    if has_phaser:
        return "phaser"
    return "unknown"


def _is_engine_compliant(requested_mode: str, detected_engine: str) -> bool:
    if requested_mode == "3d":
        return detected_engine in {"three", "mixed"}
    if requested_mode == "2d":
        return detected_engine in {"phaser", "mixed"}
    return True


def _route_issue_agents(category: str) -> list[str]:
    normalized = category.casefold()
    if normalized in {"runtime", "bug", "crash"}:
        return ["playtester", "codegen"]
    if normalized in {"visual", "readability", "ui"}:
        return ["visual_qa", "codegen"]
    return ["codegen"]


def _serialize_activity(activity: Any) -> dict[str, Any]:
    metadata = activity.metadata if isinstance(getattr(activity, "metadata", {}), dict) else {}
    return {
        "agent": str(getattr(activity, "agent", "unknown")),
        "action": str(getattr(activity, "action", "event")),
        "summary": str(getattr(activity, "summary", "")),
        "score": int(getattr(activity, "score", 0) or 0),
        "decision_reason": str(getattr(activity, "decision_reason", "")),
        "input_signal": str(getattr(activity, "input_signal", "")),
        "change_impact": str(getattr(activity, "change_impact", "")),
        "confidence": float(getattr(activity, "confidence", 0.0) or 0.0),
        "error_code": str(getattr(activity, "error_code", "")) if getattr(activity, "error_code", None) else None,
        "before_score": getattr(activity, "before_score", None),
        "after_score": getattr(activity, "after_score", None),
        "metadata": metadata,
    }


def _activity_response_from_row(row: dict[str, Any]) -> ActivityResponse:
    return ActivityResponse(
        agent=str(row.get("agent", "unknown")),
        action=str(row.get("action", "event")),
        summary=str(row.get("summary", "")),
        score=int(row.get("score", 0) or 0),
        decision_reason=str(row.get("decision_reason", "")),
        input_signal=str(row.get("input_signal", "")),
        change_impact=str(row.get("change_impact", "")),
        confidence=float(row.get("confidence", 0.0) or 0.0),
        error_code=str(row["error_code"]) if row.get("error_code") else None,
        before_score=int(row["before_score"]) if isinstance(row.get("before_score"), int) else None,
        after_score=int(row["after_score"]) if isinstance(row.get("after_score"), int) else None,
    )


def _build_run_response(store: SessionStoreProtocol, session_id: str, run: dict[str, Any]) -> SessionRunResponse:
    activities: list[ActivityResponse] = []
    raw_activities = run.get("activities")
    if isinstance(raw_activities, list):
        for activity in raw_activities:
            if isinstance(activity, dict):
                activities.append(_activity_response_from_row(activity))

    session = store.get_session(session_id) or {}
    return SessionRunResponse(
        session_id=session_id,
        run_id=str(run.get("id", "")),
        status=str(run.get("status", "queued")),
        prompt=str(run.get("prompt", "")),
        auto_qa=bool(run.get("auto_qa", True)),
        final_score=int(run.get("final_score", 0) or 0),
        error_code=str(run["error_code"]) if run.get("error_code") else None,
        error_detail=str(run.get("error_detail", "")),
        created_at=str(run.get("created_at", "")),
        started_at=str(run["started_at"]) if run.get("started_at") else None,
        finished_at=str(run["finished_at"]) if run.get("finished_at") else None,
        activities=activities,
        current_html=str(session.get("current_html", "")),
    )


def _get_run_tasks(app: Any) -> dict[str, asyncio.Task[Any]]:
    tasks = getattr(app.state, "session_run_tasks", None)
    if tasks is None:
        tasks = {}
        app.state.session_run_tasks = tasks
    return cast(dict[str, asyncio.Task[Any]], tasks)


async def _execute_prompt_run(
    *,
    app: Any,
    store: SessionStoreProtocol,
    run_id: str,
    session_id: str,
    prompt: str,
    auto_qa: bool,
    timeout_seconds: float,
    settings_obj: Settings,
) -> None:
    try:
        store.update_session_run(session_id, run_id, status="running", started_at=_now_iso())
        store.add_session_event(
            session_id=session_id,
            event_type="prompt_run_started",
            action="run",
            summary=f"Run started: {run_id[:8]}",
            decision_reason="queued_run_started",
            input_signal=prompt[:500],
            change_impact="agent_loop_running",
            confidence=1.0,
            metadata={"run_id": run_id},
        )

        session = store.get_session(session_id) or {}
        history_rows = store.get_conversation_history(session_id, limit=100)
        history = [
            ConversationMessage(role=str(msg.get("role", "user")), content=str(msg.get("content", "")))
            for msg in history_rows
        ]

        agent_loop = getattr(app.state, "agent_loop", None)
        if agent_loop is None:
            raise RuntimeError("agent_loop_not_initialized")

        result = await asyncio.wait_for(
            agent_loop.run(
                user_prompt=prompt,
                history=history,
                current_html=str(session.get("current_html", "")),
                genre_hint=str(session.get("genre", "")),
                auto_qa=auto_qa,
            ),
            timeout=timeout_seconds,
        )

        if result.error:
            error_code = _normalize_error_code(result.error)
            store.update_session_run(
                session_id,
                run_id,
                status="failed",
                finished_at=_now_iso(),
                error_code=error_code,
                error_detail=result.error,
                final_score=0,
            )
            store.add_session_event(
                session_id=session_id,
                event_type="prompt_run_failed",
                agent="codegen",
                action="run",
                summary=result.error[:_EVENT_SUMMARY_MAX_LEN],
                decision_reason="agent_loop_failed",
                input_signal=prompt[:500],
                change_impact="no_html_update",
                confidence=0.0,
                error_code=error_code,
                metadata={"run_id": run_id},
            )
            return

        store.update_session_html(session_id, result.html, score=result.final_score)
        store.add_conversation_message(
            session_id=session_id,
            role="assistant",
            content=f"[Generated game: {len(result.html)} chars, score: {result.final_score}]",
            metadata={
                "final_score": result.final_score,
                "generation_source": result.generation_source,
                "auto_refined": result.auto_refined,
                "run_id": run_id,
            },
        )

        activity_payloads: list[dict[str, Any]] = []
        for activity in result.activities:
            payload = _serialize_activity(activity)
            activity_payloads.append(payload)
            store.add_session_event(
                session_id=session_id,
                event_type="agent_activity",
                agent=str(payload.get("agent", "unknown")),
                action=str(payload.get("action", "event")),
                summary=str(payload.get("summary", "")),
                score=int(payload.get("score", 0) or 0),
                before_score=payload.get("before_score") if isinstance(payload.get("before_score"), int) else None,
                after_score=payload.get("after_score") if isinstance(payload.get("after_score"), int) else None,
                decision_reason=str(payload.get("decision_reason", "")),
                input_signal=str(payload.get("input_signal", "")),
                change_impact=str(payload.get("change_impact", "")),
                confidence=float(payload.get("confidence", 0.0) or 0.0),
                error_code=str(payload.get("error_code")) if payload.get("error_code") else None,
                metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
            )

        if settings_obj.engine_audit_enabled:
            requested_mode = _detect_requested_mode(prompt, str(session.get("genre", "")))
            detected_engine = _detect_engine(result.html)
            compliance = _is_engine_compliant(requested_mode, detected_engine)
            store.add_session_event(
                session_id=session_id,
                event_type="engine_audit",
                agent="codegen",
                action="audit",
                summary=f"requested={requested_mode}, detected={detected_engine}",
                decision_reason="engine_policy_shadow_audit",
                input_signal=prompt[:500],
                change_impact="engine_policy_observed",
                confidence=1.0 if compliance else 0.45,
                metadata={
                    "requested_mode": requested_mode,
                    "detected_engine": detected_engine,
                    "compliance": compliance,
                    "note": "non_blocking_audit",
                },
            )

        store.update_session_run(
            session_id,
            run_id,
            status="succeeded",
            finished_at=_now_iso(),
            error_code=None,
            error_detail="",
            final_score=result.final_score,
            activities=activity_payloads,
        )
        store.add_session_event(
            session_id=session_id,
            event_type="prompt_run_succeeded",
            action="run",
            summary=f"Run succeeded: {run_id[:8]}",
            score=result.final_score,
            decision_reason="agent_loop_completed",
            input_signal=prompt[:500],
            change_impact="session_html_updated",
            confidence=1.0,
            metadata={"run_id": run_id, "final_score": result.final_score},
        )
    except asyncio.CancelledError:
        store.update_session_run(
            session_id,
            run_id,
            status="cancelled",
            finished_at=_now_iso(),
            error_code="prompt_run_cancelled",
            error_detail="Cancelled by operator",
        )
        store.add_session_event(
            session_id=session_id,
            event_type="prompt_run_cancelled",
            action="cancel",
            summary="Prompt run cancelled",
            decision_reason="operator_requested_cancel",
            change_impact="run_stopped",
            confidence=1.0,
            error_code="prompt_run_cancelled",
            metadata={"run_id": run_id},
        )
        raise
    except asyncio.TimeoutError:
        store.update_session_run(
            session_id,
            run_id,
            status="failed",
            finished_at=_now_iso(),
            error_code="core_engine_timeout",
            error_detail=f"Prompt run timed out after {timeout_seconds:.0f}s",
        )
        store.add_session_event(
            session_id=session_id,
            event_type="prompt_run_failed",
            agent="codegen",
            action="run",
            summary=f"Prompt run timed out after {timeout_seconds:.0f}s",
            decision_reason="core_engine_timeout",
            input_signal=prompt[:500],
            change_impact="no_html_update",
            confidence=0.0,
            error_code="core_engine_timeout",
            metadata={"run_id": run_id},
        )
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Prompt run failed: session=%s run=%s", session_id, run_id)
        error_detail = str(exc)[:200] or "agent_loop_exception"
        store.update_session_run(
            session_id,
            run_id,
            status="failed",
            finished_at=_now_iso(),
            error_code="agent_loop_exception",
            error_detail=error_detail,
        )
        store.add_session_event(
            session_id=session_id,
            event_type="prompt_run_failed",
            agent="codegen",
            action="run",
            summary=error_detail,
            decision_reason="agent_loop_exception",
            input_signal=prompt[:500],
            change_impact="no_html_update",
            confidence=0.0,
            error_code="agent_loop_exception",
            metadata={"run_id": run_id},
        )
    finally:
        _get_run_tasks(app).pop(run_id, None)


def _build_plan_draft(prompt: str, genre_hint: str) -> PlanDraftResponse:
    mode = _detect_requested_mode(prompt, genre_hint)
    if mode == "3d":
        checklist = [
            "Three.js 기반 월드/카메라/조명 골격 생성",
            "주행 루프(가속/감속/스티어링) 및 HUD 스코어 연결",
            "Visual QA + Playtester 피드백 반영 후 밸런스 보정",
        ]
        risk_hint = "3D 씬이 무거우면 프레임 저하 가능성이 있습니다."
    elif mode == "2d":
        checklist = [
            "Phaser.js 씬/오브젝트/입력 루프 생성",
            "스테이지/점수/리스타트 흐름 연결",
            "Playtester 로그 기반 난이도/충돌 튜닝",
        ]
        risk_hint = "스프라이트 수가 과하면 저사양 브라우저에서 끊김이 생길 수 있습니다."
    else:
        checklist = [
            "요청 의도 분석 후 2D/3D 엔진 선택",
            "핵심 게임 루프 + 점수 + 게임오버 리스타트 구성",
            "QA 피드백 기반 자동 개선 1회 이상 수행",
        ]
        risk_hint = "모드가 불명확하면 첫 결과가 의도와 다를 수 있습니다."
    return PlanDraftResponse(
        mode=mode,
        summary=f"입력 프롬프트 기반 제작 플랜 ({mode})",
        checklist=checklist,
        risk_hint=risk_hint,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=CreateSessionResponse)
async def create_session(body: CreateSessionRequest, request: Request) -> CreateSessionResponse:
    """Create a new interactive game editing session."""
    store = _get_session_store(request)
    created = store.create_session(title=body.title, genre=body.genre_hint)
    session_id = str(created.get("id", ""))
    if not session_id:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Session ID missing")

    store.add_session_event(
        session_id=session_id,
        event_type="session_created",
        action="create",
        summary="Session created",
        input_signal=body.genre_hint,
        decision_reason="user_requested_new_session",
        change_impact="session_initialized",
        confidence=1.0,
    )
    logger.info("Session created: %s", session_id)
    return CreateSessionResponse(
        session_id=session_id,
        title=str(created.get("title", "")),
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, request: Request) -> SessionResponse:
    """Get session state."""
    store = _get_session_store(request)
    session = _load_session_or_404(store, session_id)
    history = store.get_conversation_history(session_id, limit=200)
    return SessionResponse(
        session_id=str(session.get("id", session_id)),
        title=str(session.get("title", "")),
        genre=str(session.get("genre", "")),
        status=str(session.get("status", "active")),
        current_html=str(session.get("current_html", "")),
        score=int(session.get("score", 0) or 0),
        conversation_count=len(history),
    )


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    request: Request,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> SessionListResponse:
    store = _get_session_store(request)
    rows = store.list_sessions(status=status, limit=limit)
    return SessionListResponse(
        sessions=[
            SessionSummary(
                session_id=str(row.get("id", "")),
                title=str(row.get("title", "")),
                genre=str(row.get("genre", "")),
                status=str(row.get("status", "active")),
                score=int(row.get("score", 0) or 0),
                updated_at=str(row.get("updated_at")) if row.get("updated_at") else None,
                created_at=str(row.get("created_at")) if row.get("created_at") else None,
            )
            for row in rows
        ]
    )


@router.get("/{session_id}/events", response_model=SessionEventsListResponse)
async def get_session_events(
    session_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> SessionEventsListResponse:
    store = _get_session_store(request)
    _load_session_or_404(store, session_id)
    events = store.get_session_events(session_id, limit=limit, cursor=cursor)
    next_cursor = None
    if len(events) >= limit:
        tail = events[-1]
        created_at = tail.get("created_at")
        if isinstance(created_at, str) and created_at.strip():
            next_cursor = created_at

    return SessionEventsListResponse(
        events=[
            SessionEventResponse(
                id=str(event.get("id", "")),
                session_id=str(event.get("session_id", session_id)),
                event_type=str(event.get("event_type", "unknown")),
                agent=str(event.get("agent")) if event.get("agent") else None,
                action=str(event.get("action")) if event.get("action") else None,
                summary=str(event.get("summary", "")),
                score=int(event["score"]) if isinstance(event.get("score"), int) else None,
                before_score=int(event["before_score"]) if isinstance(event.get("before_score"), int) else None,
                after_score=int(event["after_score"]) if isinstance(event.get("after_score"), int) else None,
                decision_reason=str(event.get("decision_reason", "")),
                input_signal=str(event.get("input_signal", "")),
                change_impact=str(event.get("change_impact", "")),
                confidence=float(event["confidence"]) if isinstance(event.get("confidence"), (int, float)) else None,
                error_code=str(event["error_code"]) if isinstance(event.get("error_code"), str) else None,
                metadata=event.get("metadata") if isinstance(event.get("metadata"), dict) else {},
                created_at=str(event.get("created_at", "")),
            )
            for event in events
        ],
        next_cursor=next_cursor,
    )


@router.post("/{session_id}/plan-draft", response_model=PlanDraftResponse)
async def create_plan_draft(session_id: str, body: PlanDraftRequest, request: Request) -> PlanDraftResponse:
    store = _get_session_store(request)
    session = _load_session_or_404(store, session_id)
    result = _build_plan_draft(body.prompt, str(session.get("genre", "")))
    store.add_session_event(
        session_id=session_id,
        event_type="plan_draft_created",
        action="plan-draft",
        summary=result.summary[:_EVENT_SUMMARY_MAX_LEN],
        input_signal=body.prompt[:500],
        decision_reason="pre_generation_planning",
        change_impact="workflow_guidance_generated",
        confidence=0.9,
        metadata={"mode": result.mode},
    )
    return result


@router.post("/{session_id}/prompt", response_model=PromptQueuedResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_prompt(session_id: str, body: PromptRequest, request: Request) -> PromptQueuedResponse:
    """Queue prompt run asynchronously."""
    if body.stream:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "stream_not_supported", "code": "async_prompt_required"},
        )

    store = _get_session_store(request)
    session = _load_session_or_404(store, session_id)
    if str(session.get("status", "active")) != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session is not active")

    store.add_conversation_message(
        session_id=session_id,
        role="user",
        content=body.prompt,
        metadata={"stream": False, "auto_qa": body.auto_qa},
    )
    store.add_session_event(
        session_id=session_id,
        event_type="user_prompt",
        action="prompt",
        summary=body.prompt[:_EVENT_SUMMARY_MAX_LEN],
        input_signal=body.prompt[:500],
        decision_reason="user_instruction_received",
        change_impact="agent_loop_triggered",
        confidence=1.0,
    )

    store.clear_publish_approvals(session_id)

    run = store.create_session_run(
        session_id=session_id,
        prompt=body.prompt,
        auto_qa=body.auto_qa,
        status="queued",
    )
    run_id = str(run.get("id", ""))
    if not run_id:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Run ID missing")

    store.add_session_event(
        session_id=session_id,
        event_type="prompt_run_queued",
        action="run",
        summary=f"Run queued: {run_id[:8]}",
        input_signal=body.prompt[:500],
        decision_reason="async_prompt_queue",
        change_impact="queued",
        confidence=1.0,
        metadata={"run_id": run_id, "auto_qa": body.auto_qa},
    )

    if settings.prompt_async_enabled:
        task = asyncio.create_task(
            _execute_prompt_run(
                app=request.app,
                store=store,
                run_id=run_id,
                session_id=session_id,
                prompt=body.prompt,
                auto_qa=body.auto_qa,
                timeout_seconds=settings.prompt_run_timeout_seconds,
                settings_obj=settings,
            )
        )
        _get_run_tasks(request.app)[run_id] = task
    else:
        await _execute_prompt_run(
            app=request.app,
            store=store,
            run_id=run_id,
            session_id=session_id,
            prompt=body.prompt,
            auto_qa=body.auto_qa,
            timeout_seconds=settings.prompt_run_timeout_seconds,
            settings_obj=settings,
        )

    return PromptQueuedResponse(session_id=session_id, run_id=run_id, status="queued")


@router.get("/{session_id}/runs/{run_id}", response_model=SessionRunResponse)
async def get_prompt_run(session_id: str, run_id: str, request: Request) -> SessionRunResponse:
    store = _get_session_store(request)
    _load_session_or_404(store, session_id)
    run = _load_run_or_404(store, session_id, run_id)
    return _build_run_response(store, session_id, run)


@router.post("/{session_id}/runs/{run_id}/cancel", response_model=SessionRunResponse)
async def cancel_prompt_run(session_id: str, run_id: str, request: Request) -> SessionRunResponse:
    store = _get_session_store(request)
    _load_session_or_404(store, session_id)
    run = _load_run_or_404(store, session_id, run_id)

    current_status = str(run.get("status", "queued"))
    if current_status in {"succeeded", "failed", "cancelled"}:
        return _build_run_response(store, session_id, run)

    task = _get_run_tasks(request.app).get(run_id)
    if task and not task.done():
        task.cancel()

    store.update_session_run(
        session_id,
        run_id,
        status="cancelled",
        finished_at=_now_iso(),
        error_code="prompt_run_cancelled",
        error_detail="Cancelled by operator",
    )
    store.add_session_event(
        session_id=session_id,
        event_type="prompt_run_cancelled",
        action="cancel",
        summary="Prompt run cancelled",
        decision_reason="operator_requested_cancel",
        change_impact="run_stopped",
        confidence=1.0,
        error_code="prompt_run_cancelled",
        metadata={"run_id": run_id},
    )
    refreshed = _load_run_or_404(store, session_id, run_id)
    return _build_run_response(store, session_id, refreshed)


@router.post("/{session_id}/issues", response_model=SessionIssueResponse)
async def create_issue(session_id: str, body: CreateIssueRequest, request: Request) -> SessionIssueResponse:
    if not settings.human_agent_issue_loop_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "issue_loop_disabled", "code": "human_agent_issue_loop_disabled"},
        )
    store = _get_session_store(request)
    _load_session_or_404(store, session_id)

    issue = store.create_session_issue(
        session_id=session_id,
        title=body.title,
        details=body.details,
        category=body.category,
    )
    routed_agents = _route_issue_agents(body.category)
    store.add_session_event(
        session_id=session_id,
        event_type="issue_reported",
        action="report",
        summary=body.title[:_EVENT_SUMMARY_MAX_LEN],
        input_signal=body.details[:500],
        decision_reason="human_feedback_received",
        change_impact="issue_queue_updated",
        confidence=1.0,
        metadata={"issue_id": issue.get("id"), "category": body.category, "routed_agents": routed_agents},
    )

    return SessionIssueResponse(
        issue_id=str(issue.get("id", "")),
        session_id=session_id,
        title=str(issue.get("title", "")),
        details=str(issue.get("details", "")),
        category=str(issue.get("category", body.category)),
        status=str(issue.get("status", "open")),
        created_at=str(issue.get("created_at", _now_iso())),
        updated_at=str(issue.get("updated_at")) if issue.get("updated_at") else None,
    )


@router.post("/{session_id}/issues/{issue_id}/propose-fix", response_model=ProposeFixResponse)
async def propose_issue_fix(
    session_id: str,
    issue_id: str,
    body: ProposeFixRequest,
    request: Request,
) -> ProposeFixResponse:
    if not settings.human_agent_issue_loop_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "issue_loop_disabled", "code": "human_agent_issue_loop_disabled"},
        )

    store = _get_session_store(request)
    session = _load_session_or_404(store, session_id)
    issue = _load_issue_or_404(store, session_id, issue_id)

    routed_agents = _route_issue_agents(str(issue.get("category", "gameplay")))
    store.add_session_event(
        session_id=session_id,
        event_type="issue_routed",
        action="route",
        summary=f"Issue routed: {', '.join(routed_agents)}",
        decision_reason="issue_category_routing",
        input_signal=str(issue.get("details", ""))[:500],
        change_impact="agent_fix_pipeline_selected",
        confidence=0.85,
        metadata={"issue_id": issue_id, "routed_agents": routed_agents},
    )

    codegen = getattr(request.app.state, "codegen_agent", None)
    if codegen is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "codegen_unavailable", "code": "agent_loop_not_initialized"},
        )

    instruction = body.instruction.strip()
    proposal_prompt = (
        "사용자가 현재 게임 결과에 대해 수정 요청을 보냈습니다.\n"
        f"- issue title: {issue.get('title', '')}\n"
        f"- issue details: {issue.get('details', '')}\n"
        f"- category: {issue.get('category', '')}\n"
        f"- extra instruction: {instruction}\n\n"
        "요청 사항만 정확히 수정하고 기존에 잘 작동하는 기능은 유지한 완전한 HTML을 반환하세요."
    )
    history_rows = store.get_conversation_history(session_id, limit=100)
    history = [
        ConversationMessage(role=str(msg.get("role", "user")), content=str(msg.get("content", "")))
        for msg in history_rows
    ]

    result = await codegen.generate(
        user_prompt=proposal_prompt,
        history=history,
        current_html=str(session.get("current_html", "")),
        genre_hint=str(session.get("genre", "")),
    )
    if result.error:
        error_code = _normalize_error_code(result.error)
        store.add_session_event(
            session_id=session_id,
            event_type="fix_proposed",
            agent="codegen",
            action="propose",
            summary=result.error[:_EVENT_SUMMARY_MAX_LEN],
            decision_reason="issue_fix_generation_failed",
            input_signal=proposal_prompt[:500],
            change_impact="proposal_not_created",
            confidence=0.0,
            error_code=error_code,
            metadata={"issue_id": issue_id},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "fix_proposal_failed", "code": error_code, "detail": result.error[:200]},
        )

    proposal = store.create_issue_proposal(
        session_id=session_id,
        issue_id=issue_id,
        summary=f"Issue fix proposal ({len(result.html)} chars)",
        proposal_prompt=proposal_prompt,
        preview_html=result.html,
        proposed_by="codegen",
    )
    store.update_session_issue(session_id, issue_id, status="proposed")
    store.add_session_event(
        session_id=session_id,
        event_type="fix_proposed",
        agent="codegen",
        action="propose",
        summary=f"Proposal generated: {proposal.get('id', '')[:8]}",
        decision_reason="issue_fix_generation",
        input_signal=proposal_prompt[:500],
        change_impact="proposal_ready_for_review",
        confidence=0.86,
        metadata={"issue_id": issue_id, "proposal_id": proposal.get("id"), "routed_agents": routed_agents},
    )

    return ProposeFixResponse(
        session_id=session_id,
        issue_id=issue_id,
        proposal_id=str(proposal.get("id", "")),
        summary=str(proposal.get("summary", "")),
        preview_html=str(proposal.get("preview_html", "")),
        routed_agents=routed_agents,
        status=str(proposal.get("status", "proposed")),
    )


@router.post("/{session_id}/issues/{issue_id}/apply-fix", response_model=ApplyFixResponse)
async def apply_issue_fix(session_id: str, issue_id: str, body: ApplyFixRequest, request: Request) -> ApplyFixResponse:
    if not settings.human_agent_issue_loop_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "issue_loop_disabled", "code": "human_agent_issue_loop_disabled"},
        )
    store = _get_session_store(request)
    session = _load_session_or_404(store, session_id)
    _load_issue_or_404(store, session_id, issue_id)

    proposal: dict[str, Any] | None
    if body.proposal_id:
        proposal = store.get_issue_proposal(session_id, issue_id, body.proposal_id)
    else:
        proposal = store.get_latest_issue_proposal(session_id, issue_id)

    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue proposal not found")

    proposal_id = str(proposal.get("id", ""))
    preview_html = str(proposal.get("preview_html", ""))
    if not preview_html.strip():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "proposal_preview_missing", "code": "fix_preview_missing"},
        )

    store.update_session_html(session_id, preview_html, score=int(session.get("score", 0) or 0))
    store.update_issue_proposal(session_id, issue_id, proposal_id, status="applied")
    store.update_session_issue(session_id, issue_id, status="resolved")
    store.add_conversation_message(
        session_id=session_id,
        role="assistant",
        content=f"[Applied fix proposal: {proposal_id}]",
        metadata={"issue_id": issue_id, "proposal_id": proposal_id},
    )
    store.add_session_event(
        session_id=session_id,
        event_type="fix_applied",
        agent="codegen",
        action="apply",
        summary=f"Proposal applied: {proposal_id[:8]}",
        decision_reason="human_approved_fix_proposal",
        input_signal=str(proposal.get("summary", ""))[:500],
        change_impact="session_html_updated",
        confidence=1.0,
        metadata={"issue_id": issue_id, "proposal_id": proposal_id},
    )

    return ApplyFixResponse(
        session_id=session_id,
        issue_id=issue_id,
        proposal_id=proposal_id,
        status="applied",
        html=preview_html,
    )


@router.post("/{session_id}/approve-publish", response_model=ApprovePublishResponse)
async def approve_publish(session_id: str, body: ApprovePublishRequest, request: Request) -> ApprovePublishResponse:
    store = _get_session_store(request)
    _load_session_or_404(store, session_id)
    approval = store.create_publish_approval(session_id=session_id, note=body.note)
    store.add_session_event(
        session_id=session_id,
        event_type="publish_approved",
        action="approve",
        summary="Publish approved by operator",
        decision_reason="human_approval_granted",
        input_signal=body.note[:500],
        change_impact="publish_unlocked",
        confidence=1.0,
        metadata={"approval_id": approval.get("id")},
    )
    return ApprovePublishResponse(
        session_id=session_id,
        approval_id=str(approval.get("id", "")),
        approved_at=str(approval.get("approved_at", _now_iso())),
    )


@router.post("/{session_id}/publish", response_model=PublishResponse)
async def publish_session(session_id: str, body: PublishRequest, request: Request) -> PublishResponse:
    """Publish the current game to the platform."""
    store = _get_session_store(request)
    session = _load_session_or_404(store, session_id)
    if str(session.get("status", "active")) == "cancelled":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cancelled session cannot be published")

    if settings.publish_approval_required:
        approval = store.get_latest_publish_approval(session_id)
        if not approval:
            store.add_session_event(
                session_id=session_id,
                event_type="publish_blocked_unapproved",
                action="publish",
                summary="Publish blocked: approval required",
                decision_reason="approval_gate_required",
                change_impact="publish_blocked",
                confidence=1.0,
                error_code="publish_unapproved",
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "publish_blocked_unapproved", "code": "publish_unapproved"},
            )

    html = str(session.get("current_html", ""))
    if not html.strip():
        raise HTTPException(status_code=400, detail="No game to publish. Generate a game first.")

    publisher = getattr(request.app.state, "publisher_service", None)
    if publisher is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Publisher not configured",
        )

    preferred_slug = _normalize_slug(body.slug)
    fallback_slug = _normalize_slug(str(session.get("title", "")))[:32]
    slug = preferred_slug or fallback_slug or session_id[:8]
    game_name = body.game_name or str(session.get("title", f"Game {slug}"))

    try:
        publish_result = await publisher.publish(
            slug=slug,
            game_name=game_name,
            genre=str(session.get("genre", "")),
            html_content=html,
        )
        store.update_session_status(session_id, "published")
        game_slug = str(publish_result.get("game_slug", slug))
        game_url = str(publish_result.get("play_url", f"/play/{game_slug}"))
        store.record_publish(
            session_id=session_id,
            game_id=str(publish_result.get("game_id")) if publish_result.get("game_id") else None,
            game_slug=game_slug,
            play_url=game_url,
            public_url=str(publish_result.get("public_url")) if publish_result.get("public_url") else None,
            metadata={"game_name": game_name},
        )
        store.add_session_event(
            session_id=session_id,
            event_type="publish_success",
            action="publish",
            summary=f"Published {game_slug}",
            input_signal=game_name,
            decision_reason="user_requested_publish",
            change_impact="session_published",
            confidence=1.0,
            metadata={"play_url": game_url},
        )
        return PublishResponse(
            success=True,
            game_slug=game_slug,
            game_url=game_url,
        )
    except Exception as exc:
        logger.exception("Publish failed: %s", exc)
        store.add_session_event(
            session_id=session_id,
            event_type="publish_failed",
            action="publish",
            summary=str(exc)[:_EVENT_SUMMARY_MAX_LEN],
            decision_reason="publish_failed",
            change_impact="session_not_published",
            confidence=0.0,
            error_code="publish_failed",
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "publish_failed", "detail": str(exc)[:200]},
        )


@router.post("/{session_id}/cancel", response_model=CancelSessionResponse)
async def cancel_session(session_id: str, request: Request) -> CancelSessionResponse:
    store = _get_session_store(request)
    _load_session_or_404(store, session_id)
    store.update_session_status(session_id, "cancelled")
    store.add_session_event(
        session_id=session_id,
        event_type="session_cancelled",
        action="cancel",
        summary="Session cancelled by operator",
        decision_reason="operator_requested_cancel",
        change_impact="future_prompt_blocked",
        confidence=1.0,
    )
    return CancelSessionResponse(session_id=session_id, status="cancelled")


@router.delete("/{session_id}", status_code=status.HTTP_200_OK)
async def delete_session(session_id: str, request: Request) -> dict[str, str]:
    """Delete a session."""
    store = _get_session_store(request)
    _load_session_or_404(store, session_id)
    store.delete_session(session_id)
    return {"status": "deleted"}
