from __future__ import annotations

from app.services.vertex_fallback_text import (
    build_ai_review_fallback,
    build_grounded_ai_review_fallback,
    build_marketing_fallback_copy,
)
from app.services.vertex_prompts import (
    build_builder_prompt,
    build_design_prompt,
    build_gdd_prompt,
)


def test_prompt_module_gdd_contains_keyword_and_formula_clause() -> None:
    prompt = build_gdd_prompt("formula drift")
    lowered = prompt.casefold()
    assert "keyword: formula drift" in lowered
    assert "formula/f1/circuit racing" in lowered


def test_prompt_module_design_mentions_readability_rules() -> None:
    prompt = build_design_prompt(keyword="네온", visual_style="neon-minimal", genre="arcade")
    lowered = prompt.casefold()
    assert "palette must have 4 colors" in lowered
    assert "hud must communicate score" in lowered


def test_prompt_module_builder_keeps_variation_hint() -> None:
    prompt = build_builder_prompt(
        keyword="neon",
        title="Neon",
        genre="arcade",
        objective="survive",
        design_spec={"visual_style": "neon"},
        variation_hint="variant-a",
    )
    lowered = prompt.casefold()
    assert "variation hint: variant-a" in lowered
    assert "relic synergy" in lowered


def test_fallback_copy_modules_return_non_empty_text() -> None:
    marketing = build_marketing_fallback_copy(display_name="Neon", keyword="neon", genre="arcade")
    review = build_ai_review_fallback(keyword="neon", game_name="Neon", genre="arcade", objective="survive")
    grounded = build_grounded_ai_review_fallback(
        objective="survive",
        evidence={"genre_engine": "lane_dodge_racer", "quality_score": 72, "gameplay_score": 68},
    )

    assert isinstance(marketing, str) and marketing.strip()
    assert isinstance(review, str) and review.strip()
    assert isinstance(grounded, str) and grounded.strip()
