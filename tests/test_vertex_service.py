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
