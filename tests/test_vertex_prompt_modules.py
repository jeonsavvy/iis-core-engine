from __future__ import annotations

from app.services.vertex_fallback_text import (
    build_ai_review_fallback,
    build_grounded_ai_review_fallback,
    build_marketing_fallback_copy,
)
from app.services.vertex_prompts import (
    build_builder_prompt,
    build_codegen_prompt,
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


def test_codegen_prompt_contains_visual_contract_targets() -> None:
    prompt = build_codegen_prompt(
        keyword="해안 도시 3d 레이싱",
        title="Neon Circuit",
        genre="racing_3d",
        objective="finish 3 laps",
        core_loop_type="webgl_three_runner",
        runtime_engine_mode="3d_three",
        variation_hint="balanced",
        design_spec={"visual_style": "sunset-neon"},
        asset_pack={"name": "neon"},
        intent_contract={"player_verbs": ["drift", "steer"]},
        synapse_contract={"required_mechanics": ["checkpoint", "lap"]},
        html_content="<html></html>",
    )
    lowered = prompt.casefold()
    assert "=== visual contract ===" in lowered
    assert "contrast_min" in lowered
    assert "color_diversity_min" in lowered
    assert "motion_delta_min" in lowered
    assert "do not reference add-on classes through `three.<symbol>` namespace" in lowered
