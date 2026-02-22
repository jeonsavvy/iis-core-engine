from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.include_router(v1_router, prefix=settings.api_v1_prefix)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "ForgeMind"}
