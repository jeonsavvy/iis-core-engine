"""Session API — interactive game creation sessions.

Replaces the batch pipeline trigger/status endpoints with a
conversational session model for the game editor.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


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


class PromptResponse(BaseModel):
    html: str
    score: int = 0
    activities: list[dict[str, Any]] = []
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


class PublishRequest(BaseModel):
    game_name: str = ""
    slug: str = ""


class PublishResponse(BaseModel):
    success: bool
    game_slug: str = ""
    game_url: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# In-memory session store (MVP; migrate to Supabase in production)
# ---------------------------------------------------------------------------

_sessions: dict[str, dict[str, Any]] = {}


def _get_session(session_id: str) -> dict[str, Any]:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=CreateSessionResponse)
async def create_session(body: CreateSessionRequest) -> CreateSessionResponse:
    """Create a new interactive game editing session."""
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "id": session_id,
        "title": body.title or f"Game #{len(_sessions) + 1}",
        "genre": body.genre_hint,
        "status": "active",
        "current_html": "",
        "history": [],
    }
    logger.info("Session created: %s", session_id)
    return CreateSessionResponse(
        session_id=session_id,
        title=_sessions[session_id]["title"],
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    """Get session state."""
    session = _get_session(session_id)
    return SessionResponse(
        session_id=session["id"],
        title=session["title"],
        genre=session.get("genre", ""),
        status=session["status"],
        current_html=session.get("current_html", ""),
        conversation_count=len(session.get("history", [])),
    )


@router.post("/{session_id}/prompt", response_model=PromptResponse)
async def send_prompt(session_id: str, body: PromptRequest, request: Request) -> Any:
    """Send a prompt to generate/modify the game.

    This is the core endpoint — replaces the entire batch pipeline.
    User sends natural language, gets back a playable game.
    """
    session = _get_session(session_id)

    # Get agent loop from app state (injected at startup)
    agent_loop = getattr(request.app.state, "agent_loop", None)
    if agent_loop is None:
        raise HTTPException(
            status_code=503,
            detail="Agent loop not initialized. Check Vertex AI configuration.",
        )

    # Build conversation history
    from app.agents.codegen_agent import ConversationMessage

    history = [
        ConversationMessage(role=msg["role"], content=msg["content"])
        for msg in session.get("history", [])
    ]

    # Add user message to history
    session.setdefault("history", []).append({
        "role": "user",
        "content": body.prompt,
    })

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
                current_html=session.get("current_html", ""),
                genre_hint=session.get("genre", ""),
            ):
                collected.append(chunk)
                yield chunk

            final_html = "".join(collected)
            session["current_html"] = final_html
            session["history"].append({
                "role": "assistant",
                "content": f"[Generated game: {len(final_html)} chars]",
            })

        return StreamingResponse(_stream(), media_type="text/html")

    # Non-streaming mode: run full agent loop
    result = await agent_loop.run(
        user_prompt=body.prompt,
        history=history,
        current_html=session.get("current_html", ""),
        genre_hint=session.get("genre", ""),
        auto_qa=body.auto_qa,
    )

    # Update session state
    session["current_html"] = result.html
    session["history"].append({
        "role": "assistant",
        "content": f"[Generated game: {len(result.html)} chars, score: {result.final_score}]",
    })

    # Add agent feedback to history
    for activity in result.activities:
        if activity.agent in ("visual_qa", "playtester") and activity.result_summary:
            session["history"].append({
                "role": activity.agent,
                "content": activity.result_summary,
            })

    return PromptResponse(
        html=result.html,
        score=result.final_score,
        activities=[
            {
                "agent": a.agent,
                "action": a.action,
                "summary": a.result_summary,
                "score": a.score,
            }
            for a in result.activities
        ],
        generation_source=result.generation_source,
        auto_refined=result.auto_refined,
        error=result.error,
    )


@router.post("/{session_id}/publish", response_model=PublishResponse)
async def publish_session(session_id: str, body: PublishRequest, request: Request) -> PublishResponse:
    """Publish the current game to the platform."""
    session = _get_session(session_id)
    html = session.get("current_html", "")
    if not html.strip():
        raise HTTPException(status_code=400, detail="No game to publish. Generate a game first.")

    publisher = getattr(request.app.state, "publisher_service", None)
    if publisher is None:
        return PublishResponse(
            success=False,
            error="Publisher not configured",
        )

    slug = body.slug or session_id[:8]
    game_name = body.game_name or session.get("title", f"Game {slug}")

    try:
        await publisher.publish(
            slug=slug,
            game_name=game_name,
            genre=session.get("genre", ""),
            html_content=html,
        )
        session["status"] = "published"
        return PublishResponse(
            success=True,
            game_slug=slug,
            game_url=f"/play/{slug}",
        )
    except Exception as exc:
        logger.exception("Publish failed: %s", exc)
        return PublishResponse(
            success=False,
            error=str(exc)[:200],
        )


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> dict[str, str]:
    """Delete a session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    del _sessions[session_id]
    return {"status": "deleted"}
