from __future__ import annotations

from typing import Any

from app.orchestration.nodes.builder_core.module_registry import list_runtime_modules, module_signature


def _module_source(module_id: str) -> str:
    if module_id == "scene_world":
        return """
runtimeModules.scene_world = {
  buildWorld(state) {
    state.worldObjects = [];
    for (let i = 0; i < 22; i++) {
      state.worldObjects.push({
        kind: i % 5 === 0 ? "interactive" : "environment",
        x: (Math.random() - 0.5) * 22,
        y: 0,
        z: 15 + (i * 8),
        radius: 0.7 + Math.random() * 0.8,
      });
    }
  },
};
""".strip()
    if module_id == "camera_stack":
        return """
runtimeModules.camera_stack = {
  createPerspective(fovRad, aspect, near, far) {
    const f = 1.0 / Math.tan(fovRad / 2);
    return [
      f / aspect, 0, 0, 0,
      0, f, 0, 0,
      0, 0, (far + near) / (near - far), -1,
      0, 0, (2 * far * near) / (near - far), 0,
    ];
  },
  project(state, p) {
    const depth = Math.max(1.2, p.z - state.camera.z);
    const scale = state.camera.focal / depth;
    return {
      x: state.viewport.w * 0.5 + (p.x - state.camera.x) * scale,
      y: state.viewport.h * 0.62 - (p.y - state.camera.y) * scale,
      s: scale,
      depth,
    };
  },
};
""".strip()
    if module_id == "controller_stack":
        return """
runtimeModules.controller_stack = {
  update(state, dt) {
    const locomotion = state.runtimeProfile.locomotionModel;
    if (locomotion === "flight") {
      const pitchInput = (state.input.pitchUp ? 1 : 0) - (state.input.pitchDown ? 1 : 0);
      const rollInput = (state.input.rollRight ? 1 : 0) - (state.input.rollLeft ? 1 : 0);
      const yawInput = (state.input.yawRight ? 1 : 0) - (state.input.yawLeft ? 1 : 0);
      const throttleInput = (state.input.throttleUp ? 1 : 0) - (state.input.throttleDown ? 1 : 0);
      state.flight.throttle = Math.max(0.35, Math.min(1.85, state.flight.throttle + throttleInput * dt * 0.65));
      state.flight.pitch = Math.max(-1.2, Math.min(1.2, state.flight.pitch + pitchInput * dt * 2.1));
      state.flight.roll = Math.max(-1.3, Math.min(1.3, state.flight.roll + rollInput * dt * 2.2));
      state.flight.yaw += yawInput * dt * 1.6;
      state.player.vx += (Math.sin(state.flight.yaw) * state.flight.throttle * 12 - state.player.vx * 1.8) * dt;
      state.player.vy += (state.flight.pitch * state.flight.throttle * 8 - state.player.vy * 2.2) * dt;
      state.player.vz = Math.max(6, (state.flight.speedBase + (state.flight.throttle * 22)) * (state.input.sprint ? 1.15 : 1.0));
      state.player.x += state.player.vx * dt;
      state.player.y += state.player.vy * dt;
      state.player.z += state.player.vz * dt;
      state.player.x = Math.max(-16, Math.min(16, state.player.x));
      state.player.y = Math.max(-4.5, Math.min(9.5, state.player.y));
      return;
    }

    const axisX = (state.input.right ? 1 : 0) - (state.input.left ? 1 : 0);
    const axisY = (state.input.up ? 1 : 0) - (state.input.down ? 1 : 0);
    const sprint = state.input.sprint ? 1.5 : 1.0;
    const accel = 8.4 * sprint;
    state.player.vx += (axisX * accel - state.player.vx * 3.8) * dt;
    state.player.vz += (axisY * accel - state.player.vz * 3.8) * dt;
    state.player.x += state.player.vx * dt;
    state.player.z += state.player.vz * dt;
    state.player.x = Math.max(-10, Math.min(10, state.player.x));
    state.player.z = Math.max(1.5, Math.min(42, state.player.z));
    if (state.input.toggleMode) {
      state.player.mode = state.player.mode === "precision" ? "aggressive" : "precision";
      state.input.toggleMode = false;
    }
  },
};
""".strip()
    if module_id == "combat_stack":
        return """
runtimeModules.combat_stack = {
  update(state, dt) {
    if (state.runtimeProfile.interactionModel === "navigation") {
      return;
    }
    state.player.attackCooldown = Math.max(0, state.player.attackCooldown - dt);
    if (state.input.attack && state.player.attackCooldown <= 0) {
      state.player.attackCooldown = 0.24;
      state.projectiles.push({
        x: state.player.x,
        y: 0.2,
        z: state.player.z + 1.2,
        vx: 0,
        vz: 18,
        ttl: 1.6,
      });
      state.feedback.hitPulse = 1;
    }
    for (const bullet of state.projectiles) {
      bullet.x += bullet.vx * dt;
      bullet.z += bullet.vz * dt;
      bullet.ttl -= dt;
    }
    state.projectiles = state.projectiles.filter((bullet) => bullet.ttl > 0);
  },
};
""".strip()
    if module_id == "progression_stack":
        return """
runtimeModules.progression_stack = {
  update(state, dt) {
    state.progress.time += dt;
    state.progress.waveTimer += dt;
    if (state.runtimeProfile.locomotionModel === "flight") {
      if (state.progress.waveTimer >= 1.15) {
        state.progress.waveTimer = 0;
        state.checkpoints.push({
          x: (Math.random() - 0.5) * 18,
          y: -1.2 + Math.random() * 8.2,
          z: state.player.z + 30 + Math.random() * 22,
          radius: 1.4 + Math.random() * 1.2,
          reward: 45,
          kind: "checkpoint",
        });
      }
      state.checkpoints = state.checkpoints.filter((checkpoint) => checkpoint.z > state.player.z - 6);
      for (const checkpoint of state.checkpoints) {
        const dx = checkpoint.x - state.player.x;
        const dy = checkpoint.y - state.player.y;
        const dz = checkpoint.z - state.player.z;
        const distSq = dx * dx + dy * dy + dz * dz;
        if (distSq <= (checkpoint.radius * checkpoint.radius) * 1.3) {
          checkpoint.passed = true;
          state.score += checkpoint.reward;
          state.timeLeft = Math.min(120, state.timeLeft + 1.8);
          state.progress.objective = "Waypoints linked. Keep stable vector.";
        }
      }
      state.checkpoints = state.checkpoints.filter((checkpoint) => !checkpoint.passed);
      return;
    }
    if (state.progress.waveTimer >= state.progress.spawnCadence) {
      state.progress.waveTimer = 0;
      state.enemies.push({
        x: (Math.random() - 0.5) * 18,
        y: 0,
        z: 30 + Math.random() * 20,
        hp: 2 + Math.floor(state.progress.wave * 0.5),
        speed: 2.2 + (state.progress.wave * 0.18),
        kind: state.progress.wave % 4 === 0 ? "elite" : "enemy",
      });
      if (state.progress.wave % 3 === 0) {
        state.interactives.push({
          x: (Math.random() - 0.5) * 16,
          y: 0,
          z: 14 + Math.random() * 14,
          reward: 25,
        });
      }
      state.progress.wave += 1;
    }
  },
};
""".strip()
    if module_id == "feedback_stack":
        return """
runtimeModules.feedback_stack = {
  update(state, dt) {
    state.feedback.hitPulse = Math.max(0, state.feedback.hitPulse - dt * 2.8);
    state.feedback.damagePulse = Math.max(0, state.feedback.damagePulse - dt * 1.8);
    state.feedback.cameraShake = Math.max(0, state.feedback.cameraShake - dt * 2.4);
  },
  emitDamage(state) {
    state.feedback.damagePulse = 1;
    state.feedback.cameraShake = 0.6;
  },
};
""".strip()
    if module_id == "hud_stack":
        return """
runtimeModules.hud_stack = {
  render(state, scoreEl, timerEl, hpEl, objectiveEl) {
    scoreEl.textContent = `Score: ${Math.floor(state.score)} · Combo x${state.player.combo.toFixed(1)}`;
    timerEl.textContent = `Time: ${Math.max(0, state.timeLeft).toFixed(1)}s`;
    hpEl.textContent = state.runtimeProfile.locomotionModel === "flight"
      ? `Stability: ${Math.max(0, Math.round(state.flight.throttle * 100))}%`
      : `HP: ${Math.max(0, state.hp)}`;
    objectiveEl.textContent = state.progress.objective;
  },
};
""".strip()
    optional_sources: dict[str, str] = {
        "flight_physics": "runtimeModules.flight_physics = { enabled: true };",
        "vehicle_dynamics": "runtimeModules.vehicle_dynamics = { enabled: true };",
        "projectile_system": "runtimeModules.projectile_system = { enabled: true };",
        "combo_chain": "runtimeModules.combo_chain = { enabled: true };",
        "checkpoint_loop": "runtimeModules.checkpoint_loop = { enabled: true };",
        "camera_fx": "runtimeModules.camera_fx = { enabled: true };",
    }
    return optional_sources.get(module_id, f"runtimeModules['{module_id}'] = {{ enabled: true }};")


def assemble_runtime_modules(*, module_plan: dict[str, Any], capability_profile: dict[str, Any]) -> dict[str, Any]:
    primary = [str(module_id) for module_id in module_plan.get("primary_modules", []) if str(module_id).strip()]
    optional = [str(module_id) for module_id in module_plan.get("optional_modules", []) if str(module_id).strip()]
    selected_ids = list(dict.fromkeys(primary + optional))
    modules = list_runtime_modules(selected_ids)
    module_sources = [_module_source(module.module_id) for module in modules]
    signature = module_signature(selected_ids)

    return {
        "module_ids": selected_ids,
        "runtime_modules": [
            {
                "module_id": module.module_id,
                "layer": module.layer,
                "version": module.version,
                "capability_tags": list(module.capability_tags),
                "stability_score": module.stability_score,
                "description": module.description,
            }
            for module in modules
        ],
        "module_sources": module_sources,
        "module_signature": signature,
        "capability_profile": capability_profile,
    }
