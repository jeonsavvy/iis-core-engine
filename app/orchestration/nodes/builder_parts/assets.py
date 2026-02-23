from __future__ import annotations


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
        "f1_formula_circuit_3d": {
            "name": "formula_circuit_neon",
            "bg_top": "#0a1730",
            "bg_bottom": "#040810",
            "horizon": "#182f58",
            "track": "#090f1b",
            "player_primary": "#38bdf8",
            "player_secondary": "#0f172a",
            "enemy_primary": "#f43f5e",
            "enemy_elite": "#f97316",
            "boost_color": "#22d3ee",
            "particle": "#facc15",
            "sfx_profile": "formula_arcade",
            "sprite_profile": "formula",
        },
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
    if core_loop_type == "f1_formula_circuit_3d":
        svg_map = {
            "player.svg": (
                f"<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120' viewBox='0 0 120 120'>"
                f"<rect width='120' height='120' fill='none'/>"
                f"<rect x='48' y='20' width='24' height='64' rx='8' fill='{player_primary}'/>"
                f"<rect x='38' y='42' width='44' height='16' rx='6' fill='{player_secondary}'/>"
                f"<rect x='22' y='70' width='76' height='12' rx='5' fill='{player_primary}'/>"
                f"<rect x='30' y='82' width='16' height='26' rx='4' fill='{player_secondary}'/>"
                f"<rect x='74' y='82' width='16' height='26' rx='4' fill='{player_secondary}'/>"
                f"<circle cx='38' cy='100' r='9' fill='{player_secondary}'/>"
                f"<circle cx='82' cy='100' r='9' fill='{player_secondary}'/>"
                f"</svg>"
            ),
            "enemy.svg": (
                f"<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120' viewBox='0 0 120 120'>"
                f"<rect width='120' height='120' fill='none'/>"
                f"<rect x='48' y='18' width='24' height='64' rx='8' fill='{enemy_primary}'/>"
                f"<rect x='36' y='40' width='48' height='16' rx='6' fill='{player_secondary}'/>"
                f"<rect x='18' y='68' width='84' height='13' rx='5' fill='{enemy_primary}'/>"
                f"<circle cx='36' cy='98' r='9' fill='{player_secondary}'/>"
                f"<circle cx='84' cy='98' r='9' fill='{player_secondary}'/>"
                f"</svg>"
            ),
            "elite.svg": (
                f"<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120' viewBox='0 0 120 120'>"
                f"<rect width='120' height='120' fill='none'/>"
                f"<rect x='46' y='12' width='28' height='70' rx='8' fill='{enemy_elite}'/>"
                f"<rect x='34' y='34' width='52' height='18' rx='6' fill='{player_secondary}'/>"
                f"<rect x='10' y='66' width='100' height='14' rx='6' fill='{enemy_elite}'/>"
                f"<rect x='20' y='78' width='20' height='28' rx='5' fill='{player_secondary}'/>"
                f"<rect x='80' y='78' width='20' height='28' rx='5' fill='{player_secondary}'/>"
                f"</svg>"
            ),
            "boost.svg": (
                f"<svg xmlns='http://www.w3.org/2000/svg' width='128' height='128' viewBox='0 0 128 128'>"
                f"<rect width='128' height='128' fill='none'/>"
                f"<path d='M64 10 L86 64 L64 118 L42 64 Z' fill='{boost_color}'/>"
                f"<path d='M64 22 L76 64 L64 106 L52 64 Z' fill='{hud_primary}' opacity='0.35'/>"
                f"</svg>"
            ),
            "ring.svg": (
                f"<svg xmlns='http://www.w3.org/2000/svg' width='160' height='128' viewBox='0 0 160 128'>"
                f"<rect width='160' height='128' fill='none'/>"
                f"<rect x='22' y='22' width='116' height='84' rx='18' fill='none' stroke='{boost_color}' stroke-width='10'/>"
                f"<rect x='40' y='38' width='80' height='52' rx='12' fill='none' stroke='{hud_primary}' stroke-width='3' opacity='0.7'/>"
                f"</svg>"
            ),
            "hazard.svg": (
                f"<svg xmlns='http://www.w3.org/2000/svg' width='112' height='112' viewBox='0 0 112 112'>"
                f"<rect width='112' height='112' fill='none'/>"
                f"<polygon points='56,8 104,98 8,98' fill='{enemy_primary}'/>"
                f"<rect x='51' y='36' width='10' height='32' rx='4' fill='{hud_primary}'/>"
                f"<circle cx='56' cy='80' r='6' fill='{hud_primary}'/>"
                f"</svg>"
            ),
            "trail.svg": (
                f"<svg xmlns='http://www.w3.org/2000/svg' width='96' height='128' viewBox='0 0 96 128'>"
                f"<defs><linearGradient id='g' x1='0' y1='0' x2='0' y2='1'>"
                f"<stop offset='0%' stop-color='{boost_color}' stop-opacity='1'/>"
                f"<stop offset='100%' stop-color='{boost_color}' stop-opacity='0'/>"
                f"</linearGradient></defs>"
                f"<rect x='28' y='10' width='40' height='108' rx='16' fill='url(#g)'/>"
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
        "asset_policy": {
            "mode": "procedural_threejs_first",
            "provider": "builtin_vector_pack",
            "external_image_generation": False,
        },
        "procedural_layers": [
            "gradient_background",
            "parallax_grid",
            "depth_fog",
            "particle_trails",
            "hud_glow_overlay",
        ],
        "contract": {
            "min_image_assets": 5,
            "min_render_layers": 4,
            "min_animation_hooks": 3,
            "min_procedural_layers": 3,
        },
    }
    return artifact_files, asset_manifest
