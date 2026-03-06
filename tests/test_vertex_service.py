from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.services.vertex_service import BuilderRoute, VertexCapacityExhausted, VertexService


def test_builder_model_name_uses_pro_by_default() -> None:
    service = VertexService(Settings(gemini_pro_model="gemini-3.1-pro", telegram_bot_token=""))
    assert service._builder_model_name() == "gemini-3.1-pro"


def test_builder_model_name_rejects_flash_when_force_pro_enabled() -> None:
    service = VertexService(
        Settings(
            gemini_pro_model="gemini-3.0-flash",
            builder_force_pro_model=True,
            telegram_bot_token="",
        )
    )
    assert service._builder_model_name() == "gemini-2.5-pro"


def test_builder_model_name_keeps_configured_value_when_force_pro_disabled() -> None:
    service = VertexService(
        Settings(
            gemini_pro_model="gemini-3.0-flash",
            builder_force_pro_model=False,
            telegram_bot_token="",
        )
    )
    assert service._builder_model_name() == "gemini-3.0-flash"


def test_builder_prompt_mentions_procedural_asset_policy() -> None:
    prompt = VertexService._builder_prompt(
        keyword="네온 드리프트",
        title="Neon Drift",
        genre="arcade",
        objective="survive and score",
        design_spec={"visual_style": "neon"},
        variation_hint="Variant A",
    )
    lowered = prompt.casefold()
    assert "procedural" in lowered
    assert "analog control" in lowered
    assert "miniboss" in lowered
    assert "relic synergy" in lowered


def test_builder_prompt_mentions_formula_guidance() -> None:
    prompt = VertexService._builder_prompt(
        keyword="F1 스타일 풀3D 레이싱",
        title="Formula Neon",
        genre="racing",
        objective="finish laps and overtake rivals",
        design_spec={"visual_style": "formula-neon"},
        variation_hint="Variant A",
    )
    lowered = prompt.casefold()
    assert "formula/f1/circuit racing" in lowered
    assert "braking windows" in lowered
    assert "requested pacing and fantasy" in lowered


def test_generate_marketing_copy_uses_stub_when_vertex_not_configured(monkeypatch) -> None:
    service = VertexService(
        Settings(
            vertex_project_id="",
            telegram_bot_token="",
        )
    )

    def _should_not_call_model():
        raise AssertionError("flash model should not be called when vertex is disabled")

    monkeypatch.setattr(service, "_flash_model", _should_not_call_model)

    result = service.generate_marketing_copy(
        keyword="네온 러너",
        slug="neon-runner",
        genre="arcade",
        game_name="Neon Runner",
    )

    assert result.meta.get("reason") == "vertex_not_configured"
    assert isinstance(result.payload.get("marketing_copy"), str)


def test_generate_ai_review_uses_stub_when_vertex_not_configured(monkeypatch) -> None:
    service = VertexService(
        Settings(
            vertex_project_id="",
            telegram_bot_token="",
        )
    )

    def _should_not_call_model():
        raise AssertionError("flash model should not be called when vertex is disabled")

    monkeypatch.setattr(service, "_flash_model", _should_not_call_model)

    result = service.generate_ai_review(
        keyword="formula drift",
        game_name="Formula Drift",
        genre="arcade",
        objective="survive and overtake",
    )

    assert result.meta.get("reason") == "vertex_not_configured"
    assert isinstance(result.payload.get("ai_review"), str)


def test_is_enabled_uses_settings_credentials_path(monkeypatch, tmp_path: Path) -> None:
    credentials_path = tmp_path / "vertex.json"
    credentials_path.write_text("{}", encoding="utf-8")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    service = VertexService(
        Settings(
            vertex_project_id="iis-vertex-prod",
            google_application_credentials=str(credentials_path),
            telegram_bot_token="",
        )
    )

    assert service._is_enabled() is True
    assert service._use_genai_sdk() is True


def test_settings_credentials_path_populates_env(monkeypatch, tmp_path: Path) -> None:
    credentials_path = tmp_path / "vertex.json"
    credentials_path.write_text("{}", encoding="utf-8")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    service = VertexService(
        Settings(
            vertex_project_id="iis-vertex-prod",
            google_application_credentials=str(credentials_path),
            telegram_bot_token="",
        )
    )

    resolved = service._credentials_path()
    assert resolved == str(credentials_path)
    assert service._is_enabled() is True


def test_build_capacity_route_chain_uses_global_preview_first() -> None:
    service = VertexService(
        Settings(
            vertex_project_id="iis-vertex-prod",
            vertex_location="global",
            gemini_preview_model="gemini-3-pro-preview",
            gemini_pro_model="gemini-2.5-pro",
            gemini_flash_model="gemini-2.5-flash",
            telegram_bot_token="",
        )
    )

    routes = service.build_capacity_route_chain()

    assert routes == [
        BuilderRoute(model_name="gemini-3-pro-preview", location="global", tier="preview", fallback_rank=0),
        BuilderRoute(model_name="gemini-2.5-pro", location="global", tier="stable-pro", fallback_rank=1),
        BuilderRoute(model_name="gemini-2.5-flash", location="global", tier="stable-flash", fallback_rank=2),
    ]


def test_generate_builder_text_with_fallback_uses_next_route_on_429(monkeypatch) -> None:
    service = VertexService(
        Settings(
            vertex_project_id="iis-vertex-prod",
            vertex_location="global",
            gemini_preview_model="gemini-3-pro-preview",
            gemini_pro_model="gemini-2.5-pro",
            gemini_flash_model="gemini-2.5-flash",
            telegram_bot_token="",
        )
    )
    calls: list[tuple[str, str | None]] = []

    def fake_text(*, model_name: str, location: str | None = None, prompt: str, temperature: float, max_output_tokens: int | None = None):
        calls.append((model_name, location))
        if model_name == "gemini-3-pro-preview":
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return ("<html>ok</html>", {"total_tokens": 123})

    monkeypatch.setattr(service, "_genai_text", fake_text)

    result = service.generate_builder_text_with_fallback(prompt="make game", temperature=0.7, max_output_tokens=2048)

    assert calls == [
        ("gemini-3-pro-preview", "global"),
        ("gemini-2.5-pro", "global"),
    ]
    assert result["model_name"] == "gemini-2.5-pro"
    assert result["fallback_used"] is True


def test_generate_builder_text_with_fallback_raises_capacity_when_all_routes_fail(monkeypatch) -> None:
    service = VertexService(
        Settings(
            vertex_project_id="iis-vertex-prod",
            vertex_location="global",
            gemini_preview_model="gemini-3-pro-preview",
            gemini_pro_model="gemini-2.5-pro",
            gemini_flash_model="gemini-2.5-flash",
            telegram_bot_token="",
        )
    )

    def fake_text(*, model_name: str, location: str | None = None, prompt: str, temperature: float, max_output_tokens: int | None = None):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(service, "_genai_text", fake_text)

    try:
        service.generate_builder_text_with_fallback(prompt="make game", temperature=0.7, max_output_tokens=2048)
    except VertexCapacityExhausted as exc:
        assert exc.retry_after_seconds == 10
        assert len(exc.attempted_routes) == 3
    else:
        raise AssertionError("VertexCapacityExhausted was expected")
