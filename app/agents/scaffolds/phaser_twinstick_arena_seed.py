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
        #hud { position: absolute; top: 18px; left: 18px; display: grid; gap: 6px; min-width: 240px; padding: 12px 14px; border-radius: 14px; background: rgba(2, 6, 23, 0.55); border: 1px solid rgba(34, 211, 238, 0.24); z-index: 20; pointer-events: none; }
        #hud strong { font-size: 26px; color: #f472b6; }
        #hud span { font-size: 13px; color: #dbeafe; }
        #tips { position: absolute; top: 18px; right: 18px; z-index: 20; padding: 12px 14px; border-radius: 12px; background: rgba(15, 23, 42, 0.55); border: 1px solid rgba(148, 163, 184, 0.24); font-size: 12px; line-height: 1.45; pointer-events: none; }
        #crosshair { position: absolute; width: 22px; height: 22px; border: 2px solid rgba(34, 211, 238, 0.75); border-radius: 999px; transform: translate(-50%, -50%); pointer-events: none; z-index: 15; box-shadow: 0 0 16px rgba(34, 211, 238, 0.2); }
        .overlay-screen { position: absolute; inset: 0; z-index: 30; display: flex; align-items: center; justify-content: center; background: radial-gradient(circle at center, rgba(15, 23, 42, 0.4) 0%, rgba(2, 6, 23, 0.92) 72%); }
        .overlay-card { width: min(440px, calc(100% - 48px)); padding: 24px 28px; border-radius: 18px; background: rgba(8, 15, 32, 0.82); border: 1px solid rgba(34, 211, 238, 0.24); box-shadow: 0 0 48px rgba(34, 211, 238, 0.12); text-align: center; }
        .overlay-card h1, .overlay-card h2 { margin: 0 0 12px; font-size: 34px; color: #67e8f9; letter-spacing: 0.12em; text-transform: uppercase; }
        .overlay-card p { margin: 0 0 18px; color: #fbcfe8; line-height: 1.6; font-size: 14px; }
        .overlay-card button { min-height: 42px; padding: 0 18px; border: 0; border-radius: 999px; background: linear-gradient(135deg, #06b6d4, #ec4899); color: white; font-size: 14px; font-weight: 800; cursor: pointer; }
      </style>
    </head>
    <body>
      <div id="game-root">
        <div id="title-screen" class="overlay-screen">
          <div class="overlay-card">
            <h1>LOWPOLY SIEGE</h1>
            <p>로우폴리 전장에서 커버를 돌며 적 압박을 끊어내세요. 대시로 각을 만들고 웨이브를 버티는 택티컬 탑뷰 슈팅 베이스라인입니다.</p>
            <button id="start-button" type="button">START RUN</button>
          </div>
        </div>
        <div id="game-over-screen" class="overlay-screen" style="display:none;">
          <div class="overlay-card">
            <h2 id="game-over-title">RUN BROKEN</h2>
            <p id="game-over-detail">HP를 모두 잃었습니다. 전장을 다시 읽고 재진입하세요.</p>
            <button id="restart-button" type="button">RESTART RUN</button>
          </div>
        </div>
        <div id="crosshair"></div>
        <div id="hud">
          <span>LOWPOLY TACTICAL ARENA</span>
          <strong id="wave-readout">Wave 1</strong>
          <span id="status-readout">Dash ready · Hold the arena</span>
          <span id="xp-readout">Level 1 · XP 0 / 110</span>
          <span id="combo-readout">Combo 0 · Enemies 0</span>
          <span id="threat-readout">Threat 0 · HP 5/5 · Dash ready</span>
        </div>
        <div id="tips">
          <b>Controls</b><br />
          Move: WASD / Arrow Keys<br />
          Aim: Mouse<br />
          Fire: Left Click<br />
          Dash: Shift<br />
          Reset: R
        </div>
        <div id="upgrade-overlay" style="display:none;position:absolute;inset:0;z-index:28;align-items:center;justify-content:center;background:rgba(2,6,23,0.74);">
          <div id="upgrade-card" style="width:min(460px,calc(100% - 48px));padding:24px 28px;border-radius:18px;background:rgba(8,15,32,0.92);border:1px solid rgba(34,211,238,0.24);box-shadow:0 0 48px rgba(34,211,238,0.12);">
            <h2 style="margin:0 0 10px;font-size:28px;color:#67e8f9;letter-spacing:0.04em;">LEVEL UP</h2>
            <p style="margin:0 0 18px;color:#cbd5e1;line-height:1.6;font-size:14px;">전장을 멈추고 하나를 골라 빌드 방향을 정하세요.</p>
            <div id="upgrade-choices" style="display:grid;gap:10px;"></div>
          </div>
        </div>
      </div>
      <script src="https://cdn.jsdelivr.net/npm/phaser@3.90.0/dist/phaser.min.js"></script>
      <script>
        if (!window.IISLeaderboard) {
          window.IISLeaderboard = { postScore: (score) => console.log("IIS:score", score) };
        }
        window.__iis_game_boot_ok = false;
        window.__iisPresentationReady = false;
        // Phaser runs its own requestAnimationFrame loop internally.

        const crosshair = document.getElementById("crosshair");
        const waveReadout = document.getElementById("wave-readout");
        const statusReadout = document.getElementById("status-readout");
        const xpReadout = document.getElementById("xp-readout");
        const comboReadout = document.getElementById("combo-readout");
        const threatReadout = document.getElementById("threat-readout");
        const titleScreen = document.getElementById("title-screen");
        const gameOverScreen = document.getElementById("game-over-screen");
        const gameOverTitle = document.getElementById("game-over-title");
        const gameOverDetail = document.getElementById("game-over-detail");
        const startButton = document.getElementById("start-button");
        const restartButton = document.getElementById("restart-button");
        const upgradeOverlay = document.getElementById("upgrade-overlay");
        const upgradeChoices = document.getElementById("upgrade-choices");

        const gameState = {
          wave: 1,
          combo: 0,
          canDash: true,
          dashCooldown: 0,
          fireCooldown: 0,
          threat: 0,
          started: false,
          level: 1,
          xp: 0,
          xpNext: 110,
          upgradePending: false,
          fireRateMul: 1,
          pierceShots: 0,
          spreadShot: 0,
          moveSpeedMul: 1,
          bulletSpeedMul: 1,
          hp: 5,
          maxHp: 5,
          dashDistance: 210,
          dashInvuln: 0,
          dashTweenActive: false,
          tempoBoostMs: 0,
          tempoBoostUntil: 0,
          shockwaveRadius: 0,
          impactBurst: 0,
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
        let coverRects = [];
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

          this.physics.world.setBounds(42, 42, this.scale.width - 84, this.scale.height - 84);
          this.add.rectangle(this.scale.width / 2, this.scale.height / 2, this.scale.width - 84, this.scale.height - 84, 0x081225, 1)
            .setStrokeStyle(2, 0x1e3a8a, 0.55);

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
            [this.scale.width * 0.24, this.scale.height * 0.26, 96, 30],
            [this.scale.width * 0.52, this.scale.height * 0.24, 128, 26],
            [this.scale.width * 0.78, this.scale.height * 0.3, 100, 30],
            [this.scale.width * 0.34, this.scale.height * 0.56, 132, 32],
            [this.scale.width * 0.66, this.scale.height * 0.58, 132, 32],
            [this.scale.width * 0.22, this.scale.height * 0.74, 84, 24],
            [this.scale.width * 0.78, this.scale.height * 0.74, 84, 24],
          ];
          arenaCoverLayout.forEach(([x, y, width, height], index) => {
            const color = index % 2 === 0 ? 0x0f172a : 0x172554;
            const cover = this.add.rectangle(x, y, width, height, color, 1).setStrokeStyle(2, 0x475569, 0.55);
            this.physics.add.existing(cover, true);
            coverBlocks.add(cover);
          });
          coverRects = arenaCoverLayout.map(([x, y, width, height]) => new Phaser.Geom.Rectangle(x - width / 2, y - height / 2, width, height));

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
            if (gameOverScreen) gameOverScreen.style.display = "none";
            sceneRef.physics.world.resume();
            player.setActive(true).setVisible(true);
            player.body.enable = true;
            statusReadout.textContent = "Run live · cut angles and break the siege";
            updateHud();
          };
          const restartRun = () => {
            resetArena();
            beginRun();
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
          restartButton?.addEventListener("click", restartRun);
          restartButton?.addEventListener("pointerdown", (event) => {
            event.preventDefault();
            event.stopPropagation();
            restartRun();
          });
          window.__iisPreparePresentationCapture = () => {
            resetArena();
            beginRun();
            gameState.upgradePending = false;
            gameState.dashTweenActive = false;
            player.setPosition(sceneRef.scale.width / 2, sceneRef.scale.height / 2);
            player.setVelocity(0, 0);
            statusReadout.textContent = "Arena preview · ready to publish";
            sceneRef.physics.world.pause();
            window.__iisPresentationReady = false;
            sceneRef.time.delayedCall(120, () => {
              updateHud();
              window.__iisPresentationReady = true;
            });
            return { delay_ms: 140, reason: "arena_thumbnail_mode" };
          };
          window.addEventListener("keydown", (event) => {
            if (!gameState.started && ["Enter", "Space", "KeyW", "KeyA", "KeyS", "KeyD", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.code)) {
              beginRun();
            }
          });
          this.time.delayedCall(480, beginRun);

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
          window.__iisPresentationReady = true;
        }

        function update(time, delta) {
          const dt = delta / 1000;
          if (!player) return;
          if (!gameState.started) return;

          if (Phaser.Input.Keyboard.JustDown(keys.R)) {
            resetArena();
            return;
          }

          if (gameState.upgradePending) return;

          if (gameState.dashTweenActive) {
            gameState.dashInvuln = Math.max(0, gameState.dashInvuln - dt);
            return;
          }

          const tempoBoostActive = gameState.tempoBoostUntil > time;
          const moveX = (keys.D.isDown || cursors.right.isDown ? 1 : 0) - (keys.A.isDown || cursors.left.isDown ? 1 : 0);
          const moveY = (keys.S.isDown || cursors.down.isDown ? 1 : 0) - (keys.W.isDown || cursors.up.isDown ? 1 : 0);
          const speedMul = tempoBoostActive ? gameState.moveSpeedMul * 1.18 : gameState.moveSpeedMul;
          const velocity = new Phaser.Math.Vector2(moveX, moveY).normalize().scale(296 * speedMul);
          player.setVelocity(velocity.x, velocity.y);
          player.rotation = Phaser.Math.Angle.Between(player.x, player.y, pointerAim.x || player.x, pointerAim.y || player.y);

          if (Phaser.Input.Keyboard.JustDown(keys.SHIFT) && gameState.canDash) {
            dash();
          }
          gameState.dashInvuln = Math.max(0, gameState.dashInvuln - dt);

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
            const enemyType = enemy.enemyType || "chaser";
            const distanceToPlayer = Phaser.Math.Distance.Between(enemy.x, enemy.y, player.x, player.y);
            const chaseVector = new Phaser.Math.Vector2(player.x - enemy.x, player.y - enemy.y).normalize();

            if (enemyType === "shooter") {
              if (distanceToPlayer < 190) {
                enemy.body.setVelocity(-chaseVector.x * (92 + gameState.wave * 4), -chaseVector.y * (92 + gameState.wave * 4));
              } else {
                enemy.body.setVelocity(chaseVector.x * (64 + gameState.wave * 4), chaseVector.y * (64 + gameState.wave * 4));
              }
            } else if (enemyType === "flanker") {
              const flankAngle = Phaser.Math.Angle.Between(enemy.x, enemy.y, player.x, player.y) + (enemy.orbitSign || 1) * Math.PI / 2;
              const flankTargetX = player.x + Math.cos(flankAngle) * 132;
              const flankTargetY = player.y + Math.sin(flankAngle) * 132;
              const flankVector = new Phaser.Math.Vector2(flankTargetX - enemy.x, flankTargetY - enemy.y).normalize();
              enemy.body.setVelocity(flankVector.x * (138 + gameState.wave * 6), flankVector.y * (138 + gameState.wave * 6));
            } else if (enemyType === "bruiser") {
              enemy.body.setVelocity(chaseVector.x * (74 + gameState.wave * 4), chaseVector.y * (74 + gameState.wave * 4));
            } else {
              enemy.body.setVelocity(chaseVector.x * (118 + gameState.wave * 8), chaseVector.y * (118 + gameState.wave * 8));
            }

            enemy.fireCooldown = (enemy.fireCooldown || 0) - dt;
            if (enemy.fireCooldown <= 0) {
              if (enemyType !== "bruiser" || distanceToPlayer < 170) {
                fireEnemyBullet(enemy);
              }
              enemy.fireCooldown =
                enemyType === "shooter"
                  ? 0.58 + Math.random() * 0.32
                  : enemyType === "flanker"
                    ? 0.9 + Math.random() * 0.28
                    : enemyType === "bruiser"
                      ? 1.15 + Math.random() * 0.4
                      : 0.82 + Math.random() * 0.24;
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
          const spreadCount = Math.max(1, 1 + gameState.spreadShot * 2);
          for (let i = 0; i < spreadCount; i += 1) {
            const bullet = bullets.create(player.x, player.y, "bullet-core");
            const spreadOffset = spreadCount === 1 ? 0 : Phaser.Math.DegToRad((i - (spreadCount - 1) / 2) * 8);
            const angle = player.rotation + spreadOffset;
            sceneRef.physics.velocityFromRotation(angle, 680 * gameState.bulletSpeedMul, bullet.body.velocity);
            bullet.setScale(0.92);
            bullet.lifeSpan = 1200;
            bullet.pierceLeft = gameState.pierceShots;
            bullet.damage = 1 + gameState.impactBurst;
          }
          const muzzleFlash = sceneRef.add.circle(player.x, player.y, 10, 0x22d3ee, 0.3).setBlendMode(Phaser.BlendModes.ADD);
          sceneRef.tweens.add({
            targets: muzzleFlash,
            alpha: 0,
            scale: 1.85,
            duration: 90,
            onComplete: () => muzzleFlash.destroy(),
          });
          gameState.fireCooldown = 0.12 / gameState.fireRateMul;
        }

        function fireEnemyBullet(enemy) {
          if (!enemy || !player) return;
          const bullet = enemyBullets.create(enemy.x, enemy.y, "bullet-core");
          bullet.setTint(enemy.enemyType === "flanker" ? 0xfbbf24 : 0xfb7185);
          bullet.setScale(enemy.enemyType === "bruiser" ? 1.1 : 0.9);
          const angle = Phaser.Math.Angle.Between(enemy.x, enemy.y, player.x, player.y);
          const speed =
            enemy.enemyType === "bruiser"
              ? 220 + gameState.wave * 10
              : enemy.enemyType === "flanker"
                ? 320 + gameState.wave * 16
                : 278 + gameState.wave * 18;
          sceneRef.physics.velocityFromRotation(angle, speed, bullet.body.velocity);
        }

        function spawnDashGhost(x, y, alpha = 0.16, scale = 1.1) {
          const ghost = sceneRef.add.circle(x, y, 16, 0x22d3ee, alpha).setBlendMode(Phaser.BlendModes.ADD);
          dashGhosts.add(ghost);
          sceneRef.tweens.add({
            targets: ghost,
            alpha: 0,
            scale,
            duration: 140,
            onComplete: () => ghost.destroy(),
          });
        }

        function dash() {
          if (!player || gameState.dashTweenActive) return;
          gameState.canDash = false;
          gameState.dashCooldown = Math.max(0.42, 1.18 - (gameState.level - 1) * 0.04);
          const moveX = (keys.D.isDown || cursors.right.isDown ? 1 : 0) - (keys.A.isDown || cursors.left.isDown ? 1 : 0);
          const moveY = (keys.S.isDown || cursors.down.isDown ? 1 : 0) - (keys.W.isDown || cursors.up.isDown ? 1 : 0);
          const fallbackAngle = player.rotation;
          const safePoint = resolveDashTarget(player.x, player.y, moveX, moveY, fallbackAngle, gameState.dashDistance);
          gameState.dashInvuln = 0.24;
          gameState.dashTweenActive = true;
          statusReadout.textContent = "Dash committed · carve a new angle";
          player.setVelocity(0, 0);
          player.body.enable = false;
          spawnDashGhost(player.x, player.y, 0.22, 1.7);
          sceneRef.tweens.add({
            targets: player,
            x: safePoint.x,
            y: safePoint.y,
            duration: 120,
            ease: "Quad.Out",
            onUpdate: () => {
              if (Math.random() > 0.35) {
                spawnDashGhost(player.x, player.y, 0.12, 1.4);
              }
            },
            onComplete: () => {
              player.body.enable = true;
              gameState.dashTweenActive = false;
              burstImpact(player.x, player.y, 0x22d3ee, 18);
              if (gameState.shockwaveRadius > 0) {
                applyShockwave(player.x, player.y, gameState.shockwaveRadius);
              }
              sceneRef.cameras.main.shake(70, 0.003);
            },
          });
        }

        function resolveDashTarget(originX, originY, moveX, moveY, fallbackAngle, dashDistance) {
          let dir = new Phaser.Math.Vector2(moveX, moveY);
          if (dir.lengthSq() === 0) {
            dir = new Phaser.Math.Vector2(Math.cos(fallbackAngle), Math.sin(fallbackAngle));
          }
          dir = dir.normalize();
          const step = 10;
          let safeX = originX;
          let safeY = originY;
          for (let travelled = step; travelled <= dashDistance; travelled += step) {
            const nextX = originX + dir.x * travelled;
            const nextY = originY + dir.y * travelled;
            if (nextX < 54 || nextX > sceneRef.scale.width - 54 || nextY < 54 || nextY > sceneRef.scale.height - 54) {
              break;
            }
            const bodyRect = new Phaser.Geom.Rectangle(nextX - 14, nextY - 14, 28, 28);
            if (coverRects.some((rect) => Phaser.Geom.Intersects.RectangleToRectangle(bodyRect, rect))) {
              break;
            }
            safeX = nextX;
            safeY = nextY;
          }
          return { x: safeX, y: safeY };
        }

        function enemyArchetypeForIndex(wave, index) {
          const roster = ["chaser", "shooter", "flanker", "bruiser"];
          return roster[(wave + index) % roster.length];
        }

        function spawnWave(wave) {
          const count = 4 + Math.min(8, wave);
          for (let i = 0; i < count; i += 1) {
            const side = i % 4;
            const spawnX = side === 0 ? 58 : side === 1 ? sceneRef.scale.width - 58 : Phaser.Math.Between(72, sceneRef.scale.width - 72);
            const spawnY = side === 2 ? 58 : side === 3 ? sceneRef.scale.height - 58 : Phaser.Math.Between(72, sceneRef.scale.height - 72);
            const enemy = enemies.create(spawnX, spawnY, "enemy-core");
            const enemyType = enemyArchetypeForIndex(wave, i);
            enemy.enemyType = enemyType;
            enemy.orbitSign = i % 2 === 0 ? 1 : -1;
            enemy.setCollideWorldBounds(true);
            if (enemyType === "shooter") {
              enemy.hp = 2 + Math.floor(wave / 2);
              enemy.fireCooldown = 0.4 + i * 0.07;
              enemy.body.setCircle(12);
              enemy.setTint(0x60a5fa);
            } else if (enemyType === "flanker") {
              enemy.hp = 2 + Math.floor(wave / 3);
              enemy.fireCooldown = 0.68 + i * 0.05;
              enemy.body.setCircle(11);
              enemy.setScale(0.92);
              enemy.setTint(0xfbbf24);
            } else if (enemyType === "bruiser") {
              enemy.hp = 5 + Math.floor(wave / 2);
              enemy.fireCooldown = 1.0 + i * 0.06;
              enemy.body.setCircle(15);
              enemy.setScale(1.2);
              enemy.setTint(0xf97316);
            } else {
              enemy.hp = 3 + Math.floor(wave / 2);
              enemy.fireCooldown = 0.8 + i * 0.05;
              enemy.body.setCircle(13);
              enemy.setTint(0xf472b6);
            }
          }
          comboReadout.textContent = `Combo ${gameState.combo} · Enemies ${enemies.countActive(true)}`;
        }

        function burstImpact(x, y, color, radius) {
          const pulse = sceneRef.add.circle(x, y, radius, color, 0.24).setBlendMode(Phaser.BlendModes.ADD);
          sceneRef.tweens.add({
            targets: pulse,
            alpha: 0,
            scale: 1.8,
            duration: 180,
            onComplete: () => pulse.destroy(),
          });
        }

        function applyEnemyDamage(enemy, damage, impactX, impactY) {
          if (!enemy || !enemy.active) return;
          enemy.hp -= damage;
          enemy.setTint(0xffffff);
          burstImpact(impactX ?? enemy.x, impactY ?? enemy.y, 0x22d3ee, 10);
          sceneRef.time.delayedCall(70, () => enemy?.active && enemy.clearTint());
          if (enemy.hp <= 0) {
            handleEnemyDefeat(enemy);
          }
        }

        function applyShockwave(x, y, radius) {
          enemies.children.iterate((enemy) => {
            if (!enemy || !enemy.active) return;
            if (Phaser.Math.Distance.Between(enemy.x, enemy.y, x, y) <= radius) {
              applyEnemyDamage(enemy, 1, enemy.x, enemy.y);
            }
          });
        }

        function handleEnemyDefeat(enemy) {
          const enemyX = enemy.x;
          const enemyY = enemy.y;
          enemy.destroy();
          gameState.combo += 1;
          gainXp(42 + Math.min(38, gameState.wave * 6));
          if (gameState.tempoBoostMs > 0) {
            gameState.tempoBoostUntil = sceneRef.time.now + gameState.tempoBoostMs;
          }
          window.IISLeaderboard.postScore(110 + gameState.combo * 26);
          statusReadout.textContent = "Target broken · keep the combo alive";
          sceneRef.cameras.main.shake(90, 0.004);
          burstImpact(enemyX, enemyY, 0xfb7185, 16);
          if (gameState.impactBurst > 0) {
            enemies.children.iterate((nearbyEnemy) => {
              if (!nearbyEnemy || !nearbyEnemy.active) return;
              if (Phaser.Math.Distance.Between(enemyX, enemyY, nearbyEnemy.x, nearbyEnemy.y) <= 76) {
                applyEnemyDamage(nearbyEnemy, gameState.impactBurst, nearbyEnemy.x, nearbyEnemy.y);
              }
            });
          }
          updateHud();
        }

        function onBulletHitEnemy(bullet, enemy) {
          const damage = bullet.damage || 1;
          if (bullet.pierceLeft > 0) {
            bullet.pierceLeft -= 1;
          } else {
            bullet.destroy();
          }
          applyEnemyDamage(enemy, damage, bullet.x, bullet.y);
        }

        function damagePlayer(amount, message, x, y) {
          gameState.combo = 0;
          gameState.hp = Math.max(0, gameState.hp - amount);
          statusReadout.textContent = message;
          burstImpact(x, y, 0xfb7185, 22);
          sceneRef.tweens.add({
            targets: player,
            alpha: 0.25,
            yoyo: true,
            repeat: 3,
            duration: 60,
            onComplete: () => player.setAlpha(1),
          });
          updateHud();
          if (gameState.hp <= 0) {
            triggerGameOver(message);
          }
        }

        function onPlayerHitEnemy(playerObj, enemy) {
          if (gameState.dashInvuln > 0) return;
          enemy.destroy();
          damagePlayer(1, "Impact taken · dash out and reset the angle", playerObj.x, playerObj.y);
        }

        function onPlayerHitByBullet(playerObj, bullet) {
          if (gameState.dashInvuln > 0) {
            bullet.destroy();
            return;
          }
          bullet.destroy();
          damagePlayer(1, "Enemy fire landed · move, dash, and re-angle", playerObj.x, playerObj.y);
        }

        function triggerGameOver(reason) {
          gameState.started = false;
          gameState.upgradePending = false;
          gameState.dashTweenActive = false;
          player.setVelocity(0, 0);
          player.body.enable = true;
          sceneRef.physics.world.pause();
          if (upgradeOverlay) upgradeOverlay.style.display = "none";
          if (upgradeChoices) upgradeChoices.innerHTML = "";
          if (gameOverTitle) gameOverTitle.textContent = "RUN BROKEN";
          if (gameOverDetail) gameOverDetail.textContent = `${reason} HP를 모두 잃었습니다.`;
          if (gameOverScreen) gameOverScreen.style.display = "flex";
          statusReadout.textContent = "Game over · restart and rebuild the lane";
        }

        function gainXp(amount) {
          gameState.xp += amount;
          while (gameState.xp >= gameState.xpNext) {
            gameState.xp -= gameState.xpNext;
            levelUp();
          }
          updateHud();
        }

        function levelUp() {
          gameState.level += 1;
          gameState.xpNext = Math.round(gameState.xpNext * 1.2);
          presentUpgradeChoices();
        }

        function presentUpgradeChoices() {
          if (!upgradeOverlay || !upgradeChoices) return;
          const pool = [
            { key: "overdrive", label: "오버드라이브", detail: "연사와 탄속을 함께 올려 압박을 밀어냅니다." },
            { key: "pierce", label: "관통 라인", detail: "탄환이 적 하나를 더 관통합니다." },
            { key: "spread", label: "삼각 분사", detail: "여러 갈래 탄막으로 측면 적을 정리합니다." },
            { key: "phase", label: "페이즈 대시", detail: "대시 거리를 늘리고 충격파를 남깁니다." },
            { key: "plating", label: "복합 장갑", detail: "최대 체력을 늘리고 1 회복합니다." },
            { key: "tempo", label: "킬 템포", detail: "적 처치 후 잠깐 더 빠르게 돌파합니다." },
            { key: "impact", label: "애프터쇼크", detail: "적 처치 시 가까운 적에게 충격 피해를 전파합니다." },
            { key: "move", label: "기동 재세팅", detail: "기본 이동 속도를 높여 각을 더 빨리 만듭니다." },
          ];
          const choices = Phaser.Utils.Array.Shuffle(pool.slice()).slice(0, 3);
          upgradeChoices.innerHTML = "";
          upgradeOverlay.style.display = "flex";
          gameState.upgradePending = true;
          sceneRef.physics.world.pause();
          choices.forEach((choice) => {
            const button = document.createElement("button");
            button.type = "button";
            button.style.minHeight = "58px";
            button.style.padding = "12px 14px";
            button.style.borderRadius = "14px";
            button.style.border = "1px solid rgba(103,232,249,0.2)";
            button.style.background = "rgba(15,23,42,0.85)";
            button.style.color = "#e2e8f0";
            button.style.cursor = "pointer";
            button.innerHTML = `<strong style="display:block;font-size:14px;color:#67e8f9;">${choice.label}</strong><span style="display:block;margin-top:6px;font-size:12px;line-height:1.5;color:#cbd5e1;">${choice.detail}</span>`;
            button.addEventListener("click", () => applyUpgrade(choice.key));
            upgradeChoices.appendChild(button);
          });
          statusReadout.textContent = `Level ${gameState.level} · choose the next edge`;
        }

        function applyUpgrade(key) {
          if (key === "overdrive") {
            gameState.fireRateMul = Math.min(2.3, gameState.fireRateMul + 0.24);
            gameState.bulletSpeedMul = Math.min(1.45, gameState.bulletSpeedMul + 0.08);
          }
          if (key === "pierce") gameState.pierceShots = Math.min(2, gameState.pierceShots + 1);
          if (key === "spread") gameState.spreadShot = Math.min(2, gameState.spreadShot + 1);
          if (key === "phase") {
            gameState.dashDistance = Math.min(280, gameState.dashDistance + 26);
            gameState.shockwaveRadius = Math.min(86, gameState.shockwaveRadius + 18);
          }
          if (key === "plating") {
            gameState.maxHp = Math.min(8, gameState.maxHp + 1);
            gameState.hp = Math.min(gameState.maxHp, gameState.hp + 1);
          }
          if (key === "tempo") gameState.tempoBoostMs = Math.min(2200, gameState.tempoBoostMs + 700);
          if (key === "impact") gameState.impactBurst = Math.min(2, gameState.impactBurst + 1);
          if (key === "move") gameState.moveSpeedMul = Math.min(1.55, gameState.moveSpeedMul + 0.09);
          if (upgradeOverlay) upgradeOverlay.style.display = "none";
          if (upgradeChoices) upgradeChoices.innerHTML = "";
          gameState.upgradePending = false;
          sceneRef.physics.world.resume();
          statusReadout.textContent = "Upgrade locked · hold the arena";
          updateHud();
        }

        function resetArena() {
          enemies.clear(true, true);
          bullets.clear(true, true);
          enemyBullets.clear(true, true);
          player.setPosition(sceneRef.scale.width / 2, sceneRef.scale.height / 2);
          player.setVelocity(0, 0);
          player.setAlpha(1);
          player.body.enable = true;
          sceneRef.physics.world.resume();
          gameState.wave = 1;
          gameState.combo = 0;
          gameState.canDash = true;
          gameState.dashCooldown = 0;
          gameState.threat = 0;
          gameState.started = false;
          gameState.level = 1;
          gameState.xp = 0;
          gameState.xpNext = 110;
          gameState.upgradePending = false;
          gameState.fireRateMul = 1;
          gameState.pierceShots = 0;
          gameState.spreadShot = 0;
          gameState.moveSpeedMul = 1;
          gameState.bulletSpeedMul = 1;
          gameState.hp = 5;
          gameState.maxHp = 5;
          gameState.dashDistance = 210;
          gameState.dashInvuln = 0;
          gameState.dashTweenActive = false;
          gameState.tempoBoostMs = 0;
          gameState.tempoBoostUntil = 0;
          gameState.shockwaveRadius = 0;
          gameState.impactBurst = 0;
          statusReadout.textContent = "Arena reset · build rhythm again";
          if (titleScreen) titleScreen.style.display = "flex";
          if (gameOverScreen) gameOverScreen.style.display = "none";
          if (upgradeOverlay) upgradeOverlay.style.display = "none";
          if (upgradeChoices) upgradeChoices.innerHTML = "";
          spawnWave(gameState.wave);
          updateHud();
        }

        function updateHud() {
          waveReadout.textContent = `Wave ${gameState.wave}`;
          xpReadout.textContent = `Level ${gameState.level} · XP ${gameState.xp} / ${gameState.xpNext}`;
          comboReadout.textContent = `Combo ${gameState.combo} · Enemies ${enemies ? enemies.countActive(true) : 0}`;
          threatReadout.textContent = `Threat ${gameState.threat} · HP ${gameState.hp}/${gameState.maxHp} · ${gameState.canDash ? "Dash ready" : "Dash cooling"}`;
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
