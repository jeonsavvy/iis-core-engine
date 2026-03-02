from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.core.runtime_health import verify_pipeline_schema_signature


class _FakeQuery:
    def __init__(self, error_message: str | None) -> None:
        self._error_message = error_message

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self._error_message is None:
            return SimpleNamespace(error=None)
        return SimpleNamespace(error=SimpleNamespace(message=self._error_message))


class _FakeClient:
    def __init__(self, error_message: str | None) -> None:
        self._error_message = error_message

    def table(self, _name: str):
        return _FakeQuery(self._error_message)


def test_schema_guard_detects_pipeline_agent_enum_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.core.runtime_health.create_client",
        lambda *_args, **_kwargs: _FakeClient("invalid input value for enum pipeline_agent_name: \"reporter\""),
    )
    settings = Settings(supabase_url="https://example.supabase.co", supabase_service_role_key="test-key")
    with pytest.raises(RuntimeError, match="pipeline_schema_mismatch"):
        verify_pipeline_schema_signature(settings)


def test_schema_guard_skips_when_enum_is_healthy(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.core.runtime_health.create_client",
        lambda *_args, **_kwargs: _FakeClient(None),
    )
    settings = Settings(supabase_url="https://example.supabase.co", supabase_service_role_key="test-key")
    verify_pipeline_schema_signature(settings)
