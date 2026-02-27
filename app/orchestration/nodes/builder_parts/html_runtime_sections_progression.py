from __future__ import annotations

from app.orchestration.nodes.builder_parts.html_runtime_sections_shared import _normalize_escaped_braces


def build_runtime_progression_functions_js() -> str:
    return _normalize_escaped_braces(r"""      function grantXp(amount) {{
        state.run.xp += amount;
        while (state.run.xp >= state.run.nextXp) {{
          state.run.xp -= state.run.nextXp;
          state.run.nextXp = Math.floor(state.run.nextXp * Number(PROGRESSION_TUNING.next_xp_multiplier || 1.2));
          const picks = Array.isArray(UPGRADE_PICKS) && UPGRADE_PICKS.length > 0 ? UPGRADE_PICKS : ["attack_speed", "mobility", "damage", "sustain", "burst"];
          const pick = picks[Math.floor(Math.random() * picks.length)];
          state.run.upgrades.push(pick);
          if (pick === "attack_speed") {{
            CONFIG.player_attack_cooldown = Math.max(
              Number(PROGRESSION_TUNING.attack_speed_cooldown_floor || 0.16),
              (CONFIG.player_attack_cooldown || 0.5) * Number(PROGRESSION_TUNING.attack_speed_cooldown_multiplier || 0.88)
            );
          }}
          if (pick === "mobility") {{
            CONFIG.player_speed = Math.min(
              Number(PROGRESSION_TUNING.mobility_speed_cap || 460),
              (CONFIG.player_speed || 240) + Number(PROGRESSION_TUNING.mobility_speed_add || 20)
            );
          }}
          if (pick === "damage") {{
            CONFIG.base_score_value = Math.min(
              Number(PROGRESSION_TUNING.damage_score_cap || 220),
              (CONFIG.base_score_value || 10) + Number(PROGRESSION_TUNING.damage_score_add || 5)
            );
          }}
          if (pick === "sustain") state.hp = Math.min((CONFIG.player_hp || 3) + 2, state.hp + 1);
          if (pick === "burst") {{
            state.run.combo = Math.min(
              Number(PROGRESSION_TUNING.combo_cap || 20),
              state.run.combo + Number(PROGRESSION_TUNING.burst_combo_add || 1.8)
            );
          }}
          state.run.relics.push(`Relic-${{pick}}-${{state.run.level}}`);
          applyRelicSynergy();
          playSfx("levelup");
          playSfx("relic");
          state.run.fxPulse = Math.max(state.run.fxPulse, 0.28);
        }}
      }}

      function stepProgression(dt) {{
        state.run.levelTimer += dt;
        state.run.waveTimer += dt;
        state.run.minibossTimer += dt;
        state.run.comboTimer = Math.max(0, state.run.comboTimer - dt);
        state.run.shake = Math.max(0, state.run.shake - dt * Number(PROGRESSION_TUNING.shake_decay_per_sec || 1.8));
        state.run.fxPulse = Math.max(0, state.run.fxPulse - dt * Number(PROGRESSION_TUNING.fx_pulse_decay_per_sec || 0.8));
        state.run.eliteTimer += dt;
        if (state.run.synergy.hpRegenTick > 0 && state.timeLeft > 0) {{
          state.hp = Math.min((CONFIG.player_hp || 3) + 2, state.hp + state.run.synergy.hpRegenTick * dt);
        }}
        if (state.run.comboTimer <= 0) state.run.combo = Math.max(0, state.run.combo - dt * Number(PROGRESSION_TUNING.combo_decay_per_sec || 2.2));
        if (state.run.waveTimer >= Number(ACTIVE_DEPTH_PACK.wave_interval_sec || PROGRESSION_TUNING.wave_interval_sec_default || 8.0)) {{
          state.run.waveTimer = 0;
          const waveMods = Array.isArray(ACTIVE_DEPTH_PACK.wave_modifiers) ? ACTIVE_DEPTH_PACK.wave_modifiers : [1.0];
          state.run.waveIndex = (state.run.waveIndex + 1) % Math.max(1, waveMods.length);
          state.run.waveModifier = Number(waveMods[state.run.waveIndex] || 1);
          state.run.shake = Math.max(state.run.shake, Number(PROGRESSION_TUNING.wave_shake_floor || 0.12));
          state.run.fxPulse = Math.max(state.run.fxPulse, Number(PROGRESSION_TUNING.wave_fx_pulse_floor || 0.24));
        }}
        if (state.run.minibossTimer >= Number(ACTIVE_DEPTH_PACK.miniboss_interval_sec || PROGRESSION_TUNING.miniboss_interval_sec_default || 24.0)) {{
          state.run.minibossTimer = 0;
          spawnMiniBoss();
        }}
        if (state.run.levelTimer >= Number(PROGRESSION_TUNING.level_interval_sec || 12)) {{
          state.run.levelTimer = 0;
          state.run.level += 1;
          state.run.difficultyScale = (1 + (state.run.level - 1) * Number(PROGRESSION_TUNING.level_difficulty_step || 0.11))
            * Math.max(1, state.run.waveModifier);
          burst(canvas.width * 0.5, 80, ASSET.particle, 20);
          grantXp(Number(PROGRESSION_TUNING.level_xp_base || 30) + state.run.level * Number(PROGRESSION_TUNING.level_xp_step || 6));
          playSfx("levelup");
          state.run.fxPulse = Math.max(state.run.fxPulse, Number(PROGRESSION_TUNING.level_fx_pulse_floor || 0.35));
        }}
      }}

      function addCombo(points) {{
        state.run.combo = clamp(state.run.combo + points, 0, Number(PROGRESSION_TUNING.combo_cap || 20));
        state.run.comboTimer = Number(PROGRESSION_TUNING.combo_timer_window_sec || 2.3);
      }}

      function consumeDash() {{
        if (state.dashCooldown > 0) return false;
        state.dashCooldown = Number(PROGRESSION_TUNING.dash_cooldown_sec || 1.35);
        state.run.shake = Number(PROGRESSION_TUNING.dash_shake_value || 0.2);
        return true;
      }}""")
