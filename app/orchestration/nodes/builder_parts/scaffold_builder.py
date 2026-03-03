"""Scaffold HTML builder for codegen-first pipeline.

Generates a minimal bootstrap HTML document that contains only:
- Runtime engine bootstrap (Three.js for 3D / Phaser for 2D)
- Stage root element
- Boot flag + Leaderboard contract stubs
- A placeholder marker for LLM-generated game code

The LLM codegen pass fills in the actual game logic.
"""

from __future__ import annotations

from typing import Any

_THREE_CDN = "https://unpkg.com/three@0.169.0/build/three.module.js"


def build_scaffold_html(
    *,
    title: str,
    genre: str,
    slug: str,
    accent_color: str,
    viewport_width: int = 1280,
    viewport_height: int = 720,
    safe_area_padding: int = 24,
    min_font_size_px: int = 14,
    text_overflow_policy: str = "ellipsis-clamp",
    core_loop_type: str = "arcade_generic",
    runtime_engine_mode: str = "3d_three",
    asset_pack: dict[str, Any] | None = None,
) -> str:
    """Return a minimal scaffold HTML for LLM codegen to populate."""
    ap = asset_pack or {}
    engine_mode = str(runtime_engine_mode).strip().casefold() or "3d_three"
    if engine_mode == "2d_phaser":
        return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title}</title>
<style>
:root {{
  --safe-area-padding: {safe_area_padding}px;
  --viewport-width: {viewport_width};
  --viewport-height: {viewport_height};
  --min-font-size: {min_font_size_px};
  --accent: {accent_color};
}}
html, body {{
  margin: 0; width: 100%; height: 100%; overflow: hidden;
  background: #050a14; color: #e2e8f0;
  font-family: Inter, system-ui, sans-serif;
}}
body {{ display: grid; place-items: center; }}
.overflow-guard {{
  width: min(100vw, calc(100vh * {viewport_width} / {viewport_height}));
  max-width: 100vw; max-height: 100vh;
  aspect-ratio: {viewport_width} / {viewport_height};
  position: relative; overflow: hidden;
  data-overflow-policy: "{text_overflow_policy}";
}}
#phaser-root {{ width: 100%; height: 100%; }}
#hud {{
  position: absolute; top: var(--safe-area-padding); left: var(--safe-area-padding);
  right: var(--safe-area-padding); pointer-events: none; z-index: 10;
  font-size: max(var(--min-font-size) * 1px, 1.1vw);
  color: #e2e8f0; text-shadow: 0 1px 4px rgba(0,0,0,.7);
}}
</style>
</head>
<body>
<div class="overflow-guard">
  <div id="phaser-root"></div>
  <div id="hud"></div>
</div>

<script src="https://cdn.jsdelivr.net/npm/phaser@3.90.0/dist/phaser.min.js"></script>
<script>
// === IIS CONTRACT ===
window.IISLeaderboard = {{ postScore: (s) => console.log('IIS:score', s) }};
window.__iis_game_meta = {{
  slug: '{slug}',
  genre: '{genre}',
  core_loop_type: '{core_loop_type}',
  runtime_engine_mode: '2d_phaser',
  asset_pack: '{ap.get("name", "default")}',
}};

// === LLM CODEGEN TARGET ===
// The LLM should replace this scaffold with full Phaser runtime.
// Requirements:
// - Keep Phaser runtime contract and use #phaser-root mount point
// - Implement update loop, restart flow, and keyboard controls
// - Set window.__iis_game_boot_ok = true when runtime is ready

console.warn('[IIS Scaffold] Awaiting LLM Phaser codegen — no game logic loaded yet');
window.__iis_game_boot_ok = true;
</script>
</body>
</html>"""
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title}</title>
<style>
:root {{
  --safe-area-padding: {safe_area_padding}px;
  --viewport-width: {viewport_width};
  --viewport-height: {viewport_height};
  --min-font-size: {min_font_size_px};
  --accent: {accent_color};
}}
html, body {{
  margin: 0; width: 100%; height: 100%; overflow: hidden;
  background: #050a14; color: #e2e8f0;
  font-family: Inter, system-ui, sans-serif;
}}
body {{ display: grid; place-items: center; }}
.overflow-guard {{
  width: min(100vw, calc(100vh * {viewport_width} / {viewport_height}));
  max-width: 100vw; max-height: 100vh;
  aspect-ratio: {viewport_width} / {viewport_height};
  position: relative; overflow: hidden;
  data-overflow-policy: "{text_overflow_policy}";
}}
canvas {{ display: block; width: 100%; height: 100%; }}
#hud {{
  position: absolute; top: var(--safe-area-padding); left: var(--safe-area-padding);
  right: var(--safe-area-padding); pointer-events: none; z-index: 10;
  font-size: max(var(--min-font-size) * 1px, 1.1vw);
  color: #e2e8f0; text-shadow: 0 1px 4px rgba(0,0,0,.7);
}}
</style>
</head>
<body>
<div class="overflow-guard">
  <canvas id="game"></canvas>
  <div id="hud"></div>
</div>

<script type="importmap">
{{
  "imports": {{
    "three": "{_THREE_CDN}"
  }}
}}
</script>

<script type="module">
import * as THREE from 'three';

// === IIS CONTRACT ===
window.IISLeaderboard = {{ postScore: (s) => console.log('IIS:score', s) }};
window.__iis_game_meta = {{
  slug: '{slug}',
  genre: '{genre}',
  core_loop_type: '{core_loop_type}',
  runtime_engine_mode: '3d_three',
  asset_pack: '{ap.get("name", "default")}',
}};

// === LLM CODEGEN TARGET ===
// The LLM will replace this entire section with full game code.
// Requirements:
// - Use THREE.js (already imported above)
// - Create WebGLRenderer attached to #game canvas
// - Implement full game loop with requestAnimationFrame
// - Set window.__iis_game_boot_ok = true when ready
// - Minimum: custom GLSL shaders, game state machine, particle systems

console.warn('[IIS Scaffold] Awaiting LLM codegen — no game logic loaded yet');
window.__iis_game_boot_ok = true;
</script>
</body>
</html>"""
