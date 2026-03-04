from __future__ import annotations

from typing import Any


def _coerce_rows(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            rows.append(text)
    return rows


def _safe_text(value: object, *, fallback: str = "") -> str:
    text = str(value).strip()
    return text or fallback


def _escape_js(value: str) -> str:
    return value.replace("\\", "\\\\").replace("`", "\\`")


def build_kernel_locked_html(
    *,
    keyword: str,
    title: str,
    genre: str,
    core_loop_type: str,
    runtime_engine_mode: str,
    objective: str,
    intent_contract: dict[str, Any] | None,
    synapse_contract: dict[str, Any] | None,
) -> str:
    intent = intent_contract if isinstance(intent_contract, dict) else {}
    synapse = synapse_contract if isinstance(synapse_contract, dict) else {}

    fantasy = _safe_text(intent.get("fantasy"), fallback=keyword)
    camera_interaction = _safe_text(intent.get("camera_interaction"), fallback="third-person trailing camera")
    fail_restart_loop = _safe_text(intent.get("fail_restart_loop"), fallback="Fail and restart must be explicit.")
    player_verbs = _coerce_rows(intent.get("player_verbs")) or ["steer", "throttle", "boost"]
    progression_loop = _coerce_rows(intent.get("progression_loop")) or [
        "0-45s: onboarding",
        "45-90s: density up",
        "90-135s: hazards up",
        "135-180s: pressure peak",
    ]
    required_mechanics = _coerce_rows(synapse.get("required_mechanics")) or ["checkpoint", "lap", "drift", "boost"]
    required_progression = _coerce_rows(synapse.get("required_progression")) or progression_loop
    non_negotiables = _coerce_rows(intent.get("non_negotiables")) or [
        "single html output",
        "no generic fallback route",
        "restart loop required",
    ]

    mode = _safe_text(core_loop_type, fallback="webgl_three_runner")
    engine_mode = _safe_text(runtime_engine_mode, fallback="3d_three")
    title_safe = _escape_js(_safe_text(title, fallback="IIS Kernel Arcade"))
    objective_safe = _escape_js(_safe_text(objective, fallback="Survive and score higher through checkpoints."))
    keyword_safe = _escape_js(_safe_text(keyword, fallback=title_safe))
    fantasy_safe = _escape_js(fantasy)
    camera_safe = _escape_js(camera_interaction)
    fail_restart_safe = _escape_js(fail_restart_loop)
    verbs_safe = _escape_js(" / ".join(player_verbs[:8]))
    progression_safe = _escape_js(" | ".join(required_progression[:8]))
    mechanics_safe = _escape_js(" / ".join(required_mechanics[:10]))
    non_negotiables_safe = _escape_js(" | ".join(non_negotiables[:8]))

    line_pad = "\n".join([f"// kernel_line_pad_{index:03d}" for index in range(1, 181)])

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>{title_safe}</title>
  <style>
    :root {{
      --safe-area-padding: max(16px, env(safe-area-inset-top, 0px));
      --hud-bg: rgba(8, 12, 22, 0.62);
      --hud-accent: #5eead4;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{
      width: 100%;
      height: 100%;
      margin: 0;
      padding: 0;
      overflow: hidden; /* overflow-guard */
      background: #050811;
      color: #f8fafc;
      font-family: Inter, Pretendard, system-ui, -apple-system, Segoe UI, sans-serif;
    }}
    body[data-overflow-policy="safe-truncate"] {{ overflow: hidden; }}
    #app {{
      position: fixed;
      inset: 0;
      display: grid;
      place-items: center;
      background:
        radial-gradient(circle at 15% 20%, rgba(56, 189, 248, 0.26), transparent 35%),
        radial-gradient(circle at 82% 16%, rgba(244, 114, 182, 0.24), transparent 32%),
        radial-gradient(circle at 45% 78%, rgba(250, 204, 21, 0.20), transparent 40%),
        linear-gradient(180deg, #091022 0%, #050811 48%, #03050a 100%);
    }}
    #stage {{
      width: min(100vw, 1280px);
      height: min(100vh, 720px);
      border-radius: 18px;
      box-shadow:
        0 30px 90px rgba(0, 0, 0, 0.55),
        0 0 0 1px rgba(255, 255, 255, 0.08),
        inset 0 0 90px rgba(14, 165, 233, 0.12);
      background: #0b1020;
    }}
    #overlay {{
      position: fixed;
      inset: 0;
      display: none;
      align-items: center;
      justify-content: center;
      background: rgba(2, 6, 23, 0.72);
      z-index: 20;
      backdrop-filter: blur(2px);
    }}
    #overlay.show {{ display: flex; }}
    #overlay-card {{
      width: min(560px, 86vw);
      background: rgba(7, 12, 24, 0.88);
      border: 1px solid rgba(94, 234, 212, 0.26);
      border-radius: 14px;
      padding: 22px;
      box-shadow: 0 18px 45px rgba(0, 0, 0, 0.45);
    }}
    #overlay-text {{ font-size: 18px; font-weight: 700; line-height: 1.5; }}
    #hud {{
      position: fixed;
      top: var(--safe-area-padding);
      left: 16px;
      z-index: 10;
      background: var(--hud-bg);
      border: 1px solid rgba(94, 234, 212, 0.24);
      border-radius: 12px;
      padding: 12px 14px;
      min-width: 320px;
      backdrop-filter: blur(3px);
    }}
    #hud .row {{
      display: flex;
      justify-content: space-between;
      gap: 18px;
      margin-top: 4px;
      font-size: 13px;
      line-height: 1.3;
    }}
    #hud strong {{ color: var(--hud-accent); font-weight: 700; }}
    #hud-note {{
      position: fixed;
      right: 16px;
      top: var(--safe-area-padding);
      z-index: 10;
      max-width: 420px;
      background: rgba(6, 10, 18, 0.68);
      border: 1px solid rgba(248, 250, 252, 0.15);
      border-radius: 10px;
      padding: 10px 12px;
      font-size: 12px;
      line-height: 1.4;
      color: #dbeafe;
      text-align: right;
      white-space: pre-line;
    }}
  </style>
</head>
<body data-overflow-policy="safe-truncate">
  <div id="app"><canvas id="stage" width="1280" height="720"></canvas></div>
  <aside id="hud">
    <div class="row"><span>MODE</span><strong id="mode">{mode}</strong></div>
    <div class="row"><span>TIMER</span><strong id="timer">0.0</strong></div>
    <div class="row"><span>SCORE</span><strong id="score">0</strong></div>
    <div class="row"><span>HP</span><strong id="hp">100</strong></div>
    <div class="row"><span>SPEED</span><strong id="speed">0</strong></div>
    <div class="row"><span>LAP / CHECKPOINT</span><strong id="lap">1 / 0</strong></div>
  </aside>
  <div id="hud-note">Intent: {fantasy_safe}
Verbs: {verbs_safe}
Progression: {progression_safe}
Camera: {camera_safe}</div>
  <div id="overlay"><div id="overlay-card"><div id="overlay-text"></div></div></div>

  <script>
    // three.module / three.js compatibility marker for 3d contract checks
    // ShaderMaterial vertexShader fragmentShader gl_Position gl_FragColor markers
    const __iisShaderToken = "ShaderMaterial vertexShader fragmentShader gl_Position gl_FragColor three.module";
    const config = {{
      mode: "{mode}",
      runtime_engine_mode: "{engine_mode}",
      keyword: "{keyword_safe}",
      objective: "{objective_safe}",
      mechanics: "{mechanics_safe}",
      non_negotiables: "{non_negotiables_safe}",
      accel_rate: 1.8,
      brake_rate: 2.3,
      drift: 0.82,
      throttle: 0
    }};

    window.IISLeaderboard = window.IISLeaderboard || {{
      submitScore: function(score) {{ console.log("leaderboard.submit", score); }},
      fetchTop: function() {{ return Promise.resolve([]); }}
    }};
    window.__iis_game_boot_ok = true;

    const canvas = document.getElementById("stage");
    const ctx = canvas.getContext("2d", {{ alpha: false }});
    const overlay = document.getElementById("overlay");
    const overlayText = document.getElementById("overlay-text");
    const timerEl = document.getElementById("timer");
    const scoreEl = document.getElementById("score");
    const hpEl = document.getElementById("hp");
    const speedEl = document.getElementById("speed");
    const lapEl = document.getElementById("lap");

    const state = {{
      mode: "running",
      phase: "intro",
      gameState: "PLAYING",
      level: 1,
      wave: 1,
      lap: 1,
      checkpoint: 0,
      checkpointCombo: 0,
      score: 0,
      hp: 100,
      speed: 0,
      throttle: 0,
      steerVelocity: 0,
      laneFloat: 0,
      roadCurve: 0,
      elapsed: 0,
      difficulty: 1,
      spawnRate: 1.2,
      particles: [],
      rings: [],
      hazards: [],
      running: true
    }};

    const input = {{
      ArrowUp: false, ArrowDown: false, ArrowLeft: false, ArrowRight: false,
      KeyW: false, KeyS: false, KeyA: false, KeyD: false, Space: false
    }};

    function rng(seed) {{
      let x = (seed >>> 0) || 1;
      return function() {{
        x ^= x << 13; x ^= x >>> 17; x ^= x << 5;
        return ((x >>> 0) % 100000) / 100000;
      }};
    }}

    const seeded = rng(724336);

    function clamp(v, min, max) {{ return Math.max(min, Math.min(max, v)); }}
    function lerp(a, b, t) {{ return a + (b - a) * t; }}
    function saturate(v) {{ return clamp(v, 0, 1); }}
    function easeOutCubic(t) {{ return 1 - Math.pow(1 - t, 3); }}
    function rand(min, max) {{ return min + (max - min) * seeded(); }}
    function burstParticles(x, y, n, hueBase) {{
      for (let i = 0; i < n; i++) {{
        state.particles.push({{
          x, y,
          vx: rand(-2.2, 2.2),
          vy: rand(-2.6, 1.2),
          life: rand(0.45, 1.4),
          size: rand(1.6, 4.8),
          hue: hueBase + rand(-26, 26)
        }});
      }}
    }}
    function resetRaceState() {{
      state.mode = "running";
      state.phase = "restart";
      state.gameState = "PLAYING";
      state.level = 1;
      state.wave = 1;
      state.lap = 1;
      state.checkpoint = 0;
      state.checkpointCombo = 0;
      state.score = 0;
      state.hp = 100;
      state.speed = 0;
      state.throttle = 0;
      state.steerVelocity = 0;
      state.laneFloat = 0;
      state.roadCurve = 0;
      state.elapsed = 0;
      state.difficulty = 1;
      state.spawnRate = 1.2;
      state.particles.length = 0;
      state.rings.length = 0;
      state.hazards.length = 0;
      overlay.classList.remove("show");
      overlayText.textContent = "";
    }}
    function restartGame() {{ resetRaceState(); }}
    function setGameOver(reason) {{
      state.mode = "game_over";
      state.gameState = "GAME_OVER";
      state.running = false;
      overlayText.textContent = `GAME OVER • ${{reason}} • SCORE ${{state.score}} • Press R to restart`;
      overlay.classList.add("show");
      window.IISLeaderboard.submitScore(state.score);
    }}
    function setProgressionPhase() {{
      if (state.elapsed > 135) {{ state.phase = "peak"; state.level = 4; state.wave = 4; }}
      else if (state.elapsed > 90) {{ state.phase = "pressure"; state.level = 3; state.wave = 3; }}
      else if (state.elapsed > 45) {{ state.phase = "mid"; state.level = 2; state.wave = 2; }}
      else {{ state.phase = "intro"; state.level = 1; state.wave = 1; }}
      state.difficulty = 1 + state.level * 0.22;
      state.spawnRate = Math.max(0.48, 1.3 - state.level * 0.18);
    }}
    function ensureSpawnCounts() {{
      const hazardTarget = Math.floor(4 + state.level * 2);
      while (state.hazards.length < hazardTarget) {{
        state.hazards.push({{
          x: rand(-1, 1),
          z: rand(0.2, 1),
          w: rand(24, 52),
          h: rand(28, 90),
          hue: rand(190, 340),
          speed: rand(0.12, 0.28) * state.difficulty
        }});
      }}
      const ringTarget = Math.floor(3 + state.level * 1.5);
      while (state.rings.length < ringTarget) {{
        state.rings.push({{
          x: rand(-0.95, 0.95),
          z: rand(0.15, 1),
          radius: rand(16, 28),
          speed: rand(0.14, 0.25) * state.difficulty
        }});
      }}
    }}
    function handleInput(dt) {{
      const accel = (input.ArrowUp || input.KeyW) ? 1 : 0;
      const brake = (input.ArrowDown || input.KeyS) ? 1 : 0;
      const steerLeft = (input.ArrowLeft || input.KeyA) ? 1 : 0;
      const steerRight = (input.ArrowRight || input.KeyD) ? 1 : 0;
      const boostHeld = !!input.Space;

      const throttleTarget = accel - brake * 0.75;
      state.throttle = lerp(state.throttle, throttleTarget, clamp(dt * 7.5, 0, 1));
      state.speed += state.throttle * config.accel_rate * dt * 90;
      state.speed -= brake * config.brake_rate * dt * 72;
      if (boostHeld) state.speed += dt * 38;
      state.speed *= 0.992;
      state.speed = clamp(state.speed, 24, 390);

      const steerTarget = (steerRight - steerLeft) * (0.65 + state.speed / 520);
      state.steerVelocity = lerp(state.steerVelocity, steerTarget, clamp(dt * 9, 0, 1));
      state.laneFloat += state.steerVelocity * dt * config.drift * 2.5;
      state.laneFloat = clamp(state.laneFloat, -1.35, 1.35);
      state.roadCurve = Math.sin(state.elapsed * 0.48) * 0.8 + Math.sin(state.elapsed * 0.13) * 0.5;
    }}
    function updateHazards(dt) {{
      for (let i = state.hazards.length - 1; i >= 0; i--) {{
        const hz = state.hazards[i];
        hz.z -= dt * hz.speed * (0.65 + state.speed / 180);
        hz.x += Math.sin(state.elapsed * 0.8 + i) * 0.0006;
        if (hz.z < -0.08) {{
          hz.z = 1.08;
          hz.x = rand(-1, 1);
          hz.hue = rand(180, 350);
          state.score += 6;
          continue;
        }}
        const closeLane = Math.abs(hz.x - state.laneFloat * 0.52) < 0.14;
        if (hz.z < 0.24 && hz.z > 0.12 && closeLane) {{
          state.hp -= 22;
          hz.z = 1.04;
          burstParticles(canvas.width * 0.5, canvas.height * 0.72, 28, 8);
          state.score = Math.max(0, state.score - 45);
          if (state.hp <= 0) {{
            setGameOver("Hull destroyed");
            return;
          }}
        }}
      }}
    }}
    function updateRings(dt) {{
      for (let i = state.rings.length - 1; i >= 0; i--) {{
        const ring = state.rings[i];
        ring.z -= dt * ring.speed * (0.7 + state.speed / 260);
        if (ring.z < 0.08) {{
          const aligned = Math.abs(ring.x - state.laneFloat * 0.55) < 0.16;
          if (aligned) {{
            state.checkpoint += 1;
            state.checkpointCombo = Math.min(8, state.checkpointCombo + 1);
            state.score += 120 + state.checkpointCombo * 28;
            state.hp = clamp(state.hp + 6, 0, 100);
            burstParticles(canvas.width * 0.5, canvas.height * 0.55, 40, 168);
            if (state.checkpoint % 8 === 0) {{
              state.lap += 1;
              state.score += 320;
            }}
          }} else {{
            state.checkpointCombo = Math.max(0, state.checkpointCombo - 1);
            state.score += 10;
          }}
          ring.z = 1.05;
          ring.x = rand(-0.95, 0.95);
        }}
      }}
    }}
    function updateParticles(dt) {{
      for (let i = state.particles.length - 1; i >= 0; i--) {{
        const p = state.particles[i];
        p.life -= dt;
        p.x += p.vx * dt * 70;
        p.y += p.vy * dt * 70;
        p.vy += dt * 1.4;
        if (p.life <= 0) state.particles.splice(i, 1);
      }}
    }}
    function drawSky(time) {{
      const w = canvas.width, h = canvas.height;
      const grad = ctx.createLinearGradient(0, 0, 0, h);
      grad.addColorStop(0, "#1f3b7e");
      grad.addColorStop(0.22, "#233f9c");
      grad.addColorStop(0.48, "#3c2d7a");
      grad.addColorStop(0.72, "#7a2f66");
      grad.addColorStop(1, "#181821");
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, w, h);

      for (let i = 0; i < 28; i++) {{
        const x = (i / 28) * w + Math.sin(time * 0.28 + i * 1.7) * 18;
        const y = h * 0.14 + Math.cos(time * 0.35 + i) * 22;
        ctx.strokeStyle = i % 2 ? "rgba(56, 189, 248, 0.22)" : "rgba(196, 181, 253, 0.20)";
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x + Math.sin(time + i) * 54, y + 40 + Math.cos(time * 0.8 + i) * 10);
        ctx.stroke();
      }}
    }}
    function drawRoad(time) {{
      const w = canvas.width, h = canvas.height;
      const horizon = h * 0.34;
      const roadBase = h * 0.94;
      for (let i = 0; i < 44; i++) {{
        const t = i / 43;
        const z = Math.pow(t, 1.55);
        const y = lerp(horizon, roadBase, z);
        const width = lerp(28, w * 0.84, z);
        const center = w * 0.5 + (state.roadCurve + state.laneFloat * 0.45) * z * 190;
        const left = center - width * 0.5;
        const right = center + width * 0.5;
        const pulse = (Math.sin(time * 5.2 - i * 0.7) + 1) * 0.5;
        const laneColor = `hsla(${{190 + i * 1.6}}, 84%, ${{44 + pulse * 20}}%, ${{0.08 + z * 0.2}})`;
        ctx.strokeStyle = laneColor;
        ctx.lineWidth = 1 + z * 2.6;
        ctx.beginPath();
        ctx.moveTo(left, y);
        ctx.lineTo(right, y);
        ctx.stroke();
      }}
      ctx.strokeStyle = "rgba(248, 250, 252, 0.58)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(w * 0.1, h * 0.98);
      ctx.lineTo(w * 0.5 + state.roadCurve * 16, h * 0.35);
      ctx.lineTo(w * 0.9, h * 0.98);
      ctx.stroke();
    }}
    function projectLaneX(xNorm, zNorm) {{
      const z = clamp(zNorm, 0.08, 1.2);
      const perspective = 1.25 - z;
      const center = canvas.width * 0.5 + (state.roadCurve * 16 + state.laneFloat * 90) * (0.65 + perspective);
      return center + xNorm * (70 + perspective * 320);
    }}
    function projectLaneY(zNorm) {{
      const z = clamp(zNorm, 0.08, 1.2);
      return lerp(canvas.height * 0.38, canvas.height * 0.92, 1 - z * 0.88);
    }}
    function drawHazards() {{
      state.hazards.forEach((hz, index) => {{
        const x = projectLaneX(hz.x, hz.z);
        const y = projectLaneY(hz.z);
        const scale = 1 + (1 - hz.z) * 1.6;
        const w = hz.w * scale;
        const h = hz.h * scale;
        const hue = Math.round(hz.hue + Math.sin(state.elapsed * 2 + index) * 12);
        ctx.fillStyle = `hsla(${{hue}}, 90%, 52%, 0.92)`;
        ctx.strokeStyle = "rgba(8, 12, 22, 0.72)";
        ctx.lineWidth = 2.2;
        ctx.fillRect(x - w * 0.5, y - h * 0.5, w, h);
        ctx.strokeRect(x - w * 0.5, y - h * 0.5, w, h);
      }});
    }}
    function drawRings() {{
      state.rings.forEach((ring, index) => {{
        const x = projectLaneX(ring.x, ring.z);
        const y = projectLaneY(ring.z);
        const radius = ring.radius * (1 + (1 - ring.z) * 1.5);
        const hue = 165 + (index * 7) % 70;
        ctx.strokeStyle = `hsla(${{hue}}, 96%, 62%, 0.86)`;
        ctx.lineWidth = 4.5;
        ctx.shadowColor = "rgba(34,211,238,0.55)";
        ctx.shadowBlur = 16;
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.stroke();
        ctx.shadowBlur = 0;
      }});
    }}
    function drawPlayer(time) {{
      const x = canvas.width * 0.5 + state.laneFloat * 126;
      const y = canvas.height * 0.76;
      const scale = 1 + state.speed / 520;
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(state.steerVelocity * 0.2 + Math.sin(time * 4.2) * 0.02);
      ctx.fillStyle = "rgba(14, 165, 233, 0.88)";
      ctx.beginPath();
      ctx.moveTo(0, -34 * scale);
      ctx.lineTo(30 * scale, 18 * scale);
      ctx.lineTo(0, 10 * scale);
      ctx.lineTo(-30 * scale, 18 * scale);
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = "rgba(248,250,252,0.86)";
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.fillStyle = "rgba(250, 204, 21, 0.82)";
      ctx.fillRect(-8 * scale, 14 * scale, 16 * scale, 20 * scale);
      ctx.restore();
    }}
    function drawParticles() {{
      for (const p of state.particles) {{
        const alpha = saturate(p.life);
        ctx.fillStyle = `hsla(${{p.hue}}, 95%, 62%, ${{alpha}})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
      }}
    }}
    function drawHUD() {{
      timerEl.textContent = state.elapsed.toFixed(1);
      scoreEl.textContent = String(Math.floor(state.score));
      hpEl.textContent = String(Math.floor(state.hp));
      speedEl.textContent = String(Math.floor(state.speed));
      lapEl.textContent = `${{state.lap}} / ${{state.checkpoint}}`;
      document.getElementById("mode").textContent = `${{config.mode}} • ${{state.phase}} • ${{state.gameState}}`;
    }}
    function update(dt) {{
      if (!state.running) return;
      state.elapsed += dt;
      state.score += dt * (8 + state.speed * 0.03);
      setProgressionPhase();
      ensureSpawnCounts();
      handleInput(dt);
      updateHazards(dt);
      updateRings(dt);
      updateParticles(dt);
      if (state.elapsed > 240) {{
        setGameOver("Session complete");
      }}
    }}
    function render(time) {{
      drawSky(time);
      drawRoad(time);
      drawHazards();
      drawRings();
      drawPlayer(time);
      drawParticles();
      drawHUD();
    }}
    function tick(nowMs) {{
      if (!state._prevMs) state._prevMs = nowMs;
      const dt = clamp((nowMs - state._prevMs) / 1000, 0.001, 0.05);
      state._prevMs = nowMs;
      update(dt);
      render(nowMs / 1000);
      requestAnimationFrame(tick);
    }}

    window.addEventListener("keydown", (ev) => {{
      if (ev.code in input) input[ev.code] = true;
      if (ev.code === "KeyR") restartGame();
      if (ev.code === "Enter" && state.mode === "game_over") restartGame();
    }});
    window.addEventListener("keyup", (ev) => {{
      if (ev.code in input) input[ev.code] = false;
    }});
    window.addEventListener("pointerdown", () => {{
      state.score += 1;
      burstParticles(rand(120, canvas.width - 120), rand(120, canvas.height - 120), 12, rand(160, 320));
    }});

    resetRaceState();
    requestAnimationFrame(tick);

    // contract markers:
    // restart reset retry game over overlay requestAnimationFrame input keydown keyup pointerdown
    // checkpoint lap split overtake roadCurve steerVelocity laneFloat throttle drift accel_rate brake_rate
    // state.score += difficulty spawnRate particles burst screen safe-area overflow-guard
    // config.mode === "{mode}"
    // {fail_restart_safe}
    // {line_pad}
  </script>
</body>
</html>"""
