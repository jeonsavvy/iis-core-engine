from __future__ import annotations

from typing import Any

from app.orchestration.nodes.builder_parts.html_runtime_balance import build_runtime_balance_block_js
from app.orchestration.nodes.builder_parts.html_runtime_config import build_runtime_config_json, resolve_mode_config
from app.orchestration.nodes.builder_parts.html_runtime_progression import build_progression_block_js
from app.orchestration.nodes.builder_parts.html_runtime_sections import (
    build_runtime_hud_functions_js,
    build_runtime_progression_functions_js,
    build_runtime_render_functions_js,
    build_runtime_spawn_combat_functions_js,
    build_runtime_update_function_js,
    build_runtime_utility_functions_js,
)
from app.orchestration.nodes.builder_parts.html_runtime_shell import (
    RUNTIME_DOCUMENT_CLOSE,
    build_runtime_document_open,
)


def _build_hybrid_engine_html(
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
    core_loop_type: str,
    game_config: dict[str, Any],
    asset_pack: dict[str, str],
    asset_manifest: dict[str, object] | None = None,
) -> str:
    mode_config = resolve_mode_config(core_loop_type)
    config_json = build_runtime_config_json(
        title=title,
        genre=genre,
        slug=slug,
        accent_color=accent_color,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        safe_area_padding=safe_area_padding,
        min_font_size_px=min_font_size_px,
        text_overflow_policy=text_overflow_policy,
        core_loop_type=core_loop_type,
        game_config=game_config,
        asset_pack=asset_pack,
        asset_manifest=asset_manifest,
    )
    runtime_balance_js = build_runtime_balance_block_js()
    runtime_progression_js = build_progression_block_js()
    runtime_utility_functions_js = build_runtime_utility_functions_js()
    runtime_progression_functions_js = build_runtime_progression_functions_js()
    runtime_spawn_combat_functions_js = build_runtime_spawn_combat_functions_js()
    runtime_update_function_js = build_runtime_update_function_js()
    runtime_render_functions_js = build_runtime_render_functions_js()
    runtime_hud_functions_js = build_runtime_hud_functions_js()
    document_open = build_runtime_document_open(
        title=title,
        genre=genre,
        slug=slug,
        accent_color=accent_color,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        safe_area_padding=safe_area_padding,
        min_font_size_px=min_font_size_px,
        text_overflow_policy=text_overflow_policy,
        mode_label=mode_config["label"],
        mode_objective=mode_config["objective"],
        mode_controls=mode_config["controls"],
        asset_pack=asset_pack,
    )

    return f"""{document_open}      window.__iis_game_boot_ok = true;
      const CONFIG = {config_json};
      const ASSET = {{
        name: "neon_arcade",
        bg_top: "#08122f",
        bg_bottom: "#050915",
        horizon: "#0f172a",
        track: "#111827",
        hud_primary: "#e2e8f0",
        hud_muted: "#93c5fd",
        player_primary: "#38bdf8",
        player_secondary: "#0f172a",
        enemy_primary: "#ef4444",
        enemy_elite: "#f97316",
        boost_color: "#22d3ee",
        accent: "#22c55e",
        particle: "#22c55e",
        sfx_profile: "synth",
        sprite_profile: "neon",
        ...(CONFIG.assetPack || {{}}),
      }};
      const ASSET_MANIFEST = CONFIG.assetManifest && typeof CONFIG.assetManifest === "object" ? CONFIG.assetManifest : {{}};
      const SPRITE_PATHS = ASSET_MANIFEST.images && typeof ASSET_MANIFEST.images === "object" ? ASSET_MANIFEST.images : {{}};
      const SPRITES = {{}};
      const MODE_IS_FLIGHT_SIM = CONFIG.mode === "flight_sim_3d";
      const MODE_IS_FORMULA_CIRCUIT = CONFIG.mode === "f1_formula_circuit_3d";
      const MODE_IS_3D_RUNNER = MODE_IS_FORMULA_CIRCUIT || CONFIG.mode === "lane_dodge_racer" || CONFIG.mode === "webgl_three_runner";
      const MODE_USES_WEBGL_BG = CONFIG.mode === "webgl_three_runner" || MODE_IS_FORMULA_CIRCUIT || MODE_IS_FLIGHT_SIM;
      const MODE_IS_SHOOTER = CONFIG.mode === "arena_shooter" || CONFIG.mode === "topdown_roguelike_shooter";
      const MODE_IS_BRAWLER = CONFIG.mode === "duel_brawler" || CONFIG.mode === "comic_action_brawler_3d";
{runtime_balance_js}
{runtime_progression_js}
      const canvas = document.getElementById("game");
      const ctx = canvas.getContext("2d");
      const webglCanvas = document.createElement("canvas");
      webglCanvas.width = canvas.width;
      webglCanvas.height = canvas.height;
      const gl = MODE_USES_WEBGL_BG ? webglCanvas.getContext("webgl", {{ antialias: true }}) : null;
      const overlay = document.getElementById("overlay");
      const overlayText = document.getElementById("overlay-text");
      const scoreEl = document.getElementById("score");
      const timerEl = document.getElementById("timer");
      const hpEl = document.getElementById("hp");
      const keys = new Set();
      let audioCtx = null;
      let webglRuntime = null;

      const state = {{
        running: true,
        score: 0,
        hp: CONFIG.player_hp || 3,
        timeLeft: CONFIG.time_limit_sec || 60,
        lastTime: 0,
        player: {{ x: canvas.width * 0.5, y: canvas.height * 0.8, w: 36, h: 56, vx: 0, vy: 0, lane: 1 }},
        enemies: [],
        bullets: [],
        particles: [],
        spawnTimer: 0,
        enemyHp: CONFIG.enemy_hp || 1,
        attackCooldown: 0,
        dashCooldown: 0,
        run: {{
          level: 1,
          levelTimer: 0,
          waveTimer: 0,
          waveIndex: 0,
          spawnGraceSec: MODE_IS_FORMULA_CIRCUIT ? 3.4 : MODE_IS_3D_RUNNER || MODE_IS_FLIGHT_SIM ? 2.6 : 1.0,
          damageCooldown: 0,
          waveModifier: 1,
          minibossTimer: 0,
          difficultyScale: 1,
          combo: 0,
          comboTimer: 0,
          eliteTimer: 0,
          autoFireTimer: 0,
          shake: 0,
          fxPulse: 0,
          relics: [],
          upgrades: [],
          xp: 0,
          nextXp: 120,
          synergy: {{
            scoreMul: 1,
            spawnEase: 1,
            boostBonus: 0,
            damageBonus: 0,
            hpRegenTick: 0,
            active: [],
          }},
        }},
        racer: {{
          speed: 280,
          boostTimer: 0,
          laneFloat: 1,
          steerVelocity: 0,
          roadScroll: 0,
          roadCurve: 0,
          roadCurveTarget: 0,
          curveTimer: 0,
          distance: 0,
        }},
        formula: {{
          lap: 1,
          checkpoints: 0,
          checkpointsPerLap: 5,
          lapTimer: 0,
          bestLap: 999,
          sectorHeat: 0,
          overtakeChain: 0,
        }},
        topdown: {{
          orbitAngle: 0,
        }},
        flight: {{
          speed: 320,
          throttle: 0.58,
          pitch: 0,
          roll: 0,
          yaw: 0,
          bankVisual: 0,
          altitude: 0.5,
          stability: 1,
          checkpointCombo: 0,
        }},
      }};

      document.addEventListener("keydown", (e) => {{
        ensureAudio();
        keys.add(e.key);
        if (!state.running && (e.key === "r" || e.key === "R")) restartGame();
        if (MODE_IS_SHOOTER && e.code === "Space") {{
          e.preventDefault();
          fireBullet();
        }}
        if (MODE_IS_BRAWLER && e.code === "Space") {{
          e.preventDefault();
          performAttack();
        }}
      }});
      document.addEventListener("keyup", (e) => keys.delete(e.key));
      document.getElementById("restart-btn").addEventListener("click", restartGame);

      function resetState() {{
        state.running = true;
        state.score = 0;
        state.hp = CONFIG.player_hp || 3;
        state.timeLeft = CONFIG.time_limit_sec || 60;
        state.lastTime = 0;
        state.player = {{ x: canvas.width * 0.5, y: canvas.height * 0.8, w: 36, h: 56, vx: 0, vy: 0, lane: 1 }};
        state.enemies = [];
        state.bullets = [];
        state.particles = [];
        state.spawnTimer = 0;
        state.enemyHp = CONFIG.enemy_hp || 1;
        state.attackCooldown = 0;
        state.dashCooldown = 0;
        state.run = {{
          level: 1,
          levelTimer: 0,
          waveTimer: 0,
          waveIndex: 0,
          spawnGraceSec: MODE_IS_FORMULA_CIRCUIT ? 3.4 : MODE_IS_3D_RUNNER || MODE_IS_FLIGHT_SIM ? 2.6 : 1.0,
          damageCooldown: 0,
          waveModifier: 1,
          minibossTimer: 0,
          difficultyScale: 1,
          combo: 0,
          comboTimer: 0,
          eliteTimer: 0,
          autoFireTimer: 0,
          shake: 0,
          fxPulse: 0,
          relics: [],
          upgrades: [],
          xp: 0,
          nextXp: 120,
          synergy: {{
            scoreMul: 1,
            spawnEase: 1,
            boostBonus: 0,
            damageBonus: 0,
            hpRegenTick: 0,
            active: [],
          }},
        }};
        state.racer = {{
          speed: 280,
          boostTimer: 0,
          laneFloat: 1,
          steerVelocity: 0,
          roadScroll: 0,
          roadCurve: 0,
          roadCurveTarget: 0,
          curveTimer: 0,
          distance: 0,
        }};
        state.formula = {{
          lap: 1,
          checkpoints: 0,
          checkpointsPerLap: 5,
          lapTimer: 0,
          bestLap: 999,
          sectorHeat: 0,
          overtakeChain: 0,
        }};
        state.topdown = {{ orbitAngle: 0 }};
        state.flight = {{
          speed: 320,
          throttle: 0.58,
          pitch: 0,
          roll: 0,
          yaw: 0,
          bankVisual: 0,
          altitude: 0.5,
          stability: 1,
          checkpointCombo: 0,
        }};
        overlay.classList.remove("show");
        updateHud();
      }}

      {runtime_utility_functions_js}

      {runtime_progression_functions_js}

      {runtime_spawn_combat_functions_js}

      {runtime_update_function_js}

      {runtime_render_functions_js}

      {runtime_hud_functions_js}

      window.IISLeaderboard = {{ submitScore }};
      loadSprites();
      resetState();
      requestAnimationFrame(frame);
{RUNTIME_DOCUMENT_CLOSE}"""
