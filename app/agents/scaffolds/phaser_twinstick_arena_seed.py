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
      <title>IIS Twin-Stick Arena Seed</title>
      <style>
        html, body { margin: 0; height: 100%; overflow: hidden; background: #050816; font-family: Inter, system-ui, sans-serif; color: #f8fafc; }
        #game-root { width: 100%; height: 100%; position: relative; }
        #hud { position: absolute; top: 18px; left: 18px; display: grid; gap: 6px; min-width: 220px; padding: 12px 14px; border-radius: 14px; background: rgba(2, 6, 23, 0.55); border: 1px solid rgba(34, 211, 238, 0.24); z-index: 20; pointer-events: none; }
        #hud strong { font-size: 26px; color: #f472b6; }
        #hud span { font-size: 13px; color: #dbeafe; }
        #tips { position: absolute; top: 18px; right: 18px; z-index: 20; padding: 12px 14px; border-radius: 12px; background: rgba(15, 23, 42, 0.55); border: 1px solid rgba(148, 163, 184, 0.24); font-size: 12px; line-height: 1.45; pointer-events: none; }
      </style>
    </head>
    <body>
      <div id="game-root">
        <div id="hud">
          <span>TWIN-STICK ARENA</span>
          <strong id="wave-readout">Wave 1</strong>
          <span id="status-readout">Dash ready · Hold the arena</span>
          <span id="combo-readout">Combo 0 · Enemies 0</span>
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

        const waveReadout = document.getElementById("wave-readout");
        const statusReadout = document.getElementById("status-readout");
        const comboReadout = document.getElementById("combo-readout");

        const gameState = {
          wave: 1,
          combo: 0,
          canDash: true,
          dashCooldown: 0,
          fireCooldown: 0,
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

        let sceneRef, player, cursors, keys, bullets, enemies, pointerAim = { x: 0, y: 0 };
        const game = new Phaser.Game(config);

        function create() {
          sceneRef = this;
          const g = this.add.graphics();
          g.fillStyle(0x22d3ee, 1);
          g.fillCircle(18, 18, 16);
          g.generateTexture("player-core", 36, 36);
          g.clear();
          g.fillStyle(0xf472b6, 1);
          g.fillCircle(8, 8, 8);
          g.generateTexture("bullet-core", 16, 16);
          g.clear();
          g.fillStyle(0xfb7185, 1);
          g.fillCircle(14, 14, 14);
          g.generateTexture("enemy-core", 28, 28);
          g.clear();

          this.add.rectangle(this.scale.width / 2, this.scale.height / 2, this.scale.width - 120, this.scale.height - 120, 0x081225, 1)
            .setStrokeStyle(2, 0x1e3a8a, 0.55);

          player = this.physics.add.image(this.scale.width / 2, this.scale.height / 2, "player-core");
          player.setCollideWorldBounds(true);
          player.body.setCircle(14);

          bullets = this.physics.add.group();
          enemies = this.physics.add.group();

          cursors = this.input.keyboard.createCursorKeys();
          keys = this.input.keyboard.addKeys("W,A,S,D,SHIFT,R");
          this.input.on("pointermove", (pointer) => {
            pointerAim.x = pointer.worldX;
            pointerAim.y = pointer.worldY;
          });
          this.input.on("pointerdown", () => fireBullet());

          this.physics.add.overlap(bullets, enemies, onBulletHitEnemy);
          this.physics.add.overlap(player, enemies, onPlayerHitEnemy);

          spawnWave(gameState.wave);
          updateHud();
          window.__iis_game_boot_ok = true;
        }

        function update(time, delta) {
          const dt = delta / 1000;
          if (!player) return;

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
          bullet.setScale(0.75);
          bullet.lifeSpan = 1200;
          gameState.fireCooldown = 0.12;
        }

        function dash() {
          gameState.canDash = false;
          gameState.dashCooldown = 1.4;
          const angle = player.rotation;
          sceneRef.physics.velocityFromRotation(angle, 620, player.body.velocity);
          statusReadout.textContent = "Dash committed · reposition and return fire";
        }

        function spawnWave(wave) {
          const count = 3 + wave;
          for (let i = 0; i < count; i += 1) {
            const side = i % 4;
            const spawnX = side === 0 ? 40 : side === 1 ? sceneRef.scale.width - 40 : Phaser.Math.Between(60, sceneRef.scale.width - 60);
            const spawnY = side === 2 ? 40 : side === 3 ? sceneRef.scale.height - 40 : Phaser.Math.Between(60, sceneRef.scale.height - 60);
            const enemy = enemies.create(spawnX, spawnY, "enemy-core");
            enemy.hp = 2 + Math.floor(wave / 2);
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

        function resetArena() {
          enemies.clear(true, true);
          bullets.clear(true, true);
          player.setPosition(sceneRef.scale.width / 2, sceneRef.scale.height / 2);
          player.setVelocity(0, 0);
          gameState.wave = 1;
          gameState.combo = 0;
          gameState.canDash = true;
          gameState.dashCooldown = 0;
          statusReadout.textContent = "Arena reset · build rhythm again";
          spawnWave(gameState.wave);
          updateHud();
        }

        function updateHud() {
          waveReadout.textContent = `Wave ${gameState.wave}`;
          comboReadout.textContent = `Combo ${gameState.combo} · Enemies ${enemies ? enemies.countActive(true) : 0}`;
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
    version="v1",
    html=TOPDOWN_HTML,
    acceptance_tags=[
        "phaser",
        "twin_stick",
        "dash",
        "wave_spawn",
        "arena_bounds",
        "fire",
        "aim",
        "requestAnimationFrame",
        "boot_flag",
    ],
    summary="Phaser twin-stick arena baseline with dash, wave loop, readable HUD, and combat feedback hooks.",
)
