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
          Pitch: W / S<br />
          Bank: A / D<br />
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

        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        document.getElementById("app").appendChild(renderer.domElement);

        const scene = new THREE.Scene();
        scene.fog = new THREE.Fog(0x93c5fd, 55, 220);
        const camera = new THREE.PerspectiveCamera(68, window.innerWidth / window.innerHeight, 0.1, 500);

        const sun = new THREE.DirectionalLight(0xffd6a3, 2.6);
        sun.position.set(18, 28, 12);
        scene.add(sun);
        scene.add(new THREE.HemisphereLight(0xfde68a, 0x0f172a, 0.9));

        const sea = new THREE.Mesh(
          new THREE.CircleGeometry(220, 64),
          new THREE.MeshStandardMaterial({ color: 0x0ea5e9, flatShading: true, roughness: 0.42, metalness: 0.06 })
        );
        sea.rotation.x = -Math.PI / 2;
        sea.position.y = -1.8;
        scene.add(sea);

        const islands = new THREE.Group();
        scene.add(islands);
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
          { x: 0, y: 8, z: -24 },
          { x: 18, y: 10, z: -36 },
          { x: -18, y: 11, z: -52 },
          { x: 8, y: 14, z: -72 },
          { x: -10, y: 10, z: -88 },
          { x: 24, y: 12, z: -102 },
          { x: -22, y: 9, z: -118 },
          { x: 0, y: 13, z: -134 },
        ].forEach((ring, index) => {
          const mesh = new THREE.Mesh(
            new THREE.TorusGeometry(2.4, 0.28, 10, 36),
            new THREE.MeshStandardMaterial({ color: 0xfbbf24, emissive: 0x78350f, flatShading: true })
          );
          mesh.position.set(ring.x, ring.y, ring.z);
          ringMeshes.push({ mesh, collected: false });
          scene.add(mesh);
        });

        const input = { pitchUp: false, pitchDown: false, bankLeft: false, bankRight: false, boost: false };
        const state = {
          position: new THREE.Vector3(0, 10, 16),
          velocity: new THREE.Vector3(0, 0, -12),
          pitch: 0,
          roll: 0,
          speed: 22,
          rings: 0,
          countdown: 3,
          started: false,
        };

        function resetFlight() {
          state.position.set(0, 10, 16);
          state.velocity.set(0, 0, -12);
          state.pitch = 0;
          state.roll = 0;
          state.speed = 22;
          state.rings = 0;
          state.countdown = 3;
          state.started = false;
          ringMeshes.forEach((ring) => {
            ring.collected = false;
            ring.mesh.visible = true;
          });
          countdownEl.textContent = "3";
          countdownEl.style.opacity = "1";
          statusReadout.textContent = "Propeller spinning · line up for the rings";
        }

        function onKey(event, pressed) {
          if (event.code === "KeyW") input.pitchDown = pressed;
          if (event.code === "KeyS") input.pitchUp = pressed;
          if (event.code === "KeyA") input.bankLeft = pressed;
          if (event.code === "KeyD") input.bankRight = pressed;
          if (event.code === "ShiftLeft" || event.code === "ShiftRight") input.boost = pressed;
          if (pressed && event.code === "Space") {
            state.roll *= 0.5;
            state.pitch *= 0.5;
          }
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

          if (!state.started) {
            state.countdown = Math.max(0, state.countdown - dt);
            const shown = Math.ceil(state.countdown);
            countdownEl.textContent = shown > 0 ? String(shown) : "GO!";
            if (state.countdown <= 0) {
              state.started = true;
              setTimeout(() => { countdownEl.style.opacity = "0"; }, 240);
            }
          }

          state.pitch += ((input.pitchUp ? 1 : 0) - (input.pitchDown ? 1 : 0)) * dt * 0.82;
          state.roll += ((input.bankRight ? 1 : 0) - (input.bankLeft ? 1 : 0)) * dt * 1.05;
          state.pitch *= 0.94;
          state.roll *= 0.92;
          const throttle = input.boost ? 1.55 : 1.0;
          state.speed = THREE.MathUtils.lerp(state.speed, 24 * throttle, dt * 2.4);

          const rotation = new THREE.Euler(state.pitch, state.roll * 0.28, state.roll, "YXZ");
          plane.quaternion.setFromEuler(rotation);
          propeller.rotation.z += dt * (24 + state.speed * 0.65);

          const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(plane.quaternion);
          state.velocity.lerp(forward.multiplyScalar(state.speed), dt * 1.8);
          state.position.addScaledVector(state.velocity, dt);
          state.position.y = THREE.MathUtils.clamp(state.position.y - state.pitch * dt * 10, 5.5, 28);
          plane.position.copy(state.position);

          ringMeshes.forEach((ring) => {
            ring.mesh.rotation.y += dt * 1.4;
            if (!ring.collected && ring.mesh.position.distanceTo(plane.position) < 2.4) {
              ring.collected = true;
              ring.mesh.visible = false;
              state.rings += 1;
              statusReadout.textContent = `Ring burst! ${state.rings} / ${ringMeshes.length}`;
              window.IISLeaderboard.postScore(200 + state.rings * 50);
              playRingTone();
            }
          });

          const desiredCamera = plane.position.clone().add(new THREE.Vector3(0, 4.5, 10.5).applyQuaternion(plane.quaternion));
          camera.position.lerp(desiredCamera, 0.1);
          camera.lookAt(plane.position.clone().add(forward.clone().multiplyScalar(25)));
          camera.fov = THREE.MathUtils.lerp(camera.fov, input.boost ? 78 : 68, dt * 3.8);
          camera.updateProjectionMatrix();

          ringReadout.textContent = `Rings ${state.rings} / ${ringMeshes.length}`;
          speedReadout.textContent = `Speed ${Math.round(state.speed * 3.8)} knots`;
          altitudeReadout.textContent = `Altitude ${Math.round(state.position.y)}m`;
          if (state.rings === ringMeshes.length) {
            statusReadout.textContent = "All rings cleared · coast over the islands";
          }

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
    version="v1",
    html=ISLAND_FLIGHT_HTML,
    acceptance_tags=[
        "three",
        "flat_shading",
        "propeller",
        "island",
        "ring_collect",
        "fog",
        "directional_light",
        "requestAnimationFrame",
        "boot_flag",
    ],
    summary="Low-poly island flight baseline with propeller plane, warm directional light, fog, ring collect loop, and gentle exploration.",
)
