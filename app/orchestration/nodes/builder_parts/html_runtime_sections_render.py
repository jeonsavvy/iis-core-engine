from __future__ import annotations

from app.orchestration.nodes.builder_parts.html_runtime_sections_shared import _normalize_escaped_braces


def build_runtime_render_functions_js() -> str:
    return _normalize_escaped_braces(r"""      function drawPostFx() {{
        const pulse = clamp(Number(state.run.fxPulse || 0), 0, 1);
        const boostGlow = clamp((state.racer.boostTimer || 0) * 0.3, 0, 0.65);
        const vignette = ctx.createRadialGradient(
          canvas.width * 0.5,
          canvas.height * 0.46,
          canvas.height * 0.18,
          canvas.width * 0.5,
          canvas.height * 0.52,
          canvas.height * 0.88,
        );
        vignette.addColorStop(0, "rgba(2, 6, 23, 0)");
        vignette.addColorStop(1, "rgba(2, 6, 23, 0.42)");
        ctx.fillStyle = vignette;
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        const accentAlpha = Math.min(0.32, 0.08 + pulse * 0.42 + boostGlow * 0.35);
        const overlay = ctx.createLinearGradient(0, 0, 0, canvas.height);
        overlay.addColorStop(0, `rgba(34, 211, 238, ${{accentAlpha * 0.45}})`);
        overlay.addColorStop(0.6, "rgba(15, 23, 42, 0)");
        overlay.addColorStop(1, `rgba(16, 24, 40, ${{accentAlpha}})`);
        ctx.fillStyle = overlay;
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        const scanAlpha = 0.05 + pulse * 0.06;
        ctx.fillStyle = `rgba(148, 163, 184, ${{scanAlpha}})`;
        for (let y = 0; y < canvas.height; y += 4) {{
          ctx.fillRect(0, y, canvas.width, 1);
        }}
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
          const horizonY = MODE_IS_FORMULA_CIRCUIT ? canvas.height * 0.22 : canvas.height * 0.2;
          const roadTop = MODE_IS_FORMULA_CIRCUIT ? canvas.width * 0.26 : canvas.width * 0.2;
          const roadBottom = MODE_IS_FORMULA_CIRCUIT ? canvas.width * 0.88 : canvas.width * 0.78;
          const curvePx = state.racer.roadCurve * canvas.width * (MODE_IS_FORMULA_CIRCUIT ? 0.2 : 0.16);

          const webglRendered = (CONFIG.mode === "webgl_three_runner" || MODE_IS_FORMULA_CIRCUIT)
            ? renderWebglBackground(1 / 60)
            : false;
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

          if (MODE_IS_FORMULA_CIRCUIT) {{
            for (let side = -1; side <= 1; side += 2) {{
              ctx.lineWidth = 5;
              for (let i = 0; i <= 28; i++) {{
                const t = i / 28;
                const tt = t * t;
                const y = horizonY + tt * (canvas.height - horizonY);
                const roadHalf = roadTop + (roadBottom - roadTop) * tt;
                const cx = canvas.width / 2 + curvePx * (1 - t);
                const x = cx + roadHalf * side;
                const stripe = (i + Math.floor(state.racer.roadScroll * 0.02)) % 2 === 0;
                ctx.strokeStyle = stripe ? "rgba(248, 113, 113, 0.95)" : "rgba(241, 245, 249, 0.92)";
                ctx.beginPath();
                ctx.moveTo(x - side * 6, y);
                ctx.lineTo(x + side * 6, y);
                ctx.stroke();
              }}
            }}
            ctx.strokeStyle = "rgba(56, 189, 248, 0.34)";
            ctx.lineWidth = 2;
            for (let side = -1; side <= 1; side += 2) {{
              ctx.beginPath();
              for (let i = 0; i <= 24; i++) {{
                const t = i / 24;
                const tt = t * t;
                const y = horizonY + tt * (canvas.height - horizonY);
                const roadHalf = roadTop + (roadBottom - roadTop) * tt;
                const cx = canvas.width / 2 + curvePx * (1 - t);
                const x = cx + roadHalf * side + side * 18;
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
              }}
              ctx.stroke();
            }}
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
            const laneOffset = (e.lane || 0) * roadHalf * (MODE_IS_FORMULA_CIRCUIT ? 0.72 : 0.54);
            const scale = 0.28 + t * 1.05;
            const ew = (e.w || 30) * scale;
            const eh = (e.h || 50) * scale;
            const ex = cx + laneOffset - ew / 2;
            const ey = y - eh;
            const allowRunnerSprite = MODE_IS_FORMULA_CIRCUIT;

            if (e.kind === "boost") {{
              if (allowRunnerSprite && drawSprite("boost", ex, ey, ew, eh, 0.96)) continue;
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
            }} else if (MODE_IS_FORMULA_CIRCUIT && e.kind === "checkpoint") {{
              if (allowRunnerSprite && drawSprite("ring", ex, ey, ew * 1.18, eh * 0.82, 0.98)) continue;
              ctx.strokeStyle = ASSET.boost_color;
              ctx.lineWidth = Math.max(3, ew * 0.08);
              ctx.shadowBlur = 16;
              ctx.shadowColor = ASSET.boost_color;
              ctx.strokeRect(ex - ew * 0.06, ey + eh * 0.08, ew * 1.12, eh * 0.7);
            }} else {{
              const eliteRender = e.kind === "elite" || e.kind === "opponent_elite" || e.miniBoss || (e.hp || 0) > 1;
              if (allowRunnerSprite && drawSprite(eliteRender ? "elite" : "enemy", ex, ey, ew, eh, 0.97)) continue;
              const bodyColor = eliteRender ? ASSET.enemy_elite : ASSET.enemy_primary;
              ctx.fillStyle = bodyColor;
              ctx.shadowBlur = eliteRender ? 16 : 12;
              ctx.shadowColor = bodyColor;
              ctx.beginPath();
              ctx.moveTo(ex + ew * 0.16, ey + eh * 0.14);
              ctx.lineTo(ex + ew * 0.84, ey + eh * 0.14);
              ctx.lineTo(ex + ew * 0.96, ey + eh * 0.82);
              ctx.lineTo(ex + ew * 0.04, ey + eh * 0.82);
              ctx.closePath();
              ctx.fill();
              ctx.fillStyle = ASSET.track;
              ctx.fillRect(ex + ew * 0.18, ey + eh * 0.26, ew * 0.64, eh * 0.22);
              ctx.fillStyle = "rgba(241,245,249,0.9)";
              ctx.fillRect(ex + ew * 0.14, ey + eh * 0.74, ew * 0.22, eh * 0.12);
              ctx.fillRect(ex + ew * 0.64, ey + eh * 0.74, ew * 0.22, eh * 0.12);
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
            const isElite = e.kind === "elite" || e.miniBoss || (e.hp || 0) > 2;
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
          const allowRunnerSprite = MODE_IS_FORMULA_CIRCUIT;
          if (allowRunnerSprite && drawSprite("player", px - 2, py - 6, pw + 4, ph + 10, 0.98)) {{
            if (state.racer.boostTimer > 0) {{
              drawSprite("trail", px + pw * 0.34, py + ph * 0.9, pw * 0.32, ph * 0.62, 0.74);
            }}
          }} else {{
          ctx.shadowBlur = 18;
          ctx.shadowColor = state.racer.boostTimer > 0 ? ASSET.boost_color : ASSET.player_primary;
          if (MODE_IS_FORMULA_CIRCUIT) {{
            ctx.fillStyle = ASSET.player_primary;
            ctx.fillRect(px + pw * 0.35, py - ph * 0.06, pw * 0.3, ph * 1.02);
            ctx.fillRect(px + pw * 0.14, py + ph * 0.25, pw * 0.72, ph * 0.18);
            ctx.fillRect(px + pw * 0.02, py + ph * 0.56, pw * 0.96, ph * 0.16);
            ctx.fillStyle = ASSET.player_secondary;
            ctx.fillRect(px + pw * 0.42, py + ph * 0.08, pw * 0.16, ph * 0.22);
            ctx.beginPath();
            ctx.arc(px + pw * 0.2, py + ph * 0.86, pw * 0.11, 0, Math.PI * 2);
            ctx.arc(px + pw * 0.8, py + ph * 0.86, pw * 0.11, 0, Math.PI * 2);
            ctx.fill();
            if (state.racer.boostTimer > 0) {{
              ctx.fillStyle = ASSET.boost_color;
              ctx.fillRect(px + pw * 0.44, py + ph * 0.92, pw * 0.12, ph * 0.34);
            }}
          }} else {{
            ctx.fillStyle = ASSET.player_primary;
            ctx.beginPath();
            ctx.moveTo(px + pw * 0.18, py + ph * 0.15);
            ctx.lineTo(px + pw * 0.82, py + ph * 0.15);
            ctx.lineTo(px + pw * 0.94, py + ph * 0.82);
            ctx.lineTo(px + pw * 0.06, py + ph * 0.82);
            ctx.closePath();
            ctx.fill();
            ctx.fillStyle = ASSET.player_secondary;
            ctx.fillRect(px + pw * 0.24, py + ph * 0.28, pw * 0.52, ph * 0.22);
            ctx.fillStyle = ASSET.track;
            ctx.fillRect(px + pw * 0.12, py + ph * 0.7, pw * 0.2, ph * 0.14);
            ctx.fillRect(px + pw * 0.68, py + ph * 0.7, pw * 0.2, ph * 0.14);
            if (state.racer.boostTimer > 0) {{
              ctx.fillStyle = ASSET.boost_color;
              ctx.fillRect(px + pw * 0.44, py + ph * 0.86, pw * 0.12, ph * 0.28);
            }}
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
        drawPostFx();
        ctx.shadowBlur = 0;
        ctx.restore();
      }}

""")


def build_runtime_hud_functions_js() -> str:
    return _normalize_escaped_braces(r"""      function updateHud() {{
        const showCombo = MODE_IS_BRAWLER || MODE_IS_SHOOTER;
        scoreEl.textContent = showCombo
          ? `Score: ${{Math.floor(state.score)}} · Combo: x${{Math.max(1, state.run.combo.toFixed(1))}}`
          : `Score: ${{Math.floor(state.score)}}`;
        if (MODE_IS_FLIGHT_SIM) {{
          timerEl.textContent = `Time: ${{state.timeLeft.toFixed(1)}} · Speed ${{Math.round(state.flight.speed)}}`;
          hpEl.textContent = `HP: ${{Math.max(0, state.hp)}} · Alt ${{Math.round(state.flight.altitude * 100)}}%`;
          return;
        }}
        if (MODE_IS_FORMULA_CIRCUIT) {{
          const bestLapText = state.formula.bestLap < 998 ? `${{state.formula.bestLap.toFixed(1)}}s` : "--";
          timerEl.textContent = `Time: ${{state.timeLeft.toFixed(1)}} · Lap ${{state.formula.lap}} · CKP ${{state.formula.checkpoints}}/${{state.formula.checkpointsPerLap}} · Best ${{bestLapText}}`;
          hpEl.textContent = `HP: ${{Math.max(0, state.hp)}} · Speed ${{Math.round(state.racer.speed)}}`;
          return;
        }}
        if (MODE_IS_3D_RUNNER) {{
          timerEl.textContent = `Time: ${{state.timeLeft.toFixed(1)}} · Speed ${{Math.round(state.racer.speed)}}`;
          hpEl.textContent = `HP: ${{Math.max(0, state.hp)}} · Boost ${{state.racer.boostTimer > 0 ? "ON" : "OFF"}}`;
          return;
        }}
        timerEl.textContent = `Time: ${{state.timeLeft.toFixed(1)}}`;
        hpEl.textContent = `HP: ${{Math.max(0, state.hp)}}`;
      }}

      function endGame() {{
        if (!state.running) return;
        state.running = false;
        const playedSec = Math.max(0, Number((CONFIG.time_limit_sec || 60) - state.timeLeft));
        if (MODE_IS_FORMULA_CIRCUIT) {{
          overlayText.textContent = `최종 점수 ${{Math.floor(state.score)}} · 랩 ${{state.formula.lap}} · 최고속도 ${{Math.round(state.racer.topSpeed || state.racer.speed)}} · R 재시작`;
        }} else if (MODE_IS_3D_RUNNER) {{
          overlayText.textContent = `최종 점수 ${{Math.floor(state.score)}} · 주행 ${{playedSec.toFixed(1)}}초 · 최고속도 ${{Math.round(state.racer.topSpeed || state.racer.speed)}} · R 재시작`;
        }} else if (MODE_IS_FLIGHT_SIM) {{
          overlayText.textContent = `최종 점수 ${{Math.floor(state.score)}} · 비행 ${{playedSec.toFixed(1)}}초 · 고도 ${{Math.round(state.flight.altitude * 100)}}% · R 재시작`;
        }} else {{
          overlayText.textContent = `최종 점수 ${{Math.floor(state.score)}} · 플레이 ${{playedSec.toFixed(1)}}초 · R 재시작`;
        }}
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

""")
