from __future__ import annotations

from textwrap import dedent

from app.agents.scaffolds.base import ScaffoldSeed


TOPDOWN_HTML = dedent(
    """
    <!doctype html>
    <html lang="ko">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>IIS Lowpoly Tactical Arena Seed</title>
      <style>
        html, body { margin: 0; height: 100%; overflow: hidden; background: #050816; font-family: Inter, system-ui, sans-serif; color: #f8fafc; }
        #game-root { width: 100%; height: 100%; position: relative; }
        #hud { position: absolute; top: 18px; left: 18px; display: grid; gap: 6px; min-width: 220px; padding: 12px 14px; border-radius: 14px; background: rgba(2, 6, 23, 0.55); border: 1px solid rgba(34, 211, 238, 0.24); z-index: 20; pointer-events: none; }
        #hud strong { font-size: 26px; color: #f472b6; }
        #hud span { font-size: 13px; color: #dbeafe; }
        #tips { position: absolute; top: 18px; right: 18px; z-index: 20; padding: 12px 14px; border-radius: 12px; background: rgba(15, 23, 42, 0.55); border: 1px solid rgba(148, 163, 184, 0.24); font-size: 12px; line-height: 1.45; pointer-events: none; }
        #crosshair { position: absolute; width: 22px; height: 22px; border: 2px solid rgba(34, 211, 238, 0.75); border-radius: 999px; transform: translate(-50%, -50%); pointer-events: none; z-index: 15; box-shadow: 0 0 16px rgba(34, 211, 238, 0.2); }
        #title-screen { position: absolute; inset: 0; z-index: 30; display: flex; align-items: center; justify-content: center; background: radial-gradient(circle at center, rgba(15, 23, 42, 0.4) 0%, rgba(2, 6, 23, 0.92) 72%); }
        #title-card { width: min(420px, calc(100% - 48px)); padding: 24px 28px; border-radius: 18px; background: rgba(8, 15, 32, 0.82); border: 1px solid rgba(34, 211, 238, 0.24); box-shadow: 0 0 48px rgba(34, 211, 238, 0.12); text-align: center; }
        #title-card h1 { margin: 0 0 12px; font-size: 34px; color: #67e8f9; letter-spacing: 0.12em; text-transform: uppercase; }
        #title-card p { margin: 0 0 18px; color: #fbcfe8; line-height: 1.6; font-size: 14px; }
        #title-card button { min-height: 42px; padding: 0 18px; border: 0; border-radius: 999px; background: linear-gradient(135deg, #06b6d4, #ec4899); color: white; font-size: 14px; font-weight: 800; cursor: pointer; }
      </style>
    </head>
    <body>
      <div id="game-root">
        <div id="title-screen">
          <div id="title-card">
            <h1>LOWPOLY SIEGE</h1>
            <p>로우폴리 전장에서 커버를 돌며 적 압박을 끊어내세요. 대시로 각을 만들고 웨이브를 버티는 택티컬 탑뷰 슈팅 베이스라인입니다.</p>
            <button id="start-button" type="button">START RUN</button>
          </div>
        </div>
        <div id="crosshair"></div>
        <div id="hud">
          <span>LOWPOLY TACTICAL ARENA</span>
          <strong id="wave-readout">Wave 1</strong>
          <span id="status-readout">Dash ready · Hold the arena</span>
          <span id="combo-readout">Combo 0 · Enemies 0</span>
          <span id="threat-readout">Threat 0 · Dash ready</span>
        </div>
        <div id="tips">
          <b>Controls</b><br />
          Move: WASD / Arrow Keys<br />
          Aim: Mouse<br />
          Fire: Left Click<br />
          Dash: Shift<br />
          Reset: R
        </div>
      </div>
      <script src="https://cdn.jsdelivr.net/npm/phaser@3.90.0/dist/phaser.min.js"></script>
      <script>
        if (!window.IISLeaderboard) {
          window.IISLeaderboard = { postScore: (score) => console.log("IIS:score", score) };
        }
        window.__iis_game_boot_ok = false;
        // Phaser runs its own requestAnimationFrame loop internally.

        const crosshair = document.getElementById("crosshair");
        const waveReadout = document.getElementById("wave-readout");
        const statusReadout = document.getElementById("status-readout");
        const comboReadout = document.getElementById("combo-readout");
        const threatReadout = document.getElementById("threat-readout");
        const titleScreen = document.getElementById("title-screen");
        const startButton = document.getElementById("start-button");

        const gameState = {
          wave: 1,
          combo: 0,
          canDash: true,
          dashCooldown: 0,
          fireCooldown: 0,
          threat: 0,
          started: false,
        };

        const config = {
          type: Phaser.AUTO,
          width: window.innerWidth,
          height: window.innerHeight,
          parent: "game-root",
          backgroundColor: "#050816",
          physics: {
            default: "arcade",
            arcade: { debug: false }
          },
          scene: {
            preload() {},
            create,
            update
          }
        };

        let sceneRef, player, cursors, keys, bullets, enemyBullets, enemies, coverBlocks, pointerAim = { x: 0, y: 0 }, dashGhosts;
        const game = new Phaser.Game(config);

        function create() {
          sceneRef = this;
          const g = this.add.graphics();
          g.fillStyle(0x22d3ee, 1);
          g.fillTriangle(18, 0, 0, 34, 36, 34);
          g.generateTexture("player-core", 36, 36);
          g.clear();
          g.fillStyle(0xf472b6, 1);
          g.fillRect(0, 6, 16, 4);
          g.generateTexture("bullet-core", 16, 16);
          g.clear();
          g.fillStyle(0xfb7185, 1);
          g.fillPoints([{x: 14,y: 0},{x: 28,y: 14},{x:14,y:28},{x:0,y:14}], true);
          g.generateTexture("enemy-core", 28, 28);
          g.clear();

          this.add.rectangle(this.scale.width / 2, this.scale.height / 2, this.scale.width - 120, this.scale.height - 120, 0x081225, 1)
            .setStrokeStyle(2, 0x1e3a8a, 0.55);
          for (let i = 0; i < 6; i += 1) {
            this.add.rectangle(180 + i * 150, 170 + (i % 2) * 260, 48, 16, 0x0f172a, 1).setStrokeStyle(2, 0x334155, 0.45);
          }

          player = this.physics.add.image(this.scale.width / 2, this.scale.height / 2, "player-core");
          player.setCollideWorldBounds(true);
          player.body.setCircle(14);
          player.setScale(1.05);

          bullets = this.physics.add.group();
          enemyBullets = this.physics.add.group();
          enemies = this.physics.add.group();
          coverBlocks = this.physics.add.staticGroup();
          dashGhosts = this.add.group();

          const arenaCoverLayout = [
            [this.scale.width * 0.28, this.scale.height * 0.32, 90, 28],
            [this.scale.width * 0.72, this.scale.height * 0.34, 90, 28],
            [this.scale.width * 0.48, this.scale.height * 0.58, 130, 30],
            [this.scale.width * 0.22, this.scale.height * 0.72, 70, 22],
            [this.scale.width * 0.78, this.scale.height * 0.72, 70, 22],
          ];
          arenaCoverLayout.forEach(([x, y, width, height]) => {
            const cover = this.add.rectangle(x, y, width, height, 0x0f172a, 1).setStrokeStyle(2, 0x475569, 0.55);
            this.physics.add.existing(cover, true);
            coverBlocks.add(cover);
          });

          cursors = this.input.keyboard.createCursorKeys();
          keys = this.input.keyboard.addKeys("W,A,S,D,SHIFT,R");
          this.input.on("pointermove", (pointer) => {
            pointerAim.x = pointer.worldX;
            pointerAim.y = pointer.worldY;
            if (crosshair) {
              crosshair.style.left = `${pointer.x}px`;
              crosshair.style.top = `${pointer.y}px`;
            }
          });
          const beginRun = () => {
            if (gameState.started) return;
            gameState.started = true;
            if (titleScreen) titleScreen.style.display = "none";
            statusReadout.textContent = "Run live · dash through the barrage";
          };
          this.input.on("pointerdown", () => {
            if (!gameState.started) {
              beginRun();
              return;
            }
            fireBullet();
          });
          startButton?.addEventListener("click", beginRun);
          startButton?.addEventListener("pointerdown", (event) => {
            event.preventDefault();
            event.stopPropagation();
            beginRun();
          });
          startButton?.addEventListener("touchend", (event) => {
            event.preventDefault();
            event.stopPropagation();
            beginRun();
          }, { passive: false });
          window.addEventListener("keydown", (event) => {
            if (!gameState.started && ["Enter", "Space", "KeyW", "KeyA", "KeyS", "KeyD", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.code)) {
              beginRun();
            }
          });

          this.physics.add.overlap(bullets, enemies, onBulletHitEnemy);
          this.physics.add.overlap(player, enemies, onPlayerHitEnemy);
          this.physics.add.overlap(player, enemyBullets, onPlayerHitByBullet);
          this.physics.add.collider(player, coverBlocks);
          this.physics.add.collider(enemies, coverBlocks);
          this.physics.add.collider(enemyBullets, coverBlocks, (bullet) => bullet.destroy());
          this.physics.add.collider(bullets, coverBlocks, (bullet) => bullet.destroy());

          spawnWave(gameState.wave);
          updateHud();
          window.__iis_game_boot_ok = true;
        }

        function update(time, delta) {
          const dt = delta / 1000;
          if (!player) return;
          if (!gameState.started) return;

          if (Phaser.Input.Keyboard.JustDown(keys.R)) {
            resetArena();
          }

          const moveX = (keys.D.isDown || cursors.right.isDown ? 1 : 0) - (keys.A.isDown || cursors.left.isDown ? 1 : 0);
          const moveY = (keys.S.isDown || cursors.down.isDown ? 1 : 0) - (keys.W.isDown || cursors.up.isDown ? 1 : 0);
          const velocity = new Phaser.Math.Vector2(moveX, moveY).normalize().scale(280);
          player.setVelocity(velocity.x, velocity.y);

          player.rotation = Phaser.Math.Angle.Between(player.x, player.y, pointerAim.x || player.x, pointerAim.y || player.y);

          if (keys.SHIFT.isDown && gameState.canDash) {
            dash();
          }

          bullets.children.iterate((bullet) => {
            if (!bullet) return;
            if (bullet.x < -40 || bullet.y < -40 || bullet.x > sceneRef.scale.width + 40 || bullet.y > sceneRef.scale.height + 40) {
              bullet.destroy();
            }
          });
          enemyBullets.children.iterate((bullet) => {
            if (!bullet) return;
            if (bullet.x < -40 || bullet.y < -40 || bullet.x > sceneRef.scale.width + 40 || bullet.y > sceneRef.scale.height + 40) {
              bullet.destroy();
            }
          });

          let liveEnemyCount = 0;
          enemies.children.iterate((enemy) => {
            if (!enemy || !player) return;
            liveEnemyCount += 1;
            const chaseVector = new Phaser.Math.Vector2(player.x - enemy.x, player.y - enemy.y).normalize();
            enemy.body.setVelocity(chaseVector.x * (72 + gameState.wave * 9), chaseVector.y * (72 + gameState.wave * 9));
            enemy.fireCooldown = (enemy.fireCooldown || 0) - dt;
            if (enemy.fireCooldown <= 0) {
              fireEnemyBullet(enemy);
              enemy.fireCooldown = 0.8 + Math.random() * 0.7;
            }
          });
          gameState.threat = liveEnemyCount;

          gameState.fireCooldown = Math.max(0, gameState.fireCooldown - dt);
          gameState.dashCooldown = Math.max(0, gameState.dashCooldown - dt);
          if (!gameState.canDash && gameState.dashCooldown <= 0) {
            gameState.canDash = true;
            statusReadout.textContent = "Dash ready · Hold the arena";
          }

          if (enemies.countActive(true) === 0) {
            gameState.wave += 1;
            gameState.combo = Math.max(0, gameState.combo - 1);
            spawnWave(gameState.wave);
            statusReadout.textContent = `Wave ${gameState.wave} inbound`;
            updateHud();
          }
        }

        function fireBullet() {
          if (gameState.fireCooldown > 0 || !player) return;
          const bullet = bullets.create(player.x, player.y, "bullet-core");
          const angle = player.rotation;
          sceneRef.physics.velocityFromRotation(angle, 620, bullet.body.velocity);
          bullet.setScale(0.92);
          bullet.lifeSpan = 1200;
          sceneRef.add.circle(player.x, player.y, 12, 0x22d3ee, 0.2).setBlendMode(Phaser.BlendModes.ADD);
          gameState.fireCooldown = 0.12;
        }

        function fireEnemyBullet(enemy) {
          if (!enemy || !player) return;
          const bullet = enemyBullets.create(enemy.x, enemy.y, "bullet-core");
          bullet.setTint(0xfb7185);
          bullet.setScale(0.9);
          const angle = Phaser.Math.Angle.Between(enemy.x, enemy.y, player.x, player.y);
          sceneRef.physics.velocityFromRotation(angle, 260 + gameState.wave * 18, bullet.body.velocity);
        }

        function dash() {
          gameState.canDash = false;
          gameState.dashCooldown = 1.4;
          const angle = player.rotation;
          sceneRef.physics.velocityFromRotation(angle, 620, player.body.velocity);
          statusReadout.textContent = "Dash committed · reposition and return fire";
          const ghost = sceneRef.add.circle(player.x, player.y, 18, 0x22d3ee, 0.18);
          dashGhosts.add(ghost);
          sceneRef.tweens.add({
            targets: ghost,
            alpha: 0,
            scale: 2.1,
            duration: 220,
            onComplete: () => ghost.destroy(),
          });
          sceneRef.cameras.main.shake(70, 0.003);
        }

        function spawnWave(wave) {
          const count = 2 + Math.min(8, wave);
          for (let i = 0; i < count; i += 1) {
            const side = i % 4;
            const spawnX = side === 0 ? 40 : side === 1 ? sceneRef.scale.width - 40 : Phaser.Math.Between(60, sceneRef.scale.width - 60);
            const spawnY = side === 2 ? 40 : side === 3 ? sceneRef.scale.height - 40 : Phaser.Math.Between(60, sceneRef.scale.height - 60);
            const enemy = enemies.create(spawnX, spawnY, "enemy-core");
            enemy.hp = 2 + Math.floor(wave / 2);
            enemy.fireCooldown = 0.6 + i * 0.12;
            enemy.body.setCircle(12);
          }
          comboReadout.textContent = `Combo ${gameState.combo} · Enemies ${enemies.countActive(true)}`;
        }

        function onBulletHitEnemy(bullet, enemy) {
          bullet.destroy();
          enemy.hp -= 1;
          enemy.setTint(0xffffff);
          sceneRef.time.delayedCall(70, () => enemy.clearTint());
          if (enemy.hp <= 0) {
            enemy.destroy();
            gameState.combo += 1;
            window.IISLeaderboard.postScore(100 + gameState.combo * 25);
            statusReadout.textContent = "Target broken · keep the combo alive";
            sceneRef.cameras.main.shake(90, 0.004);
            for (let i = 0; i < 8; i += 1) {
              const shard = sceneRef.add.rectangle(enemy.x, enemy.y, 8, 3, i % 2 === 0 ? 0x22d3ee : 0xfb7185, 0.95);
              shard.setBlendMode(Phaser.BlendModes.ADD);
              sceneRef.tweens.add({
                targets: shard,
                x: enemy.x + Phaser.Math.Between(-42, 42),
                y: enemy.y + Phaser.Math.Between(-42, 42),
                alpha: 0,
                angle: Phaser.Math.Between(0, 270),
                duration: 240,
                onComplete: () => shard.destroy(),
              });
            }
            updateHud();
          }
        }

        function onPlayerHitEnemy(playerObj, enemy) {
          enemy.destroy();
          gameState.combo = 0;
          statusReadout.textContent = "Impact taken · dash out and reset the angle";
          sceneRef.tweens.add({
            targets: playerObj,
            alpha: 0.25,
            yoyo: true,
            repeat: 3,
            duration: 60,
            onComplete: () => playerObj.setAlpha(1),
          });
          updateHud();
        }

        function onPlayerHitByBullet(playerObj, bullet) {
          bullet.destroy();
          gameState.combo = 0;
          statusReadout.textContent = "Enemy fire landed · move, dash, and re-angle";
          sceneRef.add.circle(playerObj.x, playerObj.y, 22, 0xfb7185, 0.24).setBlendMode(Phaser.BlendModes.ADD);
          updateHud();
        }

        function resetArena() {
          enemies.clear(true, true);
          bullets.clear(true, true);
          player.setPosition(sceneRef.scale.width / 2, sceneRef.scale.height / 2);
          player.setVelocity(0, 0);
          gameState.wave = 1;
          gameState.combo = 0;
          gameState.canDash = true;
          gameState.dashCooldown = 0;
          gameState.threat = 0;
          gameState.started = false;
          statusReadout.textContent = "Arena reset · build rhythm again";
          if (titleScreen) titleScreen.style.display = "flex";
          spawnWave(gameState.wave);
          updateHud();
        }

        function updateHud() {
          waveReadout.textContent = `Wave ${gameState.wave}`;
          comboReadout.textContent = `Combo ${gameState.combo} · Enemies ${enemies ? enemies.countActive(true) : 0}`;
          threatReadout.textContent = `Threat ${gameState.threat} · ${gameState.canDash ? "Dash ready" : "Dash cooling"}`;
        }
      </script>
    </body>
    </html>
    """
).strip()


SEED = ScaffoldSeed(
    key="phaser_twinstick_arena_seed",
    archetype="topdown_shooter_twinstick_2d",
    engine_mode="2d_phaser",
    version="v3",
    html=TOPDOWN_HTML,
    acceptance_tags=[
        "phaser",
        "twin_stick",
        "dash",
        "wave_spawn",
        "arena_bounds",
        "arena_landmark",
        "fire",
        "aim",
        "enemy_bullet_loop",
        "combat_feedback",
        "dash_trace",
        "title_menu",
        "screen_shake",
        "requestAnimationFrame",
        "boot_flag",
    ],
    summary="Phaser lowpoly tactical twin-stick baseline with title menu, enemy bullet pressure, cover landmarks, and strong combat feedback.",
)
