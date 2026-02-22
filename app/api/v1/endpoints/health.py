from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def v1_health() -> dict[str, str]:
    return {"status": "ok", "scope": "v1"}
