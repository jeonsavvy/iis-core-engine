from __future__ import annotations

from textwrap import dedent

from app.agents.scaffolds.base import ScaffoldSeed


FLIGHT_HTML = dedent(
    """
    <!doctype html>
    <html lang="ko">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>IIS Space Dogfight Seed</title>
      <style>
        html, body { margin: 0; height: 100%; overflow: hidden; background: radial-gradient(circle at top, #0b1230 0%, #02040b 70%); font-family: Inter, system-ui, sans-serif; color: #f8fafc; }
        #app { position: relative; width: 100%; height: 100%; }
        canvas { display: block; width: 100%; height: 100%; }
        #reticle { position: absolute; left: 50%; top: 50%; width: 28px; height: 28px; transform: translate(-50%, -50%); border: 2px solid rgba(34, 211, 238, 0.7); border-radius: 999px; pointer-events: none; box-shadow: 0 0 18px rgba(34, 211, 238, 0.28); }
        #reticle::before, #reticle::after { content: ""; position: absolute; background: rgba(34, 211, 238, 0.9); }
        #reticle::before { width: 2px; height: 40px; left: 50%; top: -6px; transform: translateX(-50%); }
        #reticle::after { width: 40px; height: 2px; top: 50%; left: -6px; transform: translateY(-50%); }
        #target-box { position: absolute; left: 58%; top: 42%; width: 78px; height: 78px; transform: translate(-50%, -50%); border: 2px solid rgba(248, 113, 113, 0.72); border-radius: 12px; pointer-events: none; box-shadow: 0 0 24px rgba(248, 113, 113, 0.18); }
        #hud { position: absolute; top: 18px; left: 18px; display: grid; gap: 6px; padding: 14px 16px; min-width: 240px; border-radius: 14px; background: rgba(2, 6, 23, 0.5); border: 1px solid rgba(56, 189, 248, 0.32); backdrop-filter: blur(12px); }
        #hud strong { font-size: 26px; color: #22d3ee; }
        #hud span { font-size: 13px; color: #dbeafe; }
        #controls { position: absolute; top: 18px; right: 18px; max-width: 290px; padding: 12px 14px; border-radius: 12px; background: rgba(15, 23, 42, 0.55); border: 1px solid rgba(148, 163, 184, 0.25); line-height: 1.45; font-size: 12px; }
        #cockpit-bars { position: absolute; inset: 0; pointer-events: none; }
        #cockpit-bars::before, #cockpit-bars::after { content: ""; position: absolute; top: 0; bottom: 0; width: 18%; background: linear-gradient(180deg, rgba(10, 18, 35, 0.88), rgba(10, 18, 35, 0.25) 24%, rgba(10, 18, 35, 0.88)); }
        #cockpit-bars::before { left: 0; clip-path: polygon(0 0, 100% 0, 62% 100%, 0 100%); }
        #cockpit-bars::after { right: 0; clip-path: polygon(38% 0, 100% 0, 100% 100%, 0 100%); }
      </style>
    </head>
    <body>
      <div id="app">
        <div id="cockpit-bars"></div>
        <div id="reticle"></div>
        <div id="target-box"></div>
        <div id="hud">
          <span>SPACE DOGFIGHT</span>
          <strong id="throttle-readout">THROTTLE 0%</strong>
          <span id="attitude-readout">Pitch 0 · Roll 0 · Yaw 0</span>
          <span id="target-readout">Target locked: none</span>
          <span id="lock-strength-readout">Lock 0%</span>
          <span id="wave-readout">Wave 1 · Enemies 3</span>
          <span id="hp">Shield 100%</span>
          <span id="status-readout">Boost ready · Cannons online</span>
        </div>
        <div id="controls">
          <b>Controls</b><br />
          Pitch: W / S<br />
          Roll: A / D<br />
          Yaw: Q / E<br />
          Fire: Space<br />
          Boost: Shift<br />
          Reset: R
        </div>
      </div>
      <script type="module">
        import * as THREE from "https://unpkg.com/three@0.169.0/build/three.module.js";

        if (!window.IISLeaderboard) {
          window.IISLeaderboard = { postScore: (score) => console.log("IIS:score", score) };
        }
        window.__iis_game_boot_ok = false;
        window.__iisPresentationReady = false;

        const throttleReadout = document.getElementById("throttle-readout");
        const attitudeReadout = document.getElementById("attitude-readout");
        const targetReadout = document.getElementById("target-readout");
        const lockStrengthReadout = document.getElementById("lock-strength-readout");
        const waveReadout = document.getElementById("wave-readout");
        const shieldReadout = document.getElementById("hp");
        const statusReadout = document.getElementById("status-readout");
        const targetBox = document.getElementById("target-box");

        const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        document.getElementById("app").appendChild(renderer.domElement);

        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x02030a, 0.006);
        const camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.1, 1500);
        const ambient = new THREE.HemisphereLight(0x7dd3fc, 0x050816, 0.65);
        const keyLight = new THREE.DirectionalLight(0xffffff, 1.0);
        keyLight.position.set(10, 16, 8);
        scene.add(ambient, keyLight);
        const nebula = new THREE.Mesh(
          new THREE.SphereGeometry(180, 24, 24),
          new THREE.MeshBasicMaterial({ color: 0x1d4ed8, side: THREE.BackSide, transparent: true, opacity: 0.22 })
        );
        scene.add(nebula);

        const stars = new THREE.Points(
          new THREE.BufferGeometry(),
          new THREE.PointsMaterial({ color: 0x93c5fd, size: 0.85 })
        );
        const starPositions = [];
        for (let i = 0; i < 1800; i += 1) {
          starPositions.push((Math.random() - 0.5) * 900, (Math.random() - 0.5) * 500, (Math.random() - 0.5) * 900);
        }
        stars.geometry.setAttribute("position", new THREE.Float32BufferAttribute(starPositions, 3));
        scene.add(stars);
        const asteroidField = new THREE.Group();
        scene.add(asteroidField);
        for (let i = 0; i < 18; i += 1) {
          const asteroid = new THREE.Mesh(
            new THREE.DodecahedronGeometry(0.8 + Math.random() * 1.6),
            new THREE.MeshStandardMaterial({ color: 0x64748b, flatShading: true, roughness: 1.0, metalness: 0.04 })
          );
          asteroid.position.set((Math.random() - 0.5) * 120, (Math.random() - 0.5) * 40, -60 - Math.random() * 180);
          asteroid.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, Math.random() * Math.PI);
          asteroidField.add(asteroid);
        }
        const carrierCore = new THREE.Group();
        scene.add(carrierCore);
        const carrierHull = new THREE.Mesh(
          new THREE.BoxGeometry(12, 2.2, 44),
          new THREE.MeshStandardMaterial({ color: 0x16213d, flatShading: true, roughness: 0.88, metalness: 0.08 })
        );
        carrierHull.position.set(0, -9, -180);
        const carrierDeck = new THREE.Mesh(
          new THREE.BoxGeometry(20, 0.45, 22),
          new THREE.MeshStandardMaterial({ color: 0x23386b, flatShading: true, roughness: 0.8 })
        );
        carrierDeck.position.set(0, -7.4, -170);
        const carrierTower = new THREE.Mesh(
          new THREE.BoxGeometry(4, 4.6, 6),
          new THREE.MeshStandardMaterial({ color: 0x2f4a85, flatShading: true, roughness: 0.8 })
        );
        carrierTower.position.set(3.2, -5.4, -176);
        carrierCore.add(carrierHull, carrierDeck, carrierTower);

        const ship = new THREE.Group();
        const fuselage = new THREE.Mesh(
          new THREE.ConeGeometry(0.7, 3.0, 6),
          new THREE.MeshStandardMaterial({ color: 0x22d3ee, metalness: 0.45, roughness: 0.38 })
        );
        fuselage.rotation.x = Math.PI / 2;
        ship.add(fuselage);
        const wingLeft = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.08, 0.5), new THREE.MeshStandardMaterial({ color: 0xe2e8f0 }));
        wingLeft.position.set(-1.0, 0, -0.1);
        ship.add(wingLeft);
        const wingRight = wingLeft.clone();
        wingRight.position.x = 1.0;
        ship.add(wingRight);
        const engineGlow = new THREE.PointLight(0x38bdf8, 3.0, 18);
        engineGlow.position.set(0, 0, 1.2);
        ship.add(engineGlow);
        const engineTrail = new THREE.Mesh(
          new THREE.CylinderGeometry(0.18, 0.55, 3.2, 10, 1, true),
          new THREE.MeshBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.45 })
        );
        engineTrail.rotation.x = Math.PI / 2;
        engineTrail.position.set(0, 0, 2.5);
        ship.add(engineTrail);
        const shieldFlash = new THREE.Mesh(
          new THREE.SphereGeometry(1.45, 16, 16),
          new THREE.MeshBasicMaterial({ color: 0x67e8f9, transparent: true, opacity: 0.0, wireframe: true })
        );
        ship.add(shieldFlash);
        scene.add(ship);

        const enemyGroup = new THREE.Group();
        scene.add(enemyGroup);
        const enemies = [];
        for (let i = 0; i < 3; i += 1) {
          const enemy = new THREE.Mesh(
            new THREE.OctahedronGeometry(1.2),
            new THREE.MeshStandardMaterial({ color: 0xfb7185, emissive: 0x450a0a, metalness: 0.18, roughness: 0.55 })
          );
          enemy.position.set((i - 1) * 12, (i % 2 === 0 ? 3 : -3), -40 - i * 10);
          enemyGroup.add(enemy);
          enemies.push({ mesh: enemy, hp: 4, pursuitSeed: Math.random() * Math.PI * 2, fireCooldown: 0.8 + i * 0.35 });
        }

        const projectileMaterial = new THREE.MeshBasicMaterial({ color: 0xf8fafc });
        const enemyLaserMaterial = new THREE.MeshBasicMaterial({ color: 0xfb7185 });
        const projectiles = [];
        const enemyLasers = [];

        const input = { pitchUp: false, pitchDown: false, rollLeft: false, rollRight: false, yawLeft: false, yawRight: false, fire: false, boost: false };
        const state = {
          position: new THREE.Vector3(0, 0, 0),
          velocity: new THREE.Vector3(0, 0, -18),
          throttle: 0.44,
          pitch: 0,
          roll: 0,
          yaw: 0,
          boostCharge: 1,
          shield: 100,
          targetLockStrength: 0,
          fireCooldown: 0,
          wave: 1,
        };

        function resetFight() {
          state.position.set(0, 0, 0);
          state.velocity.set(0, 0, -18);
          state.throttle = 0.44;
          state.pitch = 0;
          state.roll = 0;
          state.yaw = 0;
          state.boostCharge = 1;
          state.shield = 100;
          state.targetLockStrength = 0;
          state.fireCooldown = 0;
          state.wave = 1;
          enemies.forEach((enemy, index) => {
            enemy.hp = 4;
            enemy.fireCooldown = 0.8 + index * 0.35;
            enemy.mesh.visible = true;
            enemy.mesh.position.set((index - 1) * 12, (index % 2 === 0 ? 3 : -3), -40 - index * 10);
          });
          statusReadout.textContent = "Boost ready · Cannons online";
        }

        window.__iisPreparePresentationCapture = () => {
          resetFight();
          input.pitchUp = false;
          input.pitchDown = false;
          input.rollLeft = false;
          input.rollRight = false;
          input.yawLeft = false;
          input.yawRight = false;
          input.fire = false;
          input.boost = false;
          statusReadout.textContent = "Target locked · thumbnail pass";
          window.__iisPresentationReady = false;
          setTimeout(() => {
            renderer.render(scene, camera);
            window.__iisPresentationReady = true;
          }, 120);
          return { delay_ms: 140, reason: "dogfight_thumbnail_mode" };
        };

        function fireProjectile() {
          if (state.fireCooldown > 0) return;
          const bolt = new THREE.Mesh(new THREE.SphereGeometry(0.18, 8, 8), projectileMaterial);
          const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(ship.quaternion);
          bolt.position.copy(ship.position).add(forward.clone().multiplyScalar(2.8));
          scene.add(bolt);
          projectiles.push({ mesh: bolt, velocity: forward.multiplyScalar(95) });
          state.fireCooldown = 0.16;
        }

        function fireEnemyLaser(origin, target) {
          const direction = target.clone().sub(origin).normalize();
          const bolt = new THREE.Mesh(new THREE.SphereGeometry(0.15, 8, 8), enemyLaserMaterial);
          bolt.position.copy(origin);
          scene.add(bolt);
          enemyLasers.push({ mesh: bolt, velocity: direction.multiplyScalar(75) });
        }

        function onKey(event, pressed) {
          const code = event.code;
          if (code === "KeyW") input.pitchUp = pressed;
          if (code === "KeyS") input.pitchDown = pressed;
          if (code === "KeyA") input.rollLeft = pressed;
          if (code === "KeyD") input.rollRight = pressed;
          if (code === "KeyQ") input.yawLeft = pressed;
          if (code === "KeyE") input.yawRight = pressed;
          if (code === "Space") input.fire = pressed;
          if (code === "ShiftLeft" || code === "ShiftRight") input.boost = pressed;
          if (pressed && code === "KeyR") resetFight();
        }
        window.addEventListener("keydown", (event) => onKey(event, true));
        window.addEventListener("keyup", (event) => onKey(event, false));
        window.addEventListener("resize", () => {
          camera.aspect = window.innerWidth / window.innerHeight;
          camera.updateProjectionMatrix();
          renderer.setSize(window.innerWidth, window.innerHeight);
        });

        let lastTime = performance.now();
        function animate(now) {
          const dt = Math.min(0.033, (now - lastTime) / 1000);
          lastTime = now;

          state.pitch += ((input.pitchUp ? 1 : 0) - (input.pitchDown ? 1 : 0)) * dt * 0.95;
          state.roll += ((input.rollRight ? 1 : 0) - (input.rollLeft ? 1 : 0)) * dt * 1.2;
          state.yaw += ((input.yawRight ? 1 : 0) - (input.yawLeft ? 1 : 0)) * dt * 0.85;
          state.pitch *= 0.94;
          state.roll *= 0.92;
          state.yaw *= 0.9;

          const boostFactor = input.boost && state.boostCharge > 0.05 ? 1.95 : 1.0;
          if (boostFactor > 1.0) {
            state.boostCharge = Math.max(0, state.boostCharge - dt * 0.24);
          } else {
            state.boostCharge = Math.min(1, state.boostCharge + dt * 0.1);
          }

          const throttleValue = THREE.MathUtils.clamp(state.throttle * boostFactor, 0.22, 1.0);
          const rotation = new THREE.Euler(state.pitch, state.yaw, state.roll, "YXZ");
          ship.quaternion.setFromEuler(rotation);
          engineTrail.scale.set(1, 1 + (boostFactor - 1) * 1.4, 1 + (boostFactor - 1) * 0.55);
          engineTrail.material.opacity = boostFactor > 1.0 ? 0.68 : 0.45;

          const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(ship.quaternion);
          state.velocity.lerp(forward.multiplyScalar(40 * throttleValue), 0.8 * dt);
          state.position.addScaledVector(state.velocity, dt);
          ship.position.copy(state.position);

          if (input.fire) fireProjectile();
          state.fireCooldown = Math.max(0, state.fireCooldown - dt);

          projectiles.forEach((projectile, index) => {
            projectile.mesh.position.addScaledVector(projectile.velocity, dt);
            if (projectile.mesh.position.length() > 300) {
              scene.remove(projectile.mesh);
              projectiles.splice(index, 1);
            }
          });
          enemyLasers.forEach((laser, index) => {
            laser.mesh.position.addScaledVector(laser.velocity, dt);
            if (laser.mesh.position.distanceTo(ship.position) < 1.4) {
              state.shield = Math.max(0, state.shield - 14);
              shieldFlash.material.opacity = 0.82;
              statusReadout.textContent = "Incoming hit · shields absorbing fire";
              scene.remove(laser.mesh);
              enemyLasers.splice(index, 1);
              return;
            }
            if (laser.mesh.position.length() > 300) {
              scene.remove(laser.mesh);
              enemyLasers.splice(index, 1);
            }
          });

          let liveEnemies = 0;
          let nearestEnemy = null;
          let nearestDistance = Infinity;
          enemies.forEach((enemy, index) => {
            if (!enemy.mesh.visible) return;
            liveEnemies += 1;
            const drift = now * 0.0013 + enemy.pursuitSeed;
            enemy.mesh.position.x += Math.sin(drift + index) * dt * 3.8;
            enemy.mesh.position.y += Math.cos(drift * 1.3) * dt * 2.4;
            enemy.mesh.position.z += Math.sin(drift * 0.7) * dt * 4.8;
            enemy.mesh.lookAt(ship.position);
            enemy.fireCooldown -= dt;
            if (enemy.fireCooldown <= 0) {
              fireEnemyLaser(enemy.mesh.position.clone(), ship.position.clone());
              enemy.fireCooldown = 1.25 + Math.random() * 0.8;
            }
            const distance = enemy.mesh.position.distanceTo(ship.position);
            if (distance < nearestDistance) {
              nearestDistance = distance;
              nearestEnemy = enemy.mesh;
            }
            projectiles.forEach((projectile, projectileIndex) => {
              if (enemy.mesh.position.distanceTo(projectile.mesh.position) < 1.5) {
                enemy.hp -= 1;
                scene.remove(projectile.mesh);
                projectiles.splice(projectileIndex, 1);
                statusReadout.textContent = "Hit confirmed · pressure the target";
                if (enemy.hp <= 0) {
                  enemy.mesh.visible = false;
                  window.IISLeaderboard.postScore(500 + state.wave * 100);
                  statusReadout.textContent = "Target destroyed · maintain pursuit";
                }
              }
            });
          });

          if (liveEnemies === 0) {
            state.wave += 1;
            enemies.forEach((enemy, index) => {
              enemy.hp = 4 + state.wave;
              enemy.fireCooldown = 0.7 + index * 0.22;
              enemy.mesh.visible = true;
              enemy.mesh.position.set((index - 1) * 16, (index - 1) * 2.5, -48 - index * 12);
            });
            statusReadout.textContent = `Wave ${state.wave} inbound`;
          }

          shieldFlash.material.opacity = Math.max(0, shieldFlash.material.opacity - dt * 1.8);
          shieldFlash.rotation.y += dt * 0.9;
          asteroidField.children.forEach((asteroid, index) => {
            asteroid.rotation.x += dt * (0.08 + index * 0.003);
            asteroid.rotation.y -= dt * (0.06 + index * 0.002);
          });
          carrierCore.position.x = Math.sin(now * 0.00018) * 8;
          carrierCore.rotation.y = Math.sin(now * 0.00011) * 0.12;

          const cameraOffset = new THREE.Vector3(1.2, 2.8, 8.4).applyQuaternion(ship.quaternion);
          const desiredCamera = ship.position.clone().add(cameraOffset);
          camera.position.lerp(desiredCamera, Math.min(1, dt * 4.4));
          camera.fov = THREE.MathUtils.lerp(camera.fov, boostFactor > 1.0 ? 76 : 70, Math.min(1, dt * 3.5));
          camera.updateProjectionMatrix();
          camera.lookAt(ship.position.clone().add(forward.clone().multiplyScalar(28)).add(state.velocity.clone().multiplyScalar(0.08)));

          throttleReadout.textContent = `THROTTLE ${Math.round(throttleValue * 100)}%`;
          attitudeReadout.textContent = `Pitch ${state.pitch.toFixed(2)} · Roll ${state.roll.toFixed(2)} · Yaw ${state.yaw.toFixed(2)}`;
          state.targetLockStrength = nearestEnemy ? Math.max(0, Math.min(1, 1 - nearestDistance / 80)) : 0;
          targetReadout.textContent = nearestEnemy ? `Target locked · ${nearestDistance.toFixed(1)}m` : "Target locked: none";
          lockStrengthReadout.textContent = `Lock ${Math.round(state.targetLockStrength * 100)}%`;
          waveReadout.textContent = `Wave ${state.wave} · Enemies ${liveEnemies}`;
          shieldReadout.textContent = `Shield ${Math.round(state.shield)}%`;
          if (targetBox) {
            if (nearestEnemy) {
              const projected = nearestEnemy.position.clone().project(camera);
              const screenX = ((projected.x + 1) * 0.5) * window.innerWidth;
              const screenY = ((-projected.y + 1) * 0.5) * window.innerHeight;
              targetBox.style.left = `${screenX}px`;
              targetBox.style.top = `${screenY}px`;
              targetBox.style.opacity = `${Math.max(0.35, state.targetLockStrength)}`;
            } else {
              targetBox.style.opacity = "0.18";
            }
          }

          renderer.render(scene, camera);
          window.requestAnimationFrame(animate);
        }

        resetFight();
        window.__iis_game_boot_ok = true;
        window.__iisPresentationReady = true;
        window.requestAnimationFrame(animate);
      </script>
    </body>
    </html>
    """
).strip()


SEED = ScaffoldSeed(
    key="three_space_dogfight_seed",
    archetype="flight_shooter_space_dogfight_3d",
    engine_mode="3d_three",
    version="v2",
    html=FLIGHT_HTML,
    acceptance_tags=[
        "three",
        "pitch",
        "roll",
        "yaw",
        "throttle",
        "reticle",
        "primary_fire",
        "enemy_pursuit",
        "target_lock",
        "enemy_attack_loop",
        "boost_feedback",
        "space_depth",
        "requestAnimationFrame",
        "boot_flag",
    ],
    summary="Three.js space dogfight baseline with attitude controls, target lock HUD, enemy attack loop, boost feedback, and layered space depth.",
)
