from __future__ import annotations

from app.orchestration.nodes.builder_parts.html_runtime_sections_gameplay import (
    build_runtime_spawn_combat_functions_js,
    build_runtime_update_function_js,
)
from app.orchestration.nodes.builder_parts.html_runtime_sections_progression import (
    build_runtime_progression_functions_js,
)
from app.orchestration.nodes.builder_parts.html_runtime_sections_render import (
    build_runtime_hud_functions_js,
    build_runtime_render_functions_js,
)
from app.orchestration.nodes.builder_parts.html_runtime_sections_utility import (
    build_runtime_utility_functions_js,
)

__all__ = [
    "build_runtime_hud_functions_js",
    "build_runtime_progression_functions_js",
    "build_runtime_render_functions_js",
    "build_runtime_spawn_combat_functions_js",
    "build_runtime_update_function_js",
    "build_runtime_utility_functions_js",
]
