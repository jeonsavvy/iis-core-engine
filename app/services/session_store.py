"""Supabase session persistence.

Provides session CRUD + conversation + event timeline persistence.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.services.redaction import redact_sensitive_data

logger = logging.getLogger(__name__)


class SupabaseSessionStore:
    """Persistent session store backed by Supabase."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def create_session(
        self,
        *,
        user_id: str | None = None,
        title: str = "",
        genre: str = "",
    ) -> dict[str, Any]:
        session_id = str(uuid4())
        row = {
            "id": session_id,
            "user_id": user_id,
            "title": title or f"Game #{session_id[:8]}",
            "genre": genre,
            "status": "active",
            "current_html": "",
            "score": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        result = self._client.table("sessions").insert(row).execute()
        if hasattr(result, "error") and result.error:
            raise RuntimeError(f"Session creation failed: {result.error}")
        return row

    def list_sessions(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        resolved_limit = max(1, min(int(limit), 200))
        query = self._client.table("sessions").select("*").order("updated_at", desc=True).limit(resolved_limit)
        if status:
            query = query.eq("status", status)
        result = query.execute()
        rows = result.data if hasattr(result, "data") and isinstance(result.data, list) else []
        return rows

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        result = (
            self._client.table("sessions")
            .select("*")
            .eq("id", session_id)
            .single()
            .execute()
        )
        return result.data if hasattr(result, "data") else None

    def update_session_html(self, session_id: str, html: str, score: int = 0) -> None:
        self._client.table("sessions").update({
            "current_html": html,
            "score": score,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", session_id).execute()

    def update_session_status(self, session_id: str, status: str) -> None:
        self._client.table("sessions").update({
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", session_id).execute()

    def delete_session(self, session_id: str) -> None:
        self._client.table("sessions").delete().eq("id", session_id).execute()
        self._client.table("conversation_history").delete().eq("session_id", session_id).execute()
        self._client.table("session_events").delete().eq("session_id", session_id).execute()
        self._client.table("session_publish_history").delete().eq("session_id", session_id).execute()

    def add_conversation_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        safe_content = redact_sensitive_data(content) if isinstance(content, str) else ""
        safe_metadata = redact_sensitive_data(metadata or {})
        row = {
            "id": str(uuid4()),
            "session_id": session_id,
            "role": role,
            "content": safe_content[:10000],
            "metadata": safe_metadata,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._client.table("conversation_history").insert(row).execute()

    def get_conversation_history(
        self,
        session_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        result = (
            self._client.table("conversation_history")
            .select("*")
            .eq("session_id", session_id)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        return result.data if hasattr(result, "data") else []

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
            "id": str(uuid4()),
            "session_id": session_id,
            "event_type": str(event_type).strip() or "unknown",
            "agent": agent,
            "action": action,
            "summary": redact_sensitive_data(summary)[:10000],
            "score": int(score) if isinstance(score, int) else None,
            "before_score": int(before_score) if isinstance(before_score, int) else None,
            "after_score": int(after_score) if isinstance(after_score, int) else None,
            "decision_reason": redact_sensitive_data(decision_reason)[:10000],
            "input_signal": redact_sensitive_data(input_signal)[:10000],
            "change_impact": redact_sensitive_data(change_impact)[:10000],
            "confidence": float(confidence) if isinstance(confidence, (int, float)) else None,
            "error_code": str(error_code).strip() if isinstance(error_code, str) and error_code.strip() else None,
            "metadata": redact_sensitive_data(metadata or {}),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._client.table("session_events").insert(row).execute()
        return row

    def get_session_events(
        self,
        session_id: str,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> list[dict[str, Any]]:
        resolved_limit = max(1, min(int(limit), 200))
        query = (
            self._client.table("session_events")
            .select("*")
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .limit(resolved_limit)
        )
        if isinstance(cursor, str) and cursor.strip():
            query = query.lt("created_at", cursor.strip())
        result = query.execute()
        rows = result.data if hasattr(result, "data") and isinstance(result.data, list) else []
        return rows

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
        row = {
            "id": str(uuid4()),
            "session_id": session_id,
            "game_id": game_id,
            "game_slug": game_slug,
            "play_url": play_url,
            "public_url": public_url,
            "metadata": redact_sensitive_data(metadata or {}),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._client.table("session_publish_history").insert(row).execute()


def enable_supabase_persistence(app: Any, settings: Any) -> None:
    """Attach persistent session store to FastAPI app state."""
    if not settings.supabase_url or not settings.supabase_service_role_key:
        logger.warning("Supabase not configured. Session API will return 503.")
        return

    try:
        from supabase import create_client

        client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        store = SupabaseSessionStore(client)
        app.state.session_store = store
        logger.info("Supabase session persistence enabled.")
    except ImportError:
        logger.warning("supabase-py not installed. Session API will return 503.")
    except Exception as exc:
        logger.warning("Failed to init Supabase session store: %s", exc)
