from __future__ import annotations

import re
from typing import Any


def _normalize_hex_color(color: str, *, fallback: str) -> str:
    raw = str(color or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", raw):
        return raw.lower()
    if re.fullmatch(r"#[0-9a-fA-F]{3}", raw):
        return "#" + "".join(ch * 2 for ch in raw[1:]).lower()
    return fallback.lower()


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    normalized = _normalize_hex_color(color, fallback="#000000")
    return (
        int(normalized[1:3], 16),
        int(normalized[3:5], 16),
        int(normalized[5:7], 16),
    )


def _rgb_to_hex(r: float | int, g: float | int, b: float | int) -> str:
    rc = max(0, min(255, int(r)))
    gc = max(0, min(255, int(g)))
    bc = max(0, min(255, int(b)))
    return f"#{rc:02x}{gc:02x}{bc:02x}"


def _mix_hex(color_a: str, color_b: str, ratio: float) -> str:
    ar, ag, ab = _hex_to_rgb(color_a)
    br, bg, bb = _hex_to_rgb(color_b)
    r = ar + (br - ar) * ratio
    g = ag + (bg - ag) * ratio
    b = ab + (bb - ab) * ratio
    return _rgb_to_hex(r, g, b)


def _to_float(value: object, fallback: float = 0.0) -> float:
    if isinstance(value, bool):
        return fallback
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return fallback
        try:
            return float(text)
        except ValueError:
            return fallback
    return fallback


def _to_int(value: object, fallback: int = 0) -> int:
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return fallback
        try:
            return int(float(text))
        except ValueError:
            return fallback
    return fallback


def _relative_luminance(color: str) -> float:
    r, g, b = _hex_to_rgb(color)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def _build_asset_variant_candidates(
    *,
    core_loop_type: str,
    asset_pack: dict[str, str],
    art_direction_contract: dict[str, object] | None,
) -> list[dict[str, object]]:
    contract = art_direction_contract if isinstance(art_direction_contract, dict) else {}
    requested_count = _to_int(contract.get("asset_variant_count", 3), fallback=3)
    variant_count = max(1, min(5, requested_count))
    motif = str(contract.get("motif", "")).strip().casefold()

    bg_top = _normalize_hex_color(asset_pack.get("bg_top", "#08122f"), fallback="#08122f")
    bg_bottom = _normalize_hex_color(asset_pack.get("bg_bottom", "#050915"), fallback="#050915")
    track = _normalize_hex_color(asset_pack.get("track", "#111827"), fallback="#111827")
    player = _normalize_hex_color(asset_pack.get("player_primary", "#38bdf8"), fallback="#38bdf8")
    enemy = _normalize_hex_color(asset_pack.get("enemy_primary", "#ef4444"), fallback="#ef4444")
    elite = _normalize_hex_color(asset_pack.get("enemy_elite", "#f97316"), fallback="#f97316")
    boost = _normalize_hex_color(asset_pack.get("boost_color", "#22d3ee"), fallback="#22d3ee")
    hud = _normalize_hex_color(asset_pack.get("hud_primary", "#e2e8f0"), fallback="#e2e8f0")
    particle = _normalize_hex_color(asset_pack.get("particle", "#22c55e"), fallback="#22c55e")

    templates: list[dict[str, object]] = [
        {
            "id": "baseline-balanced",
            "theme": "balanced",
            "bg_top": bg_top,
            "bg_bottom": bg_bottom,
            "track": track,
            "player_primary": player,
            "enemy_primary": enemy,
            "enemy_elite": elite,
            "boost_color": boost,
            "hud_primary": hud,
            "particle": particle,
        },
        {
            "id": "high-contrast-racing",
            "theme": "high-contrast",
            "bg_top": _mix_hex(bg_top, "#0b1020", 0.45),
            "bg_bottom": _mix_hex(bg_bottom, "#010409", 0.6),
            "track": _mix_hex(track, "#0b1120", 0.55),
            "player_primary": _mix_hex(player, "#67e8f9", 0.35),
            "enemy_primary": _mix_hex(enemy, "#fb7185", 0.42),
            "enemy_elite": _mix_hex(elite, "#f59e0b", 0.45),
            "boost_color": _mix_hex(boost, "#22d3ee", 0.35),
            "hud_primary": _mix_hex(hud, "#ffffff", 0.2),
            "particle": _mix_hex(particle, "#fde047", 0.42),
        },
        {
            "id": "cinematic-glow",
            "theme": "cinematic",
            "bg_top": _mix_hex(bg_top, "#111827", 0.28),
            "bg_bottom": _mix_hex(bg_bottom, "#020617", 0.52),
            "track": _mix_hex(track, "#1e293b", 0.3),
            "player_primary": _mix_hex(player, "#60a5fa", 0.24),
            "enemy_primary": _mix_hex(enemy, "#f43f5e", 0.26),
            "enemy_elite": _mix_hex(elite, "#f97316", 0.24),
            "boost_color": _mix_hex(boost, "#38bdf8", 0.18),
            "hud_primary": _mix_hex(hud, "#f8fafc", 0.18),
            "particle": _mix_hex(particle, "#93c5fd", 0.22),
        },
        {
            "id": "aggressive-arcade",
            "theme": "aggressive",
            "bg_top": _mix_hex(bg_top, "#020617", 0.68),
            "bg_bottom": _mix_hex(bg_bottom, "#000000", 0.65),
            "track": _mix_hex(track, "#0f172a", 0.55),
            "player_primary": _mix_hex(player, "#22d3ee", 0.22),
            "enemy_primary": _mix_hex(enemy, "#ef4444", 0.18),
            "enemy_elite": _mix_hex(elite, "#f97316", 0.2),
            "boost_color": _mix_hex(boost, "#a78bfa", 0.22),
            "hud_primary": _mix_hex(hud, "#e2e8f0", 0.15),
            "particle": _mix_hex(particle, "#facc15", 0.45),
        },
        {
            "id": "clarity-first",
            "theme": "readability",
            "bg_top": _mix_hex(bg_top, "#0f172a", 0.38),
            "bg_bottom": _mix_hex(bg_bottom, "#020617", 0.4),
            "track": _mix_hex(track, "#111827", 0.45),
            "player_primary": _mix_hex(player, "#7dd3fc", 0.38),
            "enemy_primary": _mix_hex(enemy, "#fb7185", 0.4),
            "enemy_elite": _mix_hex(elite, "#f59e0b", 0.35),
            "boost_color": _mix_hex(boost, "#22d3ee", 0.28),
            "hud_primary": _mix_hex(hud, "#ffffff", 0.25),
            "particle": _mix_hex(particle, "#a3e635", 0.3),
        },
    ]
    selected_templates = templates[:variant_count]

    scored: list[dict[str, object]] = []
    for row in selected_templates:
        player_track_contrast = abs(_relative_luminance(str(row["player_primary"])) - _relative_luminance(str(row["track"])))
        enemy_track_contrast = abs(_relative_luminance(str(row["enemy_primary"])) - _relative_luminance(str(row["track"])))
        hud_bg_contrast = abs(_relative_luminance(str(row["hud_primary"])) - _relative_luminance(str(row["bg_bottom"])))
        score = (player_track_contrast * 42.0) + (enemy_track_contrast * 28.0) + (hud_bg_contrast * 26.0)
        if "racing" in core_loop_type or "formula" in core_loop_type:
            score += player_track_contrast * 8.0
        if "aero" in motif and "flight" in core_loop_type:
            score += 3.0
        if "fantasy" in motif and "roguelike" in core_loop_type:
            score += 3.0
        if "comic" in motif and "brawler" in core_loop_type:
            score += 3.0
        scored.append({**row, "score": round(score, 4)})
    return scored


def _build_decorative_svg_layers(
    *,
    bg_top: str,
    boost_color: str,
    enemy_primary: str,
    hud_primary: str,
) -> dict[str, str]:
    return {
        "hud-frame.svg": (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='256' height='96' viewBox='0 0 256 96'>"
            f"<rect width='256' height='96' rx='18' fill='rgba(15,23,42,0.62)' stroke='{hud_primary}' stroke-opacity='0.32'/>"
            f"<rect x='8' y='8' width='240' height='80' rx='14' fill='none' stroke='{boost_color}' stroke-opacity='0.24'/>"
            f"</svg>"
        ),
        "track-grid.svg": (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='320' height='180' viewBox='0 0 320 180'>"
            f"<rect width='320' height='180' fill='{bg_top}'/>"
            f"<g stroke='{boost_color}' stroke-opacity='0.24' stroke-width='1'>"
            f"<path d='M0 160 L160 100 L320 160'/>"
            f"<path d='M0 180 L160 110 L320 180'/>"
            f"<path d='M80 180 L140 102 M160 180 L160 100 M240 180 L180 102'/>"
            f"</g>"
            f"</svg>"
        ),
        "impact-flare.svg": (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='128' height='128' viewBox='0 0 128 128'>"
            f"<circle cx='64' cy='64' r='16' fill='{hud_primary}'/>"
            f"<circle cx='64' cy='64' r='28' fill='{boost_color}' fill-opacity='0.45'/>"
            f"<circle cx='64' cy='64' r='42' fill='{enemy_primary}' fill-opacity='0.2'/>"
            f"</svg>"
        ),
    }


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
    art_direction_contract: dict[str, object] | None = None,
    retrieval_profile: dict[str, object] | None = None,
) -> tuple[list[dict[str, str]], dict[str, object]]:
    variants = _build_asset_variant_candidates(
        core_loop_type=core_loop_type,
        asset_pack=asset_pack,
        art_direction_contract=art_direction_contract,
    )
    retrieval: dict[str, Any] = retrieval_profile if isinstance(retrieval_profile, dict) else {}
    preferred_variant_id = str(retrieval.get("preferred_variant_id", "")).strip()
    preferred_theme = str(retrieval.get("preferred_variant_theme", "")).strip()
    raw_failure_reasons = retrieval.get("failure_reasons")
    raw_failure_tokens = retrieval.get("failure_tokens")
    failure_reasons = {str(item).strip() for item in raw_failure_reasons if str(item).strip()} if isinstance(raw_failure_reasons, list) else set()
    failure_tokens = {str(item).strip() for item in raw_failure_tokens if str(item).strip()} if isinstance(raw_failure_tokens, list) else set()

    enriched_variants: list[dict[str, object]] = []
    for row in variants:
        memory_bonus = 0.0
        variant_id = str(row.get("id", ""))
        theme = str(row.get("theme", ""))
        if preferred_variant_id and variant_id == preferred_variant_id:
            memory_bonus += 15.0
        if preferred_theme and theme == preferred_theme:
            memory_bonus += 8.0
        if "visual_quality_below_threshold" in failure_reasons and theme in {"readability", "high-contrast"}:
            memory_bonus += 4.0
        if any(token in failure_tokens for token in {"contrast", "color_diversity", "readable_motion"}):
            if theme in {"readability", "high-contrast"}:
                memory_bonus += 3.0

        enriched_variants.append(
            {
                **row,
                "memory_bonus": round(memory_bonus, 4),
                "composed_score": round(_to_float(row.get("score", 0.0), 0.0) + memory_bonus, 4),
            }
        )

    selected_variant = max(enriched_variants, key=lambda row: _to_float(row.get("composed_score", 0.0), 0.0))

    player_primary = str(selected_variant.get("player_primary", asset_pack.get("player_primary", "#38bdf8")))
    player_secondary = str(asset_pack.get("player_secondary", "#0f172a"))
    enemy_primary = str(selected_variant.get("enemy_primary", asset_pack.get("enemy_primary", "#ef4444")))
    enemy_elite = str(selected_variant.get("enemy_elite", asset_pack.get("enemy_elite", "#f97316")))
    boost_color = str(selected_variant.get("boost_color", asset_pack.get("boost_color", "#22d3ee")))
    hud_primary = str(selected_variant.get("hud_primary", asset_pack.get("hud_primary", "#e2e8f0")))
    selected_bg_top = str(selected_variant.get("bg_top", asset_pack.get("bg_top", "#08122f")))
    selected_bg_bottom = str(selected_variant.get("bg_bottom", asset_pack.get("bg_bottom", "#050915")))
    selected_track = str(selected_variant.get("track", asset_pack.get("track", "#111827")))
    selected_particle = str(selected_variant.get("particle", asset_pack.get("particle", "#22c55e")))

    asset_pack["bg_top"] = selected_bg_top
    asset_pack["bg_bottom"] = selected_bg_bottom
    asset_pack["track"] = selected_track
    asset_pack["player_primary"] = player_primary
    asset_pack["enemy_primary"] = enemy_primary
    asset_pack["enemy_elite"] = enemy_elite
    asset_pack["boost_color"] = boost_color
    asset_pack["hud_primary"] = hud_primary
    asset_pack["particle"] = selected_particle

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
    elif core_loop_type in {"comic_action_brawler_3d", "duel_brawler"}:
        svg_map = {
            "player.svg": (
                f"<svg xmlns='http://www.w3.org/2000/svg' width='128' height='128' viewBox='0 0 128 128'>"
                f"<defs>"
                f"<linearGradient id='pbody' x1='0' y1='0' x2='0' y2='1'>"
                f"<stop offset='0%' stop-color='{player_primary}'/>"
                f"<stop offset='100%' stop-color='{player_secondary}'/>"
                f"</linearGradient>"
                f"</defs>"
                f"<rect width='128' height='128' fill='none'/>"
                f"<circle cx='64' cy='24' r='12' fill='{hud_primary}'/>"
                f"<path d='M46 40 L82 40 L88 74 L74 110 L54 110 L40 74 Z' fill='url(#pbody)'/>"
                f"<path d='M34 52 L48 46 L52 62 L38 74 Z' fill='{player_primary}'/>"
                f"<path d='M94 52 L80 46 L76 62 L90 74 Z' fill='{player_primary}'/>"
                f"<rect x='50' y='92' width='12' height='26' rx='5' fill='{player_secondary}'/>"
                f"<rect x='66' y='92' width='12' height='26' rx='5' fill='{player_secondary}'/>"
                f"</svg>"
            ),
            "enemy.svg": (
                f"<svg xmlns='http://www.w3.org/2000/svg' width='128' height='128' viewBox='0 0 128 128'>"
                f"<defs>"
                f"<linearGradient id='ebody' x1='0' y1='0' x2='0' y2='1'>"
                f"<stop offset='0%' stop-color='{enemy_primary}'/>"
                f"<stop offset='100%' stop-color='{enemy_elite}'/>"
                f"</linearGradient>"
                f"</defs>"
                f"<rect width='128' height='128' fill='none'/>"
                f"<circle cx='64' cy='24' r='12' fill='{hud_primary}'/>"
                f"<path d='M44 40 L84 40 L92 76 L78 112 L50 112 L36 76 Z' fill='url(#ebody)'/>"
                f"<path d='M30 52 L44 46 L46 62 L34 76 Z' fill='{enemy_primary}'/>"
                f"<path d='M98 52 L84 46 L82 62 L94 76 Z' fill='{enemy_primary}'/>"
                f"<rect x='48' y='94' width='14' height='24' rx='5' fill='{player_secondary}'/>"
                f"<rect x='66' y='94' width='14' height='24' rx='5' fill='{player_secondary}'/>"
                f"</svg>"
            ),
            "elite.svg": (
                f"<svg xmlns='http://www.w3.org/2000/svg' width='128' height='128' viewBox='0 0 128 128'>"
                f"<defs>"
                f"<radialGradient id='eliteAura' cx='50%' cy='35%' r='60%'>"
                f"<stop offset='0%' stop-color='{enemy_elite}'/>"
                f"<stop offset='100%' stop-color='{enemy_primary}'/>"
                f"</radialGradient>"
                f"</defs>"
                f"<rect width='128' height='128' fill='none'/>"
                f"<circle cx='64' cy='26' r='13' fill='{hud_primary}'/>"
                f"<path d='M42 42 L86 42 L96 80 L80 114 L48 114 L32 80 Z' fill='url(#eliteAura)'/>"
                f"<polygon points='32,30 44,16 54,34' fill='{enemy_elite}'/>"
                f"<polygon points='96,30 84,16 74,34' fill='{enemy_elite}'/>"
                f"<rect x='48' y='96' width='14' height='22' rx='5' fill='{player_secondary}'/>"
                f"<rect x='66' y='96' width='14' height='22' rx='5' fill='{player_secondary}'/>"
                f"</svg>"
            ),
            "boost.svg": (
                f"<svg xmlns='http://www.w3.org/2000/svg' width='128' height='128' viewBox='0 0 128 128'>"
                f"<defs>"
                f"<radialGradient id='boostCore' cx='50%' cy='50%' r='50%'>"
                f"<stop offset='0%' stop-color='{hud_primary}'/>"
                f"<stop offset='100%' stop-color='{boost_color}'/>"
                f"</radialGradient>"
                f"</defs>"
                f"<rect width='128' height='128' fill='none'/>"
                f"<circle cx='64' cy='64' r='34' fill='none' stroke='{boost_color}' stroke-width='12'/>"
                f"<circle cx='64' cy='64' r='18' fill='url(#boostCore)' opacity='0.85'/>"
                f"</svg>"
            ),
            "ring.svg": (
                f"<svg xmlns='http://www.w3.org/2000/svg' width='160' height='128' viewBox='0 0 160 128'>"
                f"<rect width='160' height='128' fill='none'/>"
                f"<ellipse cx='80' cy='64' rx='58' ry='38' fill='none' stroke='{boost_color}' stroke-width='10'/>"
                f"<ellipse cx='80' cy='64' rx='38' ry='22' fill='none' stroke='{hud_primary}' stroke-width='3' opacity='0.8'/>"
                f"</svg>"
            ),
            "hazard.svg": (
                f"<svg xmlns='http://www.w3.org/2000/svg' width='112' height='112' viewBox='0 0 112 112'>"
                f"<rect width='112' height='112' fill='none'/>"
                f"<polygon points='56,8 104,44 86,104 26,104 8,44' fill='{enemy_primary}'/>"
                f"<path d='M56 24 L68 68 L44 68 Z' fill='{hud_primary}' opacity='0.82'/>"
                f"<circle cx='56' cy='82' r='6' fill='{hud_primary}'/>"
                f"</svg>"
            ),
            "trail.svg": (
                f"<svg xmlns='http://www.w3.org/2000/svg' width='112' height='128' viewBox='0 0 112 128'>"
                f"<defs><linearGradient id='g' x1='0' y1='0' x2='0' y2='1'>"
                f"<stop offset='0%' stop-color='{boost_color}' stop-opacity='0.95'/>"
                f"<stop offset='100%' stop-color='{boost_color}' stop-opacity='0'/>"
                f"</linearGradient></defs>"
                f"<ellipse cx='56' cy='60' rx='30' ry='52' fill='url(#g)'/>"
                f"</svg>"
            ),
        }
    svg_map.update(
        _build_decorative_svg_layers(
            bg_top=selected_bg_top,
            boost_color=boost_color,
            enemy_primary=enemy_primary,
            hud_primary=hud_primary,
        )
    )

    image_keys = {
        "player": "player.svg",
        "enemy": "enemy.svg",
        "elite": "elite.svg",
        "boost": "boost.svg",
        "ring": "ring.svg",
        "hazard": "hazard.svg",
        "trail": "trail.svg",
        "hud_frame": "hud-frame.svg",
        "track_grid": "track-grid.svg",
        "impact_flare": "impact-flare.svg",
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
            "decal_layers",
        ],
        "asset_pipeline": {
            "automated": True,
            "source": "builtin_svg_asset_pipeline",
            "profile": str((art_direction_contract or {}).get("asset_detail_tier", "enhanced")),
            "variant_count": len(enriched_variants),
            "selected_variant": str(selected_variant.get("id", "baseline-balanced")),
            "selected_theme": str(selected_variant.get("theme", "balanced")),
            "selected_score": _to_float(selected_variant.get("score", 0.0), 0.0),
            "selected_composed_score": _to_float(selected_variant.get("composed_score", selected_variant.get("score", 0.0)), 0.0),
            "selected_memory_bonus": _to_float(selected_variant.get("memory_bonus", 0.0), 0.0),
            "steps": [
                "derive_contract",
                "retrieve_prior_signals",
                "sample_visual_variants",
                "score_readability_contrast",
                "compose_variant_with_memory",
                "select_best_variant",
                "compile_svg_pack",
            ],
            "candidates": [
                {
                    "id": str(row.get("id", f"variant-{index + 1}")),
                    "theme": str(row.get("theme", "balanced")),
                    "score": _to_float(row.get("score", 0.0), 0.0),
                    "memory_bonus": _to_float(row.get("memory_bonus", 0.0), 0.0),
                    "composed_score": _to_float(row.get("composed_score", row.get("score", 0.0)), 0.0),
                }
                for index, row in enumerate(enriched_variants)
            ],
            "retriever": {
                "enabled": bool(preferred_variant_id or preferred_theme or failure_reasons or failure_tokens),
                "source": str(retrieval.get("source", "pipeline_logs_v1") or "pipeline_logs_v1"),
                "preferred_variant_id": preferred_variant_id or None,
                "preferred_variant_theme": preferred_theme or None,
                "failure_reasons": sorted(failure_reasons),
                "failure_tokens": sorted(failure_tokens),
                "sample_size": _to_int(retrieval.get("sample_size", 0), fallback=0),
            },
        },
        "contract": {
            "min_image_assets": 5,
            "min_render_layers": 4,
            "min_animation_hooks": 3,
            "min_procedural_layers": 3,
        },
    }
    return artifact_files, asset_manifest
