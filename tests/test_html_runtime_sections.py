from __future__ import annotations

from app.orchestration.nodes.builder_parts.html_runtime_sections import (
    build_runtime_hud_functions_js,
    build_runtime_progression_functions_js,
    build_runtime_render_functions_js,
    build_runtime_spawn_combat_functions_js,
    build_runtime_update_function_js,
    build_runtime_utility_functions_js,
)


def test_runtime_utility_functions_block_contains_expected_tokens() -> None:
    block = build_runtime_utility_functions_js()
    assert "function restartGame() { resetState(); }" in block
    assert "function ensureWebglRuntime() {" in block
    assert "function renderWebglBackground(dt) {" in block
    assert "{{" not in block


def test_runtime_progression_functions_block_contains_expected_tokens() -> None:
    block = build_runtime_progression_functions_js()
    assert "function grantXp(amount) {" in block
    assert "function stepProgression(dt) {" in block
    assert "function consumeDash() {" in block
    assert "{{" not in block


def test_runtime_spawn_combat_functions_block_contains_expected_tokens() -> None:
    block = build_runtime_spawn_combat_functions_js()
    assert "function spawnMiniBoss() {" in block
    assert "function spawnEnemy() {" in block
    assert "function performAttack() {" in block
    assert "{{" not in block


def test_runtime_update_function_block_contains_expected_tokens() -> None:
    block = build_runtime_update_function_js()
    assert "function update(dt) {" in block
    assert "if (MODE_IS_FORMULA_CIRCUIT) {" in block
    assert "updateHud();" in block
    assert "{{" not in block


def test_runtime_render_functions_block_contains_expected_tokens() -> None:
    block = build_runtime_render_functions_js()
    assert "function drawPostFx() {" in block
    assert "function draw() {" in block
    assert "drawPostFx();" in block
    assert "{{" not in block


def test_runtime_hud_functions_block_contains_expected_tokens() -> None:
    block = build_runtime_hud_functions_js()
    assert "function updateHud() {" in block
    assert "function endGame() {" in block
    assert "async function submitScore(playerName, score, fingerprint) {" in block
    assert "{{" not in block
