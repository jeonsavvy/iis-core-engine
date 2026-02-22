from __future__ import annotations

from app.core.config import Settings


class VertexService:
    """Vertex wrapper placeholder for GDD/design/code generation."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate_gdd(self, keyword: str) -> dict[str, str]:
        return {
            "title": f"{keyword.title()} Blitz",
            "genre": "arcade",
            "goal": "Survive and maximize score in a short session.",
            "visual_style": "neon-minimal",
        }

    def generate_design_spec(self, visual_style: str) -> dict[str, str]:
        return {
            "palette": "#0B1021,#1C2A48,#F59E0B,#F3F4F6",
            "hud": "top score bar + pause button",
            "typography": "Inter",
            "style_hint": visual_style,
        }

    def generate_single_file_game(self, title: str) -> str:
        return f"<!-- generated placeholder for {title} -->"
