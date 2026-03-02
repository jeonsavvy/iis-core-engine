from __future__ import annotations

from app.orchestration.nodes.builder_parts.html_runtime_sections_shared import _normalize_escaped_braces


def build_runtime_spawn_combat_functions_js() -> str:
    return _normalize_escaped_braces(r"""      function spawnMiniBoss() {{
        const difficultyScale = Math.max(1, state.run.difficultyScale || 1);
        if (MODE_IS_FORMULA_CIRCUIT) {{
          state.enemies.push({{
            lane: rand(-0.9, 0.9),
            z: 0.06,
            speedMul: 0.92 + difficultyScale * 0.2,
            kind: "opponent_elite",
            w: 72,
            h: 110,
            hp: Math.max(2, Math.floor(2 + state.run.level * 0.22)),
            miniBoss: true,
          }});
          return;
        }}
        if (MODE_IS_FLIGHT_SIM) {{
          state.enemies.push({{
            kind: "hazard",
            x: rand(canvas.width * 0.26, canvas.width * 0.74),
            y: rand(canvas.height * 0.28, canvas.height * 0.62),
            z: 0.08,
            speedMul: 1.05 + difficultyScale * 0.16,
            w: 78,
            h: 80,
            hp: Math.max(2, Math.floor(2 + state.run.level * 0.2)),
            miniBoss: true,
          }});
          return;
        }}
        if (MODE_IS_3D_RUNNER) {{
          state.enemies.push({{
            lane: Math.floor(Math.random() * 3) - 1,
            z: 0.08,
            speedMul: 0.9 + difficultyScale * 0.18,
            kind: "elite",
            w: 54,
            h: 86,
            hp: Math.max(2, Math.floor(2 + state.run.level * 0.18)),
            miniBoss: true,
          }});
          return;
        }}
        if (MODE_IS_SHOOTER || MODE_IS_BRAWLER || CONFIG.mode === "arcade_generic" || CONFIG.mode === "request_faithful_generic") {{
          state.enemies.push({{
            x: rand(canvas.width * 0.22, canvas.width * 0.78),
            y: rand(20, canvas.height * 0.18),
            w: MODE_IS_BRAWLER ? 66 : 54,
            h: MODE_IS_BRAWLER ? 86 : 58,
            speed: (CONFIG.enemy_speed_max || 220) * (0.56 + difficultyScale * 0.16),
            hp: Math.max(3, Math.floor((CONFIG.enemy_hp || 1) + state.run.level * 0.5)),
            kind: "elite",
            miniBoss: true,
          }});
        }}
      }}

      function spawnEnemy() {{
        const spdMin = CONFIG.enemy_speed_min || 100;
        const spdMax = CONFIG.enemy_speed_max || 220;
        const difficultyScale = Math.max(1, state.run.difficultyScale || 1) * Math.max(1, state.run.waveModifier || 1);
        const weightedPattern = Array.isArray(ACTIVE_DEPTH_PACK.pattern) ? ACTIVE_DEPTH_PACK.pattern : [];
        if (MODE_IS_FORMULA_CIRCUIT) {{
          const kind = pickWeighted(weightedPattern, "opponent");
          const lane = rand(-0.95, 0.95);
          const opponentScale = kind === "opponent_elite" ? 1.18 : kind === "opponent" ? 1.0 : 0.9;
          state.enemies.push({{
            lane,
            z: rand(0.03, 0.16),
            speedMul: rand(0.88, 1.18) * (0.92 + difficultyScale * 0.16) * opponentScale,
            kind,
            w: kind === "checkpoint" ? 80 : kind === "boost" ? 28 : 52,
            h: kind === "checkpoint" ? 100 : kind === "boost" ? 28 : 88,
            hp: kind.includes("opponent") ? Math.max(1, Math.floor(1 + state.run.level * 0.16)) : 1,
          }});
          return;
        }}
        if (MODE_IS_FLIGHT_SIM) {{
          const kind = pickWeighted(weightedPattern, "hazard");
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
          const kind = pickWeighted(weightedPattern, "obstacle");
          const isElite = kind === "elite";
          state.enemies.push({{
            lane,
            z: rand(0.04, 0.14),
            speedMul: rand(0.86, 1.24) * (0.9 + difficultyScale * 0.15),
            kind,
            w: kind === "boost" ? 24 : isElite ? 42 : 34,
            h: kind === "boost" ? 24 : isElite ? 74 : 56,
            hp: isElite ? Math.max(2, Math.floor(1 + state.run.level * 0.18)) : 1,
          }});
          return;
        }}
        if (CONFIG.mode === "topdown_roguelike_shooter") {{
          const edge = Math.floor(rand(0, 4));
          const enemyKind = pickWeighted(weightedPattern, "grunt");
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
          const enemyKind = pickWeighted(weightedPattern, "grunt");
          state.enemies.push({{
            x: rand(40, canvas.width - 80),
            y: -40,
            w: enemyKind === "elite" ? 38 : 30,
            h: enemyKind === "elite" ? 38 : 30,
            speed: rand(spdMin, spdMax) * (0.84 + difficultyScale * 0.2),
            hp: enemyKind === "elite" ? Math.max(2, Math.floor((CONFIG.enemy_hp || 1) + state.run.level * 0.25)) : (CONFIG.enemy_hp || 1),
            kind: enemyKind,
          }});
          return;
        }}
        if (MODE_IS_BRAWLER) {{
          const maxWave = CONFIG.mode === "comic_action_brawler_3d"
            ? Math.min(4, 2 + Math.floor((state.run.level || 1) / 2))
            : 2;
          if (state.enemies.length < maxWave) {{
            let spawnX = rand(canvas.width * 0.12, canvas.width * 0.88);
            let spawnY = rand(canvas.height * 0.12, canvas.height * 0.82);
            let guard = 0;
            while (guard < 8) {{
              const dx = spawnX - state.player.x;
              const dy = spawnY - state.player.y;
              if (Math.hypot(dx, dy) >= Math.max(120, canvas.height * 0.22)) break;
              const side = Math.random() < 0.5 ? -1 : 1;
              spawnX = clamp(state.player.x + side * rand(canvas.width * 0.28, canvas.width * 0.42), 28, canvas.width - 72);
              spawnY = clamp(state.player.y + (Math.random() < 0.5 ? -1 : 1) * rand(canvas.height * 0.18, canvas.height * 0.26), 18, canvas.height - 92);
              guard += 1;
            }}
            const enemyKind = pickWeighted(weightedPattern, "grunt");
            state.enemies.push({{
              x: spawnX,
              y: spawnY,
              w: CONFIG.mode === "comic_action_brawler_3d" ? 48 : 44,
              h: CONFIG.mode === "comic_action_brawler_3d" ? 70 : 68,
              hp: Math.max(1, Math.floor(state.enemyHp * (CONFIG.mode === "comic_action_brawler_3d" ? 0.48 : 0.82) * (enemyKind === "elite" ? 1.35 : 1))),
              speed: spdMin * (0.48 + difficultyScale * 0.2),
              kind: enemyKind,
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
          state.score += (CONFIG.mode === "comic_action_brawler_3d" ? 62 : 45) * (1 + Number(state.run.synergy.damageBonus || 0));
          burst(enemy.x + enemy.w / 2, enemy.y + enemy.h / 2, ASSET.enemy_elite, 10);
          if (enemy.hp <= 0) {{
            state.score += 170 * Number(state.run.synergy.scoreMul || 1);
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
        state.run.fxPulse = Math.max(state.run.fxPulse, Math.min(0.42, 0.08 + count * 0.008));
        for (let i = 0; i < count; i++) {{
          state.particles.push({{
            x, y, life: rand(0.2, 0.6), t: 0, color,
            vx: rand(-160, 160), vy: rand(-160, 160),
            size: rand(1.5, MODE_USES_WEBGL_BG ? 4.8 : 3.8),
          }});
        }}
      }}

""")


def build_runtime_update_function_js() -> str:
    return _normalize_escaped_braces(r"""      function update(dt) {{
        if (!state.running) return;
        state.runtimeSec += dt;
        state.timeLeft = Math.max(0, state.timeLeft - dt);
        state.spawnTimer += dt;
        state.attackCooldown = Math.max(0, state.attackCooldown - dt);
        state.dashCooldown = Math.max(0, state.dashCooldown - dt);
        state.run.spawnGraceSec = Math.max(0, Number(state.run.spawnGraceSec || 0) - dt);
        state.run.damageCooldown = Math.max(0, Number(state.run.damageCooldown || 0) - dt);
        stepProgression(dt);
        const spawnRate = ((CONFIG.enemy_spawn_rate || 1.0) / clamp(state.run.difficultyScale, 1, 2.8))
          * Math.max(0.78, Number(state.run.synergy.spawnEase || 1));
        const collisionEnabled = (state.run.spawnGraceSec || 0) <= 0;

        if (MODE_IS_FORMULA_CIRCUIT) {{
          const left = keys.has("ArrowLeft") || keys.has("a");
          const right = keys.has("ArrowRight") || keys.has("d");
          const accel = keys.has("ArrowUp") || keys.has("w");
          const brake = keys.has("ArrowDown") || keys.has("s");

          state.formula.lapTimer += dt;
          const steerDir = (right ? 1 : 0) - (left ? 1 : 0);
          state.racer.steerVelocity += steerDir * dt * Number(CONTROL.steer_accel || 10.5);
          state.racer.steerVelocity *= (1 - Math.min(0.84, dt * Number(CONTROL.steer_drag || 8.2)));
          if (!left && !right) {{
            state.racer.steerVelocity *= (1 - Math.min(0.88, dt * Number(CONTROL.steer_return || 9.1)));
          }}
          state.racer.laneFloat = clamp(state.racer.laneFloat + state.racer.steerVelocity * dt, 0.06, 1.94);
          state.player.lane = state.racer.laneFloat;

          if (accel) state.racer.speed += Number(CONTROL.accel_rate || 320) * dt;
          if (brake) state.racer.speed -= Number(CONTROL.brake_rate || 400) * dt;
          if (!accel && !brake) state.racer.speed -= Number(CONTROL.drag_rate || 116) * dt;
          state.racer.speed = clamp(state.racer.speed, Number(CONTROL.speed_min || 210), Number(CONTROL.speed_max || 620));
          state.racer.topSpeed = Math.max(state.racer.topSpeed || state.racer.speed, state.racer.speed);

          if (keys.has("Shift") && consumeDash()) {{
            state.racer.boostTimer = Math.max(state.racer.boostTimer, 1.2 + Number(state.run.synergy.boostBonus || 0));
            state.racer.speed = Math.max(state.racer.speed, Number(CONTROL.overtake_boost_floor || 460));
            state.formula.overtakeChain += 1;
            playSfx("boost");
          }}
          if (state.racer.boostTimer > 0) {{
            state.racer.boostTimer = Math.max(0, state.racer.boostTimer - dt);
            state.racer.speed = Math.max(state.racer.speed, Number(CONTROL.overtake_boost_floor || 460));
          }}

          state.racer.curveTimer -= dt;
          if (state.racer.curveTimer <= 0) {{
            state.racer.curveTimer = rand(Number(CONTROL.curve_interval_min || 0.7), Number(CONTROL.curve_interval_max || 2.0));
            state.racer.roadCurveTarget = rand(-0.62, 0.62);
          }}
          state.racer.roadCurve += (state.racer.roadCurveTarget - state.racer.roadCurve) * Math.min(1, dt * Number(CONTROL.curve_response || 1.8));
          state.racer.roadScroll += dt * state.racer.speed * 0.064;
          state.racer.distance += dt * state.racer.speed;
          state.formula.sectorHeat = clamp(state.formula.sectorHeat + Math.abs(state.racer.roadCurve) * dt * 0.3, 0, 1.6);

          const curvePx = state.racer.roadCurve * canvas.width * 0.2;
          const laneNormalized = state.player.lane - 1;
          const playerDepth = 0.92;
          const roadTop = canvas.width * 0.26;
          const roadBottom = canvas.width * 0.88;
          const playerRoadHalf = roadTop + (roadBottom - roadTop) * (playerDepth * playerDepth);
          const laneX = canvas.width * 0.5 + curvePx * (1 - playerDepth) + laneNormalized * (playerRoadHalf * 0.72);
          state.player.x += (laneX - state.player.w / 2 - state.player.x) * Math.min(1, dt * Number(CONTROL.lane_lerp || 11));
          state.player.y = canvas.height * 0.79;

          const adaptiveSpawnRate = clamp(spawnRate * (280 / state.racer.speed), 0.16, 0.78);
          if (state.spawnTimer > adaptiveSpawnRate) {{
            state.spawnTimer = 0;
            spawnEnemy();
          }}

          const playerLaneNorm = state.player.lane - 1;
          for (const e of state.enemies) {{
            e.z += dt * (state.racer.speed / 320) * (e.speedMul || 1);
            if (e.z > 0.78 && e.z < 1.04) {{
              const laneDiff = Math.abs((e.lane || 0) - playerLaneNorm);
              const hitWindow = Number(CONTROL.apex_window || 0.32);
              if (laneDiff < hitWindow) {{
                if (e.kind === "checkpoint") {{
                  state.formula.checkpoints += 1;
                  state.timeLeft = Math.min((CONFIG.time_limit_sec || 60) + 45, state.timeLeft + Number(CONTROL.checkpoint_bonus_sec || 2.2));
                  const checkpointScore = (CONFIG.base_score_value || 10) * (4 + state.formula.overtakeChain * 0.35) * Number(state.run.synergy.scoreMul || 1);
                  state.score += checkpointScore;
                  addCombo(1.2);
                  grantXp(14);
                  playSfx("boost");
                  burst(state.player.x + state.player.w / 2, state.player.y + state.player.h * 0.2, ASSET.boost_color, 16);
                  if (state.formula.checkpoints >= state.formula.checkpointsPerLap) {{
                    const finishedLapTime = Math.max(0.1, state.formula.lapTimer);
                    state.formula.bestLap = Math.min(state.formula.bestLap, finishedLapTime);
                    state.formula.lap += 1;
                    state.formula.checkpoints = 0;
                    state.formula.lapTimer = 0;
                    state.formula.overtakeChain = Math.max(0, state.formula.overtakeChain - 1);
                    state.run.level += 1;
                    state.run.difficultyScale = (1 + (state.run.level - 1) * 0.12) * Math.max(1, state.run.waveModifier);
                    state.score += 300 * Number(state.run.synergy.scoreMul || 1);
                    state.timeLeft = Math.min((CONFIG.time_limit_sec || 60) + 55, state.timeLeft + 4);
                    playSfx("levelup");
                  }}
                }} else if (e.kind === "boost") {{
                  state.racer.boostTimer = Math.max(state.racer.boostTimer, 1.6 + Number(state.run.synergy.boostBonus || 0));
                  state.score += 50;
                  addCombo(0.9);
                  grantXp(10);
                  playSfx("boost");
                  burst(state.player.x + state.player.w / 2, state.player.y + state.player.h * 0.6, ASSET.boost_color, 14);
                }} else {{
                  if (!collisionEnabled) {{
                    e.z = 2;
                    continue;
                  }}
                  const dangerScale = e.kind === "opponent_elite" ? 2 : 1;
                  if (applyPlayerDamage(dangerScale, {{ scorePenalty: 20 * dangerScale, cooldownSec: 0.72, shake: 0.24 }})) {{
                    state.formula.overtakeChain = 0;
                    burst(state.player.x + state.player.w / 2, state.player.y + state.player.h * 0.5, ASSET.enemy_primary, 16);
                  }}
                }}
                e.z = 2;
              }}
            }}
          }}

          state.enemies = state.enemies.filter((e) => {{
            const passed = e.z > 1.08;
            if (passed && (e.kind === "opponent" || e.kind === "opponent_elite")) {{
              state.score += (CONFIG.base_score_value || 10) * (1.5 + state.formula.overtakeChain * 0.08) * Number(state.run.synergy.scoreMul || 1);
              state.formula.overtakeChain = Math.min(20, state.formula.overtakeChain + 0.6);
              addCombo(0.45);
              grantXp(6);
            }}
            if (passed && e.kind === "checkpoint") {{
              state.formula.overtakeChain = Math.max(0, state.formula.overtakeChain - 0.4);
            }}
            return !passed;
          }});

          state.score += dt * (state.racer.speed * 0.052) * (1 + state.run.combo * 0.032 + state.formula.overtakeChain * 0.014) * Number(state.run.synergy.scoreMul || 1);
        }} else if (MODE_IS_FLIGHT_SIM) {{
          const pitchInput = (keys.has("w") || keys.has("ArrowUp") ? -1 : 0) + (keys.has("s") || keys.has("ArrowDown") ? 1 : 0);
          const rollInput = (keys.has("d") ? 1 : 0) - (keys.has("a") ? 1 : 0);
          const yawInput = (keys.has("e") ? 1 : 0) - (keys.has("q") ? 1 : 0);
          const throttleInput = (keys.has("ArrowUp") ? 1 : 0) - (keys.has("ArrowDown") ? 1 : 0);
          state.flight.throttle = clamp(state.flight.throttle + throttleInput * dt * Number(CONTROL.throttle_response || 0.55), 0.18, 1);
          state.flight.pitch = clamp(state.flight.pitch + pitchInput * dt * Number(CONTROL.pitch_response || 2.4), -1, 1);
          state.flight.roll = clamp(state.flight.roll + rollInput * dt * Number(CONTROL.roll_response || 2.6), -1, 1);
          state.flight.yaw = clamp(state.flight.yaw + yawInput * dt * Number(CONTROL.yaw_response || 1.8), -1, 1);
          state.flight.pitch *= (1 - Math.min(0.7, dt * Number(CONTROL.damping_pitch || 2.8)));
          state.flight.roll *= (1 - Math.min(0.7, dt * Number(CONTROL.damping_roll || 3.2)));
          state.flight.yaw *= (1 - Math.min(0.7, dt * Number(CONTROL.damping_yaw || 3.5)));
          if (keys.has("Shift") && consumeDash()) {{
            state.flight.throttle = Math.min(1, state.flight.throttle + 0.22);
            state.racer.boostTimer = Math.max(state.racer.boostTimer, 1.35);
            playSfx("boost");
          }}

          const targetSpeed = Number(CONTROL.cruise_speed_min || 180) + state.flight.throttle * Number(CONTROL.cruise_speed_max || 420);
          state.flight.speed += (targetSpeed - state.flight.speed) * Math.min(1, dt * 2.1);
          if (state.racer.boostTimer > 0) {{
            state.racer.boostTimer = Math.max(0, state.racer.boostTimer - dt);
            state.flight.speed = Math.max(state.flight.speed, Number(CONTROL.boost_floor_speed || 430));
          }}
          state.racer.speed = state.flight.speed;
          state.racer.roadScroll += dt * state.flight.speed * 0.07;
          state.racer.distance += dt * state.flight.speed;

          const lateral = (state.flight.roll * 0.92) + (state.flight.yaw * 0.52);
          const vertical = state.flight.pitch * 1.1;
          state.player.x = clamp(state.player.x + lateral * dt * Number(CONTROL.lateral_sensitivity || 340), canvas.width * 0.12, canvas.width * 0.88 - state.player.w);
          state.player.y = clamp(state.player.y + vertical * dt * Number(CONTROL.vertical_sensitivity || 240), canvas.height * 0.35, canvas.height * 0.86);
          state.flight.altitude = 1 - clamp((state.player.y - canvas.height * 0.35) / (canvas.height * 0.51), 0, 1);
          state.flight.bankVisual += (state.flight.roll - state.flight.bankVisual) * Math.min(1, dt * (6.9 + Number(CONTROL.camera_sensitivity || 1) * 0.8));
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
                  const scoreGain = (CONFIG.base_score_value || 10) * (3.2 + state.flight.checkpointCombo * 0.14) * Number(state.run.synergy.scoreMul || 1);
                  state.score += scoreGain;
                  state.flight.checkpointCombo += 1;
                  addCombo(1.2);
                  grantXp(14 + Math.min(18, state.flight.checkpointCombo));
                  playSfx("boost");
                  burst(playerCx, playerCy - 10, ASSET.boost_color, 18);
                }} else if (e.kind === "turbulence") {{
                  if (!collisionEnabled) {{
                    e.z = 2;
                    continue;
                  }}
                  if ((state.run.damageCooldown || 0) <= 0) {{
                    state.run.damageCooldown = 0.46;
                    state.run.shake = Math.max(state.run.shake, 0.26);
                    state.flight.stability = Math.max(0.28, state.flight.stability - 0.2);
                    state.score = Math.max(0, state.score - 8);
                    playSfx("damage");
                    burst(playerCx, playerCy, ASSET.enemy_primary, 12);
                  }}
                }} else {{
                  if (!collisionEnabled) {{
                    e.z = 2;
                    continue;
                  }}
                  if (applyPlayerDamage(1, {{ scorePenalty: 22, cooldownSec: 0.68, shake: 0.22 }})) {{
                    state.flight.checkpointCombo = 0;
                    burst(playerCx, playerCy, ASSET.enemy_primary, 16);
                  }}
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

          state.score += dt * (state.flight.speed * 0.048) * (0.7 + state.flight.altitude * 0.6) * (1 + state.run.combo * 0.026) * Number(state.run.synergy.scoreMul || 1);
        }} else if (MODE_IS_3D_RUNNER) {{
          const left = keys.has("ArrowLeft") || keys.has("a");
          const right = keys.has("ArrowRight") || keys.has("d");
          const accel = keys.has("ArrowUp") || keys.has("w");
          const brake = keys.has("ArrowDown") || keys.has("s");

          const steerDir = (right ? 1 : 0) - (left ? 1 : 0);
          state.racer.steerVelocity += steerDir * dt * Number(CONTROL.steer_accel || 9.2);
          state.racer.steerVelocity *= (1 - Math.min(0.82, dt * Number(CONTROL.steer_drag || 7.4)));
          if (!left && !right) {{
            state.racer.steerVelocity *= (1 - Math.min(0.88, dt * Number(CONTROL.steer_return || 9.8)));
          }}
          state.racer.laneFloat = clamp(state.racer.laneFloat + state.racer.steerVelocity * dt, 0, 2);
          state.player.lane = state.racer.laneFloat;

          const accelRate = Number(CONTROL.accel_rate || 240);
          const brakeRate = Number(CONTROL.brake_rate || 280);
          const drag = Number(CONTROL.drag_rate || 120);
          if (accel) state.racer.speed += accelRate * dt;
          if (brake) state.racer.speed -= brakeRate * dt;
          if (!accel && !brake) state.racer.speed -= drag * dt;
          state.racer.speed = clamp(state.racer.speed, Number(CONTROL.speed_min || 180), Number(CONTROL.speed_max || 520));
          state.racer.topSpeed = Math.max(state.racer.topSpeed || state.racer.speed, state.racer.speed);

          state.racer.curveTimer -= dt;
          if (state.racer.curveTimer <= 0) {{
            state.racer.curveTimer = rand(Number(CONTROL.curve_interval_min || 1.0), Number(CONTROL.curve_interval_max || 2.4));
            state.racer.roadCurveTarget = rand(-0.38, 0.38);
          }}
          state.racer.roadCurve += (state.racer.roadCurveTarget - state.racer.roadCurve) * Math.min(1, dt * Number(CONTROL.curve_response || 1.4));
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
          const playerDepth = 0.9;
          const roadTop = canvas.width * 0.2;
          const roadBottom = canvas.width * 0.78;
          const playerRoadHalf = roadTop + (roadBottom - roadTop) * (playerDepth * playerDepth);
          const laneX = canvas.width * 0.5 + curvePx * (1 - playerDepth) + laneNormalized * (playerRoadHalf * 0.54);
          state.player.x += (laneX - state.player.w / 2 - state.player.x) * Math.min(1, dt * Number(CONTROL.lane_lerp || 12));
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
                  state.racer.boostTimer = Math.max(state.racer.boostTimer, 2.0 + Number(state.run.synergy.boostBonus || 0));
                  state.score += 30;
                  addCombo(0.8);
                  grantXp(10);
                  playSfx("boost");
                  burst(state.player.x + state.player.w / 2, state.player.y + 4, ASSET.boost_color, 14);
                }} else {{
                  if (!collisionEnabled) {{
                    e.z = 2;
                    continue;
                  }}
                  if (applyPlayerDamage(1, {{ scorePenalty: 15, cooldownSec: 0.62, shake: 0.21 }})) {{
                    burst(state.player.x + state.player.w / 2, state.player.y + state.player.h / 2, ASSET.enemy_primary, 14);
                  }}
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

          state.score += dt * (state.racer.speed * 0.045) * (1 + state.run.combo * 0.03) * Number(state.run.synergy.scoreMul || 1);
        }} else if (CONFIG.mode === "topdown_roguelike_shooter") {{
          const tunedSpeed = Number(CONTROL.move_speed || (CONFIG.player_speed || 255));
          const dashMul = Number(CONTROL.dash_multiplier || 1.95);
          const speed = tunedSpeed * (keys.has("Shift") && consumeDash() ? dashMul : 1);
          state.player.vx = (keys.has("ArrowRight") || keys.has("d") ? 1 : 0) - (keys.has("ArrowLeft") || keys.has("a") ? 1 : 0);
          state.player.vy = (keys.has("ArrowDown") || keys.has("s") ? 1 : 0) - (keys.has("ArrowUp") || keys.has("w") ? 1 : 0);
          state.player.x = clamp(state.player.x + state.player.vx * speed * dt, 20, canvas.width - state.player.w - 20);
          state.player.y = clamp(state.player.y + state.player.vy * speed * dt, 60, canvas.height - state.player.h - 20);
          state.topdown.orbitAngle += dt * Number(CONTROL.orbit_speed || 1.8);

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
              if (applyPlayerDamage(e.kind === "elite" ? 2 : 1, {{ cooldownSec: 0.6, shake: 0.22 }})) {{
                burst(state.player.x + state.player.w / 2, state.player.y + state.player.h / 2, ASSET.enemy_primary, 14);
              }}
              e.hp = 0;
            }}
          }}

          for (const b of state.bullets) b.y -= b.speed * dt;
          for (const b of state.bullets) {{
            for (const e of state.enemies) {{
              if (e.hp > 0 && rectsOverlap(b, e)) {{
                e.hp -= 1;
                b.y = -999;
                state.score += (CONFIG.base_score_value || 10) * (e.kind === "elite" ? 2.2 : 1) * (1 + Number(state.run.synergy.damageBonus || 0));
                addCombo(e.kind === "elite" ? 1.6 : 0.8);
                playSfx("hit");
                burst(e.x + e.w / 2, e.y + e.h / 2, ASSET.boost_color, e.kind === "elite" ? 12 : 8);
                if (e.hp <= 0) grantXp(e.kind === "elite" ? 24 : 12);
              }}
            }}
          }}

          state.enemies = state.enemies.filter((e) => e.hp > 0);
          state.bullets = state.bullets.filter((b) => b.y > -40);
          state.score += dt * 14 * (1 + state.run.combo * 0.04) * Number(state.run.synergy.scoreMul || 1);
        }} else if (CONFIG.mode === "arena_shooter") {{
          const speed = Number(CONTROL.move_speed || (CONFIG.player_speed || 260));
          state.player.vx = (keys.has("ArrowRight") || keys.has("d") ? 1 : 0) - (keys.has("ArrowLeft") || keys.has("a") ? 1 : 0);
          state.player.vy = (keys.has("ArrowDown") || keys.has("s") ? 1 : 0) - (keys.has("ArrowUp") || keys.has("w") ? 1 : 0);
          state.player.x = clamp(state.player.x + state.player.vx * speed * dt, 20, canvas.width - state.player.w - 20);
          state.player.y = clamp(state.player.y + state.player.vy * speed * dt, 60, canvas.height - state.player.h - 20);
          if (state.spawnTimer > clamp(spawnRate, 0.18, 1.15)) {{ state.spawnTimer = 0; spawnEnemy(); }}
          for (const e of state.enemies) {{
            e.y += e.speed * dt;
            if (e.y > canvas.height + 40) {{
              e.y = canvas.height + 999;
              applyPlayerDamage(1, {{ cooldownSec: 0.5, shake: 0.2 }});
            }}
            if (rectsOverlap(state.player, e)) {{
              e.y = canvas.height + 999;
              if (applyPlayerDamage(1, {{ cooldownSec: 0.58, shake: 0.2 }})) {{
                burst(state.player.x + state.player.w/2, state.player.y + state.player.h/2, ASSET.enemy_primary, 14);
              }}
            }}
          }}
          for (const b of state.bullets) b.y -= b.speed * dt;
          for (const b of state.bullets) {{
            for (const e of state.enemies) {{
              if (e.y < canvas.height + 500 && rectsOverlap(b, e)) {{
                e.y = canvas.height + 999;
                b.y = -999;
                const scoreGain = (CONFIG.base_score_value || 10) * (e.kind === "elite" ? 2.0 : 1) * (1 + Number(state.run.synergy.damageBonus || 0));
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
          state.score += dt * 8 * (1 + state.run.combo * 0.03) * Number(state.run.synergy.scoreMul || 1);
        }} else if (MODE_IS_BRAWLER) {{
          const baseSpeed = Number(CONTROL.move_speed || (CONFIG.player_speed || 220));
          const dashMultiplier = Number(CONTROL.dash_multiplier || 1.8);
          const speed = keys.has("Shift") && consumeDash() ? baseSpeed * dashMultiplier : baseSpeed;
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
              if (applyPlayerDamage(e.kind === "elite" ? 2 : 1, {{ cooldownSec: 0.66, shake: 0.22 }})) {{
                state.player.x = clamp(state.player.x - (dx / len) * 35, 20, canvas.width - state.player.w - 20);
                state.player.y = clamp(state.player.y - (dy / len) * 35, 60, canvas.height - state.player.h - 20);
                burst(state.player.x + state.player.w/2, state.player.y + state.player.h/2, ASSET.enemy_primary, 10);
              }}
            }}
          }}
          state.score += dt * (CONFIG.mode === "comic_action_brawler_3d" ? 12 : 8) * (1 + state.run.combo * 0.03) * Number(state.run.synergy.scoreMul || 1);
        }} else {{
          const speed = Number(CONTROL.move_speed || 240);
          state.player.vx = (keys.has("ArrowRight") ? 1 : 0) - (keys.has("ArrowLeft") ? 1 : 0);
          state.player.vy = (keys.has("ArrowDown") ? 1 : 0) - (keys.has("ArrowUp") ? 1 : 0);
          state.player.x = clamp(state.player.x + state.player.vx * speed * dt, 20, canvas.width - state.player.w - 20);
          state.player.y = clamp(state.player.y + state.player.vy * speed * dt, 60, canvas.height - state.player.h - 20);
          if (state.spawnTimer > 0.6) {{ state.spawnTimer = 0; spawnEnemy(); }}
          for (const e of state.enemies) {{
            e.y += e.speed * dt;
            if (rectsOverlap(state.player, e)) {{
              applyPlayerDamage(1, {{ cooldownSec: 0.5, shake: 0.2 }});
              e.y = canvas.height + 999;
              burst(state.player.x + state.player.w / 2, state.player.y + state.player.h / 2, ASSET.enemy_primary, 8);
            }}
          }}
          state.enemies = state.enemies.filter((e) => e.y < canvas.height + 100);
          state.score += dt * 10 * (1 + state.run.combo * 0.03) * Number(state.run.synergy.scoreMul || 1);
        }}

        for (const p of state.particles) {{
          p.t += dt;
          p.x += p.vx * dt;
          p.y += p.vy * dt;
        }}
        state.particles = state.particles.filter((p) => p.t < p.life);

        const engagementUnlocked = state.engagement.inputActivated || state.runtimeSec >= Number(state.engagement.guardSeconds || 2.8);
        if (!engagementUnlocked && state.hp <= 0) {{
          state.hp = 1;
        }}
        if (engagementUnlocked && (state.timeLeft <= 0 || state.hp <= 0)) {{
          endGame();
        }}
        updateHud();
      }}

""")
