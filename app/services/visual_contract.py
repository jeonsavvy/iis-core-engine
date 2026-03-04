from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VisualContractProfile:
    profile_id: str
    contrast_min: float
    color_diversity_min: float
    composition_non_dark_min: float
    composition_non_dark_max: float
    edge_energy_min: float
    motion_delta_min: float
    cohesion_contrast_min: float
    cohesion_edge_min: float
    cohesion_color_min: float
    advanced_density_enabled: bool
    advanced_density_color_min: float
    advanced_density_edge_min: float
    frame_probe_count: int = 4

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "profile_id": self.profile_id,
            "contrast_min": self.contrast_min,
            "color_diversity_min": self.color_diversity_min,
            "composition_non_dark_min": self.composition_non_dark_min,
            "composition_non_dark_max": self.composition_non_dark_max,
            "edge_energy_min": self.edge_energy_min,
            "motion_delta_min": self.motion_delta_min,
            "cohesion_contrast_min": self.cohesion_contrast_min,
            "cohesion_edge_min": self.cohesion_edge_min,
            "cohesion_color_min": self.cohesion_color_min,
            "advanced_density_enabled": self.advanced_density_enabled,
            "frame_probe_count": self.frame_probe_count,
        }
        if self.advanced_density_enabled:
            payload["advanced_density_color_min"] = self.advanced_density_color_min
            payload["advanced_density_edge_min"] = self.advanced_density_edge_min
        return payload


_PROFILE_DEFAULT_2D = VisualContractProfile(
    profile_id="visual_2d_default_v1",
    contrast_min=16.0,
    color_diversity_min=14.0,
    composition_non_dark_min=0.05,
    composition_non_dark_max=0.95,
    edge_energy_min=0.014,
    motion_delta_min=0.00045,
    cohesion_contrast_min=14.0,
    cohesion_edge_min=0.012,
    cohesion_color_min=12.0,
    advanced_density_enabled=False,
    advanced_density_color_min=0.0,
    advanced_density_edge_min=0.0,
)

_PROFILE_DEFAULT_3D = VisualContractProfile(
    profile_id="visual_3d_default_v1",
    contrast_min=18.0,
    color_diversity_min=18.0,
    composition_non_dark_min=0.05,
    composition_non_dark_max=0.95,
    edge_energy_min=0.019,
    motion_delta_min=0.00075,
    cohesion_contrast_min=16.0,
    cohesion_edge_min=0.017,
    cohesion_color_min=16.0,
    advanced_density_enabled=False,
    advanced_density_color_min=0.0,
    advanced_density_edge_min=0.0,
)

_PROFILE_RACING_3D = VisualContractProfile(
    profile_id="visual_3d_racing_v1",
    contrast_min=20.0,
    color_diversity_min=20.0,
    composition_non_dark_min=0.06,
    composition_non_dark_max=0.94,
    edge_energy_min=0.022,
    motion_delta_min=0.0009,
    cohesion_contrast_min=17.0,
    cohesion_edge_min=0.019,
    cohesion_color_min=18.0,
    advanced_density_enabled=True,
    advanced_density_color_min=24.0,
    advanced_density_edge_min=0.026,
)

_PROFILE_FLIGHT_3D = VisualContractProfile(
    profile_id="visual_3d_flight_v1",
    contrast_min=19.0,
    color_diversity_min=19.0,
    composition_non_dark_min=0.05,
    composition_non_dark_max=0.95,
    edge_energy_min=0.021,
    motion_delta_min=0.00085,
    cohesion_contrast_min=16.5,
    cohesion_edge_min=0.018,
    cohesion_color_min=17.0,
    advanced_density_enabled=True,
    advanced_density_color_min=23.0,
    advanced_density_edge_min=0.025,
)


def resolve_visual_contract_profile(
    *,
    core_loop_type: str | None,
    runtime_engine_mode: str | None,
    keyword: str | None = None,
) -> VisualContractProfile:
    mode = str(runtime_engine_mode or "").strip().casefold()
    core_loop = str(core_loop_type or "").strip().casefold()
    keyword_hint = str(keyword or "").strip().casefold()
    combined = f"{core_loop} {keyword_hint}"

    if mode == "2d_phaser":
        return _PROFILE_DEFAULT_2D

    if any(token in combined for token in ("racing", "race", "f1", "formula", "drift", "레이싱", "서킷")):
        return _PROFILE_RACING_3D
    if any(token in combined for token in ("flight", "space", "pilot", "비행", "조종", "전투기", "cockpit")):
        return _PROFILE_FLIGHT_3D

    return _PROFILE_DEFAULT_3D


_CANONICAL_VISUAL_TOKEN_MAP: dict[str, str] = {
    "visual_gate_unmet": "visual_gate",
    "visual_quality_below_threshold": "visual_gate",
    "visual_contrast": "contrast",
    "contrast": "contrast",
    "color_diversity": "diversity",
    "visual_color_diversity": "diversity",
    "visual_palette_too_flat": "palette",
    "composition_balance": "composition",
    "edge_definition": "edge",
    "visual_shape_definition_too_low": "edge",
    "motion_presence": "motion",
    "readable_motion": "motion",
    "visual_cohesion": "cohesion",
    "advanced_visual_density": "density",
}


def canonicalize_visual_token(token: str) -> str:
    normalized = str(token or "").strip().casefold().replace("-", "_").replace(" ", "_")
    if not normalized:
        return ""
    return _CANONICAL_VISUAL_TOKEN_MAP.get(normalized, normalized)


def canonicalize_visual_tokens(tokens: list[str] | set[str] | tuple[str, ...] | None) -> list[str]:
    rows = list(tokens or [])
    normalized: list[str] = []
    for row in rows:
        token = canonicalize_visual_token(str(row))
        if token and token not in normalized:
            normalized.append(token)
    return normalized
