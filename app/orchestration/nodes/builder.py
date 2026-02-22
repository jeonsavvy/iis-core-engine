from __future__ import annotations

import re

from pydantic import ValidationError

from app.orchestration.graph.state import PipelineState
from app.orchestration.nodes.common import append_log
from app.orchestration.nodes.dependencies import NodeDependencies
from app.schemas.payloads import BuildArtifactPayload, DesignSpecPayload, GDDPayload
from app.schemas.pipeline import PipelineAgentName, PipelineStage, PipelineStatus


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "untitled-game"


def _is_safe_slug(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value))


def _build_html(
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
) -> str:
    return f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
    <title>{title}</title>
    <style>
      :root {{
        color-scheme: dark;
        --viewport-width: {viewport_width};
        --viewport-height: {viewport_height};
        --safe-area-padding: {safe_area_padding};
        --min-font-size: {min_font_size_px};
        --text-overflow-policy: "{text_overflow_policy}";
      }}
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        font-family: Inter, system-ui, sans-serif;
        font-size: max(calc(var(--min-font-size) * 1px), 14px);
        background: radial-gradient(circle, {accent_color}22 0%, #0b1021 60%);
        color: #f8fafc;
      }}
      main {{
        width: min(92vw, calc(var(--viewport-width) * 1px));
        min-height: min(88vh, calc(var(--viewport-height) * 1px));
        padding: calc(var(--safe-area-padding) * 1px);
        border: 1px solid #1f2937;
        border-radius: 14px;
        text-align: center;
        overflow: hidden;
      }}
      button {{
        border: 1px solid {accent_color};
        background: {accent_color};
        color: #0b1021;
        border-radius: 10px;
        padding: 8px 14px;
        font-weight: 700;
        cursor: pointer;
      }}
      .hud {{ display: flex; justify-content: space-between; margin-top: 14px; }}
      .hint {{ color: #94a3b8; font-size: 13px; }}
      .overflow-guard {{
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}
    </style>
  </head>
  <body>
    <main data-overflow-policy=\"{text_overflow_policy}\">
      <h1 class=\"overflow-guard\">{title}</h1>
      <p class=\"overflow-guard\">Genre: {genre}</p>
      <button id=\"score-btn\">+100 Score</button>
      <div class=\"hud\">
        <strong id=\"score\" class=\"overflow-guard\">Score: 0</strong>
        <span class=\"overflow-guard\">{slug}</span>
      </div>
      <p class=\"hint overflow-guard\">Use IISLeaderboard.submitScore(playerName, score, fingerprint) when game over.</p>
    </main>

    <script>
      window.__iis_game_boot_ok = true;
      const state = {{ score: 0 }};

      document.getElementById("score-btn").addEventListener("click", () => {{
        state.score += 100;
        document.getElementById("score").textContent = `Score: ${{state.score}}`;
      }});

      async function submitScore(playerName, score, fingerprint) {{
        const endpoint = window.__IIS_LEADERBOARD_ENDPOINT;
        const anonKey = window.__IIS_SUPABASE_ANON_KEY;
        const gameId = window.__IIS_GAME_ID;

        if (!endpoint || !anonKey || !gameId) {{
          return {{ status: "skipped", reason: "missing_env" }};
        }}

        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 8000);

        try {{
          const response = await fetch(endpoint, {{
            method: "POST",
            headers: {{
              "Content-Type": "application/json",
              apikey: anonKey,
              Authorization: `Bearer ${{anonKey}}`,
              Prefer: "return=minimal",
            }},
            body: JSON.stringify({{
              game_id: gameId,
              player_name: playerName,
              score,
              player_fingerprint: fingerprint,
            }}),
            signal: controller.signal,
          }});

          if (!response.ok) {{
            return {{ status: "error", reason: `http_${{response.status}}` }};
          }}

          return {{ status: "ok" }};
        }} catch (error) {{
          return {{ status: "error", reason: String(error) }};
        }} finally {{
          clearTimeout(timeout);
        }}
      }}

      window.IISLeaderboard = {{ submitScore }};
    </script>
  </body>
</html>
"""


def run(state: PipelineState, _deps: NodeDependencies) -> PipelineState:
    state["build_iteration"] += 1

    try:
        gdd = GDDPayload.model_validate(state["outputs"].get("gdd", {}))
    except ValidationError:
        gdd = GDDPayload(
            title=f"{state['keyword'].title()} Infinite",
            genre="arcade",
            objective="Get highest score possible in 90 seconds.",
            visual_style="neon-minimal",
        )

    try:
        design_spec = DesignSpecPayload.model_validate(state["outputs"].get("design_spec", {}))
    except ValidationError:
        design_spec = DesignSpecPayload(
            visual_style=gdd.visual_style or "neon-minimal",
            palette=["#22C55E"],
            hud="score-top-left / timer-top-right",
            viewport_width=1280,
            viewport_height=720,
            safe_area_padding=24,
            min_font_size_px=14,
            text_overflow_policy="ellipsis-clamp",
        )

    title = gdd.title
    genre = gdd.genre
    safe_slug = state["outputs"].get("safe_slug")
    if isinstance(safe_slug, str) and safe_slug and _is_safe_slug(safe_slug):
        slug = safe_slug
    else:
        slug = _slugify(state["keyword"])

    palette = design_spec.palette
    accent_color = str(palette[0]) if palette else "#22C55E"

    artifact_html = _build_html(
        title=title,
        genre=genre,
        slug=slug,
        accent_color=accent_color,
        viewport_width=design_spec.viewport_width,
        viewport_height=design_spec.viewport_height,
        safe_area_padding=design_spec.safe_area_padding,
        min_font_size_px=design_spec.min_font_size_px,
        text_overflow_policy=design_spec.text_overflow_policy,
    )

    build_artifact = BuildArtifactPayload(
        game_slug=slug,
        game_name=title,
        game_genre=genre,
        artifact_path=f"games/{slug}/index.html",
        artifact_html=artifact_html,
    )

    state["outputs"]["build_artifact"] = build_artifact.model_dump()
    state["outputs"]["game_slug"] = build_artifact.game_slug
    state["outputs"]["game_name"] = build_artifact.game_name
    state["outputs"]["game_genre"] = build_artifact.game_genre
    state["outputs"]["artifact_path"] = build_artifact.artifact_path
    state["outputs"]["artifact_html"] = build_artifact.artifact_html

    return append_log(
        state,
        stage=PipelineStage.BUILD,
        status=PipelineStatus.SUCCESS,
        agent_name=PipelineAgentName.BUILDER,
        message=f"Single-file HTML/JS artifact generated (iteration={state['build_iteration']}).",
        metadata={
            "artifact": state["outputs"]["artifact_path"],
            "genre": genre,
            "viewport": f"{design_spec.viewport_width}x{design_spec.viewport_height}",
        },
    )
