from fastapi import HTTPException

from app.api.security import verify_internal_api_token
from app.core.config import get_settings
from app.main import ensure_internal_api_token_on_production


def test_api_token_requires_bearer_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "top-secret")
    get_settings.cache_clear()

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


def test_api_token_whitespace_disables_requirement(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "   ")
    get_settings.cache_clear()

    verify_internal_api_token(None)

    get_settings.cache_clear()


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


def test_production_rejects_whitespace_internal_api_token(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("INTERNAL_API_TOKEN", "   ")
    get_settings.cache_clear()

    try:
        ensure_internal_api_token_on_production()
    except RuntimeError as exc:
        assert "INTERNAL_API_TOKEN" in str(exc)
    else:
        raise AssertionError("expected RuntimeError when INTERNAL_API_TOKEN is blank in production")

    get_settings.cache_clear()


def test_non_production_allows_missing_internal_api_token(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("INTERNAL_API_TOKEN", raising=False)
    get_settings.cache_clear()

    ensure_internal_api_token_on_production()

    get_settings.cache_clear()
