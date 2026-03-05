"""Session API — interactive game creation sessions."""

from __future__ import annotations

import logging
import re
from typing import Any, Protocol, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents.codegen_agent import ConversationMessage
from app.api.security import verify_internal_api_token

logger = logging.getLogger(__name__)

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


class PromptResponse(BaseModel):
    html: str
    score: int = 0
    activities: list[ActivityResponse] = []
    generation_source: str = ""
    auto_refined: bool = False
    error: str = ""


class SessionResponse(BaseModel):
    session_id: str
    title: str
    genre: str = ""
    status: str = "active"
    current_html: str = ""
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
    sessions: list[SessionSummary] = []


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
    metadata: dict[str, Any] = {}
    created_at: str


class SessionEventsListResponse(BaseModel):
    events: list[SessionEventResponse]
    next_cursor: str | None = None


class CancelSessionResponse(BaseModel):
    session_id: str
    status: str


_SLUG_PATTERN = re.compile(r"[^a-z0-9-]+")


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


def _normalize_slug(raw: str) -> str:
    candidate = raw.strip().lower().replace("_", "-").replace(" ", "-")
    candidate = _SLUG_PATTERN.sub("-", candidate)
    candidate = candidate.strip("-")
    return candidate[:64] if candidate else ""


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


@router.post("/{session_id}/prompt", response_model=PromptResponse)
async def send_prompt(session_id: str, body: PromptRequest, request: Request) -> Any:
    """Send a prompt to generate/modify the game.

    This is the core endpoint — replaces the entire batch pipeline.
    User sends natural language, gets back a playable game.
    """
    store = _get_session_store(request)
    session = _load_session_or_404(store, session_id)
    if str(session.get("status", "active")) != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session is not active")

    # Get agent loop from app state (injected at startup)
    agent_loop = getattr(request.app.state, "agent_loop", None)
    if agent_loop is None:
        raise HTTPException(
            status_code=503,
            detail="Agent loop not initialized. Check Vertex AI configuration.",
        )

    history_rows = store.get_conversation_history(session_id, limit=100)
    history = [
        ConversationMessage(role=str(msg.get("role", "user")), content=str(msg.get("content", "")))
        for msg in history_rows
    ]

    store.add_conversation_message(
        session_id=session_id,
        role="user",
        content=body.prompt,
        metadata={"stream": body.stream, "auto_qa": body.auto_qa},
    )
    store.add_session_event(
        session_id=session_id,
        event_type="user_prompt",
        action="prompt",
        summary=body.prompt[:200],
        input_signal=body.prompt,
        decision_reason="user_instruction_received",
        change_impact="agent_loop_triggered",
        confidence=1.0,
    )

    if body.stream:
        # Streaming mode: return chunks as they are generated
        async def _stream():
            codegen = getattr(request.app.state, "codegen_agent", None)
            if codegen is None:
                yield "<!-- Agent not configured -->"
                return

            collected = []
            async for chunk in codegen.generate_streaming(
                user_prompt=body.prompt,
                history=history,
                current_html=str(session.get("current_html", "")),
                genre_hint=str(session.get("genre", "")),
            ):
                collected.append(chunk)
                yield chunk

            final_html = "".join(collected)
            store.update_session_html(session_id, final_html, score=0)
            store.add_conversation_message(
                session_id=session_id,
                role="assistant",
                content=f"[Generated game stream: {len(final_html)} chars]",
                metadata={"stream": True},
            )
            store.add_session_event(
                session_id=session_id,
                event_type="stream_generation_completed",
                agent="codegen",
                action="generate",
                summary=f"Generated {len(final_html)} chars (stream)",
                input_signal=body.prompt[:500],
                decision_reason="streaming_generation_mode",
                change_impact="session_html_updated",
                confidence=0.8,
            )

        return StreamingResponse(_stream(), media_type="text/html")

    # Non-streaming mode: run full agent loop
    result = await agent_loop.run(
        user_prompt=body.prompt,
        history=history,
        current_html=str(session.get("current_html", "")),
        genre_hint=str(session.get("genre", "")),
        auto_qa=body.auto_qa,
    )

    if result.error:
        store.add_session_event(
            session_id=session_id,
            event_type="prompt_failed",
            agent="codegen",
            action="generate",
            summary=result.error[:200],
            decision_reason="agent_loop_failed",
            input_signal=body.prompt[:500],
            change_impact="no_html_update",
            confidence=0.0,
            error_code=result.error[:80],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "prompt_failed", "code": result.error},
        )

    store.update_session_html(session_id, result.html, score=result.final_score)
    store.add_conversation_message(
        session_id=session_id,
        role="assistant",
        content=f"[Generated game: {len(result.html)} chars, score: {result.final_score}]",
        metadata={
            "final_score": result.final_score,
            "generation_source": result.generation_source,
            "auto_refined": result.auto_refined,
        },
    )

    activities_payload: list[ActivityResponse] = []
    for activity in result.activities:
        store.add_session_event(
            session_id=session_id,
            event_type="agent_activity",
            agent=activity.agent,
            action=activity.action,
            summary=activity.summary,
            score=activity.score,
            before_score=activity.before_score,
            after_score=activity.after_score,
            decision_reason=activity.decision_reason,
            input_signal=activity.input_signal,
            change_impact=activity.change_impact,
            confidence=activity.confidence,
            error_code=activity.error_code,
            metadata=activity.metadata,
        )
        activities_payload.append(
            ActivityResponse(
                agent=activity.agent,
                action=activity.action,
                summary=activity.summary,
                score=activity.score,
                decision_reason=activity.decision_reason,
                input_signal=activity.input_signal,
                change_impact=activity.change_impact,
                confidence=activity.confidence,
                error_code=activity.error_code,
                before_score=activity.before_score,
                after_score=activity.after_score,
            )
        )

    return PromptResponse(
        html=result.html,
        score=result.final_score,
        activities=activities_payload,
        generation_source=result.generation_source,
        auto_refined=result.auto_refined,
        error=result.error,
    )


@router.post("/{session_id}/publish", response_model=PublishResponse)
async def publish_session(session_id: str, body: PublishRequest, request: Request) -> PublishResponse:
    """Publish the current game to the platform."""
    store = _get_session_store(request)
    session = _load_session_or_404(store, session_id)
    if str(session.get("status", "active")) == "cancelled":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cancelled session cannot be published")
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
            summary=str(exc)[:200],
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
