from fastapi import HTTPException

from app.api.deps import get_pipeline_repository
from app.api.security import verify_internal_api_token
from app.api.v1.endpoints.pipelines import trigger_pipeline
from app.core.config import get_settings
from app.main import ensure_internal_api_token_on_production
from app.schemas.pipeline import TriggerRequest


def test_pipeline_endpoints_require_bearer_token_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "top-secret")
    get_settings.cache_clear()
    get_pipeline_repository.cache_clear()

    try:
        verify_internal_api_token(None)
    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail == "Missing bearer token"
    else:
        raise AssertionError("expected HTTPException for missing token")

    try:
        verify_internal_api_token("Bearer wrong-token")
    except HTTPException as exc:
        assert exc.status_code == 401
        assert exc.detail == "Invalid bearer token"
    else:
        raise AssertionError("expected HTTPException for invalid token")

    verify_internal_api_token("Bearer top-secret")

    get_settings.cache_clear()
    get_pipeline_repository.cache_clear()


def test_trigger_keyword_validation_blocks_forbidden_term(monkeypatch) -> None:
    monkeypatch.setenv("TRIGGER_FORBIDDEN_KEYWORDS", "secret,admin")
    monkeypatch.delenv("INTERNAL_API_TOKEN", raising=False)
    get_settings.cache_clear()
    get_pipeline_repository.cache_clear()

    repository = get_pipeline_repository()

    try:
        trigger_pipeline(
            TriggerRequest(keyword="secret project", source="console"),
            repository,
        )
    except HTTPException as exc:
        assert exc.status_code == 422
        assert exc.detail == "keyword_contains_blocked_term"
    else:
        raise AssertionError("expected HTTPException for forbidden keyword")

    allowed = trigger_pipeline(
        TriggerRequest(keyword="  neon   arena  ", source="console"),
        repository,
    )
    assert allowed.status.value == "queued"

    get_settings.cache_clear()
    get_pipeline_repository.cache_clear()


def test_production_requires_internal_api_token(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("INTERNAL_API_TOKEN", raising=False)
    get_settings.cache_clear()

    try:
        ensure_internal_api_token_on_production()
    except RuntimeError as exc:
        assert "INTERNAL_API_TOKEN" in str(exc)
    else:
        raise AssertionError("expected RuntimeError when INTERNAL_API_TOKEN is missing in production")

    get_settings.cache_clear()


def test_non_production_allows_missing_internal_api_token(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("INTERNAL_API_TOKEN", raising=False)
    get_settings.cache_clear()

    ensure_internal_api_token_on_production()

    get_settings.cache_clear()
