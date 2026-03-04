from app.core.config import Settings
from app.services.quality_gates import (
    evaluate_artifact_contract,
    evaluate_gameplay_gate,
    evaluate_intent_gate,
    evaluate_quality_contract,
    evaluate_visual_gate,
)


def test_evaluate_quality_contract_accepts_valid_runtime_contract() -> None:
    settings = Settings(qa_min_quality_score=40)
    html_lines = [
        '<html>',
        '  <head><meta name="viewport" content="width=device-width"></head>',
        '  <body class="overflow-guard" data-overflow-policy="clamp">',
        '    <canvas id="game"></canvas>',
        '    <script src="https://unpkg.com/three@0.169.0/build/three.module.js"></script>',
        '    <script>',
        '      window.__iis_game_boot_ok = true;',
        '      window.IISLeaderboard = {};',
        '      const style = "--safe-area-padding: 8px";',
        '      const renderer = new THREE.WebGLRenderer();',
        '      const vertexShader = "void main() { gl_Position = vec4(0); }";',
        '      const fragmentShader = "void main() { gl_FragColor = vec4(1); }";',
        '      function update() {}',
        '      function draw() {}',
        '      function initScene() {}',
        '      function createPlayer() {}',
        '      function createEnemy() {}',
        '      function spawnWave() {}',
        '      function handleInput() {}',
        '      function updatePhysics() {}',
        '      function checkCollisions() {}',
        '      function updateScore() {}',
        '      function renderHUD() {}',
        '      function gameLoop() {}',
        '      function resetGame() {}',
        '      function loadAssets() {}',
        '      function createParticles() {}',
        '      function updateCamera() {}',
        '      function applyShader() {}',
        '      requestAnimationFrame(() => {});',
        '      document.addEventListener("keydown", () => {});',
        '      const overlay = "game over";',
        '    </script>',
        '  </body>',
        '</html>',
    ]
    # Pad to 800+ lines to satisfy code_complexity_too_low_line_count
    html_lines.extend([f'    <!-- padding line {i} -->' for i in range(800)])
    html = "\n".join(html_lines)

    result = evaluate_quality_contract(settings, html)

    assert result.ok is True
    assert result.score >= result.threshold


def test_evaluate_visual_gate_fails_without_metrics() -> None:
    settings = Settings(qa_min_visual_score=45)

    result = evaluate_visual_gate(settings, None)

    assert result.ok is False
    assert "visual_metrics_missing" in result.failed_checks


def test_evaluate_artifact_contract_requires_hybrid_engine_bundle() -> None:
    settings = Settings(qa_min_artifact_contract_score=70)
    manifest = {"bundle_kind": "single_html", "files": [{"path": "index.html"}]}

    result = evaluate_artifact_contract(settings, manifest, art_direction_contract={})

    assert result.ok is False
    assert "unsupported_bundle_kind" in result.failed_checks


def test_evaluate_gameplay_gate_uses_racing_profile_without_combat_hard_failures() -> None:
    settings = Settings(qa_min_gameplay_score=55)
    html = """
    <html>
      <body class="safe-area overflow-guard">
        <canvas id="game"></canvas>
        <script>
          const config = { mode: "webgl_three_runner" };
          let state = { score: 0 };
          let steervelocity = 0;
          let accel_rate = 0.9;
          let brake_rate = 0.7;
          let checkpoint = 0;
          let lap = 1;
          let boosttimer = 0;
          function update() {
            state.score += 2;
            requestAnimationFrame(update);
          }
          function draw() {}
          function restartGame() {}
          function endGame() {}
          function drawPostFx() {}
          function renderWebglBackground() {}
          const overlayText = "Game Over";
          document.addEventListener("keydown", () => {});
        </script>
      </body>
    </html>
    """

    result = evaluate_gameplay_gate(
        settings,
        html,
        design_spec={"text_overflow_policy": "ellipsis-clamp"},
        genre="formula racing",
        genre_engine="webgl_three_runner",
        keyword="f1 circuit race",
    )

    assert "no_enemy_pressure" not in result.failed_checks
    assert "flat_scoring_loop" not in result.failed_checks


def test_evaluate_gameplay_gate_does_not_force_genre_engine_match_when_mode_token_missing() -> None:
    settings = Settings(qa_min_gameplay_score=55)
    html = """
    <html>
      <body class="safe-area overflow-guard">
        <canvas id="game"></canvas>
        <script>
          let steervelocity = 0;
          let accel_rate = 0.9;
          let brake_rate = 0.7;
          let checkpoint = 0;
          let lap = 1;
          function update() { requestAnimationFrame(update); }
          function draw() {}
          function restartGame() {}
          function endGame() {}
          function drawPostFx() {}
          function renderWebglBackground() {}
          const overlayText = "Game Over";
          document.addEventListener("keydown", () => {});
        </script>
      </body>
    </html>
    """

    result = evaluate_gameplay_gate(
        settings,
        html,
        design_spec={"text_overflow_policy": "ellipsis-clamp"},
        genre="formula racing",
        genre_engine="webgl_three_runner",
        keyword="f1 circuit race",
    )

    assert "genre_engine_mismatch" not in result.failed_checks


def test_evaluate_quality_contract_accepts_phaser_for_2d_engine_contract() -> None:
    settings = Settings(qa_min_quality_score=40)
    html = """
    <html>
      <head><meta name="viewport" content="width=device-width" /></head>
      <body class="overflow-guard" data-overflow-policy="clamp">
        <canvas id="game"></canvas>
        <script src="https://cdn.jsdelivr.net/npm/phaser@3.90.0/dist/phaser.min.js"></script>
        <script>
          window.__iis_game_boot_ok = true;
          window.IISLeaderboard = {};
          function update() {}
          function draw() {}
          requestAnimationFrame(() => {});
          document.addEventListener("keydown", () => {});
          const overlay = "game over";
        </script>
      </body>
    </html>
    """
    html = html + "\n" + "\n".join(f"function q{i}() {{}}" for i in range(24))
    html = html + "\n" + "\n".join(f"// line {i}" for i in range(900))
    result = evaluate_quality_contract(
        settings,
        html,
        genre_engine="topdown_roguelike_shooter",
        runtime_engine_mode="2d_phaser",
    )

    assert "engine_contract_2d_phaser_missing" not in result.failed_checks


def test_evaluate_quality_contract_rejects_when_2d_engine_contract_is_missing() -> None:
    settings = Settings(qa_min_quality_score=40)
    html = """
    <html>
      <head><meta name="viewport" content="width=device-width" /></head>
      <body class="overflow-guard" data-overflow-policy="clamp">
        <canvas id="game"></canvas>
        <script>
          window.__iis_game_boot_ok = true;
          window.IISLeaderboard = {};
          function update() {}
          function draw() {}
          requestAnimationFrame(() => {});
          document.addEventListener("keydown", () => {});
          const overlay = "game over";
        </script>
      </body>
    </html>
    """
    html = html + "\n" + "\n".join(f"function q{i}() {{}}" for i in range(24))
    html = html + "\n" + "\n".join(f"// line {i}" for i in range(900))
    result = evaluate_quality_contract(
        settings,
        html,
        genre_engine="topdown_roguelike_shooter",
        runtime_engine_mode="2d_phaser",
    )

    assert "engine_contract_2d_phaser_missing" in result.failed_checks


def test_evaluate_intent_gate_passes_when_intent_tokens_are_present() -> None:
    html = """
    <html><body>
      <canvas id="game"></canvas>
        <script>
          const gameState = { mode: "race", checkpoint: 0 };
          const fantasyLabel = "f1 racing fantasy";
          function restartGame() {}
          function gameOver() {}
          function updateProgression() {}
        function renderCamera() {}
        function drift() {}
        function steer() {}
      </script>
    </body></html>
    """
    report = evaluate_intent_gate(
        html,
        intent_contract={
            "fantasy": "f1 racing checkpoint fantasy",
            "player_verbs": ["drift", "steer"],
            "camera_interaction": "camera follows racer",
            "progression_loop": ["checkpoint race", "lap pressure"],
            "fail_restart_loop": "fail and restart quickly",
            "non_negotiables": ["avoid:placeholder-only visuals"],
        },
    )

    assert report["ok"] is True
    assert int(report["score"]) >= int(report["threshold"])


def test_evaluate_intent_gate_fails_when_restart_or_verbs_are_missing() -> None:
    html = """
    <html><body>
      <script>
        function update() {}
      </script>
    </body></html>
    """
    report = evaluate_intent_gate(
        html,
        intent_contract={
            "fantasy": "flight simulator mission",
            "player_verbs": ["pitch", "roll", "yaw"],
            "camera_interaction": "cockpit camera",
            "progression_loop": ["mission progression"],
            "fail_restart_loop": "fail and restart loop",
            "non_negotiables": ["preserve_requested_intent_without_generic_substitution"],
        },
    )

    assert report["ok"] is False
    assert "player_verbs" in report["failed_items"]
    assert "fail_restart_loop" in report["failed_items"]


def test_evaluate_intent_gate_does_not_hard_fail_on_non_negotiable_advisory_only() -> None:
    html = """
    <html><body>
      <script>
        const state = { mode: "flight" };
        function restartGame() {}
        function update() {}
        function throttle() {}
        function checkpoint() {}
      </script>
    </body></html>
    """
    report = evaluate_intent_gate(
        html,
        intent_contract={
            "fantasy": "섬을 돌아다니는 풀3d 비행기 시뮬레이터",
            "player_verbs": ["throttle", "checkpoint"],
            "camera_interaction": "camera follows aircraft",
            "progression_loop": ["checkpoint lap"],
            "fail_restart_loop": "fail and restart",
            "non_negotiables": [
                "preserve_requested_intent_without_generic_substitution",
                "maintain immersion in cockpit fantasy",
            ],
        },
    )

    assert report["checks"]["non_negotiables"] is True
    assert report["ok"] is True
    assert "non_negotiables_advisory" in report["reason_by_item"]


def test_quality_and_gameplay_score_drop_when_hard_failures_exist() -> None:
    settings = Settings(qa_min_quality_score=40, qa_min_gameplay_score=55)
    html = """
    <html><body>
      <canvas id="game"></canvas>
      <script>
        window.__iis_game_boot_ok = true;
        window.IISLeaderboard = {};
      </script>
    </body></html>
    """
    quality = evaluate_quality_contract(settings, html, runtime_engine_mode="3d_three")
    gameplay = evaluate_gameplay_gate(settings, html)

    assert quality.ok is False
    assert quality.score < quality.threshold
    assert gameplay.ok is False
    assert gameplay.score < gameplay.threshold


def test_gameplay_gate_blocks_when_synapse_required_mechanics_are_missing() -> None:
    settings = Settings(qa_min_gameplay_score=55)
    html = """
    <html>
      <body class="safe-area overflow-guard">
        <canvas id="game"></canvas>
        <script>
          function update() { requestAnimationFrame(update); }
          function restartGame() {}
          document.addEventListener("keydown", () => {});
          const state = { checkpoint: 1 };
        </script>
      </body>
    </html>
    """

    result = evaluate_gameplay_gate(
        settings,
        html,
        genre="simulation",
        genre_engine="flight_sim_3d",
        keyword="island flight simulator",
        intent_contract={
            "player_verbs": ["pitch", "roll", "yaw", "throttle"],
            "progression_loop": ["takeoff", "checkpoint", "landing"],
        },
        synapse_contract={
            "required_mechanics": ["pitch", "roll", "yaw", "throttle"],
            "required_progression": ["checkpoint", "landing"],
        },
    )

    assert result.ok is False
    assert "intent_mechanics_unmet" in result.failed_checks


def test_quality_gate_treats_shader_shortage_as_non_hard_failure_signal() -> None:
    settings = Settings(qa_min_quality_score=40)
    html_lines = [
        '<html>',
        '  <head><meta name="viewport" content="width=device-width"></head>',
        '  <body class="overflow-guard" data-overflow-policy="clamp">',
        '    <canvas id="game"></canvas>',
        '    <script src="https://unpkg.com/three@0.169.0/build/three.module.js"></script>',
        '    <script>',
        '      window.__iis_game_boot_ok = true;',
        '      window.IISLeaderboard = {};',
        '      const style = "--safe-area-padding: 8px";',
        '      const renderer = new THREE.WebGLRenderer();',
        '      function update() {}',
        '      function draw() {}',
        '      function initScene() {}',
        '      function createPlayer() {}',
        '      function createEnemy() {}',
        '      function spawnWave() {}',
        '      function handleInput() {}',
        '      function updatePhysics() {}',
        '      function checkCollisions() {}',
        '      function updateScore() {}',
        '      function renderHUD() {}',
        '      function gameLoop() {}',
        '      function resetGame() {}',
        '      function loadAssets() {}',
        '      function createParticles() {}',
        '      function updateCamera() {}',
        '      requestAnimationFrame(() => {});',
        '      document.addEventListener("keydown", () => {});',
        '      const overlay = "game over";',
        '    </script>',
        '  </body>',
        '</html>',
    ]
    html_lines.extend([f'    <!-- padding line {i} -->' for i in range(820)])
    html = "\n".join(html_lines)

    result = evaluate_quality_contract(settings, html, runtime_engine_mode="3d_three")

    assert result.ok is True
    assert result.checks.get("shader_complexity_too_low") is False
