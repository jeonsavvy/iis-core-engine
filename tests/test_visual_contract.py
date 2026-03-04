from app.services.visual_contract import (
    canonicalize_visual_token,
    canonicalize_visual_tokens,
    resolve_visual_contract_profile,
)


def test_resolve_visual_contract_profile_prefers_racing_profile() -> None:
    profile = resolve_visual_contract_profile(
        core_loop_type="webgl_three_runner",
        runtime_engine_mode="3d_three",
        keyword="f1 formula circuit",
    )

    assert profile.profile_id == "visual_3d_racing_v1"
    assert profile.advanced_density_enabled is True


def test_resolve_visual_contract_profile_prefers_2d_mode() -> None:
    profile = resolve_visual_contract_profile(
        core_loop_type="topdown_roguelike_shooter",
        runtime_engine_mode="2d_phaser",
    )

    assert profile.profile_id == "visual_2d_default_v1"
    assert profile.advanced_density_enabled is False


def test_canonicalize_visual_tokens_normalizes_aliases() -> None:
    normalized = canonicalize_visual_tokens(
        [
            "visual_contrast",
            "motion_presence",
            "color_diversity",
            "visual_shape_definition_too_low",
            "color_diversity",
        ]
    )

    assert normalized == ["contrast", "motion", "diversity", "edge"]
    assert canonicalize_visual_token("advanced_visual_density") == "density"
