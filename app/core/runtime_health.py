from __future__ import annotations

import os
import subprocess
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.schemas.pipeline import PipelineAgentName

try:
    from supabase import create_client
except ImportError:  # pragma: no cover - optional dependency in test environments
    create_client = None


PIPELINE_SCHEMA_VERSION = "v2"
RUNTIME_MODULE_SIGNATURE = "session_editor_loop_v1"


def pipeline_agent_enum_signature() -> str:
    return ",".join(agent.value for agent in PipelineAgentName)


@lru_cache(maxsize=1)
def resolve_git_sha() -> str:
    env_sha = os.getenv("GIT_SHA", "").strip()
    if env_sha:
        return env_sha
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "--short=12", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=1.5,
            text=True,
        )
    except Exception:
        return "unknown"
    return output.strip() or "unknown"


def verify_pipeline_schema_signature(settings: Settings) -> None:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return
    if create_client is None:
        return
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("pipeline_logs")
        .select("id")
        .eq("agent_name", PipelineAgentName.REPORTER.value)
        .limit(1)
        .execute()
    )
    error = getattr(response, "error", None)
    if not error:
        return
    detail = str(getattr(error, "message", "") or error)
    lowered = detail.casefold()
    if "pipeline_agent_name" in lowered or "invalid input value for enum" in lowered:
        raise RuntimeError(f"pipeline_schema_mismatch: {detail}")


def healthz_payload(settings: Settings | None = None) -> dict[str, str]:
    resolved = settings or get_settings()
    credentials_path = str(resolved.google_application_credentials or "").strip()
    return {
        "status": "ok",
        "service": "IIS Game Editor",
        "git_sha": resolve_git_sha(),
        "pipeline_schema_version": PIPELINE_SCHEMA_VERSION,
        "pipeline_agent_enum_signature": pipeline_agent_enum_signature(),
        "generation_engine_version": resolved.generation_engine_version,
        "rqc_version": resolved.generation_engine_version,
        "module_signature": RUNTIME_MODULE_SIGNATURE,
        "builder_codegen_enabled": "true" if resolved.builder_codegen_enabled else "false",
        "vertex_project_configured": "true" if bool(resolved.vertex_project_id) else "false",
        "vertex_credentials_path_configured": "true" if bool(credentials_path) else "false",
    }
