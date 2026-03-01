from __future__ import annotations

from typing import Final

RUNTIME_DOCUMENT_CLOSE: Final[str] = """    </script>
  </body>
</html>
"""


def build_runtime_document_open(
    *,
    title: str,
    genre: str,
    slug: str,
    accent_color: str,
    viewport_width: int,
    viewport_height: int,
    safe_area_padding: int,
    min_font_size_px: int,
    text_overflow_policy: str,
    mode_label: str,
    mode_objective: str,
    mode_controls: str,
    asset_pack: dict[str, str],
) -> str:
    return f"""<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>{title}</title>
    <style>
      :root {{
        color-scheme: dark;
        --viewport-width: {viewport_width};
        --viewport-height: {viewport_height};
        --safe-area-padding: {safe_area_padding};
        --min-font-size: {min_font_size_px};
        --text-overflow-policy: "{text_overflow_policy}";
        --accent: {accent_color};
        --asset-bg-top: {asset_pack["bg_top"]};
        --asset-bg-bottom: {asset_pack["bg_bottom"]};
        --asset-hud-primary: {asset_pack["hud_primary"]};
        --asset-hud-muted: {asset_pack["hud_muted"]};
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        height: 100vh;
        overflow: hidden;
        background:
          radial-gradient(800px 400px at 20% 0%, color-mix(in srgb, var(--accent) 35%, transparent), transparent 70%),
          radial-gradient(700px 380px at 90% 0%, #8b5cf622, transparent 68%),
          linear-gradient(180deg, var(--asset-bg-top), var(--asset-bg-bottom));
        color: var(--asset-hud-primary);
        font-family: Inter, system-ui, sans-serif;
        font-size: max(calc(var(--min-font-size) * 1px), 14px);
      }}
      main {{
        width: 100vw;
        height: 100vh;
        padding: calc(var(--safe-area-padding) * 1px);
        background: rgba(2, 6, 23, 0.8);
        display: grid;
        grid-template-rows: auto auto minmax(0, 1fr) auto;
        gap: 10px;
        overflow: hidden;
      }}
      .hud-row {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 8px;
      }}
      .overflow-guard {{
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}
      .title {{
        margin: 0;
        font-size: clamp(20px, 3vw, 30px);
        letter-spacing: -0.02em;
      }}
      .sub {{
        margin: 0;
        color: var(--asset-hud-muted);
        font-size: 13px;
      }}
      .hint {{
        margin: 0;
        color: color-mix(in srgb, var(--asset-hud-muted) 72%, #64748b);
        font-size: 12px;
      }}
      .stat {{
        font-weight: 700;
        font-size: 14px;
        color: var(--asset-hud-primary);
      }}
      .stage {{
        position: relative;
        border-radius: 14px;
        border: 1px solid #1e293b;
        overflow: hidden;
        background: linear-gradient(180deg, #020617, #081024);
        min-height: 0;
      }}
      canvas {{
        width: 100%;
        height: 100%;
        display: block;
        background: #030712;
      }}
      .overlay {{
        position: absolute;
        inset: 0;
        display: grid;
        place-items: center;
        background: rgba(2, 6, 23, 0.75);
        opacity: 0;
        pointer-events: none;
        transition: opacity 120ms ease;
      }}
      .overlay.show {{
        opacity: 1;
        pointer-events: auto;
      }}
      .overlay-card {{
        text-align: center;
        padding: 16px;
        border-radius: 12px;
        border: 1px solid #334155;
        background: rgba(15, 23, 42, 0.9);
        min-width: min(88vw, 320px);
      }}
      button {{
        border: 1px solid {accent_color};
        background: {accent_color};
        color: #031327;
        border-radius: 10px;
        padding: 8px 14px;
        cursor: pointer;
        font-weight: 700;
      }}
    </style>
  </head>
  <body>
    <main data-overflow-policy="{text_overflow_policy}">
      <div class="hud-row">
        <div style="display:grid;gap:4px;min-width:0">
          <h1 class="title overflow-guard">{title}</h1>
          <p class="sub overflow-guard">Mode: {mode_label}</p>
        </div>
      </div>
      <div class="hud-row">
        <strong id="score" class="stat overflow-guard">Score: 0</strong>
        <strong id="timer" class="stat overflow-guard">Time: 60.0</strong>
        <strong id="hp" class="stat overflow-guard">HP: 3</strong>
      </div>
      <div class="stage">
        <canvas id="game" width="{viewport_width}" height="{viewport_height}"></canvas>
        <div id="overlay" class="overlay">
          <div class="overlay-card">
            <h2 id="overlay-title" style="margin:0 0 6px">Game Over</h2>
            <p id="overlay-text" class="hint" style="margin:0 0 12px"></p>
            <button id="restart-btn" type="button">다시 시작 (R)</button>
          </div>
        </div>
      </div>
      <p class="hint overflow-guard">{mode_objective} / {mode_controls}</p>
      <!-- leaderboard contract exposed as window.IISLeaderboard.submitScore -->
    </main>
    <script>
"""
