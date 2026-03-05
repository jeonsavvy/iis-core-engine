"""Supabase session persistence.

Provides async session CRUD backed by the 'sessions' and
'conversation_history' tables in the Supabase schema.

NOTE: This is opt-in — MVP uses in-memory sessions in session_router.py.
      Call `enable_supabase_persistence(app)` at startup to switch.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

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
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        result = self._client.table("sessions").insert(row).execute()
        if hasattr(result, "error") and result.error:
            raise RuntimeError(f"Session creation failed: {result.error}")
        return row

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

    def add_conversation_message(
        self,
        *,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        row = {
            "id": str(uuid4()),
            "session_id": session_id,
            "role": role,
            "content": content[:10000],
            "metadata": metadata or {},
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


def enable_supabase_persistence(app: Any, settings: Any) -> None:
    """Attach persistent session store to FastAPI app state."""
    if not settings.supabase_url or not settings.supabase_service_role_key:
        logger.warning("Supabase not configured, using in-memory sessions.")
        return

    try:
        from supabase import create_client

        client = create_client(settings.supabase_url, settings.supabase_service_role_key)
        store = SupabaseSessionStore(client)
        app.state.session_store = store
        logger.info("Supabase session persistence enabled.")
    except ImportError:
        logger.warning("supabase-py not installed, using in-memory sessions.")
    except Exception as exc:
        logger.warning("Failed to init Supabase session store: %s", exc)
