from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.core.config import Settings, get_settings


def ensure_internal_api_token_on_production(settings: Settings | None = None) -> None:
    resolved_settings = settings or get_settings()
    app_env = resolved_settings.app_env.strip().lower()
    if app_env in {"production", "prod"} and not (resolved_settings.internal_api_token or "").strip():
        raise RuntimeError("INTERNAL_API_TOKEN must be configured when APP_ENV=production")

settings = get_settings()
ensure_internal_api_token_on_production(settings)

app = FastAPI(title=settings.app_name)
app.include_router(v1_router, prefix=settings.api_v1_prefix)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "ForgeMind"}
