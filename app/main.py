from typing import cast
import logging
import asyncio

from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.core.config import Settings, get_settings
from app.core.runtime_health import healthz_payload, verify_session_schema_signature


def ensure_internal_api_token_on_production(settings: Settings | None = None) -> None:
    resolved_settings = settings or get_settings()
    app_env = resolved_settings.app_env.strip().lower()
    if app_env in {"production", "prod"} and not (resolved_settings.internal_api_token or "").strip():
        raise RuntimeError("INTERNAL_API_TOKEN must be configured when APP_ENV=production")

settings = get_settings()
ensure_internal_api_token_on_production(settings)
if settings.app_env.strip().lower() in {"production", "prod"}:
    verify_session_schema_signature(settings)

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
app.include_router(v1_router, prefix=settings.api_v1_prefix)


# ---------------------------------------------------------------------------
# Agent lifecycle: initialize on startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def _init_agents() -> None:
    """Initialize agent loop, publisher, and session persistence."""
    from app.services.vertex_service import VertexService
    from app.agents.codegen_agent import CodegenAgent
    from app.agents.visual_qa_agent import VisualQAAgent
    from app.agents.playtester_agent import PlaytesterAgent
    from app.agents.agent_loop import AgentLoop
    from app.services.session_publisher import SessionPublisher
    from app.services.session_store import enable_supabase_persistence

    app.state.vertex_service = None
    app.state.codegen_agent = None
    app.state.visual_qa_agent = None
    app.state.playtester_agent = None
    app.state.agent_loop = None
    app.state.publisher_service = None
    app.state.session_run_tasks = {}
    app.state.prompt_run_semaphore = asyncio.Semaphore(max(1, int(settings.prompt_worker_concurrency)))

    try:
        vertex = VertexService(settings)
        codegen = CodegenAgent(vertex_service=vertex)
        visual_qa = VisualQAAgent(vertex_service=vertex)
        playtester = PlaytesterAgent()
        loop = AgentLoop(codegen=codegen, visual_qa=visual_qa, playtester=playtester)

        app.state.vertex_service = vertex
        app.state.codegen_agent = codegen
        app.state.visual_qa_agent = visual_qa
        app.state.playtester_agent = playtester
        app.state.agent_loop = loop
        logger.info("Agent loop initialized.")
    except Exception:
        logger.exception("Agent loop initialization failed. /sessions/{id}/prompt will return 503.")

    try:
        app.state.publisher_service = SessionPublisher(settings)
    except Exception:
        logger.exception("Session publisher initialization failed. Publish endpoint will stay disabled.")
        app.state.publisher_service = None

    try:
        enable_supabase_persistence(app, settings)
    except Exception:
        logger.exception("Supabase session persistence initialization failed. Session API will return 503.")


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return cast(dict[str, object], healthz_payload())
