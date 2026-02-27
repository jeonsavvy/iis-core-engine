from __future__ import annotations

from app.core.config import Settings
from app.services.vertex_service import VertexService


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
    assert "multi-minute runs" in lowered


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
