from __future__ import annotations

from textwrap import dedent

from app.agents.scaffolds.base import ScaffoldSeed


ISLAND_FLIGHT_HTML = dedent(
    """
    <!doctype html>
    <html lang="ko">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>IIS Lowpoly Island Flight Seed</title>
      <style>
        html, body { margin: 0; height: 100%; overflow: hidden; background: linear-gradient(180deg, #f59e0b 0%, #fb7185 18%, #7dd3fc 68%, #0ea5e9 100%); font-family: Inter, system-ui, sans-serif; color: #eff6ff; }
        #app { position: relative; width: 100%; height: 100%; }
        canvas { display: block; width: 100%; height: 100%; }
        #hud { position: absolute; top: 18px; left: 18px; display: grid; gap: 6px; min-width: 250px; padding: 14px 16px; border-radius: 16px; background: rgba(15, 23, 42, 0.34); border: 1px solid rgba(255, 255, 255, 0.18); backdrop-filter: blur(14px); pointer-events: none; }
        #hud strong { font-size: 28px; color: #fef3c7; }
        #hud span { font-size: 13px; color: #eff6ff; }
        #controls { position: absolute; top: 18px; right: 18px; max-width: 280px; padding: 12px 14px; border-radius: 14px; background: rgba(15, 23, 42, 0.28); border: 1px solid rgba(255, 255, 255, 0.16); line-height: 1.5; font-size: 12px; pointer-events: none; }
        #countdown { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 72px; font-weight: 900; color: rgba(254, 240, 138, 0.95); text-shadow: 0 0 28px rgba(251, 191, 36, 0.55); pointer-events: none; transition: opacity 220ms ease; }
      </style>
    </head>
    <body>
      <div id="app">
        <div id="hud">
          <span>LOW-POLY ISLAND FLIGHT</span>
          <strong id="ring-readout">Rings 0 / 8</strong>
          <span id="speed-readout">Speed 0 knots</span>
          <span id="altitude-readout">Altitude 18m</span>
          <span id="status-readout">Propeller spinning · explore the islands</span>
        </div>
        <div id="controls">
          <b>Controls</b><br />
          Pitch Up / Down: W / S<br />
          Yaw / Bank: A / D<br />
          Throttle: Shift<br />
          Stabilize: Space<br />
          Reset: R
        </div>
        <div id="countdown">3</div>
      </div>
      <script type="module">
        import * as THREE from "https://unpkg.com/three@0.169.0/build/three.module.js";

        if (!window.IISLeaderboard) {
          window.IISLeaderboard = { postScore: (score) => console.log("IIS:score", score) };
        }
        window.__iis_game_boot_ok = false;

        const ringReadout = document.getElementById("ring-readout");
        const speedReadout = document.getElementById("speed-readout");
        const altitudeReadout = document.getElementById("altitude-readout");
        const statusReadout = document.getElementById("status-readout");
        const countdownEl = document.getElementById("countdown");

        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setClearColor(0x000000, 0);
        document.getElementById("app").appendChild(renderer.domElement);

        const scene = new THREE.Scene();
        scene.fog = new THREE.Fog(0x93c5fd, 55, 220);
        const camera = new THREE.PerspectiveCamera(68, window.innerWidth / window.innerHeight, 0.1, 500);

        const sun = new THREE.DirectionalLight(0xffd6a3, 2.6);
        sun.position.set(18, 28, 12);
        scene.add(sun);
        scene.add(new THREE.HemisphereLight(0xfde68a, 0x0f172a, 0.9));

        const skyDome = new THREE.Mesh(
          new THREE.SphereGeometry(260, 24, 24),
          new THREE.MeshBasicMaterial({ color: 0xf59e0b, side: THREE.BackSide, transparent: true, opacity: 0.18 })
        );
        scene.add(skyDome);
        const sunHalo = new THREE.Mesh(
          new THREE.SphereGeometry(7.5, 18, 18),
          new THREE.MeshBasicMaterial({ color: 0xfef3c7, transparent: true, opacity: 0.42 })
        );
        sunHalo.position.set(44, 34, -120);
        scene.add(sunHalo);
        const cloudGroup = new THREE.Group();
        scene.add(cloudGroup);
        [
          { x: -32, y: 20, z: -42, scale: 1.2 },
          { x: 18, y: 24, z: -76, scale: 1.4 },
          { x: -12, y: 18, z: -108, scale: 1.0 },
          { x: 38, y: 22, z: -138, scale: 1.25 },
        ].forEach((cloud, index) => {
          const puff = new THREE.Group();
          for (let offsetIndex = 0; offsetIndex < 3; offsetIndex += 1) {
            const bubble = new THREE.Mesh(
              new THREE.SphereGeometry((1.8 - offsetIndex * 0.25) * cloud.scale, 10, 10),
              new THREE.MeshStandardMaterial({
                color: 0xfffbeb,
                flatShading: true,
                transparent: true,
                opacity: 0.9,
              })
            );
            bubble.position.set(offsetIndex * 1.9 * cloud.scale, offsetIndex % 2 === 0 ? 0.3 : -0.2, (offsetIndex - 1) * 0.8);
            puff.add(bubble);
          }
          puff.position.set(cloud.x, cloud.y + Math.sin(index) * 1.2, cloud.z);
          cloudGroup.add(puff);
        });

        const sea = new THREE.Mesh(
          new THREE.CircleGeometry(220, 64),
          new THREE.MeshStandardMaterial({ color: 0x0ea5e9, flatShading: true, roughness: 0.42, metalness: 0.06 })
        );
        sea.rotation.x = -Math.PI / 2;
        sea.position.y = -1.8;
        scene.add(sea);

        const islands = new THREE.Group();
        scene.add(islands);
        const islandDefs = [];
        const islandLayout = [
          { x: 0, z: -18, scale: 1.6 },
          { x: 22, z: -42, scale: 1.0 },
          { x: -24, z: -54, scale: 1.1 },
          { x: 10, z: -78, scale: 1.3 },
          { x: -15, z: -96, scale: 0.9 },
        ];
        islandLayout.forEach((item, index) => {
          const island = new THREE.Mesh(
            new THREE.CylinderGeometry(6 * item.scale, 14 * item.scale, 6 + item.scale * 8, 7),
            new THREE.MeshStandardMaterial({ color: 0x65a30d, flatShading: true, roughness: 1 })
          );
          island.position.set(item.x, 0, item.z);
          islands.add(island);
          islandDefs.push({ x: item.x, z: item.z, radius: 12.5 * item.scale, topY: (6 + item.scale * 8) * 0.5 });
          const beach = new THREE.Mesh(
            new THREE.CylinderGeometry(7 * item.scale, 15 * item.scale, 1.2, 7),
            new THREE.MeshStandardMaterial({ color: 0xfcd34d, flatShading: true, roughness: 0.95 })
          );
          beach.position.set(item.x, -2.8, item.z);
          islands.add(beach);
          const tree = new THREE.Group();
          const trunk = new THREE.Mesh(
            new THREE.CylinderGeometry(0.24, 0.32, 2.2, 5),
            new THREE.MeshStandardMaterial({ color: 0x78350f, flatShading: true })
          );
          trunk.position.set(item.x + 1.4 * item.scale, 2.1, item.z + 0.6 * item.scale);
          const crown = new THREE.Mesh(
            new THREE.ConeGeometry(1.5 * item.scale, 3.2 * item.scale, 5),
            new THREE.MeshStandardMaterial({ color: 0x16a34a, flatShading: true })
          );
          crown.position.set(trunk.position.x, trunk.position.y + 2.2, trunk.position.z);
          tree.add(trunk, crown);
          islands.add(tree);
          if (index === 1) {
            const lighthouseTower = new THREE.Mesh(
              new THREE.CylinderGeometry(0.52, 0.76, 6.4, 6),
              new THREE.MeshStandardMaterial({ color: 0xfffbeb, flatShading: true, roughness: 0.9 })
            );
            lighthouseTower.position.set(item.x - 1.2 * item.scale, 2.6, item.z - 0.8 * item.scale);
            const lighthouseCap = new THREE.Mesh(
              new THREE.ConeGeometry(1.0, 1.3, 6),
              new THREE.MeshStandardMaterial({ color: 0xf97316, flatShading: true })
            );
            lighthouseCap.position.set(lighthouseTower.position.x, lighthouseTower.position.y + 3.6, lighthouseTower.position.z);
            const lighthouseBeacon = new THREE.PointLight(0xfef3c7, 2.8, 26);
            lighthouseBeacon.position.set(lighthouseTower.position.x, lighthouseTower.position.y + 3.1, lighthouseTower.position.z);
            islands.add(lighthouseTower, lighthouseCap, lighthouseBeacon);
          }
        });

        const plane = new THREE.Group();
        const fuselage = new THREE.Mesh(
          new THREE.BoxGeometry(1.2, 0.75, 3.6),
          new THREE.MeshStandardMaterial({ color: 0xf8fafc, flatShading: true, roughness: 0.82 })
        );
        plane.add(fuselage);
        const nose = new THREE.Mesh(
          new THREE.ConeGeometry(0.42, 1.1, 5),
          new THREE.MeshStandardMaterial({ color: 0xfbbf24, flatShading: true })
        );
        nose.rotation.x = Math.PI / 2;
        nose.position.set(0, 0, 2.2);
        plane.add(nose);
        const leftWing = new THREE.Mesh(
          new THREE.BoxGeometry(4.6, 0.12, 0.62),
          new THREE.MeshStandardMaterial({ color: 0x38bdf8, flatShading: true })
        );
        leftWing.position.set(0, 0.08, 0.1);
        plane.add(leftWing);
        const tailWing = new THREE.Mesh(
          new THREE.BoxGeometry(1.45, 0.1, 0.4),
          new THREE.MeshStandardMaterial({ color: 0x0284c7, flatShading: true })
        );
        tailWing.position.set(0, 0.5, -1.25);
        plane.add(tailWing);
        const propeller = new THREE.Mesh(
          new THREE.BoxGeometry(0.08, 1.2, 0.1),
          new THREE.MeshStandardMaterial({ color: 0x111827, flatShading: true })
        );
        propeller.position.set(0, 0, 2.72);
        plane.add(propeller);
        scene.add(plane);

        const ringMeshes = [];
        [
          { x: 0, y: 12, z: -30 },
          { x: 26, y: 14, z: -52 },
          { x: -4, y: 15, z: -68 },
          { x: -24, y: 13, z: -86 },
          { x: 24, y: 14, z: -102 },
          { x: 0, y: 15, z: -118 },
          { x: -28, y: 13, z: -136 },
          { x: 14, y: 15, z: -154 },
        ].forEach((ring, index) => {
          const mesh = new THREE.Mesh(
            new THREE.TorusGeometry(2.4, 0.28, 10, 36),
            new THREE.MeshStandardMaterial({ color: 0xfbbf24, emissive: 0x78350f, flatShading: true })
          );
          mesh.position.set(ring.x, ring.y, ring.z);
          ringMeshes.push({ mesh, collected: false });
          scene.add(mesh);
        });

        const input = { pitchUp: false, pitchDown: false, yawLeft: false, yawRight: false, boost: false, stabilize: false };
        const state = {
          position: new THREE.Vector3(0, 11, 16),
          velocity: new THREE.Vector3(0, 0, -18),
          pitch: 0,
          roll: 0,
          yaw: 0,
          yawVelocity: 0,
          climbVelocity: 0,
          speed: 22,
          rings: 0,
          countdown: 3,
          started: false,
          lastSafePoint: new THREE.Vector3(0, 11, 16),
          lastSafeYaw: 0,
        };

        function terrainHeightAt(x, z) {
          let height = -1.8;
          islandDefs.forEach((island) => {
            const dx = x - island.x;
            const dz = z - island.z;
            const distance = Math.sqrt(dx * dx + dz * dz);
            if (distance <= island.radius) {
              height = Math.max(height, island.topY + 0.4);
            }
          });
          return height;
        }

        function respawn(reason) {
          state.position.copy(state.lastSafePoint);
          state.velocity.set(0, 0, -18);
          state.pitch = 0;
          state.roll = 0;
          state.yawVelocity = 0;
          state.climbVelocity = 0;
          state.speed = 18;
          state.yaw = state.lastSafeYaw;
          statusReadout.textContent = reason;
          ringReadout.textContent = `Rings ${state.rings} / ${ringMeshes.length}`;
        }

        function resetFlight() {
          state.position.set(0, 11, 16);
          state.velocity.set(0, 0, -18);
          state.pitch = 0;
          state.roll = 0;
          state.yaw = 0;
          state.yawVelocity = 0;
          state.climbVelocity = 0;
          state.speed = 22;
          state.rings = 0;
          state.countdown = 3;
          state.started = false;
          state.lastSafePoint.set(0, 11, 16);
          state.lastSafeYaw = 0;
          ringMeshes.forEach((ring) => {
            ring.collected = false;
            ring.mesh.visible = true;
          });
          countdownEl.textContent = "3";
          countdownEl.style.opacity = "1";
          statusReadout.textContent = "Propeller spinning · line up for the rings";
        }

        function onKey(event, pressed) {
          if (event.code === "KeyW") input.pitchUp = pressed;
          if (event.code === "KeyS") input.pitchDown = pressed;
          if (event.code === "KeyA") input.yawLeft = pressed;
          if (event.code === "KeyD") input.yawRight = pressed;
          if (event.code === "ShiftLeft" || event.code === "ShiftRight") input.boost = pressed;
          if (event.code === "Space") input.stabilize = pressed;
          if (pressed && event.code === "KeyR") resetFlight();
        }
        window.addEventListener("keydown", (event) => onKey(event, true));
        window.addEventListener("keyup", (event) => onKey(event, false));
        window.addEventListener("resize", () => {
          camera.aspect = window.innerWidth / window.innerHeight;
          camera.updateProjectionMatrix();
          renderer.setSize(window.innerWidth, window.innerHeight);
        });

        function playRingTone() {
          const context = window.__iisAudioCtx || new (window.AudioContext || window.webkitAudioContext)();
          window.__iisAudioCtx = context;
          if (context.state === "suspended") context.resume();
          const oscillator = context.createOscillator();
          const gain = context.createGain();
          oscillator.type = "triangle";
          oscillator.frequency.value = 640 + state.rings * 45;
          gain.gain.setValueAtTime(0.0001, context.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.08, context.currentTime + 0.01);
          gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.24);
          oscillator.connect(gain).connect(context.destination);
          oscillator.start();
          oscillator.stop(context.currentTime + 0.25);
        }

        let lastTime = performance.now();
        function animate(nowMs) {
          const dt = Math.min(0.033, (nowMs - lastTime) / 1000);
          lastTime = nowMs;

          const flightForward = new THREE.Vector3(0, 0, -1).applyQuaternion(plane.quaternion);

          if (!state.started) {
            state.countdown = Math.max(0, state.countdown - dt);
            const shown = Math.ceil(state.countdown);
            countdownEl.textContent = shown > 0 ? String(shown) : "GO!";
            const introCamera = plane.position.clone().add(new THREE.Vector3(-6.8, 4.6, 7.2));
            camera.position.lerp(introCamera, 0.14);
            camera.lookAt(plane.position.clone().add(flightForward.clone().multiplyScalar(-12)).add(new THREE.Vector3(0, 1.5, 0)));
            camera.fov = THREE.MathUtils.lerp(camera.fov, 64, dt * 4.2);
            camera.updateProjectionMatrix();
            if (state.countdown <= 0) {
              state.started = true;
              setTimeout(() => { countdownEl.style.opacity = "0"; }, 240);
            }
            renderer.render(scene, camera);
            window.requestAnimationFrame(animate);
            return;
          }

          const pitchInput = (input.pitchUp ? 1 : 0) - (input.pitchDown ? 1 : 0);
          const yawInput = (input.yawRight ? 1 : 0) - (input.yawLeft ? 1 : 0);
          state.pitch = THREE.MathUtils.clamp(
            THREE.MathUtils.lerp(state.pitch, pitchInput * 0.34, dt * (input.stabilize ? 5.2 : 2.8)),
            -0.55,
            0.55,
          );
          state.yawVelocity = THREE.MathUtils.lerp(state.yawVelocity, yawInput * 1.15, dt * 4.2);
          state.yaw += state.yawVelocity * dt * (0.9 + state.speed * 0.016);
          const targetRoll = -yawInput * 0.55;
          state.roll = THREE.MathUtils.lerp(state.roll, input.stabilize ? 0 : targetRoll, dt * (input.stabilize ? 6.5 : 3.4));
          const throttle = input.boost ? 1.55 : 1.0;
          state.speed = THREE.MathUtils.lerp(state.speed, 24 * throttle, dt * 2.6);
          if (input.stabilize) {
            state.pitch = THREE.MathUtils.lerp(state.pitch, 0, dt * 4.5);
            state.yawVelocity = THREE.MathUtils.lerp(state.yawVelocity, 0, dt * 4.1);
          }

          const rotation = new THREE.Euler(-state.pitch, state.yaw, state.roll, "YXZ");
          plane.quaternion.setFromEuler(rotation);
          propeller.rotation.z += dt * (24 + state.speed * 0.65);

          const forward = flightForward;
          state.velocity.lerp(forward.multiplyScalar(state.speed), dt * 1.8);
          state.position.addScaledVector(state.velocity, dt);
          state.climbVelocity = THREE.MathUtils.lerp(state.climbVelocity, state.pitch * 14, dt * 2.4);
          state.position.y = THREE.MathUtils.clamp(state.position.y + state.climbVelocity * dt, 5.5, 28);
          const terrainHeight = terrainHeightAt(state.position.x, state.position.z);
          const minClearance = terrainHeight + 2.6;
          if (state.position.y < minClearance) {
            state.position.y = THREE.MathUtils.lerp(state.position.y, minClearance, 0.42);
            state.climbVelocity = Math.max(state.climbVelocity, 2.4);
            statusReadout.textContent = "Terrain clearance assist engaged";
          }
          if (state.position.y <= 5.6 || state.position.z < -150 || Math.abs(state.position.x) > 90 || !Number.isFinite(state.position.x) || !Number.isFinite(state.position.y) || !Number.isFinite(state.position.z)) {
            respawn("Low altitude recovery · returning to safe route");
          }
          plane.position.copy(state.position);

          ringMeshes.forEach((ring) => {
            ring.mesh.rotation.y += dt * 1.4;
            if (!ring.collected && ring.mesh.position.distanceTo(plane.position) < 2.4) {
              ring.collected = true;
              ring.mesh.visible = false;
              state.rings += 1;
              state.lastSafePoint.copy(ring.mesh.position).add(new THREE.Vector3(0, 2.5, 10));
              state.lastSafeYaw = state.yaw;
              statusReadout.textContent = `Ring burst! ${state.rings} / ${ringMeshes.length}`;
              window.IISLeaderboard.postScore(200 + state.rings * 50);
              playRingTone();
            }
          });

          const desiredCamera = plane.position.clone().add(new THREE.Vector3(-2.6, 4.7, 11.2).applyQuaternion(plane.quaternion));
          camera.position.lerp(desiredCamera, 0.12);
          camera.lookAt(plane.position.clone().add(forward.clone().multiplyScalar(28)).add(new THREE.Vector3(0, 2.2, 0)));
          camera.fov = THREE.MathUtils.lerp(camera.fov, input.boost ? 78 : 68, dt * 3.8);
          camera.updateProjectionMatrix();

          ringReadout.textContent = `Rings ${state.rings} / ${ringMeshes.length}`;
          speedReadout.textContent = `Speed ${Math.round(state.speed * 3.8)} knots`;
          altitudeReadout.textContent = `Altitude ${Math.round(state.position.y)}m`;
          if (state.rings === ringMeshes.length) {
            statusReadout.textContent = "All rings cleared · coast over the islands";
          }

          cloudGroup.children.forEach((cloud, index) => {
            cloud.position.x += Math.sin(nowMs * 0.00018 + index) * 0.012;
            cloud.position.z += Math.cos(nowMs * 0.00012 + index) * 0.018;
          });

          renderer.render(scene, camera);
          window.requestAnimationFrame(animate);
        }

        resetFlight();
        window.__iis_game_boot_ok = true;
        window.requestAnimationFrame(animate);
      </script>
    </body>
    </html>
    """
).strip()


SEED = ScaffoldSeed(
    key="three_lowpoly_island_flight_seed",
    archetype="flight_lowpoly_island_3d",
    engine_mode="3d_three",
    version="v2",
    html=ISLAND_FLIGHT_HTML,
    acceptance_tags=[
        "three",
        "flat_shading",
        "propeller",
        "island",
        "ring_collect",
        "yaw_control",
        "auto_level",
        "altitude_guard",
        "fog",
        "directional_light",
        "requestAnimationFrame",
        "boot_flag",
    ],
    summary="Low-poly island flight baseline with stable yaw control, propeller plane, warm light, fog, ring collect loop, and recovery assists.",
)
