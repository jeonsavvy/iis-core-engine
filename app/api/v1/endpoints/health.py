from typing import cast

from fastapi import APIRouter

from app.core.runtime_health import healthz_payload

router = APIRouter()


@router.get("/health")
def v1_health() -> dict[str, object]:
    payload = cast(dict[str, object], healthz_payload())
    payload["scope"] = "v1"
    return payload
