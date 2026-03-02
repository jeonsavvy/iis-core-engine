from __future__ import annotations

from typing import Any


def _js_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return f"\"{escaped}\""


def export_runtime_artifact(
    *,
    title: str,
    genre: str,
    slug: str,
    accent_color: str,
    viewport_width: int,
    viewport_height: int,
    safe_area_padding: int,
    text_overflow_policy: str,
    capability_profile: dict[str, Any],
    module_plan: dict[str, Any],
    assembled_modules: dict[str, Any],
    contract_bundle: dict[str, Any],
    rqc_version: str,
) -> str:
    module_sources = "\n".join(str(chunk) for chunk in assembled_modules.get("module_sources", []))
    module_signature = str(assembled_modules.get("module_signature", "unknown"))
    camera_model = str(capability_profile.get("camera_model", "third_person"))
    locomotion_model = str(capability_profile.get("locomotion_model", "on_foot"))
    interaction_model = str(capability_profile.get("interaction_model", "action"))
    world_topology = str(capability_profile.get("world_topology", "arena"))
    progression_model = str(capability_profile.get("progression_model", "objective_chain"))
    profile_id = str(capability_profile.get("profile_id", "cp-unknown"))
    objective_lines = contract_bundle.get("deliverables", {}).get("plan") if isinstance(contract_bundle.get("deliverables"), dict) else []
    objective_text = " / ".join(str(item) for item in objective_lines[:2]) if isinstance(objective_lines, list) else ""
    objective_seed = "Engage hostiles and secure interactives"
    control_guide = "이동: W/A/S/D 또는 방향키 · 공격: Space · 회피: Shift · 상호작용: E · 모드전환: C · 재시작: R"
    if locomotion_model == "flight":
        objective_seed = "Navigate waypoints and maintain stable vector"
        control_guide = "자세 제어: W/S 피치 · A/D 롤 · Q/E 요 · 속도 제어: ↑/↓ 스로틀 · Shift 부스트 · 재시작: R"
    elif locomotion_model == "vehicle":
        objective_seed = "Hold racing line and clear checkpoints"
        control_guide = "조향: A/D 또는 ←/→ · 가속/감속: W/S 또는 ↑/↓ · Shift 부스트 · C 모드전환 · 재시작: R"
    elif interaction_model == "ranged_combat":
        objective_seed = "Maintain angle and neutralize hostiles"
        control_guide = "이동: W/A/S/D 또는 방향키 · 공격: Space · 회피: Shift · 상호작용: E · 모드전환: C · 재시작: R"

    return f"""<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <style>
      :root {{
        --safe-area-padding: {safe_area_padding}px;
        --viewport-width: {viewport_width};
        --viewport-height: {viewport_height};
        --accent: {accent_color};
      }}
      html, body {{
        margin: 0;
        width: 100%;
        height: 100%;
        overflow: hidden;
        background: radial-gradient(circle at 12% 12%, #1e293b 0%, #020617 55%, #020412 100%);
        color: #e2e8f0;
        font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      }}
      body {{
        display: grid;
        place-items: center;
      }}
      .overflow-guard {{
        width: min(100vw, calc(100vh * 16 / 9));
        max-width: 100vw;
        max-height: 100vh;
        aspect-ratio: 16 / 9;
        display: grid;
        grid-template-rows: auto 1fr auto;
        gap: 10px;
        padding: var(--safe-area-padding);
        box-sizing: border-box;
      }}
      .topbar {{
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        font-size: clamp(13px, 1.4vw, 16px);
      }}
      .title {{
        font-size: clamp(20px, 2.8vw, 36px);
        font-weight: 800;
      }}
      .hud {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }}
      .hud span {{
        border: 1px solid rgba(148, 163, 184, 0.3);
        background: rgba(15, 23, 42, 0.72);
        padding: 6px 10px;
        border-radius: 999px;
      }}
      .stage {{
        position: relative;
        border: 1px solid rgba(148, 163, 184, 0.24);
        border-radius: 14px;
        overflow: hidden;
        min-height: 320px;
        background: linear-gradient(160deg, #020617, #020812 70%, #021229);
      }}
      #game {{
        width: 100%;
        height: 100%;
        display: block;
      }}
      #overlay {{
        position: absolute;
        inset: 0;
        display: none;
        align-items: center;
        justify-content: center;
        background: rgba(2, 6, 23, 0.72);
        backdrop-filter: blur(2px);
      }}
      #overlay.show {{
        display: flex;
      }}
      #overlay-card {{
        border-radius: 12px;
        border: 1px solid rgba(148, 163, 184, 0.3);
        background: rgba(15, 23, 42, 0.9);
        padding: 18px;
        min-width: 260px;
        text-align: center;
        display: grid;
        gap: 8px;
      }}
      #restart-btn {{
        border: 1px solid rgba(125, 211, 252, 0.55);
        background: rgba(59, 130, 246, 0.22);
        color: #dbeafe;
        border-radius: 999px;
        padding: 8px 14px;
        cursor: pointer;
        font-weight: 700;
      }}
      .guide {{
        font-size: 13px;
        color: #cbd5e1;
        opacity: 0.96;
      }}
    </style>
  </head>
  <body data-overflow-policy="{text_overflow_policy}">
    <div class="overflow-guard" aria-label="game-runtime-shell">
      <header class="topbar">
        <div>
          <div class="title">{title}</div>
          <div style="font-size:13px;color:#93c5fd">{genre} · {objective_text or "목표를 달성하고 생존 시간을 늘리세요."}</div>
        </div>
        <div class="hud" aria-live="polite">
          <span id="score">Score: 0</span>
          <span id="timer">Time: 90.0s</span>
          <span id="hp">HP: 3</span>
          <span id="objective">Objective: {objective_seed}</span>
        </div>
      </header>

      <main class="stage">
        <canvas id="game" width="{viewport_width}" height="{viewport_height}" aria-label="게임 캔버스"></canvas>
        <div id="overlay" role="dialog" aria-modal="true" aria-hidden="true">
          <div id="overlay-card">
            <strong style="font-size:28px">Game Over</strong>
            <p id="overlay-text" style="margin:0;color:#bfdbfe">전투가 종료되었습니다.</p>
            <button id="restart-btn" type="button">다시 시작 (R)</button>
          </div>
        </div>
      </main>

      <footer class="guide">
        {control_guide}
      </footer>
    </div>
    <script>
      window.__iis_game_boot_ok = true;
      window.IISLeaderboard = window.IISLeaderboard || {{
        submit: async () => ({{ ok: true }}),
      }};
      const CONFIG = {{
        title: {_js_string(title)},
        genre: {_js_string(genre)},
        slug: {_js_string(slug)},
        mode: {_js_string(str(capability_profile.get("core_loop_type", "modular")))},
        cameraModel: {_js_string(camera_model)},
        locomotionModel: {_js_string(locomotion_model)},
        interactionModel: {_js_string(interaction_model)},
        worldTopology: {_js_string(world_topology)},
        progressionModel: {_js_string(progression_model)},
        profileId: {_js_string(profile_id)},
        moduleSignature: {_js_string(module_signature)},
        modulePlan: {_js_string(",".join(str(item) for item in module_plan.get("primary_modules", [])))},
        rqcVersion: {_js_string(rqc_version)},
      }};

      const runtimeModules = {{}};
{module_sources}

      const canvas = document.getElementById("game");
      const ctx = canvas.getContext("2d", {{ alpha: false }});
      const overlay = document.getElementById("overlay");
      const overlayText = document.getElementById("overlay-text");
      const scoreEl = document.getElementById("score");
      const timerEl = document.getElementById("timer");
      const hpEl = document.getElementById("hp");
      const objectiveEl = document.getElementById("objective");
      const restartBtn = document.getElementById("restart-btn");
      const glCanvas = document.createElement("canvas");
      glCanvas.width = canvas.width;
      glCanvas.height = canvas.height;
      const gl = glCanvas.getContext("webgl", {{ antialias: true }});

      const state = {{
        running: true,
        score: 0,
        hp: 3,
        timeLeft: 90,
        runtimeSec: 0,
        lastTs: 0,
        viewport: {{ w: canvas.width, h: canvas.height }},
        input: {{
          left: false, right: false, up: false, down: false,
          attack: false, sprint: false, interact: false, altAction: false,
          pitchUp: false, pitchDown: false, rollLeft: false, rollRight: false,
          yawLeft: false, yawRight: false, throttleUp: false, throttleDown: false,
          toggleMode: false,
        }},
        runtimeProfile: {{
          cameraModel: CONFIG.cameraModel,
          locomotionModel: CONFIG.locomotionModel,
          interactionModel: CONFIG.interactionModel,
        }},
        player: {{
          x: 0, y: 0, z: 4, vx: 0, vy: 0, vz: 0, combo: 1, attackCooldown: 0, mode: "precision",
        }},
        camera: {{
          x: 0, y: 2.2, z: -2.8, focal: 760,
        }},
        feedback: {{
          hitPulse: 0, damagePulse: 0, cameraShake: 0,
        }},
        progress: {{
          wave: 1,
          waveTimer: 0,
          spawnCadence: 1.35,
          objective: "{objective_seed}",
          time: 0,
        }},
        enemies: [],
        projectiles: [],
        interactives: [],
        checkpoints: [],
        worldObjects: [],
        statusMachine: "explore",
        flight: {{
          throttle: 0.85,
          pitch: 0,
          roll: 0,
          yaw: 0,
          speedBase: 11,
        }},
        vehicle: {{
          throttle: 0.72,
          speed: 9,
          baseSpeed: 8.5,
          yaw: 0,
        }},
      }};

      function drawWebglBackdrop(t) {{
        if (!gl) return;
        const r = 0.03 + Math.sin(t * 0.00025) * 0.02;
        const g = 0.06 + Math.cos(t * 0.0002) * 0.015;
        const b = 0.12 + Math.sin(t * 0.0003) * 0.025;
        gl.viewport(0, 0, glCanvas.width, glCanvas.height);
        gl.clearColor(r, g, b, 1);
        gl.clear(gl.COLOR_BUFFER_BIT);
        ctx.drawImage(glCanvas, 0, 0, canvas.width, canvas.height);
      }}

      function setInputFromKey(key, pressed) {{
        if (key === "a" || key === "arrowleft") state.input.left = pressed;
        if (key === "d" || key === "arrowright") state.input.right = pressed;
        if (key === "w" || key === "arrowup") state.input.up = pressed;
        if (key === "s" || key === "arrowdown") state.input.down = pressed;
        if (key === "w") state.input.pitchUp = pressed;
        if (key === "s") state.input.pitchDown = pressed;
        if (key === "a") state.input.rollLeft = pressed;
        if (key === "d") state.input.rollRight = pressed;
        if (key === "q") state.input.yawLeft = pressed;
        if (key === "e") state.input.yawRight = pressed;
        if (key === "arrowup") state.input.throttleUp = pressed;
        if (key === "arrowdown") state.input.throttleDown = pressed;
        if (key === " ") state.input.attack = pressed;
        if (key === "shift") state.input.sprint = pressed;
        if (key === "e") state.input.interact = pressed;
        if (key === "c" && pressed) state.input.toggleMode = true;
      }}

      document.addEventListener("keydown", (event) => {{
        if (!state.running && (event.key === "r" || event.key === "R")) {{
          restartGame();
          return;
        }}
        setInputFromKey(event.key.toLowerCase(), true);
      }});
      document.addEventListener("keyup", (event) => {{
        setInputFromKey(event.key.toLowerCase(), false);
      }});
      restartBtn.addEventListener("click", restartGame);

      window.addEventListener("message", (event) => {{
        const data = event.data || {{}};
        if (data.type === "iis:recover:start" && !state.running && state.runtimeSec < 8.0) {{
          restartGame();
        }}
      }});

      function restartGame() {{
        state.running = true;
        state.score = 0;
        state.hp = 3;
        state.timeLeft = 90;
        state.runtimeSec = 0;
        state.lastTs = 0;
        state.player.x = 0;
        state.player.z = 4;
        state.player.vx = 0;
        state.player.vy = 0;
        state.player.vz = 0;
        state.player.combo = 1;
        state.progress.wave = 1;
        state.progress.waveTimer = 0;
        state.progress.time = 0;
        state.progress.objective = "{objective_seed}";
        state.enemies = [];
        state.projectiles = [];
        state.interactives = [];
        state.checkpoints = [];
        state.flight.throttle = 0.85;
        state.flight.pitch = 0;
        state.flight.roll = 0;
        state.flight.yaw = 0;
        state.vehicle.throttle = 0.72;
        state.vehicle.speed = 9;
        state.vehicle.yaw = 0;
        runtimeModules.scene_world?.buildWorld(state);
        overlay.classList.remove("show");
        overlay.setAttribute("aria-hidden", "true");
      }}

      function damagePlayer(amount) {{
        state.hp = Math.max(0, state.hp - amount);
        runtimeModules.feedback_stack?.emitDamage(state);
      }}

      function updateStatusMachine() {{
        if (!state.running) {{
          state.statusMachine = "recover";
          return;
        }}
        if (state.feedback.damagePulse > 0.45) {{
          state.statusMachine = "combat";
          return;
        }}
        if (state.input.sprint) {{
          state.statusMachine = "dash";
          return;
        }}
        state.statusMachine = "explore";
      }}

      function updateEnemies(dt) {{
        if (state.runtimeProfile.locomotionModel === "flight" || state.runtimeProfile.locomotionModel === "vehicle") {{
          return;
        }}
        for (const enemy of state.enemies) {{
          const dx = state.player.x - enemy.x;
          const dz = state.player.z - enemy.z;
          const dist = Math.max(0.001, Math.hypot(dx, dz));
          enemy.x += (dx / dist) * enemy.speed * dt;
          enemy.z += (dz / dist) * enemy.speed * dt;
          if (dist < 1.15) {{
            damagePlayer(enemy.kind === "elite" ? 1.2 : 0.5);
          }}
        }}
      }}

      function resolveProjectiles() {{
        for (const bullet of state.projectiles) {{
          for (const enemy of state.enemies) {{
            if (enemy.hp <= 0) continue;
            const dx = enemy.x - bullet.x;
            const dz = enemy.z - bullet.z;
            if ((dx * dx + dz * dz) < 1.1) {{
              enemy.hp -= 1;
              state.score += enemy.kind === "elite" ? 50 : 20;
              state.player.combo = Math.min(8, state.player.combo + 0.15);
              state.feedback.hitPulse = 1;
              bullet.ttl = 0;
            }}
          }}
        }}
        state.enemies = state.enemies.filter((enemy) => enemy.hp > 0);
      }}

      function resolveInteractives() {{
        for (const item of state.interactives) {{
          const dx = item.x - state.player.x;
          const dz = item.z - state.player.z;
          if ((dx * dx + dz * dz) < 1.2) {{
            state.score += item.reward;
            state.timeLeft = Math.min(120, state.timeLeft + 3);
            item.taken = true;
          }}
        }}
        state.interactives = state.interactives.filter((item) => !item.taken);
      }}

      function drawObject(point, kind, scale = 1) {{
        const projected = runtimeModules.camera_stack.project(state, point);
        const radius = Math.max(2, 16 * projected.s * scale);
        if (projected.x < -60 || projected.x > canvas.width + 60) return;
        if (projected.y < -60 || projected.y > canvas.height + 60) return;
        ctx.save();
        ctx.translate(projected.x, projected.y);
        if (kind === "enemy") {{
          ctx.fillStyle = "#ef4444";
          ctx.fillRect(-radius * 0.55, -radius * 0.65, radius * 1.1, radius * 1.3);
        }} else if (kind === "elite") {{
          ctx.fillStyle = "#f97316";
          ctx.beginPath();
          ctx.moveTo(0, -radius);
          ctx.lineTo(radius * 0.95, radius * 0.35);
          ctx.lineTo(-radius * 0.95, radius * 0.35);
          ctx.closePath();
          ctx.fill();
        }} else if (kind === "interactive") {{
          ctx.fillStyle = "#22d3ee";
          ctx.beginPath();
          ctx.arc(0, 0, radius * 0.7, 0, Math.PI * 2);
          ctx.fill();
        }} else if (kind === "checkpoint") {{
          ctx.strokeStyle = "rgba(34, 211, 238, 0.95)";
          ctx.lineWidth = Math.max(2, radius * 0.15);
          ctx.beginPath();
          ctx.arc(0, 0, radius * 0.95, 0, Math.PI * 2);
          ctx.stroke();
        }} else if (kind === "player") {{
          ctx.fillStyle = "#38bdf8";
          ctx.fillRect(-radius * 0.42, -radius * 0.72, radius * 0.84, radius * 1.44);
          ctx.fillStyle = "#e2e8f0";
          ctx.fillRect(-radius * 0.2, -radius * 0.8, radius * 0.4, radius * 0.26);
        }} else {{
          ctx.fillStyle = "#334155";
          ctx.fillRect(-radius * 0.5, -radius * 0.5, radius, radius);
        }}
        ctx.restore();
      }}

      function drawGround() {{
        if (state.runtimeProfile.locomotionModel === "flight") {{
          ctx.save();
          const horizonY = canvas.height * 0.58;
          const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
          gradient.addColorStop(0, "rgba(30, 64, 175, 0.35)");
          gradient.addColorStop(0.58, "rgba(15, 23, 42, 0.12)");
          gradient.addColorStop(1, "rgba(2, 6, 23, 0.75)");
          ctx.fillStyle = gradient;
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          ctx.strokeStyle = "rgba(125, 211, 252, 0.28)";
          ctx.beginPath();
          ctx.moveTo(0, horizonY);
          ctx.lineTo(canvas.width, horizonY);
          ctx.stroke();
          ctx.restore();
          return;
        }}
        ctx.save();
        ctx.strokeStyle = "rgba(56, 189, 248, 0.18)";
        ctx.lineWidth = 1;
        for (let i = 0; i < 20; i++) {{
          const z = 4 + i * 3.2;
          const p0 = runtimeModules.camera_stack.project(state, {{ x: -12, y: 0, z }});
          const p1 = runtimeModules.camera_stack.project(state, {{ x: 12, y: 0, z }});
          ctx.beginPath();
          ctx.moveTo(p0.x, p0.y);
          ctx.lineTo(p1.x, p1.y);
          ctx.stroke();
        }}
        for (let i = 0; i < 12; i++) {{
          const x = -11 + i * 2;
          const p0 = runtimeModules.camera_stack.project(state, {{ x, y: 0, z: 4 }});
          const p1 = runtimeModules.camera_stack.project(state, {{ x, y: 0, z: 52 }});
          ctx.beginPath();
          ctx.moveTo(p0.x, p0.y);
          ctx.lineTo(p1.x, p1.y);
          ctx.stroke();
        }}
        ctx.restore();
      }}

      function renderFrame() {{
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        drawGround();
        for (const obj of state.worldObjects) drawObject(obj, obj.kind, 0.8);
        for (const checkpoint of state.checkpoints) drawObject(checkpoint, "checkpoint", 1.0);
        for (const item of state.interactives) drawObject(item, "interactive", 1.0);
        for (const enemy of state.enemies) drawObject(enemy, enemy.kind, 1.1);
        for (const bullet of state.projectiles) drawObject(bullet, "interactive", 0.5);
        drawObject({{ x: state.player.x, y: 0, z: state.player.z }}, "player", 1.2);

        if (state.feedback.hitPulse > 0.01) {{
          ctx.fillStyle = `rgba(34, 211, 238, ${{state.feedback.hitPulse * 0.18}})`;
          ctx.fillRect(0, 0, canvas.width, canvas.height);
        }}
        if (state.feedback.damagePulse > 0.01) {{
          ctx.fillStyle = `rgba(239, 68, 68, ${{state.feedback.damagePulse * 0.2}})`;
          ctx.fillRect(0, 0, canvas.width, canvas.height);
        }}
      }}

      function endGame() {{
        state.running = false;
        overlay.classList.add("show");
        overlay.setAttribute("aria-hidden", "false");
        overlayText.textContent = `최종 점수 ${{Math.floor(state.score)}} · 상태 ${{state.statusMachine}}`;
      }}

      function step(ts) {{
        if (!state.lastTs) state.lastTs = ts;
        const dt = Math.min(0.05, Math.max(0.001, (ts - state.lastTs) / 1000));
        state.lastTs = ts;

        drawWebglBackdrop(ts);

        if (state.running) {{
          state.runtimeSec += dt;
          state.timeLeft = Math.max(0, state.timeLeft - dt);
          runtimeModules.controller_stack.update(state, dt);
          runtimeModules.combat_stack.update(state, dt);
          runtimeModules.progression_stack.update(state, dt);
          updateEnemies(dt);
          resolveProjectiles();
          resolveInteractives();
          runtimeModules.feedback_stack.update(state, dt);
          updateStatusMachine();
          if (state.hp <= 0 || state.timeLeft <= 0) {{
            endGame();
          }}
        }}

        renderFrame();
        runtimeModules.hud_stack.render(state, scoreEl, timerEl, hpEl, objectiveEl);
        requestAnimationFrame(step);
      }}

      runtimeModules.scene_world?.buildWorld(state);
      requestAnimationFrame(step);
    </script>
  </body>
</html>
"""
