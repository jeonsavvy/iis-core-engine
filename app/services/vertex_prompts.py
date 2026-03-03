from __future__ import annotations

import json
from typing import Any


def build_analyze_contract_prompt(keyword: str) -> str:
    return (
        "You are a principal game producer. Return JSON only.\n"
        f"Keyword: {keyword}\n"
        "Build an execution contract for downstream agents.\n"
        "Output fields exactly: intent, scope_in, scope_out, hard_constraints, forbidden_patterns, success_outcome.\n"
        "Rules:\n"
        "- scope_in/out should be concise actionable lists\n"
        "- hard_constraints must include platform/runtime constraints\n"
        "- forbidden_patterns must include anti-patterns that degrade game quality\n"
        "- success_outcome should define player-facing completion quality"
    )


def build_plan_contract_prompt(
    *,
    keyword: str,
    gdd: dict[str, Any],
    research_summary: dict[str, Any] | None = None,
) -> str:
    gdd_json = json.dumps(gdd, ensure_ascii=False)
    research_json = json.dumps(research_summary or {}, ensure_ascii=False)
    return (
        "You are a senior gameplay planner. Return JSON only.\n"
        f"Keyword: {keyword}\n"
        f"GDD JSON: {gdd_json}\n"
        f"ResearchSummary JSON: {research_json}\n"
        "Output fields exactly: core_mechanics, progression_plan, encounter_plan, risk_reward_plan, control_model, balance_baseline.\n"
        "Rules:\n"
        "- Every list must contain concrete player-action oriented items\n"
        "- balance_baseline must contain numeric values (hp/speed/spawn/timer scale etc.)\n"
        "- avoid generic filler statements"
    )


def build_design_contract_prompt(
    *,
    keyword: str,
    genre: str,
    visual_style: str,
    design_spec: dict[str, Any],
) -> str:
    design_json = json.dumps(design_spec, ensure_ascii=False)
    return (
        "You are a principal game art director. Return JSON only.\n"
        f"Keyword: {keyword}\n"
        f"Genre: {genre}\n"
        f"VisualStyle: {visual_style}\n"
        f"DesignSpec JSON: {design_json}\n"
        "Output fields exactly: camera_ui_contract, asset_blueprint_2d3d, scene_layers, feedback_fx_contract, readability_contract.\n"
        "Rules:\n"
        "- asset_blueprint_2d3d must include reusable 2D/3D asset categories\n"
        "- scene_layers must describe layered visual composition\n"
        "- readability_contract must include player/enemy/projectile readability requirements"
    )


def build_gdd_prompt(keyword: str) -> str:
    return (
        "You are a principal game designer for high-quality browser games. "
        "Return JSON only.\n"
        "Create a compact but production-usable GDD for an AI-generated browser game.\n"
        f"Keyword: {keyword}\n"
        "Constraints:\n"
        "- genre should be a concise free-form tag that matches gameplay fantasy (e.g., formula-racing-3d, arena-shooter)\n"
        "- objective must define an actionable session target; allowed range is 120~1200 seconds when fantasy requires depth\n"
        "- visual_style should be concise (e.g., neon-minimal, pixel-retro)\n"
        "- references should be 3 short reference ideas (strings)\n"
        "- research_intent should explain what references target\n"
        "- title should preserve the spirit of the keyword and feel marketable\n"
        "- objective should imply clear win/lose pressure, not only idle score clicking\n"
        "- prefer mechanics with movement, timing, dodging, aiming, combo, or enemy pressure\n"
        "- avoid concepts that collapse into a single button increment toy\n"
        "Design quality bar:\n"
        "- The player must have a meaningful verb loop (move/aim/attack/evade/collect)\n"
        "- The fantasy implied by the keyword should be visible in the core loop\n"
        "- The game should be understandable quickly, then sustain depth across requested pacing (do not force short-session arcade cadence)\n"
        "- If keyword implies simulation/strategy/story/immersive pacing, keep that pacing instead of converting to twitch-arcade loop\n"
        "- If keyword implies Formula/F1/circuit racing, include lap/checkpoint/overtake/braking-line fantasy explicitly\n"
    )


def build_design_prompt(*, keyword: str, visual_style: str, genre: str) -> str:
    return (
        "You are a senior game UI/UX and visual direction stylist for web games. "
        "Return JSON only.\n"
        f"Keyword: {keyword}\n"
        f"Genre: {genre}\n"
        f"Requested visual style: {visual_style}\n"
        "Output fields exactly: visual_style, palette (list of hex colors), hud, viewport_width, "
        "viewport_height, safe_area_padding, min_font_size_px, text_overflow_policy, typography, thumbnail_concept.\n"
        "Constraints:\n"
        "- viewport_width: 960~1600\n"
        "- viewport_height: 540~900\n"
        "- safe_area_padding: 8~40\n"
        "- min_font_size_px: 12~20\n"
        "- text_overflow_policy: one short token like ellipsis-clamp\n"
        "- palette must have 4 colors\n"
        "Quality bar:\n"
        "- Prioritize gameplay readability over decoration (enemy/projectile/player contrast)\n"
        "- HUD must communicate score + timer/HP/round at a glance\n"
        "- Visual style should match keyword fantasy, not generic dark UI only\n"
        "- Thumbnail concept should describe a dynamic action moment with clear focal point\n"
    )


def build_builder_prompt(
    *,
    keyword: str,
    title: str,
    genre: str,
    objective: str,
    design_spec: dict[str, Any],
    variation_hint: str | None = None,
) -> str:
    spec_json = json.dumps(design_spec, ensure_ascii=False)
    variation_section = ""
    if variation_hint and variation_hint.strip():
        variation_section = (
            f"Variation hint: {variation_hint.strip()}\n"
            "Apply this variation to pacing/risk/reward so that candidates are meaningfully different.\n"
        )
    return (
        "You are a master game balancer and level designer for high-quality web games. "
        "Return JSON only.\n"
        f"Keyword: {keyword}\n"
        f"Title: {title}\n"
        f"Genre: {genre}\n"
        f"Objective: {objective}\n"
        f"DesignSpec JSON: {spec_json}\n\n"
        f"{variation_section}"
        "Based on the game's theme, objective, and pace, provide a fine-tuned configuration JSON "
        "that defines the balance and mechanics of the game. Output fields exactly according to the schema:\n"
        "- player_hp: integer (e.g. 1 to 5, default 3)\n"
        "- player_speed: integer (e.g. 150 to 400, default 240)\n"
        "- player_attack_cooldown: float (e.g. 0.2 to 1.5, default 0.5)\n"
        "- enemy_hp: integer (e.g. 1 to 20, default 1)\n"
        "- enemy_speed_min: integer (e.g. 50 to 150, default 100)\n"
        "- enemy_speed_max: integer (e.g. 150 to 300, default 220)\n"
        "- enemy_spawn_rate: float (sec between spawns, e.g. 0.3 to 2.0, default 1.0)\n"
        "- time_limit_sec: integer (e.g. 30 to 120, default 60)\n"
        "- base_score_value: integer (e.g. 10 to 100, default 10)\n\n"
        "Quality bar:\n"
        "- If the game is a fast-paced racing game, increase speeds and lower HP.\n"
        "- Do not make runs fail instantly: avoid zero/near-zero survivability tuning on initial spawn.\n"
        "- For racing/flight/3D keywords, prefer hp >= 2 and time_limit_sec >= 75 unless keyword explicitly asks hardcore.\n"
        "- The first 3 seconds must be playable without unavoidable collision.\n"
        "- If keyword implies Formula/F1/circuit racing, emphasize braking windows, lap progression, and overtake chain risk/reward.\n"
        "- If the game is a brawl, increase enemy HP and adjust attack cooldowns.\n"
        "- Preserve analog control headroom (no quantized one-step movement assumptions).\n"
        "- Prefer procedural scene layering (parallax/depth/particles) over bitmap dependency.\n"
        "- Ensure wave escalation + miniboss cadence + relic synergy potential can emerge from numeric tuning.\n"
        "- Ensure values provide a fair but challenging experience aligned with the requested pacing and fantasy (not forced arcade rhythm)."
    )


def build_marketing_copy_prompt(*, keyword: str, display_name: str, genre: str) -> str:
    return (
        f"게임 이름은 '{display_name}', 장르는 '{genre}', 키워드는 '{keyword}'입니다. "
        "한국어(ko-KR)로 1~2문장 분량의 게임 디자이너 코멘트 겸 홍보 문구를 작성하세요. "
        "과장된 표현은 피하고 실제 플레이 감각(조작/목표/긴장감)을 담아주세요. "
        "이모지 1~2개와 #indiegame #html5 해시태그를 포함하고, 오직 문구 텍스트만 반환하세요."
    )


def build_ai_review_prompt(*, keyword: str, game_name: str, genre: str, objective: str) -> str:
    return (
        f"게임 이름: {game_name}\n"
        f"장르: {genre}\n"
        f"키워드: {keyword}\n"
        f"목표: {objective}\n\n"
        "한국어(ko-KR)로 'AI 게임 디자이너 코멘트'를 작성하세요.\n"
        "- 해시태그/이모지/광고문구 금지\n"
        "- 2~3개 핵심 포인트를 문장형으로 작성\n"
        "- 구체적으로: 핵심 플레이 루프, 난이도/리듬, 시각/연출 방향\n"
        "- 최대 240자\n"
        "코멘트 텍스트만 반환하세요."
    )


def build_grounded_ai_review_prompt(
    *,
    keyword: str,
    game_name: str,
    genre: str,
    objective: str,
    evidence: dict[str, Any],
) -> str:
    evidence_json = json.dumps(evidence, ensure_ascii=False)
    return (
        f"게임 이름: {game_name}\n"
        f"장르: {genre}\n"
        f"키워드: {keyword}\n"
        f"목표: {objective}\n"
        f"근거 데이터(JSON): {evidence_json}\n\n"
        "당신은 과장 없이 사실 기반으로 쓰는 게임 디자인 리뷰어입니다.\n"
        "출력 규칙:\n"
        "- 한국어(ko-KR) 문장 2~4개\n"
        "- 근거 데이터에 없는 기능(예: 풀3D 물리/콕핏/멀티플레이)을 절대 주장하지 말 것\n"
        "- 플레이 루프 1개, 난이도/리듬 1개, 시각/피드백 1개를 포함\n"
        "- 실패/한계가 있으면 명시\n"
        "- 해시태그/이모지 금지\n"
        "코멘트 텍스트만 반환하세요."
    )


def build_codegen_prompt(
    *,
    keyword: str,
    title: str,
    genre: str,
    objective: str,
    core_loop_type: str,
    runtime_engine_mode: str,
    variation_hint: str,
    design_spec: dict[str, Any],
    asset_pack: dict[str, Any],
    html_content: str,
) -> str:
    design_spec_json = json.dumps(design_spec, ensure_ascii=False)
    asset_pack_json = json.dumps(asset_pack, ensure_ascii=False)
    lowered_engine_mode = str(runtime_engine_mode).strip().casefold()
    runtime_stack = "phaser.js" if lowered_engine_mode == "2d_phaser" else "three.js"
    return (
        "You are a senior web game engineer. Rewrite and deepen this game artifact.\n"
        "Generation policy:\n"
        "- This is a single-pass full generation. Produce complete gameplay/runtime quality in one response.\n"
        "- Do not rely on follow-up refinement loops.\n"
        f"- Runtime stack for this task is fixed: {runtime_stack}. Do not switch frameworks.\n"
        "Hard constraints:\n"
        "- Return one complete HTML document only.\n"
        "- Keep leaderboard contract (`window.IISLeaderboard`) and boot flag (`window.__iis_game_boot_ok`).\n"
        "- Keep safe-area / overflow-readability guard behavior.\n"
        "- Preserve requested fantasy and pacing; do not collapse to generic arcade wave-survival.\n"
        "- Keep keyboard controls and restart flow.\n"
        "- Implement the requested core loop mode faithfully.\n"
        "- Asset policy is procedural_threejs_first: prefer procedural visuals and internal vector sprites.\n"
        "- Do not rely on external image generation services or remote image URLs.\n"
        "- Do not regress to flat placeholder rectangle-only visuals; keep at least 3 visual layers.\n"
        "- Movement and steering must remain analog/time-based; avoid one-step quantized control.\n"
        "- Keep encounter/progression systems visible for the requested genre.\n"
        "- Artifact must run correctly inside an embedded iframe (no popup/new-tab dependency for controls).\n"
        "- Do not rely on same-origin iframe privileges (avoid direct use of localStorage/sessionStorage/cookie without guards).\n"
        "- Auto-start gameplay loop on load; avoid click/tap-to-start gates that block smoke/runtime input probes.\n"
        "- Avoid layout overflow that introduces document scrollbars in default 16:9 stage.\n"
        "- Prevent unavoidable game-over during the first 3 seconds after restart.\n"
        "- Keep HUD concise and player-facing. Do not expose debug/meta jargon.\n"
        "- Do not output markdown fences.\n\n"
        "Quality target (compact contract):\n"
        "- Playable immediately in iframe and stable for smoke/runtime probes.\n"
        "- Clear core mechanic + progression loop + failure/restart loop.\n"
        "- Distinct foreground/midground/background visual separation.\n"
        "- Meaningful feedback (impact, motion, HUD readability) and no dead controls.\n"
        "- Keep implementation concrete and production-grade, not toy/demo placeholders.\n\n"
        f"Keyword: {keyword}\n"
        f"Title: {title}\n"
        f"Genre: {genre}\n"
        f"Objective: {objective}\n"
        f"Core loop mode: {core_loop_type}\n"
        f"Variation: {variation_hint}\n"
        f"DesignSpec: {design_spec_json}\n"
        f"AssetPack: {asset_pack_json}\n\n"
        "Improve gameplay depth by adding clearer mechanics, readable telegraphs, and richer game feel.\n"
        "Preserve compatibility with plain browser runtime (no external npm imports).\n\n"
        "Original HTML:\n"
        f"{html_content}"
    )


def build_polish_prompt(*, keyword: str, title: str, genre: str, html_content: str) -> str:
    return (
        "You are a senior HTML5 game polish engineer.\n"
        "Improve this single-file browser game for stronger visual quality and game-feel.\n"
        "Generation policy: keep this as a single-pass optional rescue. Do not assume iterative polish loops.\n"
        "Hard constraints:\n"
        "- Keep one complete HTML document.\n"
        "- Preserve all existing gameplay rules and controls.\n"
        "- Keep framework contract strict: 3D runtime must stay Three.js, 2D runtime must stay Phaser.js.\n"
        "- Preserve leaderboard contract and `window.__iis_game_boot_ok`.\n"
        "- Keep responsive/safe-area/readability rules.\n"
        "- Preserve requested genre fantasy and pacing; do not simplify into generic arcade loop during polish.\n"
        "- Keep procedural_threejs_first asset policy: improve via procedural rendering layers, not external generated image dependencies.\n"
        "- Keep primitive fillRect-only rendering under 35% of total draw operations; add path/gradient/sprite richness.\n"
        "- Preserve at least 3 visual layers and 4 distinct gameplay silhouettes after polish.\n"
        "- Keep analog control smoothness; never convert movement into one-step lane snapping.\n"
        "- Keep encounter systems (wave/miniboss/events) functional and visible.\n"
        "- The game must boot and be playable directly in embedded iframe without requiring popup/new-tab context.\n"
        "- Do not require same-origin iframe APIs; guard storage/cookie access.\n"
        "- Keep the game loop auto-started; do not require click/tap before controls work.\n"
        "- Avoid document-level scrollbars in the runtime scene; main gameplay should fit the viewport shell.\n"
        "- Avoid unavoidable death in the first 3 seconds after restart.\n"
        "- Remove generic genre label text from top HUD copy.\n"
        "- Keep HUD text concise and player-facing only. Never expose Lv/W/XP/Relic/Syn/Build style jargon.\n"
        "- Return only the final HTML text (no markdown fences).\n\n"
        f"Game title: {title}\n"
        f"Keyword: {keyword}\n"
        f"Genre: {genre}\n\n"
        "Focus improvements:\n"
        "- clearer silhouette/readability\n"
        "- stronger feedback VFX/juice\n"
        "- richer background motion/parallax\n"
        "- cleaner HUD polish\n\n"
        "Original HTML:\n"
        f"{html_content}"
    )
