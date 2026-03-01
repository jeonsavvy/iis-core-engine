from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Iterable
from uuid import UUID, uuid4

from supabase import Client, create_client

from app.core.config import Settings
from app.schemas.pipeline import ExecutionMode, PipelineAgentName, PipelineLogRecord, PipelineStage, PipelineStatus, TriggerRequest, TriggerSource
from app.services.trigger_guard import validate_keyword

logger = logging.getLogger(__name__)


@dataclass
class PipelineJob:
    pipeline_id: UUID
    keyword: str
    source: TriggerSource
    status: PipelineStatus
    requested_by: UUID | None
    qa_fail_until: int
    metadata: dict[str, Any]
    error_reason: str | None
    created_at: datetime
    updated_at: datetime


class PipelineRepository:
    """Supabase-backed queue with in-memory fallback for local scaffolding."""

    def __init__(self, client: Client | None = None, settings: Settings | None = None) -> None:
        self.client = client
        self.settings = settings or Settings()
        self._lock = Lock()
        self._memory_jobs: dict[str, dict[str, Any]] = {}
        self._memory_logs: dict[str, list[dict[str, Any]]] = {}
        self._memory_asset_registry: dict[str, dict[str, Any]] = {}
        self._memory_qa_improvements: list[dict[str, Any]] = []

    @classmethod
    def from_settings(cls, settings: Settings) -> "PipelineRepository":
        supabase_url = (settings.supabase_url or "").strip()
        service_key = (settings.supabase_service_role_key or "").strip()
        if supabase_url and service_key and supabase_url.startswith(("http://", "https://")):
            try:
                client = create_client(supabase_url, service_key)
                return cls(client=client, settings=settings)
            except Exception as exc:  # pragma: no cover - defensive fallback
                logger.warning("Failed to initialize Supabase client; falling back to in-memory repository: %s", exc)
        return cls(client=None, settings=settings)

    def create_pipeline(self, request: TriggerRequest) -> PipelineJob:
        idempotency_key = (request.idempotency_key or "").strip() or None
        if idempotency_key:
            existing = self._find_pipeline_by_idempotency_key(
                idempotency_key=idempotency_key,
                requested_by=request.requested_by,
                source=request.source,
            )
            if existing is not None:
                return existing

        normalized_keyword, safe_slug = validate_keyword(
            request.keyword,
            forbidden_terms=self.settings.trigger_forbidden_keyword_set(),
            min_length=self.settings.trigger_min_keyword_length,
            max_length=200,
        )
        pipeline_version = request.pipeline_version.strip() or self.settings.pipeline_default_version
        request_id = str(uuid4())
        payload = {
            **request.metadata,
            "qa_fail_until": request.qa_fail_until,
            "safe_slug": safe_slug,
            "execution_mode": ExecutionMode.AUTO.value,
            "pipeline_version": pipeline_version,
            "request_id": request_id,
            "idempotency_key": idempotency_key,
            "operator_control": {"pause_requested": False, "cancel_requested": False},
        }
        return self._insert_admin_config(
            requested_by=request.requested_by,
            source=request.source,
            keyword=normalized_keyword,
            payload=payload,
            status=PipelineStatus.QUEUED,
            error_reason=None,
        )

    def _find_pipeline_by_idempotency_key(
        self,
        *,
        idempotency_key: str,
        requested_by: UUID | None,
        source: TriggerSource,
    ) -> PipelineJob | None:
        requested_by_value = str(requested_by) if requested_by else None

        if self.client:
            result = (
                self.client.table("admin_config")
                .select("*")
                .eq("trigger_source", source.value)
                .order("created_at", desc=True)
                .limit(200)
                .execute()
            )
            for row in result.data or []:
                payload = row.get("payload")
                if not isinstance(payload, dict):
                    continue
                if payload.get("idempotency_key") != idempotency_key:
                    continue
                row_requested_by = str(row["requested_by"]) if row.get("requested_by") else None
                if row_requested_by != requested_by_value:
                    continue
                return self._job_from_row(row)
            return None

        with self._lock:
            sorted_rows = sorted(self._memory_jobs.values(), key=lambda row: row.get("created_at", ""), reverse=True)
            for row in sorted_rows:
                if row.get("trigger_source") != source.value:
                    continue
                payload = row.get("payload")
                if not isinstance(payload, dict):
                    continue
                if payload.get("idempotency_key") != idempotency_key:
                    continue
                row_requested_by = str(row["requested_by"]) if row.get("requested_by") else None
                if row_requested_by != requested_by_value:
                    continue
                return self._job_from_row(row)
            return None

    def create_audit_entry(
        self,
        *,
        source: TriggerSource,
        keyword: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> PipelineJob:
        return self._insert_admin_config(
            requested_by=None,
            source=source,
            keyword=keyword,
            payload=metadata or {},
            status=PipelineStatus.SKIPPED,
            error_reason=reason,
        )

    def _insert_admin_config(
        self,
        *,
        requested_by: UUID | None,
        source: TriggerSource,
        keyword: str,
        payload: dict[str, Any],
        status: PipelineStatus,
        error_reason: str | None,
    ) -> PipelineJob:
        now = datetime.now(timezone.utc)
        pipeline_id = uuid4()

        if self.client:
            data = {
                "id": str(pipeline_id),
                "requested_by": str(requested_by) if requested_by else None,
                "trigger_source": source.value,
                "keyword": keyword,
                "payload": payload,
                "status": status.value,
                "error_reason": error_reason,
            }
            result = self.client.table("admin_config").insert(data).execute()
            row = (result.data or [data])[0]
            return self._job_from_row(row)

        with self._lock:
            row = {
                "id": str(pipeline_id),
                "requested_by": str(requested_by) if requested_by else None,
                "trigger_source": source.value,
                "keyword": keyword,
                "payload": payload,
                "status": status.value,
                "error_reason": error_reason,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
            self._memory_jobs[str(pipeline_id)] = row
            self._memory_logs[str(pipeline_id)] = []
            return self._job_from_row(row)

    def requeue_stale_running_pipelines(self, max_age_seconds: int) -> int:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=max_age_seconds)
        requeued = 0

        if self.client:
            running_rows = (
                self.client.table("admin_config")
                .select("id,updated_at,status")
                .eq("status", PipelineStatus.RUNNING.value)
                .limit(500)
                .execute()
            )

            for row in running_rows.data or []:
                updated_at = self._to_dt(row.get("updated_at"))
                if updated_at >= cutoff:
                    continue

                updated = (
                    self.client.table("admin_config")
                    .update(
                        {
                            "status": PipelineStatus.QUEUED.value,
                            "error_reason": "requeued_stale_running",
                            "updated_at": now.isoformat(),
                        }
                    )
                    .eq("id", row["id"])
                    .eq("status", PipelineStatus.RUNNING.value)
                    .execute()
                )
                if updated.data:
                    requeued += 1
            return requeued

        with self._lock:
            for row in self._memory_jobs.values():
                if row.get("status") != PipelineStatus.RUNNING.value:
                    continue

                updated_at = self._to_dt(row.get("updated_at"))
                if updated_at >= cutoff:
                    continue

                row["status"] = PipelineStatus.QUEUED.value
                row["error_reason"] = "requeued_stale_running"
                row["updated_at"] = now.isoformat()
                requeued += 1

        return requeued

    def get_pipeline(self, pipeline_id: UUID) -> PipelineJob | None:
        if self.client:
            result = self.client.table("admin_config").select("*").eq("id", str(pipeline_id)).limit(1).execute()
            rows = result.data or []
            if not rows:
                return None
            return self._job_from_row(rows[0])

        with self._lock:
            row = self._memory_jobs.get(str(pipeline_id))
            if not row:
                return None
            return self._job_from_row(row)

    def has_pipeline_history(self, pipeline_id: UUID) -> bool:
        pipeline_id_text = str(pipeline_id)
        if self.client:
            admin_rows = self.client.table("admin_config").select("id").eq("id", pipeline_id_text).limit(1).execute()
            if admin_rows.data:
                return True
            log_rows = self.client.table("pipeline_logs").select("id").eq("pipeline_id", pipeline_id_text).limit(1).execute()
            return bool(log_rows.data)

        with self._lock:
            if pipeline_id_text in self._memory_jobs:
                return True
            return any(str(row.get("pipeline_id", "")).strip() == pipeline_id_text for rows in self._memory_logs.values() for row in rows)

    def list_logs(self, pipeline_id: UUID, limit: int = 200) -> list[PipelineLogRecord]:
        if self.client:
            result = (
                self.client.table("pipeline_logs")
                .select("*")
                .eq("pipeline_id", str(pipeline_id))
                .order("created_at", desc=False)
                .limit(limit)
                .execute()
            )
            return [self._log_from_row(row) for row in (result.data or [])]

        with self._lock:
            rows = self._memory_logs.get(str(pipeline_id), [])[:limit]
            return [self._log_from_row(row) for row in rows]

    def list_recent_logs(self, limit: int = 100) -> list[PipelineLogRecord]:
        if self.client:
            result = self.client.table("pipeline_logs").select("*").order("created_at", desc=True).limit(limit).execute()
            return [self._log_from_row(row) for row in (result.data or [])]

        with self._lock:
            rows: list[dict[str, Any]] = []
            for log_list in self._memory_logs.values():
                rows.extend(log_list)
            rows.sort(key=lambda row: row["created_at"], reverse=True)
            return [self._log_from_row(row) for row in rows[:limit]]

    def upsert_asset_registry_entry(self, payload: dict[str, Any]) -> None:
        if not payload:
            return

        if self.client:
            try:
                self.client.table("asset_registry").upsert(payload, on_conflict="pipeline_id").execute()
            except Exception as exc:
                logger.warning("Failed to upsert asset_registry entry (continuing): %s", exc)
            return

        pipeline_id = str(payload.get("pipeline_id", "")).strip()
        if not pipeline_id:
            return
        with self._lock:
            row = dict(payload)
            row.setdefault("created_at", datetime.now(timezone.utc).isoformat())
            row["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._memory_asset_registry[pipeline_id] = row

    def list_asset_registry(self, *, core_loop_type: str, limit: int = 80) -> list[dict[str, Any]]:
        normalized = core_loop_type.strip()
        if not normalized:
            return []

        if self.client:
            try:
                result = (
                    self.client.table("asset_registry")
                    .select("*")
                    .eq("core_loop_type", normalized)
                    .order("created_at", desc=True)
                    .limit(limit)
                    .execute()
                )
                rows = result.data or []
                return [row for row in rows if isinstance(row, dict)]
            except Exception as exc:
                logger.warning("Failed to read asset_registry (fallback to logs): %s", exc)
                return []

        with self._lock:
            rows = [dict(row) for row in self._memory_asset_registry.values() if str(row.get("core_loop_type", "")).strip() == normalized]
            rows.sort(key=lambda row: str(row.get("created_at", "")), reverse=True)
            return rows[:limit]

    def append_qa_improvement_entries(
        self,
        *,
        pipeline_id: str,
        game_slug: str,
        core_loop_type: str,
        keyword: str,
        entries: list[dict[str, object]],
    ) -> None:
        rows: list[dict[str, Any]] = []

        def _normalize_tokens(value: object) -> list[str]:
            if not isinstance(value, Iterable) or isinstance(value, (str, bytes, dict)):
                return []
            normalized_tokens: list[str] = []
            for token in value:
                text = str(token).strip()
                if text:
                    normalized_tokens.append(text)
            return normalized_tokens

        for entry in entries:
            reason = str(entry.get("reason", "")).strip()
            if not reason:
                continue
            row = {
                "pipeline_id": pipeline_id,
                "game_slug": game_slug,
                "core_loop_type": core_loop_type,
                "keyword": keyword,
                "stage": str(entry.get("stage", "")).strip(),
                "reason": reason,
                "severity": str(entry.get("severity", "low")).strip() or "low",
                "tokens": _normalize_tokens(entry.get("tokens")),
                "metrics": entry.get("metrics") if isinstance(entry.get("metrics"), dict) else {},
            }
            rows.append(row)

        if not rows:
            return

        if self.client:
            try:
                self.client.table("qa_improvement_queue").insert(rows).execute()
            except Exception as exc:
                logger.warning("Failed to append qa_improvement_queue rows (continuing): %s", exc)
            return

        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            for row in rows:
                row["created_at"] = now
                self._memory_qa_improvements.append(row)
            self._memory_qa_improvements = self._memory_qa_improvements[-600:]

    def list_qa_improvement_entries(self, *, core_loop_type: str, limit: int = 120) -> list[dict[str, Any]]:
        normalized = core_loop_type.strip()
        if not normalized:
            return []

        if self.client:
            try:
                result = (
                    self.client.table("qa_improvement_queue")
                    .select("*")
                    .eq("core_loop_type", normalized)
                    .order("created_at", desc=True)
                    .limit(limit)
                    .execute()
                )
                rows = result.data or []
                return [row for row in rows if isinstance(row, dict)]
            except Exception as exc:
                logger.warning("Failed to read qa_improvement_queue (continuing): %s", exc)
                return []

        with self._lock:
            rows = [dict(row) for row in self._memory_qa_improvements if str(row.get("core_loop_type", "")).strip() == normalized]
            rows.sort(key=lambda row: str(row.get("created_at", "")), reverse=True)
            return rows[:limit]

    def claim_next_queued_pipeline(self) -> PipelineJob | None:
        if self.client:
            queued = (
                self.client.table("admin_config")
                .select("*")
                .eq("status", PipelineStatus.QUEUED.value)
                .order("created_at", desc=False)
                .limit(10)
                .execute()
            )
            for row in queued.data or []:
                update = (
                    self.client.table("admin_config")
                    .update(
                        {
                            "status": PipelineStatus.RUNNING.value,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    .eq("id", row["id"])
                    .eq("status", PipelineStatus.QUEUED.value)
                    .execute()
                )
                updated_rows = update.data or []
                if updated_rows:
                    return self._job_from_row(updated_rows[0])
            return None

        with self._lock:
            queued_rows = sorted(
                (row for row in self._memory_jobs.values() if row["status"] == PipelineStatus.QUEUED.value),
                key=lambda row: row["created_at"],
            )
            if not queued_rows:
                return None
            row = queued_rows[0]
            row["status"] = PipelineStatus.RUNNING.value
            row["updated_at"] = datetime.now(timezone.utc).isoformat()
            return self._job_from_row(row)

    def get_execution_mode(self, job: PipelineJob) -> ExecutionMode:
        return ExecutionMode.AUTO

    def get_pipeline_version(self, job: PipelineJob) -> str:
        value = str(job.metadata.get("pipeline_version", "")).strip()
        return value or self.settings.pipeline_default_version

    def get_waiting_for_stage(self, job: PipelineJob) -> PipelineStage | None:
        return None

    def approve_stage(self, pipeline_id: UUID, stage: PipelineStage) -> PipelineJob | None:
        raise ValueError("approval_api_removed")

    def update_pipeline_metadata(
        self,
        pipeline_id: UUID,
        *,
        metadata_update: dict[str, Any],
        status: PipelineStatus | None = None,
        error_reason: str | None = None,
    ) -> PipelineJob | None:
        job = self.get_pipeline(pipeline_id)
        if job is None:
            return None

        merged_metadata = {**job.metadata, **metadata_update}
        update_payload: dict[str, Any] = {
            "payload": merged_metadata,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if status is not None:
            update_payload["status"] = status.value
        if error_reason is not None or status is not None:
            update_payload["error_reason"] = error_reason

        if self.client:
            result = self.client.table("admin_config").update(update_payload).eq("id", str(pipeline_id)).execute()
            rows = result.data or []
            return self._job_from_row(rows[0]) if rows else self.get_pipeline(pipeline_id)

        with self._lock:
            row = self._memory_jobs.get(str(pipeline_id))
            if not row:
                return None
            row["payload"] = merged_metadata
            row["updated_at"] = update_payload["updated_at"]
            if status is not None:
                row["status"] = status.value
                row["error_reason"] = error_reason
            elif error_reason is not None:
                row["error_reason"] = error_reason
            return self._job_from_row(row)

    @staticmethod
    def _parse_stage_values(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        parsed: list[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            try:
                parsed.append(PipelineStage(item).value)
            except ValueError:
                continue
        return parsed

    def is_stage_approved(self, job: PipelineJob, stage: PipelineStage) -> bool:
        return True

    def mark_pipeline_status(self, pipeline_id: UUID, status: PipelineStatus, error_reason: str | None = None) -> None:
        payload = {
            "status": status.value,
            "error_reason": error_reason,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if self.client:
            self.client.table("admin_config").update(payload).eq("id", str(pipeline_id)).execute()
            return

        with self._lock:
            row = self._memory_jobs.get(str(pipeline_id))
            if not row:
                return
            row.update(payload)

    def append_logs(self, logs: list[PipelineLogRecord]) -> None:
        if not logs:
            return

        if self.client:
            rows = [self._row_from_log(log) for log in logs]
            self.client.table("pipeline_logs").insert(rows).execute()
            return

        with self._lock:
            for log in logs:
                pipeline_id = str(log.pipeline_id)
                self._memory_logs.setdefault(pipeline_id, []).append(self._row_from_log(log))

    def _job_from_row(self, row: dict[str, Any]) -> PipelineJob:
        payload_raw = row.get("payload") or {}
        payload = payload_raw if isinstance(payload_raw, dict) else {}
        payload.setdefault("execution_mode", ExecutionMode.AUTO.value)
        payload.setdefault("pipeline_version", self.settings.pipeline_default_version)
        payload.setdefault("request_id", str(row.get("id")))
        payload.setdefault("idempotency_key", None)
        payload.setdefault("operator_control", {"pause_requested": False, "cancel_requested": False})
        return PipelineJob(
            pipeline_id=UUID(str(row["id"])),
            keyword=row.get("keyword", ""),
            source=TriggerSource(row.get("trigger_source", TriggerSource.CONSOLE.value)),
            status=PipelineStatus(row.get("status", PipelineStatus.QUEUED.value)),
            requested_by=UUID(str(row["requested_by"])) if row.get("requested_by") else None,
            qa_fail_until=int(payload.get("qa_fail_until", 0)),
            metadata=payload,
            error_reason=row.get("error_reason"),
            created_at=self._to_dt(row.get("created_at")),
            updated_at=self._to_dt(row.get("updated_at")),
        )

    @staticmethod
    def _to_dt(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.now(timezone.utc)

    @staticmethod
    def _row_from_log(log: PipelineLogRecord) -> dict[str, Any]:
        return {
            "pipeline_id": str(log.pipeline_id),
            "stage": log.stage.value,
            "status": log.status.value,
            "agent_name": log.agent_name.value,
            "message": log.message,
            "reason": log.reason,
            "attempt": log.attempt,
            "metadata": log.metadata,
            "created_at": log.created_at.isoformat(),
        }

    @staticmethod
    def _log_from_row(row: dict[str, Any]) -> PipelineLogRecord:
        return PipelineLogRecord(
            pipeline_id=UUID(str(row["pipeline_id"])),
            stage=PipelineStage(row["stage"]),
            status=PipelineStatus(row["status"]),
            agent_name=PipelineAgentName(row["agent_name"]),
            message=row.get("message", ""),
            reason=row.get("reason"),
            attempt=int(row.get("attempt", 1)),
            metadata=row.get("metadata") or {},
            created_at=PipelineRepository._to_dt(row.get("created_at")),
        )
