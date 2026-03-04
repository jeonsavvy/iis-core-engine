from __future__ import annotations

from app.services.vertex_text_utils import (
    compile_generated_artifact,
    coerce_message_text,
    looks_like_playable_artifact,
    playable_artifact_missing_requirements,
    strip_code_fences,
)


def test_coerce_message_text_handles_mixed_content() -> None:
    raw = ["line-1", {"text": "line-2"}, {"ignored": "value"}]
    assert coerce_message_text(raw) == "line-1\nline-2"


def test_strip_code_fences_removes_markdown_wrapper() -> None:
    wrapped = "```html\n<html></html>\n```"
    assert strip_code_fences(wrapped) == "<html></html>"


def test_looks_like_playable_artifact_checks_required_tokens() -> None:
    html = (
        "<html><body><canvas></canvas><script>"
        "window.__iis_game_boot_ok=true;"
        "window.IISLeaderboard={};"
        "requestAnimationFrame(()=>{});"
        "</script></body></html>"
    )
    assert looks_like_playable_artifact(html)


def test_looks_like_playable_artifact_accepts_canvas_runtime_without_canvas_tag() -> None:
    html = (
        "<html><body><script>"
        "const c = document.createElement('canvas');"
        "document.body.appendChild(c);"
        "window.__iis_game_boot_ok=true;"
        "window.IISLeaderboard={};"
        "requestAnimationFrame(()=>{});"
        "</script></body></html>"
    )
    assert looks_like_playable_artifact(html)


def test_playable_artifact_missing_requirements_returns_missing_tokens() -> None:
    html = "<html><body><script>requestAnimationFrame(()=>{});</script></body></html>"
    missing = playable_artifact_missing_requirements(html)
    assert "boot_flag" in missing
    assert "leaderboard_contract" in missing


def test_playable_artifact_missing_requirements_rejects_unsupported_three_utils_usage() -> None:
    html = (
        "<html><body><canvas></canvas><script>"
        "window.__iis_game_boot_ok=true;"
        "window.IISLeaderboard={};"
        "requestAnimationFrame(()=>{});"
        "const merged = new THREE.BufferGeometryUtils();"
        "</script></body></html>"
    )
    missing = playable_artifact_missing_requirements(html)
    assert "unsupported_three_buffergeometryutils" in missing
    assert "unsupported_three_namespace_addon_utils" in missing


def test_playable_artifact_missing_requirements_rejects_three_namespace_addon_controls() -> None:
    html = (
        "<html><body><canvas></canvas><script>"
        "window.__iis_game_boot_ok=true;"
        "window.IISLeaderboard={};"
        "requestAnimationFrame(()=>{});"
        "const c = new THREE.OrbitControls(camera, renderer.domElement);"
        "</script></body></html>"
    )
    missing = playable_artifact_missing_requirements(html)
    assert "unsupported_three_namespace_addon_controls" in missing


def test_playable_artifact_missing_requirements_detects_unresolved_addon_constructor() -> None:
    html = (
        "<html><body><canvas></canvas><script>"
        "window.__iis_game_boot_ok=true;"
        "window.IISLeaderboard={};"
        "requestAnimationFrame(()=>{});"
        "const controls = new OrbitControls(camera, renderer.domElement);"
        "</script></body></html>"
    )
    missing = playable_artifact_missing_requirements(html)
    assert "unresolved_addon_constructor_controls" in missing


def test_playable_artifact_missing_requirements_accepts_explicitly_imported_addon_constructor() -> None:
    html = (
        "<html><body><canvas></canvas><script type='module'>"
        "import { OrbitControls } from 'https://unpkg.com/three/examples/jsm/controls/OrbitControls.js';"
        "window.__iis_game_boot_ok=true;"
        "window.IISLeaderboard={};"
        "requestAnimationFrame(()=>{});"
        "const controls = new OrbitControls(camera, renderer.domElement);"
        "</script></body></html>"
    )
    missing = playable_artifact_missing_requirements(html)
    assert "unresolved_addon_constructor_controls" not in missing


def test_compile_generated_artifact_rewrites_three_namespace_addons_with_shim() -> None:
    html = (
        "<html><body><canvas></canvas><script>"
        "window.__iis_game_boot_ok=true;"
        "window.IISLeaderboard={};"
        "requestAnimationFrame(()=>{});"
        "const controls = new THREE.OrbitControls(camera, renderer.domElement);"
        "</script></body></html>"
    )
    compiled, meta = compile_generated_artifact(html)
    assert "window.__iis_addon_shims.OrbitControls" in compiled
    assert "iis-addon-shims" in compiled
    assert "rewrite_three_namespace_addons" in meta["transforms_applied"]


def test_compile_generated_artifact_rewrites_unresolved_addon_constructors() -> None:
    html = (
        "<html><body><canvas></canvas><script>"
        "window.__iis_game_boot_ok=true;"
        "window.IISLeaderboard={};"
        "requestAnimationFrame(()=>{});"
        "const controls = new OrbitControls(camera, renderer.domElement);"
        "</script></body></html>"
    )
    compiled, meta = compile_generated_artifact(html)
    assert "new window.__iis_addon_shims.OrbitControls(" in compiled
    assert "rewrite_unresolved_addon_constructors" in meta["transforms_applied"]


def test_compile_generated_artifact_injects_runtime_contract_shim_when_missing_required_tokens() -> None:
    html = "<html><body><canvas></canvas><script>const x = 1;</script></body></html>"
    compiled, meta = compile_generated_artifact(html)
    assert "__iis_game_boot_ok" in compiled
    assert "IISLeaderboard" in compiled
    assert "requestAnimationFrame" in compiled
    assert "inject_runtime_contract_shim" in meta["transforms_applied"]


def test_compile_generated_artifact_reports_visual_precheck_and_asset_usage() -> None:
    html = (
        "<html><body><canvas></canvas><script>"
        "window.__iis_game_boot_ok=true;"
        "window.IISLeaderboard={};"
        "requestAnimationFrame(()=>{});"
        "const sprite='./player.svg';"
        "</script></body></html>"
    )
    compiled, meta = compile_generated_artifact(
        html,
        asset_manifest={"images": {"player": "./player.svg", "enemy": "./enemy.svg", "boost": "./boost.svg"}},
        asset_files_index={"hud_frame": "./hud-frame.svg", "track_grid": "./track-grid.svg"},
    )
    assert isinstance(meta.get("precheck_before"), dict)
    assert isinstance(meta.get("precheck_after"), dict)
    assert isinstance(meta.get("asset_usage_count"), int)
    assert "required_asset_keys" in meta
    assert "used_asset_keys" in meta
    assert compiled.startswith("<html")
