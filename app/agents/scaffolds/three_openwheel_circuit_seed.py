from __future__ import annotations

from textwrap import dedent

from app.agents.scaffolds.base import ScaffoldSeed


RACING_HTML = dedent(
    """
    <!doctype html>
    <html lang="ko">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>IIS Openwheel Circuit Seed</title>
      <style>
        html, body { margin: 0; height: 100%; overflow: hidden; background: radial-gradient(circle at top, #18254d 0%, #060814 62%, #02030a 100%); font-family: Inter, system-ui, sans-serif; color: #eef2ff; }
        #app { position: relative; width: 100%; height: 100%; }
        canvas { display: block; width: 100%; height: 100%; }
        #hud { position: absolute; top: 18px; left: 18px; display: grid; gap: 6px; padding: 14px 16px; background: rgba(2, 6, 23, 0.52); border: 1px solid rgba(148, 163, 184, 0.32); border-radius: 14px; backdrop-filter: blur(12px); pointer-events: none; min-width: 220px; }
        #hud strong { font-size: 28px; color: #7dd3fc; }
        #hud span { font-size: 13px; color: #cbd5e1; }
        #banner { position: absolute; top: 18px; right: 18px; padding: 12px 14px; background: rgba(15, 23, 42, 0.55); border-radius: 12px; border: 1px solid rgba(244, 114, 182, 0.28); max-width: 280px; line-height: 1.45; font-size: 12px; color: #e5e7eb; }
        #banner b { color: #fbbf24; }
      </style>
    </head>
    <body>
      <div id="app">
        <div id="hud">
          <span>OPEN-WHEEL CIRCUIT RACING</span>
          <strong id="lap-timer">00.000</strong>
          <span id="lap-state">Lap 1 / Checkpoint 1</span>
          <span id="speed-state">Speed 0 km/h</span>
          <span id="hint-state">Steer / throttle / brake to set a lap time</span>
        </div>
        <div id="banner">
          <b>Controls</b><br />
          Steering: A / D or ← / →<br />
          Throttle / Brake: W / S or ↑ / ↓<br />
          Reset: R
        </div>
      </div>
      <script type="module">
        import * as THREE from "https://unpkg.com/three@0.169.0/build/three.module.js";

        if (!window.IISLeaderboard) {
          window.IISLeaderboard = { postScore: (score) => console.log("IIS:score", score) };
        }
        window.__iis_game_boot_ok = false;

        const lapTimerEl = document.getElementById("lap-timer");
        const lapStateEl = document.getElementById("lap-state");
        const speedStateEl = document.getElementById("speed-state");
        const hintStateEl = document.getElementById("hint-state");

        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        document.getElementById("app").appendChild(renderer.domElement);

        const scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x040611, 0.012);
        const camera = new THREE.PerspectiveCamera(65, window.innerWidth / window.innerHeight, 0.1, 300);
        const ambient = new THREE.HemisphereLight(0x99ccff, 0x101020, 0.9);
        const sun = new THREE.DirectionalLight(0xffffff, 1.2);
        sun.position.set(12, 18, 10);
        scene.add(ambient, sun);

        const trackCurve = new THREE.CatmullRomCurve3([
          new THREE.Vector3(0, 0, -26),
          new THREE.Vector3(17, 0, -18),
          new THREE.Vector3(22, 0, 2),
          new THREE.Vector3(14, 0, 20),
          new THREE.Vector3(-8, 0, 25),
          new THREE.Vector3(-22, 0, 10),
          new THREE.Vector3(-18, 0, -14),
          new THREE.Vector3(0, 0, -26),
        ], true);

        const roadPoints = trackCurve.getPoints(240);
        const roadShape = new THREE.Shape();
        roadShape.moveTo(-2.8, 0);
        roadShape.lineTo(2.8, 0);
        const roadGeometry = new THREE.ExtrudeGeometry(roadShape, {
          steps: roadPoints.length - 1,
          bevelEnabled: false,
          extrudePath: trackCurve,
        });
        const roadMaterial = new THREE.MeshStandardMaterial({ color: 0x141a2d, metalness: 0.2, roughness: 0.88 });
        const roadMesh = new THREE.Mesh(roadGeometry, roadMaterial);
        roadMesh.rotation.x = Math.PI;
        scene.add(roadMesh);

        const laneGeometry = new THREE.BufferGeometry().setFromPoints(roadPoints.map((point) => point.clone().add(new THREE.Vector3(0, 0.03, 0))));
        const laneLine = new THREE.Line(laneGeometry, new THREE.LineBasicMaterial({ color: 0xffd166 }));
        scene.add(laneLine);

        const ground = new THREE.Mesh(
          new THREE.CircleGeometry(120, 64),
          new THREE.MeshStandardMaterial({ color: 0x07111f, roughness: 1.0, metalness: 0.0 }),
        );
        ground.rotation.x = -Math.PI / 2;
        ground.position.y = -0.08;
        scene.add(ground);

        const checkpointMarkers = [];
        const checkpointState = {
          currentCheckpointIndex: 0,
          lapCount: 1,
          checkpointPassed: 0,
          lapTimerMs: 0,
          lapStartMs: performance.now(),
          bestLapMs: null,
          lastLapMs: null,
        };
        [0.02, 0.27, 0.53, 0.78].forEach((t, index) => {
          const position = trackCurve.getPointAt(t);
          const marker = new THREE.Mesh(
            new THREE.TorusGeometry(1.8, 0.15, 12, 32),
            new THREE.MeshBasicMaterial({ color: index === 0 ? 0x34d399 : 0x7c3aed }),
          );
          marker.position.copy(position).add(new THREE.Vector3(0, 1.4, 0));
          marker.rotation.x = Math.PI / 2;
          scene.add(marker);
          checkpointMarkers.push({ marker, position, threshold: 5.4 });
        });

        const car = new THREE.Group();
        const body = new THREE.Mesh(
          new THREE.BoxGeometry(1.2, 0.35, 2.6),
          new THREE.MeshStandardMaterial({ color: 0xe11d48, metalness: 0.45, roughness: 0.4 }),
        );
        body.position.y = 0.55;
        car.add(body);
        const nose = new THREE.Mesh(
          new THREE.ConeGeometry(0.4, 1.4, 4),
          new THREE.MeshStandardMaterial({ color: 0xfb7185, metalness: 0.2, roughness: 0.45 }),
        );
        nose.rotation.x = Math.PI / 2;
        nose.position.set(0, 0.55, 1.9);
        car.add(nose);
        const wing = new THREE.Mesh(
          new THREE.BoxGeometry(1.8, 0.1, 0.3),
          new THREE.MeshStandardMaterial({ color: 0xe2e8f0 }),
        );
        wing.position.set(0, 0.82, -1.1);
        car.add(wing);
        const wheelMaterial = new THREE.MeshStandardMaterial({ color: 0x09090b, roughness: 0.9 });
        const wheelOffsets = [
          [-0.75, 0.28, 1.0], [0.75, 0.28, 1.0], [-0.75, 0.28, -0.85], [0.75, 0.28, -0.85]
        ];
        wheelOffsets.forEach(([x, y, z]) => {
          const wheel = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.24, 0.26, 16), wheelMaterial);
          wheel.rotation.z = Math.PI / 2;
          wheel.position.set(x, y, z);
          car.add(wheel);
        });
        scene.add(car);

        const input = { throttle: false, brake: false, left: false, right: false };
        const carState = {
          position: trackCurve.getPointAt(0.0).clone(),
          heading: 0,
          speed: 0,
          steerVelocity: 0,
          accelRate: 22,
          brakeRate: 28,
        };

        function resetRace() {
          carState.position.copy(trackCurve.getPointAt(0.0));
          carState.heading = 0;
          carState.speed = 0;
          carState.steerVelocity = 0;
          checkpointState.currentCheckpointIndex = 0;
          checkpointState.checkpointPassed = 0;
          checkpointState.lapCount = 1;
          checkpointState.lapStartMs = performance.now();
          checkpointState.lapTimerMs = 0;
          checkpointMarkers.forEach(({ marker }, index) => {
            marker.material.color.set(index === 0 ? 0x34d399 : 0x7c3aed);
          });
          hintStateEl.textContent = "Reset complete — attack the circuit again";
        }

        function onKey(event, pressed) {
          const code = event.code;
          if (code === "KeyW" || code === "ArrowUp") input.throttle = pressed;
          if (code === "KeyS" || code === "ArrowDown") input.brake = pressed;
          if (code === "KeyA" || code === "ArrowLeft") input.left = pressed;
          if (code === "KeyD" || code === "ArrowRight") input.right = pressed;
          if (pressed && code === "KeyR") resetRace();
        }

        window.addEventListener("keydown", (event) => onKey(event, true));
        window.addEventListener("keyup", (event) => onKey(event, false));
        window.addEventListener("resize", () => {
          camera.aspect = window.innerWidth / window.innerHeight;
          camera.updateProjectionMatrix();
          renderer.setSize(window.innerWidth, window.innerHeight);
        });

        function updateCheckpoints(nowMs) {
          const active = checkpointMarkers[checkpointState.currentCheckpointIndex];
          if (!active) return;
          const distance = active.position.distanceTo(carState.position);
          if (distance > active.threshold) return;

          active.marker.material.color.set(0x22d3ee);
          checkpointState.checkpointPassed += 1;
          checkpointState.currentCheckpointIndex += 1;

          if (checkpointState.currentCheckpointIndex >= checkpointMarkers.length) {
            const lapTime = nowMs - checkpointState.lapStartMs;
            checkpointState.lastLapMs = lapTime;
            checkpointState.bestLapMs = checkpointState.bestLapMs === null ? lapTime : Math.min(checkpointState.bestLapMs, lapTime);
            checkpointState.lapCount += 1;
            checkpointState.currentCheckpointIndex = 0;
            checkpointState.lapStartMs = nowMs;
            window.IISLeaderboard.postScore(Math.max(1, Math.round(90000 - lapTime)));
            hintStateEl.textContent = `Last lap ${formatLap(lapTime)} · Best ${formatLap(checkpointState.bestLapMs)}`;
            checkpointMarkers.forEach(({ marker }, index) => {
              marker.material.color.set(index === 0 ? 0x34d399 : 0x7c3aed);
            });
          } else {
            checkpointMarkers[checkpointState.currentCheckpointIndex].marker.material.color.set(0x34d399);
          }
        }

        function formatLap(ms) {
          const total = ms / 1000;
          return total.toFixed(3);
        }

        let lastTime = performance.now();
        function animate(nowMs) {
          const dt = Math.min(0.033, (nowMs - lastTime) / 1000);
          lastTime = nowMs;

          if (input.throttle) carState.speed += carState.accelRate * dt;
          if (input.brake) carState.speed -= carState.brakeRate * dt;
          carState.speed *= input.brake ? 0.988 : 0.996;
          carState.speed = THREE.MathUtils.clamp(carState.speed, 0, 72);

          const steerInput = (input.left ? 1 : 0) - (input.right ? 1 : 0);
          carState.steerVelocity = THREE.MathUtils.lerp(carState.steerVelocity, steerInput * 1.25, 4 * dt);
          carState.heading += carState.steerVelocity * dt * (0.4 + carState.speed * 0.03);

          const forward = new THREE.Vector3(Math.sin(carState.heading), 0, Math.cos(carState.heading));
          carState.position.addScaledVector(forward, carState.speed * dt * 0.32);

          const nearest = roadPoints.reduce((best, point) => {
            const dist = point.distanceToSquared(carState.position);
            return dist < best.dist ? { point, dist } : best;
          }, { point: roadPoints[0], dist: Infinity });
          const pull = nearest.point.clone().sub(carState.position).multiplyScalar(0.04);
          carState.position.add(pull);

          car.position.copy(carState.position);
          car.position.y = 0.02;
          car.rotation.y = carState.heading;

          const cameraOffset = new THREE.Vector3(0, 3.8, -8.4).applyAxisAngle(new THREE.Vector3(0, 1, 0), carState.heading);
          camera.position.copy(car.position).add(cameraOffset);
          camera.lookAt(car.position.clone().add(forward.clone().multiplyScalar(8)).add(new THREE.Vector3(0, 1.3, 0)));

          checkpointState.lapTimerMs = nowMs - checkpointState.lapStartMs;
          updateCheckpoints(nowMs);

          lapTimerEl.textContent = formatLap(checkpointState.lapTimerMs);
          lapStateEl.textContent = `Lap ${checkpointState.lapCount} / Checkpoint ${checkpointState.currentCheckpointIndex + 1}`;
          speedStateEl.textContent = `Speed ${Math.round(carState.speed * 4.6)} km/h`;

          renderer.render(scene, camera);
          window.requestAnimationFrame(animate);
        }

        resetRace();
        window.__iis_game_boot_ok = true;
        window.requestAnimationFrame(animate);
      </script>
    </body>
    </html>
    """
).strip()


SEED = ScaffoldSeed(
    key="three_openwheel_circuit_seed",
    archetype="racing_openwheel_circuit_3d",
    engine_mode="3d_three",
    version="v1",
    html=RACING_HTML,
    acceptance_tags=[
        "three",
        "lap_timer",
        "checkpoint",
        "chase_cam",
        "steer",
        "throttle",
        "brake",
        "requestAnimationFrame",
        "boot_flag",
    ],
    summary="Open-wheel circuit racing baseline with lap timer, checkpoints, chase cam, and analog control separation.",
)
