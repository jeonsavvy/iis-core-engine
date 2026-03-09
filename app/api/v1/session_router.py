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
from app.agents.genre_briefs import build_genre_brief, scaffold_seed_for_brief
from app.agents.scaffolds import get_scaffold_seed
from app.api.security import verify_internal_api_token
from app.core.config import Settings, get_settings
from app.services.vertex_service import VertexCapacityExhausted

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


class ImageAttachmentRequest(BaseModel):
    name: str = Field(default="", max_length=200)
    mime_type: str = Field(..., min_length=6, max_length=100)
    data_url: str = Field(..., min_length=24, max_length=2_500_000)


class PromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    auto_qa: bool = True
    stream: bool = False
    image_attachment: ImageAttachmentRequest | None = None


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
    current_run_id: str | None = None
    current_run_status: str | None = None
    last_issue_id: str | None = None
    last_proposal_id: str | None = None
    last_preview_html: str | None = None


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
    attempt_count: int = 0
    retry_after_seconds: int | None = None
    model_name: str | None = None
    model_location: str | None = None
    fallback_used: bool = False
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
    category: str = Field(default="auto", max_length=40)
    image_attachment: ImageAttachmentRequest | None = None


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
    image_attachment: ImageAttachmentRequest | None = None


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
    presentation_status: str = "ready"
    thumbnail_url: str | None = None
    marketing_summary: str = ""
    play_overview: list[str] = Field(default_factory=list)
    controls_guide: list[str] = Field(default_factory=list)


class ConversationMessageResponse(BaseModel):
    role: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ConversationHistoryResponse(BaseModel):
    messages: list[ConversationMessageResponse] = Field(default_factory=list)


class LatestIssueSnapshotResponse(BaseModel):
    issue: SessionIssueResponse | None = None
    proposal_id: str | None = None
    proposal_status: str | None = None
    routed_agents: list[str] = Field(default_factory=list)
    preview_html: str | None = None


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
_ISSUE_CATEGORY_ALIASES = {
    "runtime": "fatal_runtime",
    "runtime_bug": "fatal_runtime",
    "bug": "fatal_runtime",
    "crash": "fatal_runtime",
    "visual": "visual_polish",
    "readability": "visual_polish",
    "ui": "visual_polish",
    "gameplay": "gameplay_bug",
    "physics": "gameplay_bug",
    "ux": "ux_copy",
    "copy": "ux_copy",
    "publish": "publish_blocker",
}
_PUBLISH_BLOCKING_ISSUES = {"fatal_runtime", "publish_blocker"}
_SUPPORTED_ATTACHMENT_MIME_PREFIXES = ("image/png", "image/jpeg", "image/webp")


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

    def update_session(self, session_id: str, **fields: Any) -> None:
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


def _resolve_actor(request: Request) -> tuple[str | None, str | None]:
    actor_id = request.headers.get("X-IIS-Actor-Id")
    actor_role = request.headers.get("X-IIS-Actor-Role")
    resolved_actor_id = actor_id.strip() if isinstance(actor_id, str) and actor_id.strip() else None
    resolved_actor_role = actor_role.strip() if isinstance(actor_role, str) and actor_role.strip() else None
    return resolved_actor_id, resolved_actor_role


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


def _is_generic_session_title(title: str) -> bool:
    normalized = title.strip().casefold()
    return normalized in {"", "new session", "newsession"} or normalized.startswith("game #") or normalized.startswith("game ")


def _suggest_session_title(*, prompt: str, genre_brief: dict[str, Any]) -> str:
    archetype = str(genre_brief.get("archetype", "")).strip()
    if archetype == "racing_openwheel_circuit_3d":
        return "Neon Grid Grand Prix"
    if archetype == "flight_lowpoly_island_3d":
        return "Golden Isles Flight"
    if archetype == "flight_shooter_space_dogfight_3d":
        return "Skyline Jet Dogfight"
    if archetype == "topdown_shooter_twinstick_2d":
        return "Lowpoly Siege"
    snippet = prompt.strip().replace("\n", " ")[:32].strip()
    return snippet or "IIS Game"


def _normalize_error_code(raw: str) -> str:
    code = raw.strip().lower()
    if not code:
        return "agent_loop_exception"
    if "timeout" in code:
        return "core_engine_timeout"
    if code.startswith("fatal_runtime_unresolved"):
        return "fatal_runtime_unresolved"
    return code.replace(" ", "_")[:80]


def _prompt_retry_schedule(settings_obj: Settings) -> list[int]:
    raw = str(getattr(settings_obj, "prompt_retry_backoff_seconds", "") or "").strip()
    values: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            parsed = int(token)
        except ValueError:
            continue
        if parsed > 0:
            values.append(parsed)
    return values or [10, 30, 60, 120, 240]


def _summarize_publish_issues(issues: list[str], *, limit: int = 3) -> str:
    return "; ".join(issue.strip() for issue in issues[:limit] if issue.strip())


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
    normalized = _normalize_issue_category(category)
    if normalized in {"fatal_runtime", "publish_blocker"}:
        return ["playtester", "codegen"]
    if normalized == "visual_polish":
        return ["visual_qa", "codegen"]
    if normalized == "gameplay_bug":
        return ["playtester", "codegen"]
    return ["codegen"]


def _normalize_issue_category(category: str) -> str:
    normalized = category.strip().casefold().replace(" ", "_").replace("-", "_")
    return _ISSUE_CATEGORY_ALIASES.get(normalized, normalized or "gameplay_bug")


def _attachment_metadata(image_attachment: ImageAttachmentRequest | None) -> dict[str, Any] | None:
    if image_attachment is None:
        return None
    mime_type = image_attachment.mime_type.strip().lower()
    data_url = image_attachment.data_url.strip()
    if not mime_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_image_mime", "code": "image_attachment_invalid"},
        )
    if not any(mime_type.startswith(prefix) for prefix in _SUPPORTED_ATTACHMENT_MIME_PREFIXES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "unsupported_image_mime", "code": "image_attachment_unsupported"},
        )
    if not data_url.startswith(f"data:{mime_type};base64,"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_image_payload", "code": "image_attachment_invalid"},
        )
    return {
        "name": image_attachment.name.strip() or "attachment",
        "mime_type": mime_type,
        "has_image": True,
    }


def _infer_issue_category(*, title: str, details: str, has_attachment: bool) -> str:
    text = f"{title} {details}".casefold()

    if any(token in text for token in ("퍼블리시", "publish", "출시", "승인", "차단")):
        return "publish_blocker"
    if any(token in text for token in ("안 떠", "안뜸", "검은 화면", "부팅", "실행 안", "error", "오류", "버그", "튕김", "크래시")):
        return "fatal_runtime"
    if any(token in text for token in ("조작", "핸들링", "코너링", "브레이크", "속도감", "충돌", "랩타임", "난이도", "gameplay")):
        return "gameplay_bug"
    if any(token in text for token in ("문구", "설명", "조작법", "안내", "카피", "텍스트")):
        return "ux_copy"
    if has_attachment or any(token in text for token in ("화면", "비주얼", "가독성", "느낌", "스타일", "연출", "색감", "이미지")):
        return "visual_polish"
    return "gameplay_bug"


def _build_issue_fix_prompt(issue: dict[str, Any], instruction: str, attachment_meta: dict[str, Any] | None = None) -> str:
    category = _normalize_issue_category(str(issue.get("category", "")))
    lines = [
        "사용자가 현재 게임 결과에 대해 구체적인 수정 요청을 보냈습니다.",
        "완전한 HTML을 반환하되, DIFF 감성으로 필요한 부분만 최소 수정하세요.",
        "이미 잘 작동하는 시스템은 유지하세요.",
        f"- issue title: {issue.get('title', '')}",
        f"- issue details: {issue.get('details', '')}",
        f"- category: {category}",
    ]
    if instruction.strip():
        lines.append(f"- extra instruction: {instruction.strip()}")
    if attachment_meta:
        lines.append(
            f"- reference image attached: {attachment_meta.get('name', 'attachment')} ({attachment_meta.get('mime_type', 'image')})"
        )

    lines.extend(
        [
            "",
            "카테고리별 우선순위:",
            "- fatal_runtime / publish_blocker: 실행 불가 원인 제거가 최우선",
            "- gameplay_bug: 조작감/밸런스/흐름 문제를 국소 수정",
            "- visual_polish: 가독성/연출을 저위험 범위에서 개선",
            "- ux_copy: 설명/문구/피드백 표현만 정리",
            "",
            "규칙:",
            "- 전체 재작성보다 국소 수정 우선",
            "- requestAnimationFrame 기반 게임 루프를 유지/복원",
            "- window.__iis_game_boot_ok 와 IISLeaderboard 계약은 유지",
        ]
    )
    return "\n".join(lines)


def _latest_run_snapshot(store: SessionStoreProtocol, session_id: str) -> tuple[str | None, str | None]:
    events = store.get_session_events(session_id, limit=80)
    for event in events:
        event_type = str(event.get("event_type", ""))
        metadata = cast(dict[str, Any], event.get("metadata")) if isinstance(event.get("metadata"), dict) else {}
        run_id = str(metadata.get("run_id", "")).strip() or None
        if not run_id:
            continue
        if event_type == "prompt_run_started":
            return run_id, "running"
        if event_type == "prompt_run_retry_scheduled":
            return run_id, "retrying"
        if event_type == "prompt_run_queued":
            return run_id, "queued"
        if event_type == "prompt_run_succeeded":
            return run_id, "succeeded"
        if event_type == "prompt_run_failed":
            return run_id, "failed"
        if event_type == "prompt_run_cancelled":
            return run_id, "cancelled"
    return None, None


def _latest_issue_snapshot(store: SessionStoreProtocol, session_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    events = store.get_session_events(session_id, limit=80)
    issue_id: str | None = None
    routed_agents: list[str] = []
    for event in events:
        metadata = cast(dict[str, Any], event.get("metadata")) if isinstance(event.get("metadata"), dict) else {}
        maybe_issue_id = metadata.get("issue_id")
        if isinstance(maybe_issue_id, str) and maybe_issue_id.strip():
            issue_id = maybe_issue_id.strip()
            raw_routed = metadata.get("routed_agents")
            if isinstance(raw_routed, list):
                routed_agents = [str(agent) for agent in raw_routed if str(agent).strip()]
            break

    if not issue_id:
        return None, None, []

    issue = store.get_session_issue(session_id, issue_id)
    proposal = store.get_latest_issue_proposal(session_id, issue_id)
    return issue, proposal, routed_agents


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
        attempt_count=int(run.get("attempt_count", 0) or 0),
        retry_after_seconds=int(run["retry_after_seconds"]) if isinstance(run.get("retry_after_seconds"), int) else None,
        model_name=str(run["model_name"]) if run.get("model_name") else None,
        model_location=str(run["model_location"]) if run.get("model_location") else None,
        fallback_used=bool(run.get("fallback_used", False)),
        activities=activities,
        current_html=str(session.get("current_html", "")),
    )


def _get_run_tasks(app: Any) -> dict[str, asyncio.Task[Any]]:
    tasks = getattr(app.state, "session_run_tasks", None)
    if tasks is None:
        tasks = {}
        app.state.session_run_tasks = tasks
    return cast(dict[str, asyncio.Task[Any]], tasks)


def _get_prompt_run_semaphore(app: Any) -> asyncio.Semaphore:
    semaphore = getattr(app.state, "prompt_run_semaphore", None)
    if semaphore is None:
        semaphore = asyncio.Semaphore(max(1, int(settings.prompt_worker_concurrency)))
        app.state.prompt_run_semaphore = semaphore
    return cast(asyncio.Semaphore, semaphore)


async def _validate_publish_runtime(*, app: Any, html: str) -> tuple[bool, str, list[str]]:
    playtester = getattr(app.state, "playtester_agent", None)
    if playtester is None:
        return False, "playtester_unavailable", ["Playtester agent is unavailable"]

    result = await playtester.test(html_content=html)
    issues = result.fatal_issues or result.issues
    if result.boots_ok:
        return True, "", issues
    return False, "publish_runtime_blocked", issues


def _schedule_prompt_run(
    *,
    app: Any,
    store: SessionStoreProtocol,
    run_id: str,
    session_id: str,
    prompt: str,
    auto_qa: bool,
    image_attachment: ImageAttachmentRequest | None,
    timeout_seconds: float,
    settings_obj: Settings,
    delay_seconds: int = 0,
) -> None:
    async def _runner() -> None:
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)
        await _execute_prompt_run(
            app=app,
            store=store,
            run_id=run_id,
            session_id=session_id,
            prompt=prompt,
            auto_qa=auto_qa,
            image_attachment=image_attachment,
            timeout_seconds=timeout_seconds,
            settings_obj=settings_obj,
        )

    task = asyncio.create_task(_runner())
    _get_run_tasks(app)[run_id] = task


async def _execute_prompt_run(
    *,
    app: Any,
    store: SessionStoreProtocol,
    run_id: str,
    session_id: str,
    prompt: str,
    auto_qa: bool,
    image_attachment: ImageAttachmentRequest | None,
    timeout_seconds: float,
    settings_obj: Settings,
) -> None:
    current_task = asyncio.current_task()
    try:
        semaphore = _get_prompt_run_semaphore(app)
        async with semaphore:
            run = store.get_session_run(session_id, run_id) or {}
            attempt_count = int(run.get("attempt_count", 0) or 0) + 1
            store.update_session_run(
                session_id,
                run_id,
                status="running",
                started_at=_now_iso(),
                attempt_count=attempt_count,
                retry_after_seconds=None,
                capacity_error=None,
            )
            store.add_session_event(
                session_id=session_id,
                event_type="prompt_run_started",
                action="run",
                summary=f"Run started: {run_id[:8]}",
                decision_reason="queued_run_started",
                input_signal=prompt[:500],
                change_impact="agent_loop_running",
                confidence=1.0,
                metadata={"run_id": run_id, "attempt_count": attempt_count},
            )

            session = store.get_session(session_id) or {}
            history_rows = store.get_conversation_history(session_id, limit=100)
            history = [
                ConversationMessage(role=str(msg.get("role", "user")), content=str(msg.get("content", "")))
                for msg in history_rows
            ]
            genre_brief = build_genre_brief(user_prompt=prompt, genre_hint=str(session.get("genre", "")))
            scaffold_seed = scaffold_seed_for_brief(genre_brief)
            scaffold = get_scaffold_seed(str(genre_brief.get("scaffold_key", "")).strip()) if scaffold_seed else None
            if scaffold is not None and not str(session.get("current_html", "")).strip():
                store.update_session_html(session_id, scaffold.html, score=0)
                store.add_session_event(
                    session_id=session_id,
                    event_type="scaffold_materialized",
                    agent="codegen",
                    action="generate",
                    summary=f"Materialized scaffold {scaffold.key}",
                    decision_reason="deterministic_scaffold_baseline",
                    input_signal=prompt[:500],
                    change_impact="baseline_draft_created",
                    confidence=1.0,
                    metadata={
                        "run_id": run_id,
                        "genre_brief": genre_brief,
                        "scaffold_key": scaffold.key,
                        "scaffold_version": scaffold.version,
                        "generation_mode": "deterministic_scaffold",
                    },
                )

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
                    image_attachment={
                        "mime_type": image_attachment.mime_type,
                        "data_url": image_attachment.data_url,
                        "name": image_attachment.name,
                    }
                    if image_attachment
                    else None,
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
                metadata={"run_id": run_id, "fatal_runtime": "fatal_runtime_unresolved" in result.error},
            )
            return

        store.update_session_html(session_id, result.html, score=0)
        store.add_conversation_message(
            session_id=session_id,
            role="assistant",
            content=f"[Generated game: {len(result.html)} chars]",
            metadata={
                "generation_source": result.generation_source,
                "auto_refined": result.auto_refined,
                "reverted_to_baseline": result.reverted_to_baseline,
                "run_id": run_id,
            },
        )

        activity_payloads: list[dict[str, Any]] = []
        selected_model: str | None = None
        selected_location: str | None = None
        fallback_used = False
        fallback_rank = 0
        for activity in result.activities:
            payload = _serialize_activity(activity)
            activity_payloads.append(payload)
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            if payload.get("agent") == "codegen" and isinstance(metadata, dict) and not selected_model:
                selected_model = str(metadata.get("model")) if metadata.get("model") else None
                selected_location = str(metadata.get("model_location")) if metadata.get("model_location") else None
                fallback_used = bool(metadata.get("fallback_used", False))
                fallback_rank = int(metadata.get("fallback_rank", 0) or 0)
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

        if selected_model:
            store.add_session_event(
                session_id=session_id,
                event_type="prompt_run_model_selected",
                agent="codegen",
                action="run",
                summary=f"model={selected_model} @ {selected_location or 'global'}",
                decision_reason="capacity_router_selected_model",
                input_signal=prompt[:500],
                change_impact="model_selected",
                confidence=1.0,
                metadata={
                    "run_id": run_id,
                    "selected_model": selected_model,
                    "selected_location": selected_location or "global",
                    "fallback_used": fallback_used,
                    "fallback_rank": fallback_rank,
                },
            )
            if fallback_used:
                store.add_session_event(
                    session_id=session_id,
                    event_type="prompt_run_capacity_fallback",
                    agent="codegen",
                    action="run",
                    summary=f"Fallback route selected: {selected_model}",
                    decision_reason="capacity_router_fallback",
                    input_signal=prompt[:500],
                    change_impact="fallback_route_used",
                    confidence=1.0,
                    metadata={
                        "run_id": run_id,
                        "selected_model": selected_model,
                        "selected_location": selected_location or "global",
                        "fallback_rank": fallback_rank,
                    },
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
            final_score=0,
            retry_after_seconds=None,
            attempt_count=attempt_count,
            model_name=selected_model,
            model_location=selected_location or "global" if selected_model else None,
            fallback_used=fallback_used,
            capacity_error=None,
            activities=activity_payloads,
        )
        store.add_session_event(
            session_id=session_id,
            event_type="prompt_run_succeeded",
            action="run",
            summary=f"Run succeeded: {run_id[:8]}",
            decision_reason="agent_loop_completed",
            input_signal=prompt[:500],
            change_impact="session_html_updated",
            confidence=1.0,
            metadata={
                "run_id": run_id,
                "auto_refined": result.auto_refined,
                "refinement_rounds": result.refinement_rounds,
                "reverted_to_baseline": result.reverted_to_baseline,
            },
        )
        if result.reverted_to_baseline:
            store.add_session_event(
                session_id=session_id,
                event_type="scaffold_reverted_to_baseline",
                agent="codegen",
                action="revert",
                summary="초기 베이스라인으로 안전하게 되돌려 플레이 가능한 상태를 유지했습니다.",
                decision_reason="fatal_runtime_fallback_to_scaffold",
                input_signal=prompt[:500],
                change_impact="baseline_preserved",
                confidence=1.0,
                metadata={"run_id": run_id},
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
    except VertexCapacityExhausted as exc:
        run = store.get_session_run(session_id, run_id) or {}
        current_attempt = int(run.get("attempt_count", 1) or 1)
        retry_schedule = _prompt_retry_schedule(settings_obj)
        retry_after = retry_schedule[min(max(current_attempt - 1, 0), len(retry_schedule) - 1)]
        can_retry = current_attempt < int(settings_obj.prompt_retry_max_attempts)
        attempted_routes = [
            {"model": route.model_name, "location": route.location, "tier": route.tier, "fallback_rank": route.fallback_rank}
            for route in exc.attempted_routes
        ]
        if can_retry:
            store.update_session_run(
                session_id,
                run_id,
                status="retrying",
                error_code="resource_exhausted_retrying",
                error_detail=exc.last_error,
                retry_after_seconds=retry_after,
                attempt_count=current_attempt,
                fallback_used=True,
                capacity_error=exc.last_error,
            )
            store.add_session_event(
                session_id=session_id,
                event_type="prompt_run_capacity_exhausted",
                agent="codegen",
                action="run",
                summary="Capacity exhausted on all configured routes",
                decision_reason="capacity_router_all_routes_exhausted",
                input_signal=prompt[:500],
                change_impact="retry_scheduling_considered",
                confidence=0.0,
                error_code="resource_exhausted",
                metadata={"run_id": run_id, "attempted_routes": attempted_routes, "capacity_error": exc.last_error},
            )
            store.add_session_event(
                session_id=session_id,
                event_type="prompt_run_retry_scheduled",
                agent="codegen",
                action="run",
                summary=f"Capacity retry scheduled in {retry_after}s",
                decision_reason="capacity_router_backoff",
                input_signal=prompt[:500],
                change_impact="retrying",
                confidence=1.0,
                error_code="resource_exhausted",
                metadata={
                    "run_id": run_id,
                    "retry_after_seconds": retry_after,
                    "attempt_count": current_attempt,
                    "attempted_routes": attempted_routes,
                    "capacity_error": exc.last_error,
                },
            )
            _schedule_prompt_run(
                app=app,
                store=store,
                run_id=run_id,
                session_id=session_id,
                prompt=prompt,
                auto_qa=auto_qa,
                image_attachment=image_attachment,
                timeout_seconds=timeout_seconds,
                settings_obj=settings_obj,
                delay_seconds=retry_after,
            )
        else:
            store.update_session_run(
                session_id,
                run_id,
                status="failed",
                finished_at=_now_iso(),
                error_code="resource_exhausted",
                error_detail=exc.last_error,
                retry_after_seconds=retry_after,
                attempt_count=current_attempt,
                fallback_used=True,
                capacity_error=exc.last_error,
            )
            store.add_session_event(
                session_id=session_id,
                event_type="prompt_run_failed",
                agent="codegen",
                action="run",
                summary="Vertex capacity exhausted after fallback attempts",
                decision_reason="capacity_router_exhausted",
                input_signal=prompt[:500],
                change_impact="no_html_update",
                confidence=0.0,
                error_code="resource_exhausted",
                metadata={"run_id": run_id, "attempt_count": current_attempt, "attempted_routes": attempted_routes},
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
        tasks = _get_run_tasks(app)
        if tasks.get(run_id) is current_task:
            tasks.pop(run_id, None)


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
    actor_id, actor_role = _resolve_actor(request)
    created = store.create_session(user_id=actor_id, title=body.title, genre=body.genre_hint)
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
        metadata={"actor_id": actor_id, "actor_role": actor_role} if actor_id or actor_role else {},
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
    current_run_id, current_run_status = _latest_run_snapshot(store, session_id)
    latest_issue, latest_proposal, _ = _latest_issue_snapshot(store, session_id)
    return SessionResponse(
        session_id=str(session.get("id", session_id)),
        title=str(session.get("title", "")),
        genre=str(session.get("genre", "")),
        status=str(session.get("status", "active")),
        current_html=str(session.get("current_html", "")),
        score=int(session.get("score", 0) or 0),
        conversation_count=len(history),
        current_run_id=current_run_id,
        current_run_status=current_run_status,
        last_issue_id=str(latest_issue.get("id")) if latest_issue else None,
        last_proposal_id=str(latest_proposal.get("id")) if latest_proposal else None,
        last_preview_html=str(latest_proposal.get("preview_html", "")) if latest_proposal else None,
    )


@router.get("/{session_id}/conversation", response_model=ConversationHistoryResponse)
async def get_session_conversation(
    session_id: str,
    request: Request,
    limit: int = Query(default=80, ge=1, le=200),
) -> ConversationHistoryResponse:
    store = _get_session_store(request)
    _load_session_or_404(store, session_id)
    history = store.get_conversation_history(session_id, limit=limit)
    return ConversationHistoryResponse(
        messages=[
            ConversationMessageResponse(
                role=str(message.get("role", "user")),
                content=str(message.get("content", "")),
                metadata=message.get("metadata") if isinstance(message.get("metadata"), dict) else {},
                created_at=str(message.get("created_at", "")),
            )
            for message in history
        ]
    )


@router.get("/{session_id}/issues/latest", response_model=LatestIssueSnapshotResponse)
async def get_latest_issue_snapshot(session_id: str, request: Request) -> LatestIssueSnapshotResponse:
    store = _get_session_store(request)
    _load_session_or_404(store, session_id)
    issue, proposal, routed_agents = _latest_issue_snapshot(store, session_id)
    if not issue:
        return LatestIssueSnapshotResponse()

    return LatestIssueSnapshotResponse(
        issue=SessionIssueResponse(
            issue_id=str(issue.get("id", "")),
            session_id=session_id,
            title=str(issue.get("title", "")),
            details=str(issue.get("details", "")),
            category=str(issue.get("category", "gameplay_bug")),
            status=str(issue.get("status", "open")),
            created_at=str(issue.get("created_at", _now_iso())),
            updated_at=str(issue.get("updated_at")) if issue.get("updated_at") else None,
        ),
        proposal_id=str(proposal.get("id")) if proposal else None,
        proposal_status=str(proposal.get("status")) if proposal else None,
        routed_agents=routed_agents,
        preview_html=str(proposal.get("preview_html", "")) if proposal else None,
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

    genre_brief = build_genre_brief(user_prompt=body.prompt, genre_hint=str(session.get("genre", "")))
    scaffold_seed = scaffold_seed_for_brief(genre_brief)
    scaffold = get_scaffold_seed(str(genre_brief.get("scaffold_key", "")).strip()) if scaffold_seed else None
    attachment_meta = _attachment_metadata(body.image_attachment)
    current_title = str(session.get("title", ""))
    if _is_generic_session_title(current_title):
        store.update_session(
            session_id,
            title=_suggest_session_title(prompt=body.prompt, genre_brief=genre_brief),
            genre=str(session.get("genre", "")) or str(genre_brief.get("archetype", ""))[:80],
        )
        session = store.get_session(session_id) or session

    store.add_conversation_message(
        session_id=session_id,
        role="user",
        content=body.prompt,
        metadata={"stream": False, "auto_qa": body.auto_qa, "attachment": attachment_meta} if attachment_meta else {"stream": False, "auto_qa": body.auto_qa},
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
        metadata={"has_image_attachment": bool(attachment_meta)} if attachment_meta else {},
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
        metadata={
            "run_id": run_id,
            "auto_qa": body.auto_qa,
            "genre_brief": genre_brief,
            "scaffold_key": scaffold.key if scaffold else None,
            "scaffold_version": scaffold.version if scaffold else None,
            "generation_mode": "scaffold_seeded" if scaffold else "blank",
            "has_image_attachment": bool(attachment_meta),
        },
    )

    if settings.prompt_async_enabled:
        _schedule_prompt_run(
            app=request.app,
            store=store,
            run_id=run_id,
            session_id=session_id,
            prompt=body.prompt,
            auto_qa=body.auto_qa,
            image_attachment=body.image_attachment,
            timeout_seconds=settings.prompt_run_timeout_seconds,
            settings_obj=settings,
        )
    else:
        await _execute_prompt_run(
            app=request.app,
            store=store,
            run_id=run_id,
            session_id=session_id,
            prompt=body.prompt,
            auto_qa=body.auto_qa,
            image_attachment=body.image_attachment,
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

    attachment_meta = _attachment_metadata(body.image_attachment)
    actor_id, actor_role = _resolve_actor(request)
    normalized_category = (
        _infer_issue_category(title=body.title, details=body.details, has_attachment=bool(attachment_meta))
        if body.category.strip().casefold() in {"", "auto"}
        else _normalize_issue_category(body.category)
    )
    issue = store.create_session_issue(
        session_id=session_id,
        title=body.title,
        details=body.details,
        category=normalized_category,
        created_by=actor_id or actor_role or "creator",
    )
    store.add_conversation_message(
        session_id=session_id,
        role="user",
        content=body.details or body.title,
        metadata={"issue_id": issue.get("id"), "category": normalized_category, "attachment": attachment_meta}
        if attachment_meta
        else {"issue_id": issue.get("id"), "category": normalized_category},
    )
    routed_agents = _route_issue_agents(normalized_category)
    store.add_session_event(
        session_id=session_id,
        event_type="issue_reported",
        action="report",
        summary=body.title[:_EVENT_SUMMARY_MAX_LEN],
        input_signal=body.details[:500],
        decision_reason="human_feedback_received",
        change_impact="issue_queue_updated",
        confidence=1.0,
        metadata={
            "issue_id": issue.get("id"),
            "category": normalized_category,
            "routed_agents": routed_agents,
            "has_image_attachment": bool(attachment_meta),
            "actor_id": actor_id,
            "actor_role": actor_role,
        },
    )

    return SessionIssueResponse(
        issue_id=str(issue.get("id", "")),
        session_id=session_id,
        title=str(issue.get("title", "")),
        details=str(issue.get("details", "")),
        category=str(issue.get("category", normalized_category)),
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
    attachment_meta = _attachment_metadata(body.image_attachment)

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
    proposal_prompt = _build_issue_fix_prompt(issue, instruction, attachment_meta)
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
        image_attachment={
            "mime_type": body.image_attachment.mime_type,
            "data_url": body.image_attachment.data_url,
            "name": body.image_attachment.name,
        }
        if body.image_attachment
        else None,
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
        summary=f"{issue.get('category', 'gameplay_bug')} fix proposal ({len(result.html)} chars)",
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
        metadata={
            "issue_id": issue_id,
            "proposal_id": proposal.get("id"),
            "routed_agents": routed_agents,
            "has_image_attachment": bool(attachment_meta),
        },
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
    _load_session_or_404(store, session_id)
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

    store.update_session_html(session_id, preview_html, score=0)
    store.update_issue_proposal(session_id, issue_id, proposal_id, status="applied")
    store.update_session_issue(session_id, issue_id, status="resolved")
    store.clear_publish_approvals(session_id)
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
        change_impact="session_html_updated_publish_requires_reapproval",
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
    actor_id, actor_role = _resolve_actor(request)
    approval = store.create_publish_approval(session_id=session_id, approved_by=actor_id or actor_role or "master_admin", note=body.note)
    store.add_session_event(
        session_id=session_id,
        event_type="publish_approved",
        action="approve",
        summary="Publish approved by operator",
        decision_reason="human_approval_granted",
        input_signal=body.note[:500],
        change_impact="publish_unlocked",
        confidence=1.0,
        metadata={"approval_id": approval.get("id"), "actor_id": actor_id, "actor_role": actor_role},
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
    recent_history = store.get_conversation_history(session_id, limit=20)
    recent_events = store.get_session_events(session_id, limit=20)
    genre_brief = build_genre_brief(
        user_prompt="\n".join(str(message.get("content", "")) for message in recent_history[-6:]),
        genre_hint=str(session.get("genre", "")),
    )
    session_title = str(session.get("title", ""))
    derived_name = _suggest_session_title(
        prompt="\n".join(str(message.get("content", "")) for message in recent_history[-6:]) or session_title,
        genre_brief=genre_brief,
    )
    game_name = body.game_name or (derived_name if _is_generic_session_title(session_title) else session_title or f"Game {slug}")
    if session_title != game_name:
        store.update_session(session_id, title=game_name)

    publishable, publish_error_code, publish_issues = await _validate_publish_runtime(app=request.app, html=html)
    if not publishable:
        summary = _summarize_publish_issues(publish_issues, limit=3) or "Runtime fatal issue detected"
        store.add_session_event(
            session_id=session_id,
            event_type="publish_blocked_runtime",
            agent="playtester",
            action="publish",
            summary=summary[:_EVENT_SUMMARY_MAX_LEN],
            decision_reason="runtime_fatal_must_be_zero",
            input_signal=game_name,
            change_impact="publish_blocked",
            confidence=1.0,
            error_code=publish_error_code,
            metadata={"issues": publish_issues[:8], "category": "publish_blocker"},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "publish_blocked_runtime", "code": publish_error_code, "issues": publish_issues[:8]},
        )

    try:
        actor_id, _ = _resolve_actor(request)
        publish_result = await publisher.publish(
            slug=slug,
            game_name=game_name,
            genre=str(session.get("genre", "")),
            html_content=html,
            recent_history=recent_history,
            recent_events=recent_events,
            genre_brief=genre_brief,
            created_by=str(session.get("user_id") or actor_id or "").strip() or None,
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
            metadata={
                "game_name": game_name,
                "presentation_status": str(publish_result.get("presentation_status", "ready")),
                "thumbnail_url": str(publish_result.get("thumbnail_url", "")).strip() or None,
                "marketing_summary": publish_result.get("marketing_summary", ""),
                "play_overview": publish_result.get("play_overview", []),
                "controls_guide": publish_result.get("controls_guide", []),
            },
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
            presentation_status=str(publish_result.get("presentation_status", "ready")),
            thumbnail_url=str(publish_result.get("thumbnail_url", "")).strip() or None,
            marketing_summary=str(publish_result.get("marketing_summary", "")),
            play_overview=publish_result.get("play_overview") if isinstance(publish_result.get("play_overview"), list) else [],
            controls_guide=publish_result.get("controls_guide") if isinstance(publish_result.get("controls_guide"), list) else [],
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
