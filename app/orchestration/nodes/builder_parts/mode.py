from __future__ import annotations

import re


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "untitled-game"


def _is_safe_slug(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value))


def _contains_any(haystack: str, tokens: tuple[str, ...]) -> bool:
    return any(token in haystack for token in tokens)


def _infer_core_loop_profile(*, keyword: str, title: str, genre: str) -> dict[str, object]:
    haystack = " ".join([keyword, title, genre]).casefold()
    explicit_rules: tuple[tuple[str, tuple[str, ...], str], ...] = (
        (
            "f1_formula_circuit_3d",
            (
                "f1",
                "formula 1",
                "formula-one",
                "포뮬러",
                "grand prix",
                "그랑프리",
                "circuit race",
                "circuit racing",
                "formula racing",
            ),
            "explicit_formula_tokens",
        ),
        (
            "flight_sim_3d",
            (
                "비행기",
                "비행 시뮬",
                "항공기",
                "flight sim",
                "flight simulator",
                "aircraft",
                "pilot",
                "cockpit",
                "dogfight",
            ),
            "explicit_flight_tokens",
        ),
        (
            "topdown_roguelike_shooter",
            (
                "탑뷰",
                "탑다운",
                "로그라이크",
                "roguelike",
                "top-down",
                "topdown",
                "dungeon",
                "판타지 슈팅",
            ),
            "explicit_topdown_tokens",
        ),
        (
            "comic_action_brawler_3d",
            (
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
            ),
            "explicit_3d_brawler_tokens",
        ),
        (
            "webgl_three_runner",
            (
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
            ),
            "explicit_webgl_tokens",
        ),
    )
    for core_loop_type, tokens, reason in explicit_rules:
        if _contains_any(haystack, tokens):
            return {
                "core_loop_type": core_loop_type,
                "confidence": 0.99,
                "reason": reason,
            }

    capability_tokens: dict[str, tuple[str, ...]] = {
        "is_3d": ("3d", "풀3d", "풀 3d", "입체", "first-person", "first person", "fps", "tps", "3인칭", "third person"),
        "is_racing": ("레이싱", "레이스", "드리프트", "racing", "race", "car", "circuit", "lap"),
        "is_flight": ("flight", "비행", "pilot", "aircraft", "cockpit", "dogfight"),
        "is_shooter": ("슈팅", "사격", "총", "shooter", "shoot", "bullet", "fps"),
        "is_brawler": ("격투", "파이터", "권투", "복싱", "fight", "fighting", "brawler", "brawl", "boxing", "sumo", "근접"),
        "is_topdown": ("탑뷰", "탑다운", "top-down", "topdown"),
        "is_roguelike": ("로그라이크", "roguelike", "dungeon"),
        "is_runner": ("runner", "outrun", "질주", "sprint"),
    }
    capabilities: dict[str, bool] = {
        key: _contains_any(haystack, tokens)
        for key, tokens in capability_tokens.items()
    }

    scores: dict[str, float] = {
        "f1_formula_circuit_3d": 0.0,
        "flight_sim_3d": 0.0,
        "webgl_three_runner": 0.0,
        "topdown_roguelike_shooter": 0.0,
        "comic_action_brawler_3d": 0.0,
        "lane_dodge_racer": 0.0,
        "arena_shooter": 0.0,
        "duel_brawler": 0.0,
        "request_faithful_generic": 0.55,
    }
    if capabilities["is_racing"]:
        scores["lane_dodge_racer"] += 2.2
        scores["webgl_three_runner"] += 2.0
    if capabilities["is_flight"]:
        scores["flight_sim_3d"] += 3.6
    if capabilities["is_shooter"]:
        scores["arena_shooter"] += 2.8
        scores["topdown_roguelike_shooter"] += 1.2
    if capabilities["is_brawler"]:
        scores["duel_brawler"] += 2.6
        scores["comic_action_brawler_3d"] += 1.8
    if capabilities["is_topdown"]:
        scores["topdown_roguelike_shooter"] += 2.8
    if capabilities["is_roguelike"]:
        scores["topdown_roguelike_shooter"] += 1.8
    if capabilities["is_runner"]:
        scores["webgl_three_runner"] += 1.2
        scores["lane_dodge_racer"] += 0.8
    if capabilities["is_3d"]:
        scores["flight_sim_3d"] += 0.8
        scores["webgl_three_runner"] += 1.4
        scores["comic_action_brawler_3d"] += 2.0
        scores["lane_dodge_racer"] -= 0.3
        scores["duel_brawler"] -= 0.4

    ranked = sorted(scores.items(), key=lambda row: row[1], reverse=True)
    selected_loop, selected_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    score_gap = max(0.0, selected_score - second_score)
    confidence = min(0.95, max(0.35, 0.45 + (score_gap * 0.15)))

    if selected_loop in {"lane_dodge_racer", "duel_brawler"} and capabilities["is_3d"]:
        selected_loop = "webgl_three_runner" if selected_loop == "lane_dodge_racer" else "comic_action_brawler_3d"
        confidence = max(confidence, 0.72)

    return {
        "core_loop_type": selected_loop,
        "confidence": round(confidence, 2),
        "reason": "capability_routing",
        "capabilities": capabilities,
    }


def _infer_core_loop_type(*, keyword: str, title: str, genre: str) -> str:
    profile = _infer_core_loop_profile(keyword=keyword, title=title, genre=genre)
    return str(profile.get("core_loop_type", "request_faithful_generic"))


def _build_request_capability_hint(*, keyword: str, title: str, genre: str) -> str:
    profile = _infer_core_loop_profile(keyword=keyword, title=title, genre=genre)
    capabilities = profile.get("capabilities")
    active_flags: list[str] = []
    if isinstance(capabilities, dict):
        for key, value in capabilities.items():
            if bool(value):
                active_flags.append(key)
    active = ", ".join(active_flags[:8]) if active_flags else "no-explicit-capability-token"
    return (
        f"Requested intent: {keyword}. "
        f"Detected capability flags: {active}. "
        "If the exact genre stack is unsupported, preserve requested fantasy and camera/interaction intent instead of collapsing to simple rectangles."
    )


def _synthesize_genre_profile(
    *,
    keyword: str,
    title: str,
    genre: str,
    core_loop_profile: dict[str, object] | None = None,
) -> dict[str, object]:
    profile = core_loop_profile if isinstance(core_loop_profile, dict) else _infer_core_loop_profile(keyword=keyword, title=title, genre=genre)
    core_loop_type = str(profile.get("core_loop_type", "request_faithful_generic"))
    capabilities = profile.get("capabilities")
    typed_capabilities = capabilities if isinstance(capabilities, dict) else {}
    haystack = " ".join([keyword, title, genre]).casefold()

    camera_model = "third_person"
    if _contains_any(haystack, ("1인칭", "first-person", "first person", "fps", "cockpit")):
        camera_model = "first_person"
    elif bool(typed_capabilities.get("is_topdown")):
        camera_model = "top_down"
    elif core_loop_type == "flight_sim_3d":
        camera_model = "cockpit_or_chase"

    interaction_model = "request_driven_action"
    if bool(typed_capabilities.get("is_racing")):
        interaction_model = "vehicle_control"
    elif bool(typed_capabilities.get("is_flight")):
        interaction_model = "flight_control"
    elif bool(typed_capabilities.get("is_shooter")) and bool(typed_capabilities.get("is_brawler")):
        interaction_model = "hybrid_shoot_melee"
    elif bool(typed_capabilities.get("is_shooter")):
        interaction_model = "ranged_combat"
    elif bool(typed_capabilities.get("is_brawler")):
        interaction_model = "melee_combat"

    world_style = "request_native"
    if _contains_any(haystack, ("cyber", "사이버", "네온", "neon", "sci-fi", "sf")):
        world_style = "sci_fi_neon"
    elif _contains_any(haystack, ("fantasy", "판타지", "마법")):
        world_style = "fantasy"
    elif _contains_any(haystack, ("military", "현대전", "전술", "tactical")):
        world_style = "tactical"
    elif _contains_any(haystack, ("horror", "공포")):
        world_style = "horror"

    pillars: list[str] = []
    if bool(typed_capabilities.get("is_3d")):
        pillars.append("3d_spatial_readability")
    if interaction_model == "vehicle_control":
        pillars.extend(["speed_control_curve", "corner_or_obstacle_mastery"])
    elif interaction_model == "flight_control":
        pillars.extend(["pitch_roll_yaw_feedback", "air_route_precision"])
    elif interaction_model == "ranged_combat":
        pillars.extend(["enemy_pressure_patterns", "aim_and_positioning_loop"])
    elif interaction_model == "melee_combat":
        pillars.extend(["combo_and_counter_timing", "spacing_and_recovery"])
    elif interaction_model == "hybrid_shoot_melee":
        pillars.extend(["stance_switch_readability", "ranged_to_melee_transition"])
    else:
        pillars.extend(["reactive_core_loop", "clear_risk_reward_feedback"])
    if bool(typed_capabilities.get("is_roguelike")):
        pillars.append("run_based_progression")
    if not pillars:
        pillars.append("core_loop_clarity")

    non_negotiables = [
        "no_rectangle_placeholder_only_visuals",
        "stable_embedded_iframe_runtime",
        "playable_loop_with_clear_fail_and_restart",
    ]
    if bool(typed_capabilities.get("is_3d")):
        non_negotiables.append("maintain_3d_depth_cues_and_camera_identity")
    if bool(typed_capabilities.get("is_shooter")):
        non_negotiables.append("projectile_and_hit_feedback_clarity")
    if bool(typed_capabilities.get("is_brawler")):
        non_negotiables.append("impactful_melee_contact_feedback")

    profile_label = str(genre).strip() or "hybrid"
    profile_id = _slugify(f"{profile_label}-{core_loop_type}-{world_style}")
    return {
        "profile_id": profile_id,
        "core_loop_type": core_loop_type,
        "camera_model": camera_model,
        "interaction_model": interaction_model,
        "world_style": world_style,
        "pillars": pillars[:6],
        "non_negotiables": non_negotiables[:8],
        "confidence": float(profile.get("confidence", 0.45)),
    }


def _build_generated_genre_directive(
    *,
    keyword: str,
    title: str,
    genre: str,
    genre_profile: dict[str, object] | None = None,
) -> str:
    profile = genre_profile if isinstance(genre_profile, dict) else _synthesize_genre_profile(keyword=keyword, title=title, genre=genre)
    pillars = profile.get("pillars")
    typed_pillars = [str(item).strip() for item in pillars] if isinstance(pillars, list) else []
    required_rules = profile.get("non_negotiables")
    typed_rules = [str(item).strip() for item in required_rules] if isinstance(required_rules, list) else []
    return (
        f"Auto-generated genre profile ({profile.get('profile_id', 'dynamic-profile')}): "
        f"camera={profile.get('camera_model', 'third_person')}, "
        f"interaction={profile.get('interaction_model', 'request_driven_action')}, "
        f"style={profile.get('world_style', 'request_native')}. "
        f"Gameplay pillars: {', '.join(typed_pillars[:4]) if typed_pillars else 'core_loop_clarity'}. "
        f"Non-negotiables: {', '.join(typed_rules[:5]) if typed_rules else 'stable_runtime'}. "
        "If exact genre implementation is unavailable, synthesize the closest playable interpretation while preserving requested fantasy and control identity."
    )


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
            "Variant E: simulation-forward blend prioritizing believable handling and progressive mastery depth.",
        ],
        "webgl_three_runner": [
            "Variant A: ultra-fast neon sprint with aggressive traffic and boost-chain risk/reward.",
            "Variant B: technical drift line with sharper corner pressure and stricter recovery windows.",
            "Variant C: endurance outrun loop with escalating depth speed and combo streak scoring.",
            "Variant D: cinematic sunset highway run with moderate pace and dense late-wave threats.",
            "Variant E: precision sprint with high readability, low randomness, and skill expression focus.",
        ],
        "topdown_roguelike_shooter": [
            "Variant A: high-mobility dash shooter with aggressive close-range swarms and fast tactical resets.",
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
            "Variant E: flashy cinematic beat-em-up loop prioritizing readable impact feedback.",
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
        "request_faithful_generic": [
            "Variant A: request-faithful action loop with high responsiveness and clear visual intent.",
            "Variant B: request-faithful tactical loop with stronger telegraphs and deliberate pacing.",
            "Variant C: request-faithful progression loop with reward multipliers for execution mastery.",
            "Variant D: request-faithful endurance loop with escalating pressure and adaptation windows.",
            "Variant E: request-faithful balanced loop prioritizing readability while preserving fantasy identity.",
        ],
    }
    hints = list(presets.get(core_loop_type, presets["request_faithful_generic"]))
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
