from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any
from uuid import UUID

from app.core.config import Settings
from app.schemas.pipeline import ExecutionMode, PipelineStage, PipelineStatus, TriggerRequest, TriggerSource
from app.schemas.telegram import TelegramWebhookResponse, TelegramWebhookUpdate
from app.services.game_admin_service import GameAdminService
from app.services.http_client import request_with_retry
from app.services.pipeline_repository import PipelineRepository

DANGEROUS_COMMANDS = {"/retry", "/cancel", "/reset", "/delete_game"}


class TelegramService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send_message(self, chat_id: str, text: str) -> dict[str, str]:
        if not self.settings.telegram_bot_token:
            return {"status": "skipped", "reason": "TELEGRAM_BOT_TOKEN is not configured."}

        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        request_with_retry(
            "POST",
            url,
            timeout_seconds=self.settings.http_timeout_seconds,
            max_retries=self.settings.http_max_retries,
            json={"chat_id": chat_id, "text": text},
        )
        return {"status": "sent"}

    def broadcast_message(self, text: str) -> dict[str, str]:
        allowed = self.settings.telegram_allowed_chat_id_set()
        if not allowed:
            return {"status": "skipped", "reason": "No allowed chat IDs configured for broadcast."}

        success_count = 0
        for chat_id in allowed:
            result = self.send_message(chat_id, text)
            if result.get("status") == "sent":
                success_count += 1

        if success_count > 0:
            return {"status": "posted"}
        return {"status": "error", "reason": "Failed to send broadcast to any allowed chats."}

    def handle_update(self, update: TelegramWebhookUpdate, repository: PipelineRepository) -> TelegramWebhookResponse:
        message = update.active_message()
        if message is None or not message.text:
            return TelegramWebhookResponse(status="ignored", detail="message.text is missing")

        chat_id = str(message.chat.id)
        user_id = str(message.from_user.id) if message.from_user else ""
        command, argument = self._parse_command(message.text)
        if not command:
            return TelegramWebhookResponse(status="ignored", detail="empty command")

        control_guard = self._guard_control_mode()
        if control_guard:
            audit_job = repository.create_audit_entry(
                source=TriggerSource.TELEGRAM,
                keyword=f"[BLOCKED] {message.text[:120]}",
                reason=control_guard,
                metadata={"chat_id": chat_id, "user_id": user_id, "command": command, "argument": argument},
            )
            self.send_message(chat_id, f"명령 거부: {control_guard}")
            self._notify_admin_security_event(
                f"[SECURITY] command blocked ({control_guard}) user={user_id or '-'} chat={chat_id} cmd={command}"
            )
            return TelegramWebhookResponse(
                status="blocked",
                detail=control_guard,
                pipeline_id=str(audit_job.pipeline_id),
                payload={"chat_id": chat_id, "user_id": user_id, "reason": control_guard},
            )

        if not self._is_allowed_chat(chat_id):
            return self._reject_unauthorized(
                repository=repository,
                message_text=message.text,
                chat_id=chat_id,
                user_id=user_id,
                command=command,
                argument=argument,
                reason="telegram_chat_not_allowed",
            )

        if not self._is_allowed_user(user_id):
            return self._reject_unauthorized(
                repository=repository,
                message_text=message.text,
                chat_id=chat_id,
                user_id=user_id,
                command=command,
                argument=argument,
                reason="telegram_user_not_allowed",
            )

        if command in {"/start", "/help"}:
            self.send_message(chat_id, self._command_help_message())
            return TelegramWebhookResponse(status="help", detail=command)

        if command == "/run":
            return self._handle_run(chat_id=chat_id, keyword=argument, repository=repository, user_id=user_id)

        if command == "/status":
            return self._handle_status(chat_id=chat_id, pipeline_id_arg=argument, repository=repository)

        if command == "/approve":
            return self._handle_approve(chat_id=chat_id, argument=argument, repository=repository)

        if command == "/logs":
            return self._handle_logs(chat_id=chat_id, argument=argument, repository=repository)

        if command in DANGEROUS_COMMANDS and not self.settings.telegram_allow_dangerous_commands:
            self.send_message(chat_id, "위험 명령은 현재 비활성화되어 있습니다.")
            return TelegramWebhookResponse(status="blocked", detail="dangerous_commands_disabled")

        if command == "/retry":
            return self._request_confirmation(
                chat_id=chat_id,
                user_id=user_id,
                action="retry",
                target=argument,
                repository=repository,
            )

        if command == "/cancel":
            return self._request_confirmation(
                chat_id=chat_id,
                user_id=user_id,
                action="cancel",
                target=argument,
                repository=repository,
            )

        if command == "/reset":
            return self._request_confirmation(
                chat_id=chat_id,
                user_id=user_id,
                action="reset",
                target=argument,
                repository=repository,
            )

        if command == "/delete_game":
            return self._request_confirmation(
                chat_id=chat_id,
                user_id=user_id,
                action="delete_game",
                target=argument,
                repository=repository,
            )

        if command == "/confirm":
            return self._handle_confirm(chat_id=chat_id, user_id=user_id, token=argument, repository=repository)

        self.send_message(
            chat_id,
            self._command_help_message(),
        )
        return TelegramWebhookResponse(status="unknown_command", detail=command)

    @staticmethod
    def _command_help_message() -> str:
        return (
            "IIS 제어 봇 명령 안내\n"
            "- /run <keyword>\n"
            "- /status <pipeline_id>\n"
            "- /approve <pipeline_id> <stage>\n"
            "- /logs <pipeline_id> [limit]\n"
            "- /retry|/cancel|/reset <pipeline_id> (확인 필요)\n"
            "- /delete_game <game_id> (확인 필요)\n"
            "- /confirm <token>"
        )

    def _handle_run(
        self,
        *,
        chat_id: str,
        keyword: str,
        repository: PipelineRepository,
        user_id: str,
    ) -> TelegramWebhookResponse:
        if not keyword:
            self.send_message(chat_id, "Usage: /run <keyword>")
            return TelegramWebhookResponse(status="invalid", detail="missing keyword")

        trigger_request = TriggerRequest(
            keyword=keyword,
            source=TriggerSource.TELEGRAM,
            metadata={"chat_id": chat_id, "user_id": user_id, "entry": "telegram_command"},
        )
        try:
            job = repository.create_pipeline(trigger_request)
        except ValueError as exc:
            self.send_message(chat_id, f"Invalid keyword: {exc}")
            return TelegramWebhookResponse(status="invalid", detail=str(exc))

        self.send_message(chat_id, f"Queued: {job.pipeline_id}")
        return TelegramWebhookResponse(
            status="queued",
            pipeline_id=str(job.pipeline_id),
            payload={"source": TriggerSource.TELEGRAM.value},
        )

    def _handle_status(self, *, chat_id: str, pipeline_id_arg: str, repository: PipelineRepository) -> TelegramWebhookResponse:
        pipeline_id = self._parse_uuid_arg(pipeline_id_arg, usage_message="Usage: /status <pipeline_id>", chat_id=chat_id)
        if pipeline_id is None:
            return TelegramWebhookResponse(status="invalid", detail="pipeline_id must be UUID")

        job = repository.get_pipeline(pipeline_id)
        if job is None:
            self.send_message(chat_id, "Pipeline not found.")
            return TelegramWebhookResponse(status="not_found", detail="pipeline does not exist")

        waiting = repository.get_waiting_for_stage(job)
        self.send_message(
            chat_id,
            "\n".join(
                [
                    f"Pipeline {job.pipeline_id}",
                    f"status={job.status.value}",
                    f"source={job.source.value}",
                    f"execution_mode={repository.get_execution_mode(job).value}",
                    f"waiting_for_stage={waiting.value if waiting else '-'}",
                    f"error={job.error_reason or '-'}",
                ]
            ),
        )
        return TelegramWebhookResponse(
            status="status_reported",
            pipeline_id=str(job.pipeline_id),
            payload={"pipeline_status": job.status.value},
        )

    def _handle_approve(self, *, chat_id: str, argument: str, repository: PipelineRepository) -> TelegramWebhookResponse:
        args = argument.split()
        if len(args) != 2:
            self.send_message(chat_id, "Usage: /approve <pipeline_id> <stage>")
            return TelegramWebhookResponse(status="invalid", detail="approve_args_invalid")

        pipeline_id = self._parse_uuid_arg(args[0], usage_message="Usage: /approve <pipeline_id> <stage>", chat_id=chat_id)
        if pipeline_id is None:
            return TelegramWebhookResponse(status="invalid", detail="pipeline_id must be UUID")

        try:
            stage = PipelineStage(args[1].lower())
        except ValueError:
            self.send_message(chat_id, "Invalid stage. Allowed: plan|style|build|qa|publish|echo")
            return TelegramWebhookResponse(status="invalid", detail="invalid_stage")

        if stage in {PipelineStage.TRIGGER, PipelineStage.DONE}:
            self.send_message(chat_id, "Invalid stage. Allowed: plan|style|build|qa|publish|echo")
            return TelegramWebhookResponse(status="invalid", detail="invalid_stage")

        try:
            job = repository.approve_stage(pipeline_id, stage)
        except ValueError as exc:
            self.send_message(chat_id, f"Approve failed: {exc}")
            return TelegramWebhookResponse(status="error", detail=str(exc))

        if job is None:
            self.send_message(chat_id, "Pipeline not found.")
            return TelegramWebhookResponse(status="not_found", detail="pipeline does not exist")

        self.send_message(chat_id, f"Approved: {pipeline_id} stage={stage.value} status={job.status.value}")
        return TelegramWebhookResponse(
            status="approved",
            pipeline_id=str(job.pipeline_id),
            payload={"approved_stage": stage.value, "pipeline_status": job.status.value},
        )

    def _handle_logs(self, *, chat_id: str, argument: str, repository: PipelineRepository) -> TelegramWebhookResponse:
        args = argument.split()
        if not args:
            self.send_message(chat_id, "Usage: /logs <pipeline_id> [limit]")
            return TelegramWebhookResponse(status="invalid", detail="missing pipeline_id")

        pipeline_id = self._parse_uuid_arg(args[0], usage_message="Usage: /logs <pipeline_id> [limit]", chat_id=chat_id)
        if pipeline_id is None:
            return TelegramWebhookResponse(status="invalid", detail="pipeline_id must be UUID")

        limit = 12
        if len(args) > 1:
            try:
                limit = max(1, min(50, int(args[1])))
            except ValueError:
                self.send_message(chat_id, "Invalid limit. Use integer 1~50.")
                return TelegramWebhookResponse(status="invalid", detail="invalid_limit")

        logs = repository.list_logs(pipeline_id, limit=200)
        if not logs:
            self.send_message(chat_id, "No logs.")
            return TelegramWebhookResponse(status="ok", pipeline_id=str(pipeline_id), payload={"log_count": 0})

        tail = logs[-limit:]
        lines = [f"{log.created_at.isoformat()} [{log.stage.value}/{log.status.value}] {log.message}" for log in tail]
        self.send_message(chat_id, "\n".join(lines))
        return TelegramWebhookResponse(
            status="ok",
            pipeline_id=str(pipeline_id),
            payload={"log_count": len(tail)},
        )

    def _request_confirmation(
        self,
        *,
        chat_id: str,
        user_id: str,
        action: str,
        target: str,
        repository: PipelineRepository,
    ) -> TelegramWebhookResponse:
        if not target.strip():
            self.send_message(chat_id, f"Usage: /{action} <target_id>")
            return TelegramWebhookResponse(status="invalid", detail=f"missing_target_for_{action}")

        issued_at = int(time.time())
        payload = {
            "action": action,
            "target": target.strip(),
            "chat_id": chat_id,
            "user_id": user_id,
            "iat": issued_at,
            "exp": issued_at + int(self.settings.telegram_confirm_ttl_seconds),
        }
        token = self._encode_confirm_token(payload)
        if not token:
            self.send_message(chat_id, "confirm 토큰 생성 실패: TELEGRAM_CONFIRM_SECRET 또는 TELEGRAM_WEBHOOK_SECRET 필요")
            return TelegramWebhookResponse(status="error", detail="confirm_secret_missing")

        audit = repository.create_audit_entry(
            source=TriggerSource.TELEGRAM,
            keyword=f"[CONFIRM_REQUIRED] /{action} {target[:80]}",
            reason="telegram_confirm_required",
            metadata={"chat_id": chat_id, "user_id": user_id, "action": action, "target": target},
        )

        self.send_message(
            chat_id,
            "\n".join(
                [
                    f"확인 필요: action={action} target={target}",
                    f"만료: {self.settings.telegram_confirm_ttl_seconds}초",
                    f"실행 명령: /confirm {token}",
                ]
            ),
        )
        return TelegramWebhookResponse(
            status="confirm_required",
            pipeline_id=str(audit.pipeline_id),
            payload={"action": action, "target": target, "require_confirm": True},
        )

    def _handle_confirm(
        self,
        *,
        chat_id: str,
        user_id: str,
        token: str,
        repository: PipelineRepository,
    ) -> TelegramWebhookResponse:
        if not token.strip():
            self.send_message(chat_id, "Usage: /confirm <token>")
            return TelegramWebhookResponse(status="invalid", detail="missing_confirm_token")

        decoded, reason = self._decode_confirm_token(token.strip())
        if decoded is None:
            repository.create_audit_entry(
                source=TriggerSource.TELEGRAM,
                keyword="[CONFIRM_FAILED]",
                reason=reason or "confirm_invalid",
                metadata={"chat_id": chat_id, "user_id": user_id},
            )
            self.send_message(chat_id, f"confirm 실패: {reason or 'invalid'}")
            return TelegramWebhookResponse(status="invalid", detail=reason or "confirm_invalid")

        if str(decoded.get("chat_id")) != chat_id:
            self.send_message(chat_id, "confirm 실패: chat mismatch")
            return TelegramWebhookResponse(status="invalid", detail="confirm_chat_mismatch")
        if str(decoded.get("user_id")) != user_id:
            self.send_message(chat_id, "confirm 실패: user mismatch")
            return TelegramWebhookResponse(status="invalid", detail="confirm_user_mismatch")

        action = str(decoded.get("action", ""))
        target = str(decoded.get("target", ""))
        if action == "retry":
            return self._execute_retry(chat_id=chat_id, target=target, repository=repository)
        if action == "cancel":
            return self._execute_cancel(chat_id=chat_id, target=target, repository=repository)
        if action == "reset":
            return self._execute_reset(chat_id=chat_id, target=target, repository=repository)
        if action == "delete_game":
            return self._execute_delete_game(chat_id=chat_id, target=target)

        self.send_message(chat_id, f"confirm 실패: unsupported action={action}")
        return TelegramWebhookResponse(status="invalid", detail="confirm_action_unsupported")

    def _execute_retry(
        self,
        *,
        chat_id: str,
        target: str,
        repository: PipelineRepository,
    ) -> TelegramWebhookResponse:
        pipeline_id = self._parse_uuid_arg(target, usage_message="retry target must be pipeline UUID", chat_id=chat_id)
        if pipeline_id is None:
            return TelegramWebhookResponse(status="invalid", detail="pipeline_id must be UUID")

        job = repository.get_pipeline(pipeline_id)
        if job is None:
            self.send_message(chat_id, "Pipeline not found.")
            return TelegramWebhookResponse(status="not_found", detail="pipeline does not exist")
        if job.status not in {PipelineStatus.ERROR, PipelineStatus.SKIPPED}:
            self.send_message(chat_id, f"retry 불가 상태: {job.status.value}")
            return TelegramWebhookResponse(status="blocked", detail="retry_status_not_allowed")

        updated = repository.update_pipeline_metadata(
            pipeline_id,
            metadata_update={"waiting_for_stage": None},
            status=PipelineStatus.QUEUED,
            error_reason=None,
        )
        if updated is None:
            self.send_message(chat_id, "retry failed: pipeline not found")
            return TelegramWebhookResponse(status="not_found", detail="pipeline does not exist")

        self.send_message(chat_id, f"retry queued: {updated.pipeline_id}")
        return TelegramWebhookResponse(
            status="ok",
            pipeline_id=str(updated.pipeline_id),
            payload={"action": "retry", "pipeline_status": updated.status.value},
        )

    def _execute_cancel(
        self,
        *,
        chat_id: str,
        target: str,
        repository: PipelineRepository,
    ) -> TelegramWebhookResponse:
        pipeline_id = self._parse_uuid_arg(target, usage_message="cancel target must be pipeline UUID", chat_id=chat_id)
        if pipeline_id is None:
            return TelegramWebhookResponse(status="invalid", detail="pipeline_id must be UUID")

        job = repository.get_pipeline(pipeline_id)
        if job is None:
            self.send_message(chat_id, "Pipeline not found.")
            return TelegramWebhookResponse(status="not_found", detail="pipeline does not exist")
        if job.status not in {PipelineStatus.QUEUED, PipelineStatus.RUNNING, PipelineStatus.SKIPPED}:
            self.send_message(chat_id, f"cancel 불가 상태: {job.status.value}")
            return TelegramWebhookResponse(status="blocked", detail="cancel_status_not_allowed")

        repository.mark_pipeline_status(pipeline_id, PipelineStatus.ERROR, error_reason="cancelled_by_admin")
        self.send_message(chat_id, f"cancelled: {pipeline_id}")
        return TelegramWebhookResponse(
            status="ok",
            pipeline_id=str(pipeline_id),
            payload={"action": "cancel", "pipeline_status": PipelineStatus.ERROR.value},
        )

    def _execute_reset(
        self,
        *,
        chat_id: str,
        target: str,
        repository: PipelineRepository,
    ) -> TelegramWebhookResponse:
        pipeline_id = self._parse_uuid_arg(target, usage_message="reset target must be pipeline UUID", chat_id=chat_id)
        if pipeline_id is None:
            return TelegramWebhookResponse(status="invalid", detail="pipeline_id must be UUID")

        job = repository.get_pipeline(pipeline_id)
        if job is None:
            self.send_message(chat_id, "Pipeline not found.")
            return TelegramWebhookResponse(status="not_found", detail="pipeline does not exist")

        metadata_update = {
            "approved_stages": [],
            "waiting_for_stage": None,
            "manual_cursor": "trigger",
            "manual_outputs": {},
            "manual_qa_attempt": 0,
            "manual_build_iteration": 0,
            "execution_mode": job.metadata.get("execution_mode", ExecutionMode.AUTO.value),
        }

        updated = repository.update_pipeline_metadata(
            pipeline_id,
            metadata_update=metadata_update,
            status=PipelineStatus.QUEUED,
            error_reason=None,
        )
        if updated is None:
            self.send_message(chat_id, "reset failed: pipeline not found")
            return TelegramWebhookResponse(status="not_found", detail="pipeline does not exist")

        self.send_message(chat_id, f"reset queued: {updated.pipeline_id}")
        return TelegramWebhookResponse(
            status="ok",
            pipeline_id=str(updated.pipeline_id),
            payload={"action": "reset", "pipeline_status": updated.status.value},
        )

    def _execute_delete_game(self, *, chat_id: str, target: str) -> TelegramWebhookResponse:
        game_id = self._parse_uuid_arg(target, usage_message="delete_game target must be game UUID", chat_id=chat_id)
        if game_id is None:
            return TelegramWebhookResponse(status="invalid", detail="game_id must be UUID")

        service = GameAdminService(self.settings)
        result = service.delete_game(
            game_id=game_id,
            delete_storage=True,
            delete_archive=True,
            reason="telegram_admin_delete",
        )
        status_value = str(result.get("status", "unknown"))
        if status_value in {"error", "partial_error"}:
            self.send_message(chat_id, f"delete_game failed: {result.get('reason', 'unknown_error')}")
            return TelegramWebhookResponse(status="error", detail=str(result.get("reason", "delete_game_failed")))

        if status_value == "not_found":
            self.send_message(chat_id, "Game not found.")
            return TelegramWebhookResponse(status="not_found", detail="game_not_found")

        self.send_message(chat_id, f"delete_game done: {result.get('slug', game_id)}")
        return TelegramWebhookResponse(
            status="ok",
            payload={"action": "delete_game", "game_id": str(game_id), "result_status": status_value},
        )

    def _guard_control_mode(self) -> str | None:
        if not self.settings.telegram_control_enabled:
            return "telegram_control_disabled"
        if not self.settings.telegram_webhook_secret:
            return "telegram_webhook_secret_required"
        if not self.settings.telegram_allowed_chat_id_set():
            return "telegram_allowed_chat_ids_missing"
        if not self.settings.telegram_allowed_user_id_set():
            return "telegram_allowed_user_ids_missing"
        return None

    def _reject_unauthorized(
        self,
        *,
        repository: PipelineRepository,
        message_text: str,
        chat_id: str,
        user_id: str,
        command: str,
        argument: str,
        reason: str,
    ) -> TelegramWebhookResponse:
        audit_job = repository.create_audit_entry(
            source=TriggerSource.TELEGRAM,
            keyword=f"[BLOCKED] {message_text[:120]}",
            reason=reason,
            metadata={"chat_id": chat_id, "user_id": user_id, "command": command, "argument": argument},
        )
        self.send_message(chat_id, "Unauthorized command. Contact master_admin.")
        self._notify_admin_security_event(
            f"[SECURITY] unauthorized command rejected reason={reason} user={user_id or '-'} chat={chat_id} cmd={command}"
        )
        return TelegramWebhookResponse(
            status="blocked",
            detail=reason,
            pipeline_id=str(audit_job.pipeline_id),
            payload={"chat_id": chat_id, "user_id": user_id},
        )

    def _notify_admin_security_event(self, text: str) -> None:
        for chat_id in self.settings.telegram_allowed_chat_id_set():
            self.send_message(chat_id, text)

    def _is_allowed_chat(self, chat_id: str) -> bool:
        allowed = self.settings.telegram_allowed_chat_id_set()
        return bool(allowed and chat_id in allowed)

    def _is_allowed_user(self, user_id: str) -> bool:
        allowed = self.settings.telegram_allowed_user_id_set()
        return bool(user_id and allowed and user_id in allowed)

    def _encode_confirm_token(self, payload: dict[str, Any]) -> str | None:
        secret = self.settings.telegram_confirm_secret or self.settings.telegram_webhook_secret
        if not secret:
            return None
        payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        payload_encoded = self._b64encode(payload_json)
        signature = hmac.new(secret.encode("utf-8"), payload_encoded.encode("utf-8"), hashlib.sha256).digest()
        signature_encoded = self._b64encode(signature)
        return f"{payload_encoded}.{signature_encoded}"

    def _decode_confirm_token(self, token: str) -> tuple[dict[str, Any] | None, str | None]:
        secret = self.settings.telegram_confirm_secret or self.settings.telegram_webhook_secret
        if not secret:
            return None, "confirm_secret_missing"

        parts = token.split(".")
        if len(parts) != 2:
            return None, "confirm_token_format_invalid"

        payload_encoded, signature_encoded = parts
        expected_sig = hmac.new(secret.encode("utf-8"), payload_encoded.encode("utf-8"), hashlib.sha256).digest()
        expected_sig_encoded = self._b64encode(expected_sig)
        if not hmac.compare_digest(signature_encoded, expected_sig_encoded):
            return None, "confirm_signature_invalid"

        try:
            payload_raw = self._b64decode(payload_encoded)
            payload = json.loads(payload_raw.decode("utf-8"))
        except Exception:
            return None, "confirm_payload_invalid"

        if not isinstance(payload, dict):
            return None, "confirm_payload_invalid"

        exp = payload.get("exp")
        if not isinstance(exp, int):
            return None, "confirm_exp_missing"
        if exp < int(time.time()):
            return None, "confirm_token_expired"

        return payload, None

    @staticmethod
    def _b64encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")

    @staticmethod
    def _b64decode(value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding)

    def _parse_uuid_arg(self, raw: str, *, usage_message: str, chat_id: str) -> UUID | None:
        value = raw.strip()
        if not value:
            self.send_message(chat_id, usage_message)
            return None
        try:
            return UUID(value)
        except ValueError:
            self.send_message(chat_id, "Invalid UUID format.")
            return None

    @staticmethod
    def _parse_command(text: str) -> tuple[str, str]:
        raw = text.strip()
        if not raw:
            return "", ""
        split = raw.split(maxsplit=1)
        command_part = split[0].split("@", maxsplit=1)[0].lower()
        argument = split[1].strip() if len(split) > 1 else ""
        return command_part, argument
