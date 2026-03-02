from __future__ import annotations

import os
import subprocess
from functools import lru_cache

from supabase import create_client

from app.core.config import Settings
from app.schemas.pipeline import PipelineAgentName


PIPELINE_SCHEMA_VERSION = "v2"


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


def healthz_payload() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "ForgeMind",
        "git_sha": resolve_git_sha(),
        "pipeline_schema_version": PIPELINE_SCHEMA_VERSION,
        "pipeline_agent_enum_signature": pipeline_agent_enum_signature(),
    }
