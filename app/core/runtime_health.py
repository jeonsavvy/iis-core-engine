from __future__ import annotations

import os
import subprocess
from functools import lru_cache

from app.core.config import Settings, get_settings

try:
    from supabase import create_client
except ImportError:  # pragma: no cover - optional dependency in test environments
    create_client = None


SESSION_SCHEMA_VERSION = "v2"
LEGACY_PIPELINE_SCHEMA_VERSION = "v2"
RUNTIME_MODULE_SIGNATURE = "session_editor_loop_v2"


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


def verify_session_schema_signature(settings: Settings) -> None:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return
    if create_client is None:
        return
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    for table_name in ("sessions", "session_runs"):
        response = (
            client.table(table_name)
            .select("id")
            .limit(1)
            .execute()
        )
        error = getattr(response, "error", None)
        if not error:
            continue
        detail = str(getattr(error, "message", "") or error)
        lowered = detail.casefold()
        if "relation" in lowered and table_name in lowered:
            raise RuntimeError(f"session_schema_mismatch({table_name}): {detail}")


def healthz_payload(settings: Settings | None = None) -> dict[str, str]:
    resolved = settings or get_settings()
    credentials_path = str(resolved.google_application_credentials or "").strip()
    return {
        "status": "ok",
        "service": "IIS Game Editor",
        "git_sha": resolve_git_sha(),
        "session_schema_version": SESSION_SCHEMA_VERSION,
        # Backward compatibility for older deploy scripts that still probe
        # pipeline_schema_version during health signature checks.
        "pipeline_schema_version": LEGACY_PIPELINE_SCHEMA_VERSION,
        "generation_engine_version": resolved.generation_engine_version,
        "rqc_version": resolved.generation_engine_version,
        "module_signature": RUNTIME_MODULE_SIGNATURE,
        "builder_codegen_enabled": "true" if resolved.builder_codegen_enabled else "false",
        "vertex_project_configured": "true" if bool(resolved.vertex_project_id) else "false",
        "vertex_credentials_path_configured": "true" if bool(credentials_path) else "false",
    }
