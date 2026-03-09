"""Supabase-backed storage for editor sessions.

세션 본문, 대화 기록, 실행 상태, 이슈/수정안, 퍼블리시 이력을
하나의 저장 계층으로 묶어 세션 API가 같은 계약을 보게 합니다.
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

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    # --- Session lifecycle -------------------------------------------------

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
            "created_at": self._now_iso(),
            "updated_at": self._now_iso(),
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
            "updated_at": self._now_iso(),
        }).eq("id", session_id).execute()

    def update_session_status(self, session_id: str, status: str) -> None:
        self._client.table("sessions").update({
            "status": status,
            "updated_at": self._now_iso(),
        }).eq("id", session_id).execute()

    def update_session(self, session_id: str, **fields: Any) -> None:
        if not fields:
            return
        safe_fields = dict(fields)
        if "title" in safe_fields:
            safe_fields["title"] = redact_sensitive_data(str(safe_fields["title"]))[:300]
        if "genre" in safe_fields:
            safe_fields["genre"] = redact_sensitive_data(str(safe_fields["genre"]))[:120]
        safe_fields["updated_at"] = self._now_iso()
        self._client.table("sessions").update(safe_fields).eq("id", session_id).execute()

    def delete_session(self, session_id: str) -> None:
        self._client.table("sessions").delete().eq("id", session_id).execute()
        self._client.table("conversation_history").delete().eq("session_id", session_id).execute()
        self._client.table("session_events").delete().eq("session_id", session_id).execute()
        self._client.table("session_runs").delete().eq("session_id", session_id).execute()
        self._client.table("session_issues").delete().eq("session_id", session_id).execute()
        self._client.table("session_issue_proposals").delete().eq("session_id", session_id).execute()
        self._client.table("session_publish_approvals").delete().eq("session_id", session_id).execute()
        self._client.table("session_publish_history").delete().eq("session_id", session_id).execute()

    # --- Conversation and timeline ----------------------------------------

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
            "created_at": self._now_iso(),
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
            "created_at": self._now_iso(),
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

    # --- Async run tracking ------------------------------------------------

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
            "created_at": self._now_iso(),
        }
        self._client.table("session_publish_history").insert(row).execute()

    def create_session_run(
        self,
        *,
        session_id: str,
        prompt: str,
        auto_qa: bool,
        status: str = "queued",
    ) -> dict[str, Any]:
        row = {
            "id": str(uuid4()),
            "session_id": session_id,
            "prompt": redact_sensitive_data(prompt)[:10000],
            "auto_qa": bool(auto_qa),
            "status": status,
            "error_code": None,
            "error_detail": "",
            "final_score": 0,
            "activities": [],
            "created_at": self._now_iso(),
            "started_at": None,
            "finished_at": None,
            "attempt_count": 0,
            "retry_after_seconds": None,
            "model_name": None,
            "model_location": None,
            "fallback_used": False,
            "capacity_error": None,
            "updated_at": self._now_iso(),
        }
        try:
            self._client.table("session_runs").insert(row).execute()
        except Exception:
            legacy_row = dict(row)
            for key in ("attempt_count", "retry_after_seconds", "model_name", "model_location", "fallback_used", "capacity_error"):
                legacy_row.pop(key, None)
            self._client.table("session_runs").insert(legacy_row).execute()
        return row

    def get_session_run(self, session_id: str, run_id: str) -> dict[str, Any] | None:
        result = (
            self._client.table("session_runs")
            .select("*")
            .eq("session_id", session_id)
            .eq("id", run_id)
            .single()
            .execute()
        )
        return result.data if hasattr(result, "data") else None

    def update_session_run(self, session_id: str, run_id: str, **fields: Any) -> None:
        if not fields:
            return
        safe_fields = dict(fields)
        if "error_detail" in safe_fields:
            safe_fields["error_detail"] = redact_sensitive_data(str(safe_fields["error_detail"]))[:10000]
        if "activities" in safe_fields:
            safe_fields["activities"] = redact_sensitive_data(safe_fields["activities"])
        safe_fields["updated_at"] = self._now_iso()
        try:
            self._client.table("session_runs").update(safe_fields).eq("session_id", session_id).eq("id", run_id).execute()
        except Exception:
            legacy_fields = dict(safe_fields)
            if legacy_fields.get("status") == "retrying":
                legacy_fields["status"] = "queued"
            for key in ("attempt_count", "retry_after_seconds", "model_name", "model_location", "fallback_used", "capacity_error"):
                legacy_fields.pop(key, None)
            self._client.table("session_runs").update(legacy_fields).eq("session_id", session_id).eq("id", run_id).execute()

    # --- Human review loop -------------------------------------------------

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
            "id": str(uuid4()),
            "session_id": session_id,
            "title": redact_sensitive_data(title)[:300],
            "details": redact_sensitive_data(details)[:4000],
            "category": category,
            "status": "open",
            "created_by": created_by,
            "created_at": self._now_iso(),
            "updated_at": self._now_iso(),
        }
        self._client.table("session_issues").insert(row).execute()
        return row

    def get_session_issue(self, session_id: str, issue_id: str) -> dict[str, Any] | None:
        result = (
            self._client.table("session_issues")
            .select("*")
            .eq("session_id", session_id)
            .eq("id", issue_id)
            .single()
            .execute()
        )
        return result.data if hasattr(result, "data") else None

    def update_session_issue(self, session_id: str, issue_id: str, **fields: Any) -> None:
        if not fields:
            return
        safe_fields = dict(fields)
        if "details" in safe_fields:
            safe_fields["details"] = redact_sensitive_data(str(safe_fields["details"]))[:4000]
        if "title" in safe_fields:
            safe_fields["title"] = redact_sensitive_data(str(safe_fields["title"]))[:300]
        safe_fields["updated_at"] = self._now_iso()
        self._client.table("session_issues").update(safe_fields).eq("session_id", session_id).eq("id", issue_id).execute()

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
            "id": str(uuid4()),
            "session_id": session_id,
            "issue_id": issue_id,
            "summary": redact_sensitive_data(summary)[:1000],
            "proposal_prompt": redact_sensitive_data(proposal_prompt)[:4000],
            "preview_html": preview_html,
            "status": "proposed",
            "proposed_by": proposed_by,
            "created_at": self._now_iso(),
            "updated_at": self._now_iso(),
        }
        self._client.table("session_issue_proposals").insert(row).execute()
        return row

    def get_issue_proposal(self, session_id: str, issue_id: str, proposal_id: str) -> dict[str, Any] | None:
        result = (
            self._client.table("session_issue_proposals")
            .select("*")
            .eq("session_id", session_id)
            .eq("issue_id", issue_id)
            .eq("id", proposal_id)
            .single()
            .execute()
        )
        return result.data if hasattr(result, "data") else None

    def get_latest_issue_proposal(self, session_id: str, issue_id: str) -> dict[str, Any] | None:
        result = (
            self._client.table("session_issue_proposals")
            .select("*")
            .eq("session_id", session_id)
            .eq("issue_id", issue_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data if hasattr(result, "data") and isinstance(result.data, list) else []
        return rows[0] if rows else None

    def update_issue_proposal(self, session_id: str, issue_id: str, proposal_id: str, **fields: Any) -> None:
        if not fields:
            return
        safe_fields = dict(fields)
        if "summary" in safe_fields:
            safe_fields["summary"] = redact_sensitive_data(str(safe_fields["summary"]))[:1000]
        safe_fields["updated_at"] = self._now_iso()
        self._client.table("session_issue_proposals").update(safe_fields).eq("session_id", session_id).eq("issue_id", issue_id).eq("id", proposal_id).execute()

    def create_publish_approval(
        self,
        *,
        session_id: str,
        approved_by: str = "master_admin",
        note: str = "",
    ) -> dict[str, Any]:
        row = {
            "id": str(uuid4()),
            "session_id": session_id,
            "approved_by": approved_by,
            "note": redact_sensitive_data(note)[:1000],
            "approved_at": self._now_iso(),
        }
        self._client.table("session_publish_approvals").insert(row).execute()
        return row

    def get_latest_publish_approval(self, session_id: str) -> dict[str, Any] | None:
        result = (
            self._client.table("session_publish_approvals")
            .select("*")
            .eq("session_id", session_id)
            .order("approved_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data if hasattr(result, "data") and isinstance(result.data, list) else []
        return rows[0] if rows else None

    def clear_publish_approvals(self, session_id: str) -> None:
        self._client.table("session_publish_approvals").delete().eq("session_id", session_id).execute()


def enable_supabase_persistence(app: Any, settings: Any) -> None:
    """앱 상태에 세션 저장소를 연결하고 없으면 명시적으로 비웁니다."""
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
