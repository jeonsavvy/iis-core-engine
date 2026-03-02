from __future__ import annotations

from app.orchestration.nodes.builder_parts.html_runtime_sections_shared import _normalize_escaped_braces


def build_runtime_utility_functions_js() -> str:
    return _normalize_escaped_braces(r"""      function restartGame() {{ resetState(); }}

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

      function pickWeighted(entries, fallback) {{
        if (!Array.isArray(entries) || entries.length === 0) return fallback;
        let total = 0;
        for (const entry of entries) {{
          const weight = Number(entry?.[1] || 0);
          if (weight > 0) total += weight;
        }}
        if (total <= 0) return fallback;
        let roll = Math.random() * total;
        for (const entry of entries) {{
          const weight = Number(entry?.[1] || 0);
          if (weight <= 0) continue;
          roll -= weight;
          if (roll <= 0) return String(entry?.[0] || fallback);
        }}
        return fallback;
      }}

      function applyPlayerDamage(amount, options = {{}}) {{
        const modeCooldownFloor = MODE_IS_BRAWLER ? 0.88 : MODE_IS_3D_RUNNER ? 0.78 : 0.62;
        const cooldown = Math.max(modeCooldownFloor, Number(options.cooldownSec ?? modeCooldownFloor));
        if ((state.run.damageCooldown || 0) > 0) return false;
        const requestedDamage = Math.max(1, Number(amount || 1));
        const hpDamage = MODE_IS_BRAWLER
          ? Math.max(1, Math.floor(requestedDamage * 0.7 + 0.3))
          : MODE_IS_3D_RUNNER
            ? Math.max(1, Math.floor(requestedDamage * 0.82 + 0.25))
            : requestedDamage;
        state.hp -= hpDamage;
        const scorePenalty = Math.max(0, Number(options.scorePenalty || 0));
        if (scorePenalty > 0) {{
          state.score = Math.max(0, state.score - scorePenalty);
        }}
        state.run.combo = 0;
        state.run.damageCooldown = cooldown;
        state.run.shake = Math.max(state.run.shake, Math.max(0.18, Number(options.shake || 0.22)));
        playSfx("damage");
        return true;
      }}

      function applyRelicSynergy() {{
        const upgrades = new Set(state.run.upgrades);
        const synergy = {{
          scoreMul: 1,
          spawnEase: 1,
          boostBonus: 0,
          damageBonus: 0,
          hpRegenTick: 0,
          active: [],
        }};
        for (const rule of RELIC_SYNERGY_RULES) {{
          const requires = Array.isArray(rule.requires) ? rule.requires : [];
          if (!requires.every((token) => upgrades.has(token))) continue;
          synergy.scoreMul *= Number(rule.score_mul || 1);
          synergy.spawnEase *= Number(rule.spawn_ease || 1);
          synergy.boostBonus += Number(rule.boost_bonus || 0);
          synergy.damageBonus += Number(rule.damage_bonus || 0);
          synergy.hpRegenTick += Number(rule.hp_regen_tick || 0);
          synergy.active.push(String(rule.id || "synergy"));
        }}
        state.run.synergy = synergy;
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

        if (kind === "boost" || kind === "levelup" || kind === "relic") {{
          const pad = ac.createOscillator();
          const padGain = ac.createGain();
          pad.connect(padGain);
          padGain.connect(ac.destination);
          pad.type = "sine";
          pad.frequency.setValueAtTime(Math.max(90, freq * 0.5), now);
          pad.frequency.exponentialRampToValueAtTime(Math.max(80, freq * 0.38), now + 0.2);
          padGain.gain.setValueAtTime(0.0001, now);
          padGain.gain.exponentialRampToValueAtTime(0.03, now + 0.04);
          padGain.gain.exponentialRampToValueAtTime(0.0001, now + 0.22);
          pad.start(now);
          pad.stop(now + 0.24);
        }}
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
      }}""")
