from __future__ import annotations

import json
import re
from typing import Any

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



def _infer_core_loop_type(*, keyword: str, title: str, genre: str) -> str:
    haystack = " ".join([keyword, title, genre]).casefold()
    if any(
        token in haystack
        for token in (
            "비행기",
            "비행 시뮬",
            "항공기",
            "flight sim",
            "flight simulator",
            "aircraft",
            "pilot",
            "cockpit",
            "dogfight",
        )
    ):
        return "flight_sim_3d"
    if any(
        token in haystack
        for token in (
            "webgl",
            "three.js",
            "threejs",
            "3d 레이싱",
            "3d 드리프트",
            "3d racing",
            "3d drift",
            "outrun",
            "아웃런",
            "voxel race",
        )
    ):
        return "webgl_three_runner"
    if any(
        token in haystack
        for token in (
            "탑뷰",
            "탑다운",
            "로그라이크",
            "roguelike",
            "top-down",
            "topdown",
            "dungeon",
            "판타지 슈팅",
        )
    ):
        return "topdown_roguelike_shooter"
    if any(
        token in haystack
        for token in ("코믹액션", "코믹 액션", "comic action", "beat em up", "3d 액션", "3d brawler")
    ):
        return "comic_action_brawler_3d"
    if any(token in haystack for token in ("레이싱", "레이스", "드리프트", "racing", "race", "car")):
        return "lane_dodge_racer"
    if any(token in haystack for token in ("슈팅", "사격", "총", "shooter", "shoot", "bullet")):
        return "arena_shooter"
    if any(token in haystack for token in ("격투", "파이터", "권투", "복싱", "스모", "fight", "fighting", "brawler", "brawl", "boxing", "sumo")):
        return "duel_brawler"
    return "arcade_generic"


def _detect_unsupported_scope(*, keyword: str, title: str, genre: str) -> str | None:
    haystack = " ".join([keyword, title, genre]).casefold()
    out_of_scope_map: dict[str, tuple[str, ...]] = {
        "open_world_scope": ("오픈월드", "open world", "sandbox world"),
        "mmo_scope": ("mmorpg", "mmo", "대규모 멀티플레이"),
        "metaverse_scope": ("메타버스", "metaverse"),
    }
    for reason, tokens in out_of_scope_map.items():
        if any(token in haystack for token in tokens):
            return reason
    return None


def _candidate_variation_hints(*, core_loop_type: str, candidate_count: int) -> list[str]:
    presets = {
        "flight_sim_3d": [
            "Variant A: atmospheric canyon training with strict throttle control and ring precision scoring.",
            "Variant B: high-altitude storm run with turbulence dodges and aggressive speed-management.",
            "Variant C: relay checkpoint sprint emphasizing roll control, near-miss bonuses, and route optimization.",
            "Variant D: endurance flight with escalating hazard density and careful stall-risk handling.",
            "Variant E: arcade sim blend prioritizing believable handling while keeping short-session replayability.",
        ],
        "webgl_three_runner": [
            "Variant A: ultra-fast neon sprint with aggressive traffic and boost-chain risk/reward.",
            "Variant B: technical drift line with sharper corner pressure and stricter recovery windows.",
            "Variant C: endurance outrun loop with escalating depth speed and combo streak scoring.",
            "Variant D: cinematic sunset highway run with moderate pace and dense late-wave threats.",
            "Variant E: arcade sprint with high readability, low randomness, and skill expression focus.",
        ],
        "topdown_roguelike_shooter": [
            "Variant A: high-mobility dash shooter with aggressive close-range swarms and fast loop resets.",
            "Variant B: methodical dungeon skirmish with elite enemy telegraphs and tactical spacing.",
            "Variant C: combo survival loop where kill streaks accelerate rewards and enemy pressure.",
            "Variant D: relic-run pacing with periodic power spikes and escalating arena threats.",
            "Variant E: precision rogue run emphasizing dodges, cooldown windows, and clutch recovery.",
        ],
        "comic_action_brawler_3d": [
            "Variant A: crowd-control brawler with punchy knockback and short combo chains.",
            "Variant B: heavier enemy archetypes with slower cadence and dramatic counter windows.",
            "Variant C: tempo-driven arena brawl with burst waves and score multipliers.",
            "Variant D: endurance showdown with mini-boss style spikes and survival pressure.",
            "Variant E: flashy arcade beat-em-up loop prioritizing readable impact feedback.",
        ],
        "lane_dodge_racer": [
            "Variant A: high-speed drift pressure with frequent boost pickups and tighter lane windows.",
            "Variant B: tactical pacing with wider lanes, fewer boosts, and heavier punishment on collisions.",
            "Variant C: rhythm-based overtakes with accelerating wave cadence and score combo emphasis.",
            "Variant D: endurance run with higher HP but late-stage aggressive traffic spikes.",
            "Variant E: risk-heavy sprint where boost chaining is powerful but failure is costly.",
        ],
        "arena_shooter": [
            "Variant A: dense bullet pressure with lower HP and fast dodge rhythm.",
            "Variant B: slower enemy waves with tankier enemies and positioning focus.",
            "Variant C: combo-oriented clear speed where aggressive play accelerates spawn pacing.",
            "Variant D: survival-heavy loop with recovery windows and burst threats.",
            "Variant E: precision loop with narrow safe zones and high-reward shots.",
        ],
        "duel_brawler": [
            "Variant A: close-range pressure with short cooldown attacks and reactive dodges.",
            "Variant B: spacing-focused duel with slower attacks and punishing counters.",
            "Variant C: tempo-brawler with wave bursts and combo scoring windows.",
            "Variant D: high-risk burst mode where attack openings are rare but decisive.",
            "Variant E: attrition duel with resilient enemies and clutch comeback flow.",
        ],
        "arcade_generic": [
            "Variant A: fast pressure loop with high movement speed and dense hazards.",
            "Variant B: strategic loop with clearer telegraphs and slower threat escalation.",
            "Variant C: combo loop with reward multipliers for consecutive clean actions.",
            "Variant D: survival endurance with stronger late-game pacing spikes.",
            "Variant E: balanced loop with readability-first but escalating risk windows.",
        ],
    }
    hints = list(presets.get(core_loop_type, presets["arcade_generic"]))
    if candidate_count <= len(hints):
        return hints[:candidate_count]

    extra_needed = candidate_count - len(hints)
    for idx in range(extra_needed):
        hints.append(f"Variant extra-{idx + 1}: preserve core loop but shift pacing and risk/reward curve.")
    return hints


def _candidate_composite_score(
    *,
    quality_score: int,
    gameplay_score: int,
    quality_ok: bool,
    gameplay_ok: bool,
) -> float:
    score = (quality_score * 0.4) + (gameplay_score * 0.6)
    if not quality_ok:
        score -= 15
    if not gameplay_ok:
        score -= 20
    return round(score, 2)


def _resolve_asset_pack(
    *,
    core_loop_type: str,
    palette: list[str],
) -> dict[str, str]:
    fallback_accent = str(palette[0]) if palette else "#22C55E"
    defaults = {
        "name": "neon_arcade",
        "bg_top": "#08122f",
        "bg_bottom": "#050915",
        "horizon": "#0f172a",
        "track": "#111827",
        "hud_primary": "#e2e8f0",
        "hud_muted": "#93c5fd",
        "player_primary": "#38bdf8",
        "player_secondary": "#0f172a",
        "enemy_primary": "#ef4444",
        "enemy_elite": "#f97316",
        "boost_color": "#22d3ee",
        "accent": fallback_accent,
        "particle": "#22c55e",
        "sfx_profile": "synth",
        "sprite_profile": "neon",
    }
    by_mode = {
        "flight_sim_3d": {
            "name": "flight_sim_neon",
            "bg_top": "#020716",
            "bg_bottom": "#030d22",
            "horizon": "#123248",
            "track": "#050c1d",
            "player_primary": "#34d399",
            "player_secondary": "#0f172a",
            "enemy_primary": "#f97316",
            "enemy_elite": "#ef4444",
            "boost_color": "#22d3ee",
            "particle": "#22d3ee",
            "sfx_profile": "flight_arcade",
            "sprite_profile": "flight",
        },
        "webgl_three_runner": {
            "name": "webgl_neon_highway",
            "bg_top": "#071125",
            "bg_bottom": "#020617",
            "horizon": "#13233f",
            "track": "#080f1d",
            "player_primary": "#38bdf8",
            "player_secondary": "#0f172a",
            "enemy_primary": "#fb7185",
            "enemy_elite": "#f97316",
            "boost_color": "#22d3ee",
            "particle": "#38bdf8",
            "sfx_profile": "synth_race",
            "sprite_profile": "neon",
        },
        "topdown_roguelike_shooter": {
            "name": "fantasy_topdown",
            "bg_top": "#10162c",
            "bg_bottom": "#090b16",
            "horizon": "#1a1532",
            "track": "#151427",
            "player_primary": "#60a5fa",
            "player_secondary": "#0f172a",
            "enemy_primary": "#f43f5e",
            "enemy_elite": "#f59e0b",
            "boost_color": "#a78bfa",
            "particle": "#c4b5fd",
            "sfx_profile": "fantasy_arcade",
            "sprite_profile": "fantasy",
        },
        "comic_action_brawler_3d": {
            "name": "comic_brawler",
            "bg_top": "#1a1c38",
            "bg_bottom": "#0d1024",
            "horizon": "#2a2f5e",
            "track": "#171a32",
            "player_primary": "#22d3ee",
            "player_secondary": "#0b1120",
            "enemy_primary": "#fb7185",
            "enemy_elite": "#f97316",
            "boost_color": "#facc15",
            "particle": "#fde047",
            "sfx_profile": "comic_arcade",
            "sprite_profile": "comic",
        },
        "lane_dodge_racer": {
            "name": "neon_racer",
            "bg_top": "#06112a",
            "bg_bottom": "#060a17",
            "horizon": "#111b34",
            "track": "#0f172a",
            "player_primary": "#38bdf8",
            "enemy_primary": "#ef4444",
            "boost_color": "#22d3ee",
            "particle": "#38bdf8",
            "sfx_profile": "synth_race",
            "sprite_profile": "neon",
        },
        "arena_shooter": {
            "name": "arena_assault",
            "bg_top": "#0a1226",
            "bg_bottom": "#060814",
            "horizon": "#101934",
            "track": "#111827",
            "player_primary": "#38bdf8",
            "enemy_primary": "#f43f5e",
            "boost_color": "#22d3ee",
            "particle": "#38bdf8",
            "sfx_profile": "pulse_shooter",
            "sprite_profile": "neon",
        },
        "duel_brawler": {
            "name": "duel_fighter",
            "bg_top": "#161c2f",
            "bg_bottom": "#0b1020",
            "horizon": "#1f2942",
            "track": "#151b2f",
            "player_primary": "#38bdf8",
            "enemy_primary": "#ef4444",
            "enemy_elite": "#f59e0b",
            "boost_color": "#22d3ee",
            "particle": "#f59e0b",
            "sfx_profile": "impact_duel",
            "sprite_profile": "comic",
        },
    }
    resolved = {**defaults, **by_mode.get(core_loop_type, {})}
    if len(palette) >= 2:
        resolved["bg_top"] = str(palette[1])
    if len(palette) >= 3:
        resolved["player_primary"] = str(palette[2])
    if len(palette) >= 4:
        resolved["enemy_primary"] = str(palette[3])
    resolved["accent"] = fallback_accent
    return resolved


def _build_hybrid_asset_bank(
    *,
    slug: str,
    core_loop_type: str,
    asset_pack: dict[str, str],
) -> tuple[list[dict[str, str]], dict[str, object]]:
    player_primary = str(asset_pack.get("player_primary", "#38bdf8"))
    player_secondary = str(asset_pack.get("player_secondary", "#0f172a"))
    enemy_primary = str(asset_pack.get("enemy_primary", "#ef4444"))
    enemy_elite = str(asset_pack.get("enemy_elite", "#f97316"))
    boost_color = str(asset_pack.get("boost_color", "#22d3ee"))
    hud_primary = str(asset_pack.get("hud_primary", "#e2e8f0"))

    svg_map = {
        "player.svg": (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96' viewBox='0 0 96 96'>"
            f"<rect width='96' height='96' fill='none'/>"
            f"<path d='M48 6 L84 66 L60 64 L60 90 L36 90 L36 64 L12 66 Z' fill='{player_primary}'/>"
            f"<rect x='42' y='34' width='12' height='24' rx='4' fill='{player_secondary}'/>"
            f"</svg>"
        ),
        "enemy.svg": (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96' viewBox='0 0 96 96'>"
            f"<rect width='96' height='96' fill='none'/>"
            f"<rect x='22' y='14' width='52' height='68' rx='10' fill='{enemy_primary}'/>"
            f"<rect x='30' y='24' width='36' height='20' rx='6' fill='{player_secondary}'/>"
            f"</svg>"
        ),
        "elite.svg": (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96' viewBox='0 0 96 96'>"
            f"<rect width='96' height='96' fill='none'/>"
            f"<polygon points='48,6 90,30 74,90 22,90 6,30' fill='{enemy_elite}'/>"
            f"<circle cx='48' cy='46' r='10' fill='{hud_primary}'/>"
            f"</svg>"
        ),
        "boost.svg": (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96' viewBox='0 0 96 96'>"
            f"<rect width='96' height='96' fill='none'/>"
            f"<polygon points='48,4 80,48 48,92 16,48' fill='{boost_color}'/>"
            f"<polygon points='48,18 66,48 48,78 30,48' fill='{hud_primary}' opacity='0.35'/>"
            f"</svg>"
        ),
        "ring.svg": (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='128' height='128' viewBox='0 0 128 128'>"
            f"<circle cx='64' cy='64' r='48' fill='none' stroke='{boost_color}' stroke-width='10'/>"
            f"<circle cx='64' cy='64' r='28' fill='none' stroke='{hud_primary}' stroke-width='3' opacity='0.7'/>"
            f"</svg>"
        ),
        "hazard.svg": (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96' viewBox='0 0 96 96'>"
            f"<polygon points='48,4 92,86 4,86' fill='{enemy_primary}'/>"
            f"<rect x='44' y='30' width='8' height='30' rx='4' fill='{hud_primary}'/>"
            f"<circle cx='48' cy='72' r='5' fill='{hud_primary}'/>"
            f"</svg>"
        ),
        "trail.svg": (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96' viewBox='0 0 96 96'>"
            f"<defs><linearGradient id='g' x1='0' y1='0' x2='0' y2='1'>"
            f"<stop offset='0%' stop-color='{boost_color}' stop-opacity='1'/>"
            f"<stop offset='100%' stop-color='{boost_color}' stop-opacity='0'/>"
            f"</linearGradient></defs>"
            f"<rect x='34' y='8' width='28' height='80' rx='14' fill='url(#g)'/>"
            f"</svg>"
        ),
    }

    image_keys = {
        "player": "player.svg",
        "enemy": "enemy.svg",
        "elite": "elite.svg",
        "boost": "boost.svg",
        "ring": "ring.svg",
        "hazard": "hazard.svg",
        "trail": "trail.svg",
    }
    artifact_files = [
        {
            "path": f"games/{slug}/{filename}",
            "content": content,
            "content_type": "image/svg+xml; charset=utf-8",
        }
        for filename, content in svg_map.items()
    ]
    asset_manifest: dict[str, object] = {
        "schema_version": 1,
        "pack_name": str(asset_pack.get("name", "hybrid-asset-pack")),
        "genre_engine": core_loop_type,
        "images": {key: f"./{filename}" for key, filename in image_keys.items()},
        "audio": {"profile": str(asset_pack.get("sfx_profile", "synth"))},
        "contract": {
            "min_image_assets": 5,
            "min_render_layers": 4,
            "min_animation_hooks": 3,
        },
    }
    return artifact_files, asset_manifest


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
    mode_config = {
        "flight_sim_3d": {
            "label": "Flight Sim 3D",
            "objective": "스로틀·피치·롤·요 제어로 항로 링을 통과하며 스톨/충돌을 피하고 최고 점수를 달성하세요.",
            "controls": "W/S 피치 · A/D 롤 · Q/E 요 · ↑/↓ 스로틀 · Shift 부스트 · R 재시작",
        },
        "webgl_three_runner": {
            "label": "WebGL 3D Runner",
            "objective": "WebGL 기반 네온 하이웨이에서 드리프트 라인과 부스트 체인을 유지하며 최장 생존 점수를 노리세요.",
            "controls": "← → 조향 / ↑ 가속 / ↓ 브레이크 / Shift 부스트 / R 재시작",
        },
        "topdown_roguelike_shooter": {
            "label": "Topdown Roguelike",
            "objective": "대시와 집중 사격으로 몬스터 웨이브를 돌파하고 생존 콤보를 이어가세요.",
            "controls": "← → ↑ ↓ 이동 / Space 발사 / Shift 대시 / R 재시작",
        },
        "comic_action_brawler_3d": {
            "label": "Comic 3D Brawler",
            "objective": "파도처럼 몰려오는 적을 연속 타격으로 제압하고 콤보 보너스를 유지하세요.",
            "controls": "← → ↑ ↓ 이동 / Space 공격 / Shift 회피 / R 재시작",
        },
        "lane_dodge_racer": {
            "label": "Racing",
            "objective": "코너를 읽고 드리프트 라인을 유지하며 장애물 회피+부스트 박스를 활용해 최고 점수를 달성하세요.",
            "controls": "← → 조향 / ↑ 가속 / ↓ 브레이크 / R 재시작",
        },
        "arena_shooter": {
            "label": "Shooter",
            "objective": "적을 피하며 발사체로 처치하고 생존 시간을 늘리세요.",
            "controls": "← → ↑ ↓ 이동 / Space 발사 / R 재시작",
        },
        "duel_brawler": {
            "label": "Fighter",
            "objective": "근접전으로 적의 체력을 먼저 깎아 승리하세요.",
            "controls": "← → ↑ ↓ 이동 / Space 공격 / R 재시작",
        },
        "arcade_generic": {
            "label": "Arcade",
            "objective": "움직이며 위험 요소를 피하고 점수를 올리세요.",
            "controls": "← → ↑ ↓ 이동 / R 재시작",
        },
    }[core_loop_type]

    config_dict = {
        "mode": core_loop_type,
        "title": title,
        "genre": genre,
        "slug": slug,
        "accentColor": accent_color,
        "viewportWidth": viewport_width,
        "viewportHeight": viewport_height,
        "safeAreaPadding": safe_area_padding,
        "minFontSizePx": min_font_size_px,
        "textOverflowPolicy": text_overflow_policy,
        "assetPack": asset_pack,
        "assetManifest": asset_manifest or {},
    }
    config_dict.update(game_config)
    config_json = json.dumps(config_dict, ensure_ascii=False)

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
        min-height: 100vh;
        display: grid;
        place-items: center;
        background:
          radial-gradient(800px 400px at 20% 0%, color-mix(in srgb, var(--accent) 35%, transparent), transparent 70%),
          radial-gradient(700px 380px at 90% 0%, #8b5cf622, transparent 68%),
          linear-gradient(180deg, var(--asset-bg-top), var(--asset-bg-bottom));
        color: var(--asset-hud-primary);
        font-family: Inter, system-ui, sans-serif;
        font-size: max(calc(var(--min-font-size) * 1px), 14px);
      }}
      main {{
        width: min(96vw, calc(var(--viewport-width) * 1px));
        min-height: min(92vh, calc(var(--viewport-height) * 1px));
        padding: calc(var(--safe-area-padding) * 1px);
        border: 1px solid #1f2937;
        border-radius: 16px;
        background: rgba(2, 6, 23, 0.8);
        display: grid;
        grid-template-rows: auto auto 1fr auto;
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
      .chip {{
        display: inline-flex;
        align-items: center;
        border: 1px solid {accent_color}55;
        color: #dbeafe;
        background: rgba(255,255,255,0.03);
        padding: 4px 10px;
        border-radius: 999px;
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
      }}
      canvas {{
        width: 100%;
        height: 100%;
        display: block;
        aspect-ratio: 16 / 9;
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
          <p class="sub overflow-guard">Genre: {genre} · Mode: {mode_config["label"]}</p>
        </div>
        <span class="chip overflow-guard">{slug}</span>
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
      <p class="hint overflow-guard">{mode_config["objective"]} / {mode_config["controls"]}</p>
      <!-- leaderboard contract exposed as window.IISLeaderboard.submitScore -->
    </main>
    <script>
      window.__iis_game_boot_ok = true;
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
      const MODE_IS_3D_RUNNER = CONFIG.mode === "lane_dodge_racer" || CONFIG.mode === "webgl_three_runner";
      const MODE_USES_WEBGL_BG = CONFIG.mode === "webgl_three_runner" || MODE_IS_FLIGHT_SIM;
      const MODE_IS_SHOOTER = CONFIG.mode === "arena_shooter" || CONFIG.mode === "topdown_roguelike_shooter";
      const MODE_IS_BRAWLER = CONFIG.mode === "duel_brawler" || CONFIG.mode === "comic_action_brawler_3d";
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
          difficultyScale: 1,
          combo: 0,
          comboTimer: 0,
          eliteTimer: 0,
          autoFireTimer: 0,
          shake: 0,
          relics: [],
          upgrades: [],
          xp: 0,
          nextXp: 120,
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
          difficultyScale: 1,
          combo: 0,
          comboTimer: 0,
          eliteTimer: 0,
          autoFireTimer: 0,
          shake: 0,
          relics: [],
          upgrades: [],
          xp: 0,
          nextXp: 120,
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

      function restartGame() {{ resetState(); }}

      function clamp(v, min, max) {{ return Math.max(min, Math.min(max, v)); }}
      function rand(min, max) {{ return Math.random() * (max - min) + min; }}
      function rectsOverlap(a, b) {{
        return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
      }}

      function loadSprites() {{
        for (const [key, path] of Object.entries(SPRITE_PATHS)) {{
          if (typeof path !== "string" || !path.trim()) continue;
          const img = new Image();
          img.decoding = "async";
          img.src = path;
          SPRITES[key] = img;
        }}
      }}

      function drawSprite(key, x, y, w, h, alpha = 1) {{
        const img = SPRITES[key];
        if (!img || !img.complete || img.naturalWidth <= 0 || img.naturalHeight <= 0) return false;
        ctx.save();
        ctx.globalAlpha = alpha;
        ctx.drawImage(img, x, y, w, h);
        ctx.restore();
        return true;
      }}

      function ensureAudio() {{
        if (audioCtx) return audioCtx;
        const Ctor = window.AudioContext || window.webkitAudioContext;
        if (!Ctor) return null;
        audioCtx = new Ctor();
        return audioCtx;
      }}

      function playSfx(kind) {{
        const ac = ensureAudio();
        if (!ac) return;
        const osc = ac.createOscillator();
        const gain = ac.createGain();
        osc.connect(gain);
        gain.connect(ac.destination);
        const now = ac.currentTime;
        const profile = ASSET.sfx_profile || "synth";
        const base = profile.includes("fantasy") ? 240 : profile.includes("comic") ? 180 : 220;
        const freqMap = {{
          shoot: base + 120,
          hit: base + 60,
          damage: base - 70,
          boost: base + 220,
          levelup: base + 320,
          relic: base + 260,
          gameover: base - 120,
        }};
        const freq = freqMap[kind] || base;
        osc.type = kind === "damage" ? "sawtooth" : kind === "boost" ? "triangle" : "square";
        osc.frequency.setValueAtTime(freq, now);
        osc.frequency.exponentialRampToValueAtTime(Math.max(80, freq * 0.62), now + 0.12);
        gain.gain.setValueAtTime(0.0001, now);
        gain.gain.exponentialRampToValueAtTime(0.05, now + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.14);
        osc.start(now);
        osc.stop(now + 0.16);
      }}

      function ensureWebglRuntime() {{
        if (!gl || webglRuntime) return webglRuntime;
        const vert = `
          attribute vec2 aPos;
          void main() {{
            gl_Position = vec4(aPos, 0.0, 1.0);
          }}
        `;
        const frag = `
          precision mediump float;
          uniform vec2 uRes;
          uniform float uTime;
          uniform float uSpeed;
          uniform vec3 uAccent;
          void main() {{
            vec2 uv = (gl_FragCoord.xy / uRes.xy) * 2.0 - 1.0;
            uv.x *= uRes.x / uRes.y;
            float depth = max(0.01, 1.0 - (uv.y + 1.0) * 0.5);
            float lane = abs(fract((uv.x / depth + 0.5) * 0.5) - 0.5);
            float laneLine = smoothstep(0.06, 0.0, lane);
            float speedFlow = fract((uTime * (0.35 + uSpeed * 0.0008)) + depth * 4.0);
            float grid = smoothstep(0.05, 0.0, abs(fract(speedFlow) - 0.5));
            vec3 bg = mix(vec3(0.03,0.06,0.14), vec3(0.01,0.03,0.08), depth);
            vec3 road = mix(vec3(0.04,0.06,0.11), vec3(0.08,0.11,0.18), (uv.y + 1.0) * 0.5);
            vec3 color = mix(bg, road, smoothstep(-0.1, -0.9, uv.y));
            color += uAccent * laneLine * 0.28;
            color += vec3(0.15,0.2,0.35) * grid * 0.22;
            gl_FragColor = vec4(color, 1.0);
          }}
        `;
        const compile = (type, src) => {{
          const shader = gl.createShader(type);
          gl.shaderSource(shader, src);
          gl.compileShader(shader);
          if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) return null;
          return shader;
        }};
        const vs = compile(gl.VERTEX_SHADER, vert);
        const fs = compile(gl.FRAGMENT_SHADER, frag);
        if (!vs || !fs) return null;
        const program = gl.createProgram();
        gl.attachShader(program, vs);
        gl.attachShader(program, fs);
        gl.linkProgram(program);
        if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return null;
        const buffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 1,-1, -1,1, 1,1]), gl.STATIC_DRAW);
        const aPos = gl.getAttribLocation(program, "aPos");
        const uRes = gl.getUniformLocation(program, "uRes");
        const uTime = gl.getUniformLocation(program, "uTime");
        const uSpeed = gl.getUniformLocation(program, "uSpeed");
        const uAccent = gl.getUniformLocation(program, "uAccent");
        webglRuntime = {{ program, buffer, aPos, uRes, uTime, uSpeed, uAccent, t: 0 }};
        return webglRuntime;
      }}

      function renderWebglBackground(dt) {{
        const rt = ensureWebglRuntime();
        if (!rt) return false;
        rt.t += dt;
        const hex = (ASSET.boost_color || "#22d3ee").replace("#", "");
        const r = parseInt(hex.slice(0, 2), 16) / 255 || 0.13;
        const g = parseInt(hex.slice(2, 4), 16) / 255 || 0.83;
        const b = parseInt(hex.slice(4, 6), 16) / 255 || 0.93;
        gl.viewport(0, 0, webglCanvas.width, webglCanvas.height);
        gl.useProgram(rt.program);
        gl.bindBuffer(gl.ARRAY_BUFFER, rt.buffer);
        gl.enableVertexAttribArray(rt.aPos);
        gl.vertexAttribPointer(rt.aPos, 2, gl.FLOAT, false, 0, 0);
        gl.uniform2f(rt.uRes, webglCanvas.width, webglCanvas.height);
        gl.uniform1f(rt.uTime, rt.t);
        gl.uniform1f(rt.uSpeed, state.racer.speed || 260);
        gl.uniform3f(rt.uAccent, r, g, b);
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
        ctx.drawImage(webglCanvas, 0, 0, canvas.width, canvas.height);
        return true;
      }}

      function grantXp(amount) {{
        state.run.xp += amount;
        while (state.run.xp >= state.run.nextXp) {{
          state.run.xp -= state.run.nextXp;
          state.run.nextXp = Math.floor(state.run.nextXp * 1.2);
          const picks = ["attack_speed", "mobility", "damage", "sustain", "burst"];
          const pick = picks[Math.floor(Math.random() * picks.length)];
          state.run.upgrades.push(pick);
          if (pick === "attack_speed") CONFIG.player_attack_cooldown = Math.max(0.16, (CONFIG.player_attack_cooldown || 0.5) * 0.88);
          if (pick === "mobility") CONFIG.player_speed = Math.min(460, (CONFIG.player_speed || 240) + 20);
          if (pick === "damage") CONFIG.base_score_value = Math.min(220, (CONFIG.base_score_value || 10) + 5);
          if (pick === "sustain") state.hp = Math.min((CONFIG.player_hp || 3) + 2, state.hp + 1);
          if (pick === "burst") state.run.combo = Math.min(20, state.run.combo + 1.8);
          state.run.relics.push(`Relic-${{pick}}-${{state.run.level}}`);
          playSfx("levelup");
          playSfx("relic");
        }}
      }}

      function stepProgression(dt) {{
        state.run.levelTimer += dt;
        state.run.comboTimer = Math.max(0, state.run.comboTimer - dt);
        state.run.shake = Math.max(0, state.run.shake - dt * 1.8);
        state.run.eliteTimer += dt;
        if (state.run.comboTimer <= 0) state.run.combo = Math.max(0, state.run.combo - dt * 2.2);
        if (state.run.levelTimer >= 12) {{
          state.run.levelTimer = 0;
          state.run.level += 1;
          state.run.difficultyScale = 1 + (state.run.level - 1) * 0.11;
          burst(canvas.width * 0.5, 80, ASSET.particle, 20);
          grantXp(30 + state.run.level * 6);
          playSfx("levelup");
        }}
      }}

      function addCombo(points) {{
        state.run.combo = clamp(state.run.combo + points, 0, 20);
        state.run.comboTimer = 2.3;
      }}

      function consumeDash() {{
        if (state.dashCooldown > 0) return false;
        state.dashCooldown = 1.35;
        state.run.shake = 0.2;
        return true;
      }}

      function spawnEnemy() {{
        const spdMin = CONFIG.enemy_speed_min || 100;
        const spdMax = CONFIG.enemy_speed_max || 220;
        const difficultyScale = Math.max(1, state.run.difficultyScale || 1);
        if (MODE_IS_FLIGHT_SIM) {{
          const kindRoll = Math.random();
          const kind = kindRoll < 0.2 ? "ring" : kindRoll < 0.82 ? "hazard" : "turbulence";
          state.enemies.push({{
            kind,
            x: rand(canvas.width * 0.2, canvas.width * 0.8),
            y: rand(canvas.height * 0.22, canvas.height * 0.72),
            z: rand(0.04, 0.22),
            speedMul: rand(0.78, 1.22) * (0.9 + difficultyScale * 0.18),
            w: kind === "ring" ? 56 : kind === "turbulence" ? 72 : 42,
            h: kind === "ring" ? 56 : kind === "turbulence" ? 72 : 44,
          }});
          return;
        }}
        if (MODE_IS_3D_RUNNER) {{
          const lane = Math.floor(Math.random() * 3) - 1;
          const boostRate = CONFIG.mode === "webgl_three_runner" ? 0.24 : 0.2;
          const kind = Math.random() < boostRate ? "boost" : "obstacle";
          state.enemies.push({{
            lane,
            z: rand(0.04, 0.14),
            speedMul: rand(0.86, 1.24) * (0.9 + difficultyScale * 0.15),
            kind,
            w: kind === "boost" ? 24 : 34,
            h: kind === "boost" ? 24 : 56,
          }});
          return;
        }}
        if (CONFIG.mode === "topdown_roguelike_shooter") {{
          const edge = Math.floor(rand(0, 4));
          const enemyKindRoll = Math.random();
          const enemyKind = enemyKindRoll < 0.14 ? "elite" : enemyKindRoll < 0.36 ? "charger" : "grunt";
          let ex = 0;
          let ey = 0;
          if (edge === 0) {{ ex = rand(20, canvas.width - 20); ey = -30; }}
          if (edge === 1) {{ ex = canvas.width + 30; ey = rand(30, canvas.height - 30); }}
          if (edge === 2) {{ ex = rand(20, canvas.width - 20); ey = canvas.height + 30; }}
          if (edge === 3) {{ ex = -30; ey = rand(30, canvas.height - 30); }}
          state.enemies.push({{
            x: ex,
            y: ey,
            w: enemyKind === "elite" ? 42 : 30,
            h: enemyKind === "elite" ? 42 : 30,
            speed: rand(spdMin, spdMax) * (enemyKind === "charger" ? 1.24 : 1.0) * (0.84 + difficultyScale * 0.22),
            hp: enemyKind === "elite" ? Math.max(2, Math.floor((CONFIG.enemy_hp || 1) + state.run.level * 0.35)) : (CONFIG.enemy_hp || 1),
            kind: enemyKind,
          }});
          return;
        }}
        if (CONFIG.mode === "arena_shooter") {{
          state.enemies.push({{
            x: rand(40, canvas.width - 80),
            y: -40,
            w: 30,
            h: 30,
            speed: rand(spdMin, spdMax) * (0.84 + difficultyScale * 0.2),
            hp: CONFIG.enemy_hp || 1,
            kind: Math.random() < 0.18 ? "elite" : "grunt",
          }});
          return;
        }}
        if (MODE_IS_BRAWLER) {{
          const maxWave = CONFIG.mode === "comic_action_brawler_3d" ? 3 : 1;
          if (state.enemies.length < maxWave) {{
            const spawnX = rand(canvas.width * 0.25, canvas.width * 0.82);
            const spawnY = rand(canvas.height * 0.2, canvas.height * 0.72);
            state.enemies.push({{
              x: spawnX,
              y: spawnY,
              w: CONFIG.mode === "comic_action_brawler_3d" ? 42 : 46,
              h: CONFIG.mode === "comic_action_brawler_3d" ? 64 : 72,
              hp: Math.max(1, Math.floor(state.enemyHp * (CONFIG.mode === "comic_action_brawler_3d" ? 0.55 : 1))),
              speed: spdMin * (0.6 + difficultyScale * 0.26),
              kind: Math.random() < 0.22 ? "elite" : "grunt",
            }});
          }}
          return;
        }}
        state.enemies.push({{
          x: rand(40, canvas.width - 80),
          y: -40,
          w: 26,
          h: 26,
          speed: rand(spdMin, spdMax) * (0.84 + difficultyScale * 0.2),
          kind: "grunt",
        }});
      }}

      function fireBullet() {{
        if (!state.running) return;
        playSfx("shoot");
        const bulletSpeed = CONFIG.mode === "topdown_roguelike_shooter" ? 620 : 520;
        const bulletW = CONFIG.mode === "topdown_roguelike_shooter" ? 7 : 6;
        const bulletH = CONFIG.mode === "topdown_roguelike_shooter" ? 18 : 16;
        state.bullets.push({{
          x: state.player.x + state.player.w * 0.5 - bulletW * 0.5,
          y: state.player.y - 2,
          w: bulletW,
          h: bulletH,
          speed: bulletSpeed,
          kind: CONFIG.mode === "topdown_roguelike_shooter" ? "arcane" : "basic",
        }});
      }}

      function performAttack() {{
        if (!state.running || state.attackCooldown > 0) return;
        state.attackCooldown = CONFIG.player_attack_cooldown || (CONFIG.mode === "comic_action_brawler_3d" ? 0.34 : 0.5);
        let hitCount = 0;
        for (const enemy of state.enemies) {{
          const dx = (enemy.x + enemy.w / 2) - (state.player.x + state.player.w / 2);
          const dy = (enemy.y + enemy.h / 2) - (state.player.y + state.player.h / 2);
          const dist = Math.hypot(dx, dy);
          if (dist > 96) continue;
          enemy.hp -= 1;
          hitCount += 1;
          playSfx("hit");
          state.score += CONFIG.mode === "comic_action_brawler_3d" ? 62 : 45;
          burst(enemy.x + enemy.w / 2, enemy.y + enemy.h / 2, ASSET.enemy_elite, 10);
          if (enemy.hp <= 0) {{
            state.score += 170;
            addCombo(1.4);
            grantXp(18);
            burst(enemy.x + enemy.w / 2, enemy.y + enemy.h / 2, ASSET.particle, 18);
          }}
        }}
        if (hitCount <= 0) return;
        state.run.shake = Math.max(state.run.shake, 0.12);
        state.enemies = state.enemies.filter((enemy) => enemy.hp > 0);
        if (state.enemies.length === 0) {{
          state.enemyHp += CONFIG.mode === "comic_action_brawler_3d" ? 1 : 3;
        }}
      }}

      function burst(x, y, color, count) {{
        for (let i = 0; i < count; i++) {{
          state.particles.push({{
            x, y, life: rand(0.2, 0.6), t: 0, color,
            vx: rand(-160, 160), vy: rand(-160, 160)
          }});
        }}
      }}

      function update(dt) {{
        if (!state.running) return;
        state.timeLeft = Math.max(0, state.timeLeft - dt);
        state.spawnTimer += dt;
        state.attackCooldown = Math.max(0, state.attackCooldown - dt);
        state.dashCooldown = Math.max(0, state.dashCooldown - dt);
        stepProgression(dt);
        const spawnRate = (CONFIG.enemy_spawn_rate || 1.0) / clamp(state.run.difficultyScale, 1, 2.8);

        if (MODE_IS_FLIGHT_SIM) {{
          const pitchInput = (keys.has("w") || keys.has("ArrowUp") ? -1 : 0) + (keys.has("s") || keys.has("ArrowDown") ? 1 : 0);
          const rollInput = (keys.has("d") ? 1 : 0) - (keys.has("a") ? 1 : 0);
          const yawInput = (keys.has("e") ? 1 : 0) - (keys.has("q") ? 1 : 0);
          const throttleInput = (keys.has("ArrowUp") ? 1 : 0) - (keys.has("ArrowDown") ? 1 : 0);
          state.flight.throttle = clamp(state.flight.throttle + throttleInput * dt * 0.55, 0.18, 1);
          state.flight.pitch = clamp(state.flight.pitch + pitchInput * dt * 2.4, -1, 1);
          state.flight.roll = clamp(state.flight.roll + rollInput * dt * 2.6, -1, 1);
          state.flight.yaw = clamp(state.flight.yaw + yawInput * dt * 1.8, -1, 1);
          state.flight.pitch *= (1 - Math.min(0.7, dt * 2.8));
          state.flight.roll *= (1 - Math.min(0.7, dt * 3.2));
          state.flight.yaw *= (1 - Math.min(0.7, dt * 3.5));
          if (keys.has("Shift") && consumeDash()) {{
            state.flight.throttle = Math.min(1, state.flight.throttle + 0.22);
            state.racer.boostTimer = Math.max(state.racer.boostTimer, 1.35);
            playSfx("boost");
          }}

          const targetSpeed = 180 + state.flight.throttle * 420;
          state.flight.speed += (targetSpeed - state.flight.speed) * Math.min(1, dt * 2.1);
          if (state.racer.boostTimer > 0) {{
            state.racer.boostTimer = Math.max(0, state.racer.boostTimer - dt);
            state.flight.speed = Math.max(state.flight.speed, 430);
          }}
          state.racer.speed = state.flight.speed;
          state.racer.roadScroll += dt * state.flight.speed * 0.07;
          state.racer.distance += dt * state.flight.speed;

          const lateral = (state.flight.roll * 0.92) + (state.flight.yaw * 0.52);
          const vertical = state.flight.pitch * 1.1;
          state.player.x = clamp(state.player.x + lateral * dt * 340, canvas.width * 0.12, canvas.width * 0.88 - state.player.w);
          state.player.y = clamp(state.player.y + vertical * dt * 240, canvas.height * 0.35, canvas.height * 0.86);
          state.flight.altitude = 1 - clamp((state.player.y - canvas.height * 0.35) / (canvas.height * 0.51), 0, 1);
          state.flight.bankVisual += (state.flight.roll - state.flight.bankVisual) * Math.min(1, dt * 7.5);
          state.flight.stability = clamp(1 - Math.abs(state.flight.pitch) * 0.35 - Math.abs(state.flight.roll) * 0.32, 0.2, 1.1);

          const adaptiveSpawnRate = clamp(spawnRate * (260 / state.flight.speed), 0.2, 0.88);
          if (state.spawnTimer > adaptiveSpawnRate) {{
            state.spawnTimer = 0;
            spawnEnemy();
          }}

          const playerCx = state.player.x + state.player.w * 0.5;
          const playerCy = state.player.y + state.player.h * 0.5;
          for (const e of state.enemies) {{
            e.z += dt * (state.flight.speed / 310) * (e.speedMul || 1);
            const depth = clamp(e.z, 0.03, 1.2);
            const depthScale = 0.28 + depth * 1.35;
            const ex = e.x + (state.flight.yaw * -120) * (1 - depth);
            const ey = e.y + (state.flight.pitch * 80) * (1 - depth);
            e.screenW = (e.w || 32) * depthScale;
            e.screenH = (e.h || 32) * depthScale;
            e.screenX = ex - e.screenW * 0.5;
            e.screenY = ey - e.screenH * 0.5;
            if (depth > 0.76 && depth < 1.05) {{
              const dist = Math.hypot((e.screenX + e.screenW * 0.5) - playerCx, (e.screenY + e.screenH * 0.5) - playerCy);
              const hitRadius = Math.max(24, (e.screenW + e.screenH) * 0.24);
              if (dist < hitRadius) {{
                if (e.kind === "ring") {{
                  const scoreGain = (CONFIG.base_score_value || 10) * (3.2 + state.flight.checkpointCombo * 0.14);
                  state.score += scoreGain;
                  state.flight.checkpointCombo += 1;
                  addCombo(1.2);
                  grantXp(14 + Math.min(18, state.flight.checkpointCombo));
                  playSfx("boost");
                  burst(playerCx, playerCy - 10, ASSET.boost_color, 18);
                }} else if (e.kind === "turbulence") {{
                  state.run.shake = Math.max(state.run.shake, 0.26);
                  state.flight.stability = Math.max(0.28, state.flight.stability - 0.2);
                  state.score = Math.max(0, state.score - 8);
                  playSfx("damage");
                  burst(playerCx, playerCy, ASSET.enemy_primary, 12);
                }} else {{
                  state.hp -= 1;
                  state.flight.checkpointCombo = 0;
                  state.run.combo = 0;
                  state.score = Math.max(0, state.score - 22);
                  playSfx("damage");
                  burst(playerCx, playerCy, ASSET.enemy_primary, 16);
                }}
                e.z = 2;
              }}
            }}
          }}

          state.enemies = state.enemies.filter((e) => {{
            const passed = e.z > 1.08;
            if (passed && e.kind === "ring") {{
              state.flight.checkpointCombo = Math.max(0, state.flight.checkpointCombo - 1);
            }} else if (passed && e.kind === "hazard") {{
              state.score += (CONFIG.base_score_value || 10) * (1.1 + state.run.combo * 0.04);
              addCombo(0.28);
              grantXp(5);
            }}
            return !passed;
          }});

          state.score += dt * (state.flight.speed * 0.048) * (0.7 + state.flight.altitude * 0.6) * (1 + state.run.combo * 0.026);
        }} else if (MODE_IS_3D_RUNNER) {{
          const left = keys.has("ArrowLeft") || keys.has("a");
          const right = keys.has("ArrowRight") || keys.has("d");
          const accel = keys.has("ArrowUp") || keys.has("w");
          const brake = keys.has("ArrowDown") || keys.has("s");

          const steerDir = (right ? 1 : 0) - (left ? 1 : 0);
          state.racer.steerVelocity += steerDir * dt * 9.2;
          state.racer.steerVelocity *= (1 - Math.min(0.82, dt * 7.4));
          if (!left && !right) {{
            state.racer.steerVelocity *= (1 - Math.min(0.88, dt * 9.8));
          }}
          state.racer.laneFloat = clamp(state.racer.laneFloat + state.racer.steerVelocity * dt, 0, 2);
          state.player.lane = state.racer.laneFloat;

          const accelRate = 240;
          const brakeRate = 280;
          const drag = 120;
          if (accel) state.racer.speed += accelRate * dt;
          if (brake) state.racer.speed -= brakeRate * dt;
          if (!accel && !brake) state.racer.speed -= drag * dt;
          state.racer.speed = clamp(state.racer.speed, 180, 520);

          state.racer.curveTimer -= dt;
          if (state.racer.curveTimer <= 0) {{
            state.racer.curveTimer = rand(1.0, 2.4);
            state.racer.roadCurveTarget = rand(-0.38, 0.38);
          }}
          state.racer.roadCurve += (state.racer.roadCurveTarget - state.racer.roadCurve) * Math.min(1, dt * 1.4);
          state.racer.roadScroll += dt * state.racer.speed * 0.055;
          state.racer.distance += dt * state.racer.speed;

          if (state.racer.boostTimer > 0) {{
            state.racer.boostTimer = Math.max(0, state.racer.boostTimer - dt);
            state.racer.speed = Math.max(state.racer.speed, 390);
          }}
          if (CONFIG.mode === "webgl_three_runner" && keys.has("Shift") && consumeDash()) {{
            state.racer.boostTimer = Math.max(state.racer.boostTimer, 1.4);
            state.racer.speed = Math.min(560, state.racer.speed + 70);
            playSfx("boost");
          }}

          const curvePx = state.racer.roadCurve * canvas.width * 0.16;
          const laneNormalized = state.player.lane - 1;
          const laneX = canvas.width * 0.5 + curvePx * 0.15 + laneNormalized * (canvas.width * 0.22);
          state.player.x += (laneX - state.player.w / 2 - state.player.x) * Math.min(1, dt * 12);
          state.player.y = canvas.height * 0.78;

          const adaptiveSpawnRate = clamp(spawnRate * (260 / state.racer.speed), 0.22, 1.1);
          if (state.spawnTimer > adaptiveSpawnRate) {{
            state.spawnTimer = 0;
            spawnEnemy();
          }}

          const playerLaneNorm = state.player.lane - 1;
          for (const e of state.enemies) {{
            e.z += dt * (state.racer.speed / 300) * (e.speedMul || 1);
            if (e.z > 0.77 && e.z < 1.02) {{
              const laneDiff = Math.abs((e.lane || 0) - playerLaneNorm);
              if (laneDiff < 0.35) {{
                if (e.kind === "boost") {{
                  state.racer.boostTimer = Math.max(state.racer.boostTimer, 2.0);
                  state.score += 30;
                  addCombo(0.8);
                  grantXp(10);
                  playSfx("boost");
                  burst(state.player.x + state.player.w / 2, state.player.y + 4, ASSET.boost_color, 14);
                }} else {{
                  state.hp -= 1;
                  state.run.combo = 0;
                  state.score = Math.max(0, state.score - 15);
                  playSfx("damage");
                  burst(state.player.x + state.player.w / 2, state.player.y + state.player.h / 2, ASSET.enemy_primary, 14);
                }}
                e.z = 2;
              }}
            }}
          }}

          state.enemies = state.enemies.filter((e) => {{
            const passed = e.z > 1.05;
            if (passed && e.kind !== "boost") {{
              state.score += (CONFIG.base_score_value || 10) * (1 + state.run.combo * 0.06);
              addCombo(0.3);
              grantXp(4);
            }}
            return !passed;
          }});

          state.score += dt * (state.racer.speed * 0.045) * (1 + state.run.combo * 0.03);
        }} else if (CONFIG.mode === "topdown_roguelike_shooter") {{
          const speed = (CONFIG.player_speed || 255) * (keys.has("Shift") && consumeDash() ? 1.95 : 1);
          state.player.vx = (keys.has("ArrowRight") || keys.has("d") ? 1 : 0) - (keys.has("ArrowLeft") || keys.has("a") ? 1 : 0);
          state.player.vy = (keys.has("ArrowDown") || keys.has("s") ? 1 : 0) - (keys.has("ArrowUp") || keys.has("w") ? 1 : 0);
          state.player.x = clamp(state.player.x + state.player.vx * speed * dt, 20, canvas.width - state.player.w - 20);
          state.player.y = clamp(state.player.y + state.player.vy * speed * dt, 60, canvas.height - state.player.h - 20);
          state.topdown.orbitAngle += dt * 1.8;

          if (state.spawnTimer > clamp(spawnRate * 0.82, 0.14, 0.9)) {{
            state.spawnTimer = 0;
            spawnEnemy();
          }}
          state.run.autoFireTimer += dt;
          if (state.run.autoFireTimer > 0.26) {{
            state.run.autoFireTimer = 0;
            fireBullet();
          }}

          for (const e of state.enemies) {{
            const dx = (state.player.x + state.player.w * 0.5) - (e.x + e.w * 0.5);
            const dy = (state.player.y + state.player.h * 0.5) - (e.y + e.h * 0.5);
            const len = Math.max(1, Math.hypot(dx, dy));
            const approach = e.kind === "charger" ? 1.2 : 0.92;
            e.x += (dx / len) * e.speed * dt * approach;
            e.y += (dy / len) * e.speed * dt;
            if (rectsOverlap(state.player, e)) {{
              state.hp -= e.kind === "elite" ? 2 : 1;
              state.run.combo = 0;
              state.run.shake = 0.22;
              playSfx("damage");
              burst(state.player.x + state.player.w / 2, state.player.y + state.player.h / 2, ASSET.enemy_primary, 14);
              e.hp = 0;
            }}
          }}

          for (const b of state.bullets) b.y -= b.speed * dt;
          for (const b of state.bullets) {{
            for (const e of state.enemies) {{
              if (e.hp > 0 && rectsOverlap(b, e)) {{
                e.hp -= 1;
                b.y = -999;
                state.score += (CONFIG.base_score_value || 10) * (e.kind === "elite" ? 2.2 : 1);
                addCombo(e.kind === "elite" ? 1.6 : 0.8);
                playSfx("hit");
                burst(e.x + e.w / 2, e.y + e.h / 2, ASSET.boost_color, e.kind === "elite" ? 12 : 8);
                if (e.hp <= 0) grantXp(e.kind === "elite" ? 24 : 12);
              }}
            }}
          }}

          state.enemies = state.enemies.filter((e) => e.hp > 0);
          state.bullets = state.bullets.filter((b) => b.y > -40);
          state.score += dt * 14 * (1 + state.run.combo * 0.04);
        }} else if (CONFIG.mode === "arena_shooter") {{
          const speed = CONFIG.player_speed || 260;
          state.player.vx = (keys.has("ArrowRight") || keys.has("d") ? 1 : 0) - (keys.has("ArrowLeft") || keys.has("a") ? 1 : 0);
          state.player.vy = (keys.has("ArrowDown") || keys.has("s") ? 1 : 0) - (keys.has("ArrowUp") || keys.has("w") ? 1 : 0);
          state.player.x = clamp(state.player.x + state.player.vx * speed * dt, 20, canvas.width - state.player.w - 20);
          state.player.y = clamp(state.player.y + state.player.vy * speed * dt, 60, canvas.height - state.player.h - 20);
          if (state.spawnTimer > clamp(spawnRate, 0.18, 1.15)) {{ state.spawnTimer = 0; spawnEnemy(); }}
          for (const e of state.enemies) {{
            e.y += e.speed * dt;
            if (e.y > canvas.height + 40) {{
              e.y = canvas.height + 999;
              state.hp -= 1;
              state.run.combo = 0;
              playSfx("damage");
            }}
            if (rectsOverlap(state.player, e)) {{
              e.y = canvas.height + 999;
              state.hp -= 1;
              state.run.combo = 0;
              playSfx("damage");
              burst(state.player.x + state.player.w/2, state.player.y + state.player.h/2, ASSET.enemy_primary, 14);
            }}
          }}
          for (const b of state.bullets) b.y -= b.speed * dt;
          for (const b of state.bullets) {{
            for (const e of state.enemies) {{
              if (e.y < canvas.height + 500 && rectsOverlap(b, e)) {{
                e.y = canvas.height + 999;
                b.y = -999;
                const scoreGain = (CONFIG.base_score_value || 10) * (e.kind === "elite" ? 2.0 : 1);
                state.score += scoreGain * (1 + state.run.combo * 0.04);
                addCombo(e.kind === "elite" ? 1.2 : 0.7);
                playSfx("hit");
                grantXp(e.kind === "elite" ? 18 : 8);
                burst(e.x + e.w/2, e.y + e.h/2, ASSET.boost_color, e.kind === "elite" ? 10 : 8);
              }}
            }}
          }}
          state.enemies = state.enemies.filter((e) => e.y < canvas.height + 120);
          state.bullets = state.bullets.filter((b) => b.y > -40);
          state.score += dt * 8 * (1 + state.run.combo * 0.03);
        }} else if (MODE_IS_BRAWLER) {{
          const baseSpeed = CONFIG.player_speed || 220;
          const speed = keys.has("Shift") && consumeDash() ? baseSpeed * 1.8 : baseSpeed;
          state.player.vx = (keys.has("ArrowRight") || keys.has("d") ? 1 : 0) - (keys.has("ArrowLeft") || keys.has("a") ? 1 : 0);
          state.player.vy = (keys.has("ArrowDown") || keys.has("s") ? 1 : 0) - (keys.has("ArrowUp") || keys.has("w") ? 1 : 0);
          state.player.x = clamp(state.player.x + state.player.vx * speed * dt, 20, canvas.width - state.player.w - 20);
          state.player.y = clamp(state.player.y + state.player.vy * speed * dt, 60, canvas.height - state.player.h - 20);
          if (state.spawnTimer > clamp(spawnRate * (CONFIG.mode === "comic_action_brawler_3d" ? 0.72 : 1.0), 0.24, 1.1) || state.enemies.length === 0) {{
            state.spawnTimer = 0;
            spawnEnemy();
          }}
          for (const e of state.enemies) {{
            const dx = state.player.x - e.x;
            const dy = state.player.y - e.y;
            const len = Math.max(1, Math.hypot(dx, dy));
            e.x += (dx / len) * e.speed * dt;
            e.y += (dy / len) * e.speed * dt;
            if (rectsOverlap(state.player, e)) {{
              state.hp -= e.kind === "elite" ? 2 : 1;
              state.run.combo = 0;
              playSfx("damage");
              state.player.x = clamp(state.player.x - (dx / len) * 35, 20, canvas.width - state.player.w - 20);
              state.player.y = clamp(state.player.y - (dy / len) * 35, 60, canvas.height - state.player.h - 20);
              burst(state.player.x + state.player.w/2, state.player.y + state.player.h/2, ASSET.enemy_primary, 10);
            }}
          }}
          state.score += dt * (CONFIG.mode === "comic_action_brawler_3d" ? 12 : 8) * (1 + state.run.combo * 0.03);
        }} else {{
          const speed = 240;
          state.player.vx = (keys.has("ArrowRight") ? 1 : 0) - (keys.has("ArrowLeft") ? 1 : 0);
          state.player.vy = (keys.has("ArrowDown") ? 1 : 0) - (keys.has("ArrowUp") ? 1 : 0);
          state.player.x = clamp(state.player.x + state.player.vx * speed * dt, 20, canvas.width - state.player.w - 20);
          state.player.y = clamp(state.player.y + state.player.vy * speed * dt, 60, canvas.height - state.player.h - 20);
          if (state.spawnTimer > 0.6) {{ state.spawnTimer = 0; spawnEnemy(); }}
          for (const e of state.enemies) {{
            e.y += e.speed * dt;
            if (rectsOverlap(state.player, e)) {{
              state.hp -= 1;
              state.run.combo = 0;
              playSfx("damage");
              e.y = canvas.height + 999;
              burst(state.player.x + state.player.w / 2, state.player.y + state.player.h / 2, ASSET.enemy_primary, 8);
            }}
          }}
          state.enemies = state.enemies.filter((e) => e.y < canvas.height + 100);
          state.score += dt * 10 * (1 + state.run.combo * 0.03);
        }}

        for (const p of state.particles) {{
          p.t += dt;
          p.x += p.vx * dt;
          p.y += p.vy * dt;
        }}
        state.particles = state.particles.filter((p) => p.t < p.life);

        if (state.timeLeft <= 0 || state.hp <= 0) {{
          endGame();
        }}
        updateHud();
      }}

      function draw() {{
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.save();
        if (state.run.shake > 0) {{
          const shakePx = 5 * state.run.shake;
          ctx.translate(rand(-shakePx, shakePx), rand(-shakePx, shakePx));
        }}
        ctx.fillStyle = ASSET.track;
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        if (MODE_IS_FLIGHT_SIM) {{
          const horizonY = canvas.height * 0.52;
          const webglRendered = renderWebglBackground(1 / 60);
          if (!webglRendered) {{
            const sky = ctx.createLinearGradient(0, 0, 0, canvas.height);
            sky.addColorStop(0, ASSET.bg_top);
            sky.addColorStop(1, ASSET.bg_bottom);
            ctx.fillStyle = sky;
            ctx.fillRect(0, 0, canvas.width, canvas.height);
          }}

          ctx.fillStyle = "rgba(34,211,238,0.35)";
          ctx.fillRect(0, horizonY, canvas.width, 2);
          ctx.strokeStyle = "rgba(56,189,248,0.16)";
          ctx.lineWidth = 1;
          for (let i = 0; i < 12; i++) {{
            const t = i / 11;
            const y = horizonY + (t * t) * (canvas.height - horizonY);
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(canvas.width, y);
            ctx.stroke();
          }}
          for (let i = -6; i <= 6; i++) {{
            const x = canvas.width * 0.5 + i * 90 - state.flight.yaw * 80;
            ctx.beginPath();
            ctx.moveTo(x, horizonY);
            ctx.lineTo(canvas.width * 0.5 + i * 180, canvas.height);
            ctx.stroke();
          }}

          const sortedEnemies = [...state.enemies].sort((a, b) => (a.z || 0) - (b.z || 0));
          for (const e of sortedEnemies) {{
            const ex = e.screenX ?? e.x;
            const ey = e.screenY ?? e.y;
            const ew = e.screenW ?? e.w ?? 32;
            const eh = e.screenH ?? e.h ?? 32;
            if ((e.z || 0) > 1.08) continue;
            if (e.kind === "ring") {{
              if (drawSprite("ring", ex, ey, ew, eh, 0.95)) continue;
              ctx.strokeStyle = ASSET.boost_color;
              ctx.lineWidth = Math.max(2, ew * 0.08);
              ctx.shadowBlur = 16;
              ctx.shadowColor = ASSET.boost_color;
              ctx.beginPath();
              ctx.ellipse(ex + ew * 0.5, ey + eh * 0.5, ew * 0.5, eh * 0.45, 0, 0, Math.PI * 2);
              ctx.stroke();
            }} else if (e.kind === "turbulence") {{
              if (drawSprite("hazard", ex, ey, ew, eh, 0.78)) continue;
              ctx.strokeStyle = "rgba(148,163,184,0.75)";
              ctx.lineWidth = 2;
              ctx.shadowBlur = 10;
              ctx.shadowColor = "rgba(148,163,184,0.7)";
              for (let i = 0; i < 3; i++) {{
                const yy = ey + i * (eh / 2.5);
                ctx.beginPath();
                ctx.moveTo(ex, yy);
                ctx.quadraticCurveTo(ex + ew * 0.45, yy - 8, ex + ew, yy);
                ctx.stroke();
              }}
            }} else {{
              if (drawSprite("hazard", ex, ey, ew, eh, 0.92)) continue;
              ctx.fillStyle = ASSET.enemy_primary;
              ctx.shadowBlur = 14;
              ctx.shadowColor = ASSET.enemy_primary;
              ctx.beginPath();
              ctx.moveTo(ex + ew * 0.5, ey - eh * 0.08);
              ctx.lineTo(ex + ew * 0.92, ey + eh * 0.45);
              ctx.lineTo(ex + ew * 0.5, ey + eh * 1.02);
              ctx.lineTo(ex + ew * 0.08, ey + eh * 0.45);
              ctx.closePath();
              ctx.fill();
            }}
          }}
        }} else if (MODE_IS_3D_RUNNER) {{
          const horizonY = canvas.height * 0.2;
          const roadTop = canvas.width * 0.2;
          const roadBottom = canvas.width * 0.78;
          const curvePx = state.racer.roadCurve * canvas.width * 0.16;

          const webglRendered = CONFIG.mode === "webgl_three_runner" ? renderWebglBackground(1 / 60) : false;
          if (!webglRendered) {{
            const sky = ctx.createLinearGradient(0, 0, 0, canvas.height);
            sky.addColorStop(0, ASSET.bg_top);
            sky.addColorStop(1, ASSET.bg_bottom);
            ctx.fillStyle = sky;
            ctx.fillRect(0, 0, canvas.width, canvas.height);
          }}

          const haze = ctx.createLinearGradient(0, horizonY - 40, 0, horizonY + 90);
          haze.addColorStop(0, "rgba(56,189,248,0.08)");
          haze.addColorStop(1, "rgba(15,23,42,0.55)");
          ctx.fillStyle = haze;
          ctx.fillRect(0, horizonY - 40, canvas.width, 140);

          ctx.strokeStyle = "rgba(34,211,238,0.2)";
          ctx.lineWidth = 1.2;
          for (let i = 0; i < 12; i++) {{
            const y = horizonY - 22 + i * 6;
            const w = canvas.width * (0.15 + i * 0.03);
            ctx.beginPath();
            ctx.moveTo(canvas.width * 0.5 - w, y);
            ctx.lineTo(canvas.width * 0.5 + w, y);
            ctx.stroke();
          }}

          const leftTop = canvas.width / 2 - roadTop + curvePx;
          const rightTop = canvas.width / 2 + roadTop + curvePx;
          const leftBottom = canvas.width / 2 - roadBottom;
          const rightBottom = canvas.width / 2 + roadBottom;

          ctx.fillStyle = ASSET.track;
          ctx.beginPath();
          ctx.moveTo(leftTop, horizonY);
          ctx.lineTo(rightTop, horizonY);
          ctx.lineTo(rightBottom, canvas.height);
          ctx.lineTo(leftBottom, canvas.height);
          ctx.closePath();
          ctx.fill();

          for (let i = 0; i < 18; i++) {{
            const t = ((i / 18) + (state.racer.roadScroll * 0.02)) % 1;
            const tt = t * t;
            const y = horizonY + tt * (canvas.height - horizonY);
            const roadHalf = roadTop + (roadBottom - roadTop) * tt;
            const cx = canvas.width / 2 + curvePx * (1 - t);
            const dashW = Math.max(4, 16 * (0.2 + t));
            const dashH = Math.max(2, 18 * (0.2 + t));
            ctx.fillStyle = "rgba(241,245,249,0.5)";
            ctx.fillRect(cx - dashW / 2, y, dashW, dashH);
          }}

          ctx.strokeStyle = "rgba(148,163,184,0.35)";
          ctx.lineWidth = 2;
          for (const laneFactor of [-0.33, 0.33]) {{
            ctx.beginPath();
            for (let i = 0; i <= 20; i++) {{
              const t = i / 20;
              const tt = t * t;
              const y = horizonY + tt * (canvas.height - horizonY);
              const roadHalf = roadTop + (roadBottom - roadTop) * tt;
              const cx = canvas.width / 2 + curvePx * (1 - t);
              const x = cx + roadHalf * laneFactor;
              if (i === 0) ctx.moveTo(x, y);
              else ctx.lineTo(x, y);
            }}
            ctx.stroke();
          }}

          const sortedEnemies = [...state.enemies].sort((a, b) => (a.z || 0) - (b.z || 0));
          for (const e of sortedEnemies) {{
            const t = clamp(e.z || 0, 0, 1.2);
            if (t > 1.08) continue;
            const tt = t * t;
            const y = horizonY + tt * (canvas.height - horizonY);
            const roadHalf = roadTop + (roadBottom - roadTop) * tt;
            const cx = canvas.width / 2 + curvePx * (1 - t);
            const laneOffset = (e.lane || 0) * roadHalf * 0.54;
            const scale = 0.28 + t * 1.05;
            const ew = (e.w || 30) * scale;
            const eh = (e.h || 50) * scale;
            const ex = cx + laneOffset - ew / 2;
            const ey = y - eh;

            if (e.kind === "boost") {{
              if (drawSprite("boost", ex, ey, ew, eh, 0.96)) continue;
              ctx.save();
              ctx.translate(ex + ew / 2, ey + eh / 2);
              ctx.rotate((state.racer.roadScroll * 0.05) % (Math.PI * 2));
              ctx.fillStyle = ASSET.boost_color;
              ctx.shadowBlur = 14;
              ctx.shadowColor = ASSET.boost_color;
              ctx.beginPath();
              ctx.moveTo(0, -eh / 2);
              ctx.lineTo(ew / 2, 0);
              ctx.lineTo(0, eh / 2);
              ctx.lineTo(-ew / 2, 0);
              ctx.closePath();
              ctx.fill();
              ctx.restore();
            }} else {{
              if (drawSprite(e.kind === "elite" ? "elite" : "enemy", ex, ey, ew, eh, 0.97)) continue;
              ctx.fillStyle = ASSET.enemy_primary;
              ctx.shadowBlur = 14;
              ctx.shadowColor = ASSET.enemy_primary;
              ctx.fillRect(ex, ey, ew, eh);
              ctx.fillStyle = ASSET.track;
              ctx.fillRect(ex + ew * 0.1, ey + eh * 0.16, ew * 0.8, eh * 0.28);
            }}
          }}
        }} else {{
          const g = ctx.createLinearGradient(0, 0, 0, canvas.height);
          g.addColorStop(0, ASSET.bg_top);
          g.addColorStop(1, ASSET.bg_bottom);
          ctx.fillStyle = g;
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          for (let i = 0; i < 100; i++) {{
            ctx.fillStyle = `rgba(148,163,184,${{(i % 6) * 0.018}})`;
            ctx.fillRect((i * 73 + state.run.level * 5) % canvas.width, (i * 41 + state.run.level * 2) % canvas.height, 2, 2);
          }}

          for (const e of state.enemies) {{
            const isElite = e.kind === "elite";
            ctx.fillStyle = isElite ? ASSET.enemy_elite : ASSET.enemy_primary;
            ctx.shadowBlur = isElite ? 18 : 14;
            ctx.shadowColor = isElite ? ASSET.enemy_elite : ASSET.enemy_primary;
            if (CONFIG.mode === "topdown_roguelike_shooter") {{
              if (drawSprite(isElite ? "elite" : "enemy", e.x, e.y, e.w, e.h, 0.95)) {{
                if (e.kind === "charger") {{
                  ctx.strokeStyle = ASSET.boost_color;
                  ctx.lineWidth = 2;
                  ctx.beginPath();
                  ctx.arc(e.x + e.w / 2, e.y + e.h / 2, (e.w / 2) + 5, 0, Math.PI * 2);
                  ctx.stroke();
                }}
                continue;
              }}
              const cx = e.x + e.w / 2;
              const cy = e.y + e.h / 2;
              const radius = e.w / 2;
              ctx.beginPath();
              ctx.arc(cx, cy, radius, 0, Math.PI * 2);
              ctx.fill();
              if (e.kind === "charger") {{
                ctx.strokeStyle = ASSET.boost_color;
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.arc(cx, cy, radius + 5, 0, Math.PI * 2);
                ctx.stroke();
              }}
            }} else if (ASSET.sprite_profile === "comic") {{
              const r = Math.max(6, e.w * 0.18);
              ctx.beginPath();
              ctx.roundRect(e.x, e.y, e.w, e.h, r);
              ctx.fill();
              ctx.fillStyle = "rgba(255,255,255,0.16)";
              ctx.fillRect(e.x + e.w * 0.16, e.y + e.h * 0.12, e.w * 0.2, e.h * 0.16);
            }} else {{
              ctx.fillRect(e.x, e.y, e.w, e.h);
            }}
          }}
        }}
        for (const b of state.bullets) {{
          if (drawSprite("trail", b.x - b.w * 0.5, b.y - b.h * 1.2, b.w * 2.0, b.h * 2.4, 0.7)) continue;
          ctx.fillStyle = ASSET.boost_color;
          ctx.shadowBlur = 10;
          ctx.shadowColor = ASSET.boost_color;
          ctx.fillRect(b.x, b.y, b.w, b.h);
        }}
        for (const p of state.particles) {{
          const a = 1 - p.t / p.life;
          ctx.fillStyle = p.color.replace(")", `, ${{a}})`).replace("rgb", "rgba");
          ctx.globalAlpha = a;
          ctx.fillRect(p.x, p.y, 3, 3);
          ctx.globalAlpha = 1;
        }}

        if (MODE_IS_FLIGHT_SIM) {{
          const px = state.player.x;
          const py = state.player.y;
          const pw = state.player.w;
          const ph = state.player.h;
          const bank = state.flight.bankVisual;
          if (drawSprite("player", px - 6, py - 8, pw + 12, ph + 18, 0.98)) {{
            if (state.racer.boostTimer > 0 || state.flight.throttle > 0.82) {{
              drawSprite("trail", px + pw * 0.28, py + ph * 0.84, pw * 0.45, ph * 0.72, 0.72);
            }}
          }} else {{
          ctx.save();
          ctx.translate(px + pw * 0.5, py + ph * 0.5);
          ctx.rotate(bank * 0.45);
          ctx.shadowBlur = 18;
          ctx.shadowColor = state.racer.boostTimer > 0 ? ASSET.boost_color : ASSET.player_primary;
          ctx.fillStyle = ASSET.player_primary;
          ctx.beginPath();
          ctx.moveTo(0, -ph * 0.6);
          ctx.lineTo(pw * 0.44, ph * 0.34);
          ctx.lineTo(0, ph * 0.58);
          ctx.lineTo(-pw * 0.44, ph * 0.34);
          ctx.closePath();
          ctx.fill();
          ctx.fillStyle = ASSET.player_secondary;
          ctx.fillRect(-pw * 0.08, -ph * 0.2, pw * 0.16, ph * 0.56);
          ctx.fillRect(-pw * 0.5, ph * 0.2, pw, ph * 0.12);
          if (state.racer.boostTimer > 0 || state.flight.throttle > 0.82) {{
            ctx.fillStyle = ASSET.boost_color;
            ctx.fillRect(-pw * 0.12, ph * 0.58, pw * 0.24, ph * 0.38);
          }}
          ctx.restore();
          }}
        }} else if (MODE_IS_3D_RUNNER) {{
          const px = state.player.x;
          const py = state.player.y;
          const pw = state.player.w;
          const ph = state.player.h;
          if (drawSprite("player", px - 2, py - 6, pw + 4, ph + 10, 0.98)) {{
            if (state.racer.boostTimer > 0) {{
              drawSprite("trail", px + pw * 0.34, py + ph * 0.9, pw * 0.32, ph * 0.62, 0.74);
            }}
          }} else {{
          ctx.shadowBlur = 18;
          ctx.shadowColor = state.racer.boostTimer > 0 ? ASSET.boost_color : ASSET.player_primary;
          ctx.fillStyle = ASSET.player_primary;
          ctx.beginPath();
          ctx.moveTo(px + pw * 0.5, py - ph * 0.08);
          ctx.lineTo(px + pw * 0.9, py + ph * 0.3);
          ctx.lineTo(px + pw * 0.78, py + ph * 0.95);
          ctx.lineTo(px + pw * 0.22, py + ph * 0.95);
          ctx.lineTo(px + pw * 0.1, py + ph * 0.3);
          ctx.closePath();
          ctx.fill();
          ctx.fillStyle = ASSET.player_secondary;
          ctx.fillRect(px + pw * 0.2, py + ph * 0.25, pw * 0.6, ph * 0.26);
          ctx.fillStyle = ASSET.track;
          ctx.fillRect(px + pw * 0.02, py + ph * 0.62, pw * 0.18, ph * 0.2);
          ctx.fillRect(px + pw * 0.8, py + ph * 0.62, pw * 0.18, ph * 0.2);
          if (state.racer.boostTimer > 0) {{
            ctx.fillStyle = ASSET.boost_color;
            ctx.fillRect(px + pw * 0.4, py + ph * 0.95, pw * 0.2, ph * 0.35);
          }}
          }}
        }} else {{
          ctx.shadowBlur = 18;
          ctx.shadowColor = ASSET.player_primary;
          if (CONFIG.mode === "topdown_roguelike_shooter") {{
            if (drawSprite("player", state.player.x - 2, state.player.y - 2, state.player.w + 4, state.player.h + 4, 0.96)) {{
              // sprite path loaded
            }} else {{
            const px = state.player.x + state.player.w / 2;
            const py = state.player.y + state.player.h / 2;
            ctx.fillStyle = ASSET.player_primary;
            ctx.beginPath();
            ctx.arc(px, py, state.player.w * 0.45, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = ASSET.player_secondary;
            ctx.fillRect(px - 5, py - 18, 10, 20);
            }}
          }} else if (ASSET.sprite_profile === "comic") {{
            const w = state.player.w;
            const h = state.player.h;
            const x = state.player.x;
            const y = state.player.y;
            ctx.fillStyle = ASSET.player_primary;
            ctx.beginPath();
            ctx.roundRect(x, y, w, h, Math.max(7, w * 0.2));
            ctx.fill();
            ctx.fillStyle = "rgba(255,255,255,0.2)";
            ctx.fillRect(x + w * 0.18, y + h * 0.12, w * 0.22, h * 0.14);
          }} else {{
            ctx.fillStyle = ASSET.player_primary;
            ctx.fillRect(state.player.x, state.player.y, state.player.w, state.player.h);
          }}
          if (MODE_IS_BRAWLER && state.attackCooldown > 0) {{
            ctx.strokeStyle = ASSET.enemy_elite;
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.arc(state.player.x + state.player.w/2, state.player.y + state.player.h/2, 52, 0, Math.PI * 2);
            ctx.stroke();
          }}
        }}
        ctx.shadowBlur = 0;
        ctx.restore();
      }}

      function updateHud() {{
        scoreEl.textContent = `Score: ${{Math.floor(state.score)}} · Combo: x${{Math.max(1, state.run.combo.toFixed(1))}}`;
        if (MODE_IS_FLIGHT_SIM) {{
          timerEl.textContent = `Time: ${{state.timeLeft.toFixed(1)}} · Lv.${{state.run.level}} · THR ${{Math.round(state.flight.throttle * 100)}}%`;
          hpEl.textContent = `HP: ${{Math.max(0, state.hp)}} · Relic: ${{state.run.relics.length}} · CKP ${{state.flight.checkpointCombo}}`;
          return;
        }}
        timerEl.textContent = `Time: ${{state.timeLeft.toFixed(1)}} · Lv.${{state.run.level}} · XP ${{Math.floor(state.run.xp)}}/${{state.run.nextXp}}`;
        hpEl.textContent = `HP: ${{Math.max(0, state.hp)}} · Relic: ${{state.run.relics.length}}`;
      }}

      function endGame() {{
        if (!state.running) return;
        state.running = false;
        const buildSummary = state.run.upgrades.slice(-3).join(", ") || "none";
        overlayText.textContent = `최종 점수 ${{Math.floor(state.score)}} · 콤보 x${{Math.max(1, state.run.combo.toFixed(1))}} · 빌드(${{buildSummary}}) · R 재시작`;
        playSfx("gameover");
        overlay.classList.add("show");
      }}

      function frame(ts) {{
        if (!state.lastTime) state.lastTime = ts;
        const dt = Math.min(0.05, (ts - state.lastTime) / 1000);
        state.lastTime = ts;
        update(dt);
        draw();
        requestAnimationFrame(frame);
      }}

      async function submitScore(playerName, score, fingerprint) {{
        const endpoint = window.__IIS_LEADERBOARD_ENDPOINT;
        const anonKey = window.__IIS_SUPABASE_ANON_KEY;
        const gameId = window.__IIS_GAME_ID;
        if (!endpoint || !anonKey || !gameId) return {{ status: "skipped", reason: "missing_env" }};
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
          if (!response.ok) return {{ status: "error", reason: `http_${{response.status}}` }};
          return {{ status: "ok" }};
        }} catch (error) {{
          return {{ status: "error", reason: String(error) }};
        }} finally {{
          clearTimeout(timeout);
        }}
      }}

      window.IISLeaderboard = {{ submitScore }};
      loadSprites();
      resetState();
      requestAnimationFrame(frame);
    </script>
  </body>
</html>
"""


def _extract_hybrid_bundle_from_inline_html(
    *,
    slug: str,
    inline_html: str,
    asset_bank_files: list[dict[str, str]] | None = None,
    runtime_asset_manifest: dict[str, object] | None = None,
) -> tuple[list[dict[str, str]], dict[str, object]] | None:
    style_match = re.search(r"<style>\s*(.*?)\s*</style>", inline_html, flags=re.DOTALL)
    script_match = re.search(r"<script>\s*(.*?)\s*</script>\s*</body>", inline_html, flags=re.DOTALL)
    if not style_match or not script_match:
        return None

    styles_css = style_match.group(1).strip()
    game_js = script_match.group(1).strip()
    if not styles_css or not game_js:
        return None

    index_html = inline_html
    index_html = index_html.replace(style_match.group(0), '    <link rel="stylesheet" href="./styles.css" />', 1)
    index_html = index_html.replace(
        script_match.group(0),
        '    <script src="./game.js"></script>\n  </body>',
        1,
    )

    artifact_files = [
        {
            "path": f"games/{slug}/index.html",
            "content": index_html,
            "content_type": "text/html; charset=utf-8",
        },
        {
            "path": f"games/{slug}/styles.css",
            "content": styles_css,
            "content_type": "text/css; charset=utf-8",
        },
        {
            "path": f"games/{slug}/game.js",
            "content": game_js,
            "content_type": "application/javascript; charset=utf-8",
        },
    ]
    files_by_path = {row["path"]: row for row in artifact_files}
    for row in asset_bank_files or []:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path", "")).strip()
        content = str(row.get("content", ""))
        content_type = str(row.get("content_type", "")).strip()
        if not path.startswith(f"games/{slug}/"):
            continue
        if not content or not content_type:
            continue
        files_by_path[path] = {
            "path": path,
            "content": content,
            "content_type": content_type,
        }
    artifact_files = list(files_by_path.values())

    resolved_asset_manifest: dict[str, object] = {}
    if isinstance(runtime_asset_manifest, dict):
        resolved_asset_manifest = dict(runtime_asset_manifest)

    image_manifest = resolved_asset_manifest.get("images")
    if not isinstance(image_manifest, dict):
        image_manifest = {}
    for row in artifact_files:
        path = str(row["path"])
        if not path.endswith(".svg"):
            continue
        filename = path.rsplit("/", 1)[-1]
        image_key = filename[:-4]
        image_manifest.setdefault(image_key, f"./{filename}")
    resolved_asset_manifest["images"] = image_manifest
    resolved_asset_manifest["styles"] = ["./styles.css"]
    resolved_asset_manifest["scripts"] = ["./game.js"]

    runtime_hooks = [
        "requestAnimationFrame",
        "loadSprites",
        "renderWebglBackground",
        "spawnEnemy",
        "stepProgression",
        "update",
        "draw",
        "playSfx",
    ]
    artifact_manifest = {
        "schema_version": 1,
        "entrypoint": f"games/{slug}/index.html",
        "files": [row["path"] for row in artifact_files],
        "bundle_kind": "hybrid_engine",
        "modules": [
            "runtime_bootstrap",
            "input_controls",
            "spawn_system",
            "combat_or_navigation_loop",
            "render_pipeline",
            "hud_overlay",
            "audio_feedback",
        ],
        "runtime_hooks": runtime_hooks,
        "asset_manifest": resolved_asset_manifest,
    }
    return artifact_files, artifact_manifest


def run(state: PipelineState, deps: NodeDependencies) -> PipelineState:
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
    core_loop_type = _infer_core_loop_type(keyword=state["keyword"], title=title, genre=genre)
    unsupported_scope_reason = _detect_unsupported_scope(keyword=state["keyword"], title=title, genre=genre)
    if unsupported_scope_reason and deps.vertex_service.settings.builder_scope_guard_enabled:
        state["status"] = PipelineStatus.ERROR
        state["reason"] = unsupported_scope_reason
        state["outputs"]["scope_guard_reason"] = unsupported_scope_reason
        state["outputs"]["requested_keyword"] = state["keyword"]
        return append_log(
            state,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.ERROR,
            agent_name=PipelineAgentName.BUILDER,
            message="빌드 중단: 현재 파이프라인 범위를 초과한 요청입니다.",
            reason=unsupported_scope_reason,
            metadata={
                "keyword": state["keyword"],
                "title": title,
                "genre": genre,
                "supported_modes": [
                    "flight_sim_3d",
                    "webgl_three_runner",
                    "topdown_roguelike_shooter",
                    "comic_action_brawler_3d",
                    "lane_dodge_racer",
                    "arena_shooter",
                    "duel_brawler",
                    "arcade_generic",
                ],
            },
        )
    asset_pack = _resolve_asset_pack(core_loop_type=core_loop_type, palette=palette)
    art_direction_contract = state["outputs"].get("art_direction_contract")
    if not isinstance(art_direction_contract, dict):
        art_direction_contract = {}
    asset_bank_files, runtime_asset_manifest = _build_hybrid_asset_bank(
        slug=slug,
        core_loop_type=core_loop_type,
        asset_pack=asset_pack,
    )
    contract = runtime_asset_manifest.get("contract")
    if isinstance(contract, dict):
        for key in ("min_image_assets", "min_render_layers", "min_animation_hooks"):
            value = art_direction_contract.get(key)
            if isinstance(value, int) and value > 0:
                contract[key] = int(value)
    if art_direction_contract:
        runtime_asset_manifest["art_direction"] = {
            key: art_direction_contract.get(key)
            for key in ("style_tag", "motif", "required_visual_keywords", "forbidden_visual_tokens")
        }
    candidate_count = max(1, int(deps.vertex_service.settings.builder_candidate_count))
    variation_hints = _candidate_variation_hints(core_loop_type=core_loop_type, candidate_count=candidate_count)
    design_spec_dump = design_spec.model_dump()

    append_log(
        state,
        stage=PipelineStage.BUILD,
        status=PipelineStatus.RUNNING,
        agent_name=PipelineAgentName.BUILDER,
        message=f"Production V2 generation started (iteration={state['build_iteration']}).",
        metadata={
            "iteration": state["build_iteration"],
            "core_loop_type": core_loop_type,
            "asset_pack": asset_pack["name"],
            "candidate_count": candidate_count,
        },
    )

    candidate_rows: list[dict[str, Any]] = []
    for index, variation_hint in enumerate(variation_hints, start=1):
        generated_config = deps.vertex_service.generate_game_config(
            keyword=state["keyword"],
            title=title,
            genre=genre,
            objective=gdd.objective,
            design_spec=design_spec_dump,
            variation_hint=variation_hint,
        )
        base_candidate_html = _build_hybrid_engine_html(
            title=title,
            genre=genre,
            slug=slug,
            accent_color=accent_color,
            viewport_width=design_spec.viewport_width,
            viewport_height=design_spec.viewport_height,
            safe_area_padding=design_spec.safe_area_padding,
            min_font_size_px=design_spec.min_font_size_px,
            text_overflow_policy=design_spec.text_overflow_policy,
            core_loop_type=core_loop_type,
            game_config=generated_config.payload,
            asset_pack=asset_pack,
            asset_manifest=runtime_asset_manifest,
        )
        candidate_html = base_candidate_html
        codegen_meta_rows: list[dict[str, Any]] = []
        for pass_index in range(max(0, int(deps.vertex_service.settings.builder_codegen_passes))):
            codegen_result = deps.vertex_service.generate_codegen_candidate_artifact(
                keyword=state["keyword"],
                title=title,
                genre=genre,
                objective=gdd.objective,
                core_loop_type=core_loop_type,
                variation_hint=variation_hint,
                design_spec=design_spec_dump,
                asset_pack=asset_pack,
                html_content=candidate_html,
            )
            generated_candidate_html = str(codegen_result.payload.get("artifact_html", "")).strip()
            if generated_candidate_html:
                candidate_html = generated_candidate_html
            codegen_meta_rows.append(
                {
                    "pass": pass_index + 1,
                    "generation_source": codegen_result.meta.get("generation_source", "stub"),
                    "model": codegen_result.meta.get("model"),
                    "reason": codegen_result.meta.get("reason"),
                }
            )
        base_quality_probe = deps.quality_service.evaluate_quality_contract(base_candidate_html, design_spec=design_spec_dump)
        base_gameplay_probe = deps.quality_service.evaluate_gameplay_gate(
            base_candidate_html,
            design_spec=design_spec_dump,
            genre=genre,
            genre_engine=core_loop_type,
            keyword=state["keyword"],
        )
        base_composite_score = _candidate_composite_score(
            quality_score=base_quality_probe.score,
            gameplay_score=base_gameplay_probe.score,
            quality_ok=base_quality_probe.ok,
            gameplay_ok=base_gameplay_probe.ok,
        )
        quality_probe = deps.quality_service.evaluate_quality_contract(candidate_html, design_spec=design_spec_dump)
        gameplay_probe = deps.quality_service.evaluate_gameplay_gate(
            candidate_html,
            design_spec=design_spec_dump,
            genre=genre,
            genre_engine=core_loop_type,
            keyword=state["keyword"],
        )
        composite_score = _candidate_composite_score(
            quality_score=quality_probe.score,
            gameplay_score=gameplay_probe.score,
            quality_ok=quality_probe.ok,
            gameplay_ok=gameplay_probe.ok,
        )
        if base_composite_score > composite_score:
            candidate_html = base_candidate_html
            quality_probe = base_quality_probe
            gameplay_probe = base_gameplay_probe
            composite_score = base_composite_score
            codegen_meta_rows.append(
                {
                    "pass": 0,
                    "generation_source": "template_baseline",
                    "model": None,
                    "reason": "codegen_regression_guard",
                    "baseline_composite_score": base_composite_score,
                }
            )

        candidate_row = {
            "index": index,
            "variation_hint": variation_hint,
            "artifact_html": candidate_html,
            "generation_meta": generated_config.meta,
            "quality_ok": quality_probe.ok,
            "quality_score": quality_probe.score,
            "gameplay_ok": gameplay_probe.ok,
            "gameplay_score": gameplay_probe.score,
            "composite_score": composite_score,
            "asset_pack": asset_pack["name"],
            "codegen_passes": codegen_meta_rows,
        }
        candidate_rows.append(candidate_row)

        append_log(
            state,
            stage=PipelineStage.BUILD,
            status=PipelineStatus.RUNNING,
            agent_name=PipelineAgentName.BUILDER,
            message=f"Candidate {index}/{candidate_count} evaluated.",
            metadata={
                "iteration": state["build_iteration"],
                "candidate_index": index,
                "quality_score": quality_probe.score,
                "gameplay_score": gameplay_probe.score,
                "composite_score": composite_score,
                "generation_source": generated_config.meta.get("generation_source", "stub"),
                "model": generated_config.meta.get("model"),
                "asset_pack": asset_pack["name"],
                "codegen_passes": codegen_meta_rows,
            },
        )

    best_candidate = max(
        candidate_rows,
        key=lambda row: (float(row["composite_score"]), int(row["gameplay_score"]), int(row["quality_score"])),
    )
    selected_generation_meta = dict(best_candidate.get("generation_meta", {}))
    selected_html = str(best_candidate["artifact_html"])

    append_log(
        state,
        stage=PipelineStage.BUILD,
        status=PipelineStatus.RUNNING,
        agent_name=PipelineAgentName.BUILDER,
        message="Final polish pass started for selected candidate.",
        metadata={
            "iteration": state["build_iteration"],
            "selected_candidate": best_candidate["index"],
            "selected_composite_score": best_candidate["composite_score"],
        },
    )

    polish_result = deps.vertex_service.polish_hybrid_artifact(
        keyword=state["keyword"],
        title=title,
        genre=genre,
        html_content=selected_html,
    )
    polished_html = str(polish_result.payload.get("artifact_html", "")).strip() or selected_html
    polished_quality = deps.quality_service.evaluate_quality_contract(polished_html, design_spec=design_spec_dump)
    polished_gameplay = deps.quality_service.evaluate_gameplay_gate(
        polished_html,
        design_spec=design_spec_dump,
        genre=genre,
        genre_engine=core_loop_type,
        keyword=state["keyword"],
    )
    polished_composite = _candidate_composite_score(
        quality_score=polished_quality.score,
        gameplay_score=polished_gameplay.score,
        quality_ok=polished_quality.ok,
        gameplay_ok=polished_gameplay.ok,
    )
    selected_composite = float(best_candidate["composite_score"])
    use_polished = polished_composite >= (selected_composite - 2.0)
    if polished_quality.ok and polished_gameplay.ok:
        use_polished = True
    artifact_html = polished_html if use_polished else selected_html

    final_quality_score = polished_quality.score if use_polished else int(best_candidate["quality_score"])
    final_gameplay_score = polished_gameplay.score if use_polished else int(best_candidate["gameplay_score"])
    final_composite_score = polished_composite if use_polished else selected_composite

    builder_strategy = "production_v3_candidates_codegen_qa_polish"
    candidate_scoreboard = [
        {
            "index": int(row["index"]),
            "quality_score": int(row["quality_score"]),
            "gameplay_score": int(row["gameplay_score"]),
            "composite_score": float(row["composite_score"]),
            "quality_ok": bool(row["quality_ok"]),
            "gameplay_ok": bool(row["gameplay_ok"]),
            "generation_source": row["generation_meta"].get("generation_source", "stub"),
            "model": row["generation_meta"].get("model"),
            "asset_pack": row.get("asset_pack"),
            "codegen_passes": row.get("codegen_passes", []),
        }
        for row in candidate_rows
    ]

    artifact_files: list[dict[str, str]] | None = None
    artifact_manifest: dict[str, object] | None = None

    hybrid_bundle = _extract_hybrid_bundle_from_inline_html(
        slug=slug,
        inline_html=artifact_html,
        asset_bank_files=asset_bank_files,
        runtime_asset_manifest=runtime_asset_manifest,
    )
    if not hybrid_bundle:
        fallback_files = [
            {
                "path": f"games/{slug}/index.html",
                "content": artifact_html,
                "content_type": "text/html; charset=utf-8",
            },
            *asset_bank_files,
        ]
        fallback_asset_manifest = runtime_asset_manifest if isinstance(runtime_asset_manifest, dict) else {}
        fallback_manifest = {
            "schema_version": 1,
            "entrypoint": f"games/{slug}/index.html",
            "files": [row["path"] for row in fallback_files],
            "bundle_kind": "hybrid_engine",
            "modules": [
                "runtime_bootstrap",
                "input_controls",
                "spawn_system",
                "combat_or_navigation_loop",
                "render_pipeline",
                "hud_overlay",
                "audio_feedback",
            ],
            "runtime_hooks": ["requestAnimationFrame", "update", "draw", "playSfx"],
            "asset_manifest": fallback_asset_manifest,
        }
        hybrid_bundle = (fallback_files, fallback_manifest)
    if hybrid_bundle:
        artifact_files, artifact_manifest = hybrid_bundle
        artifact_manifest["genre_engine"] = core_loop_type
        artifact_manifest["asset_pack"] = asset_pack["name"]

    build_artifact = BuildArtifactPayload(
        game_slug=slug,
        game_name=title,
        game_genre=genre,
        artifact_path=f"games/{slug}/index.html",
        artifact_html=artifact_html,
        entrypoint_path=f"games/{slug}/index.html",
        artifact_files=artifact_files,
        artifact_manifest=artifact_manifest,
    )

    state["outputs"]["build_artifact"] = build_artifact.model_dump()
    state["outputs"]["game_slug"] = build_artifact.game_slug
    state["outputs"]["game_name"] = build_artifact.game_name
    state["outputs"]["game_genre"] = build_artifact.game_genre
    state["outputs"]["genre_engine"] = core_loop_type
    state["outputs"]["asset_pack"] = asset_pack["name"]
    state["outputs"]["artifact_path"] = build_artifact.artifact_path
    state["outputs"]["artifact_html"] = build_artifact.artifact_html
    state["outputs"]["artifact_files"] = [row.model_dump() for row in build_artifact.artifact_files or []]
    state["outputs"]["artifact_manifest"] = build_artifact.artifact_manifest or {}

    return append_log(
        state,
        stage=PipelineStage.BUILD,
        status=PipelineStatus.SUCCESS,
        agent_name=PipelineAgentName.BUILDER,
        message=f"Production V2 artifact selected and polished (iteration={state['build_iteration']}).",
        metadata={
            "artifact": state["outputs"]["artifact_path"],
            "genre": genre,
            "viewport": f"{design_spec.viewport_width}x{design_spec.viewport_height}",
            "generation_source": selected_generation_meta.get("generation_source", "stub"),
            **{
                key: value
                for key, value in selected_generation_meta.items()
                if key in {"model", "latency_ms", "reason", "vertex_error"}
            },
            "builder_strategy": builder_strategy,
            "genre_engine_selected": core_loop_type,
            "asset_pack": asset_pack["name"],
            "artifact_file_count": len(build_artifact.artifact_files or []),
            "candidate_count": candidate_count,
            "codegen_enabled": bool(deps.vertex_service.settings.builder_codegen_enabled),
            "codegen_passes_per_candidate": int(deps.vertex_service.settings.builder_codegen_passes),
            "selected_candidate_index": int(best_candidate["index"]),
            "selected_candidate_score": selected_composite,
            "final_quality_score": final_quality_score,
            "final_gameplay_score": final_gameplay_score,
            "final_composite_score": final_composite_score,
            "polish_applied": use_polished,
            "polish_generation_source": polish_result.meta.get("generation_source", "stub"),
            "polish_model": polish_result.meta.get("model"),
            "polish_reason": polish_result.meta.get("reason"),
            "candidate_scoreboard": candidate_scoreboard,
        },
    )
