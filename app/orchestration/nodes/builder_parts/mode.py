from __future__ import annotations

import re


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
            "f1",
            "formula 1",
            "formula-one",
            "포뮬러",
            "formula",
            "grand prix",
            "그랑프리",
            "circuit race",
            "circuit racing",
            "formula racing",
        )
    ):
        return "f1_formula_circuit_3d"
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
        for token in (
            "코믹액션",
            "코믹 액션",
            "comic action",
            "beat em up",
            "3d 액션",
            "3d brawler",
            "풀3d 격투",
            "풀 3d 격투",
            "3d 격투",
            "3d 파이터",
            "3d fighter",
            "3d fighting",
            "full 3d fighting",
            "full3d fighting",
            "arena fighter",
            "arena brawler",
        )
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
        "f1_formula_circuit_3d": [
            "Variant A: high-downforce technical circuit emphasizing braking zones and apex precision.",
            "Variant B: high-speed street circuit with narrower margins and aggressive overtakes.",
            "Variant C: endurance grand-prix loop balancing tire heat management with late-lap push.",
            "Variant D: rain-threat circuit pacing with unstable grip windows and recovery-focused handling.",
            "Variant E: balanced modern F1 feel prioritizing smooth steering response and clean racing lines.",
        ],
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
