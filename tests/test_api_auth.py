from fastapi.testclient import TestClient

from app.api.deps import get_pipeline_repository
from app.core.config import get_settings
from app.main import app


def test_pipeline_endpoints_require_bearer_token_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "top-secret")
    get_settings.cache_clear()
    get_pipeline_repository.cache_clear()

    client = TestClient(app)
    payload = {"keyword": "token check", "source": "console"}

    missing = client.post("/api/v1/pipelines/trigger", json=payload)
    assert missing.status_code == 401

    wrong = client.post(
        "/api/v1/pipelines/trigger",
        json=payload,
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert wrong.status_code == 401

    allowed = client.post(
        "/api/v1/pipelines/trigger",
        json=payload,
        headers={"Authorization": "Bearer top-secret"},
    )
    assert allowed.status_code == 202

    get_settings.cache_clear()
    get_pipeline_repository.cache_clear()


def test_trigger_keyword_validation_blocks_forbidden_term(monkeypatch) -> None:
    monkeypatch.setenv("TRIGGER_FORBIDDEN_KEYWORDS", "secret,admin")
    monkeypatch.delenv("INTERNAL_API_TOKEN", raising=False)
    get_settings.cache_clear()
    get_pipeline_repository.cache_clear()

    client = TestClient(app)
    blocked = client.post(
        "/api/v1/pipelines/trigger",
        json={"keyword": "secret project", "source": "console"},
    )

    assert blocked.status_code == 422
    assert blocked.json()["detail"] == "keyword_contains_blocked_term"

    allowed = client.post(
        "/api/v1/pipelines/trigger",
        json={"keyword": "  neon   arena  ", "source": "console"},
    )

    assert allowed.status_code == 202

    get_settings.cache_clear()
    get_pipeline_repository.cache_clear()
