from pathlib import Path

from app.services.quality_smoke import (
    evaluate_runtime_liveness,
    is_representative_capture_ready,
    is_non_fatal_request_failure,
    is_non_fatal_runtime_issue,
    prepare_smoke_workspace,
)


def test_prepare_smoke_workspace_prefers_entrypoint_path(tmp_path: Path) -> None:
    html = "<html><body>entry</body></html>"
    entry_path = prepare_smoke_workspace(
        tmp_dir=str(tmp_path),
        html_content=html,
        artifact_files=[{"path": "assets/readme.txt", "content": "ok"}],
        entrypoint_path="play/index.html",
    )

    assert entry_path.as_posix().endswith("/artifact/play/index.html")
    assert entry_path.read_text(encoding="utf-8") == html


def test_prepare_smoke_workspace_falls_back_to_index_when_entrypoint_invalid(tmp_path: Path) -> None:
    html = "<html><body>fallback</body></html>"
    entry_path = prepare_smoke_workspace(
        tmp_dir=str(tmp_path),
        html_content=html,
        artifact_files=[{"path": "../escape.html", "content": "bad"}],
        entrypoint_path="../invalid.html",
    )

    assert entry_path.as_posix().endswith("/artifact/index.html")
    assert entry_path.read_text(encoding="utf-8") == html


def test_prepare_smoke_workspace_coerces_extensionless_entrypoint_to_index_html(tmp_path: Path) -> None:
    html = "<html><body>inline</body></html>"
    entry_path = prepare_smoke_workspace(
        tmp_dir=str(tmp_path),
        html_content=html,
        artifact_files=[],
        entrypoint_path="inline",
    )

    assert entry_path.as_posix().endswith("/artifact/inline/index.html")
    assert entry_path.read_text(encoding="utf-8") == html


def test_non_fatal_issue_classifiers() -> None:
    assert is_non_fatal_runtime_issue("Failed to load resource: net::ERR_FILE_NOT_FOUND")
    assert is_non_fatal_runtime_issue("The AudioContext was not allowed to start.")
    assert is_non_fatal_runtime_issue("NotAllowedError: play() failed because the user didn't interact with the document first.")
    assert is_non_fatal_request_failure(
        resource_type="image",
        url="file:///tmp/asset.png",
        error_text="net::ERR_FILE_NOT_FOUND",
    )
    assert not is_non_fatal_request_failure(
        resource_type="script",
        url="https://example.com/app.js",
        error_text="timed out",
    )


def test_representative_capture_waits_until_countdown_clears() -> None:
    assert not is_representative_capture_ready({"countdown_text": "2", "start_gate_visible": False})
    assert not is_representative_capture_ready({"countdown_text": "", "start_gate_visible": True})
    assert not is_representative_capture_ready({"countdown_text": "", "start_gate_visible": False, "overlay_visible": True})
    assert not is_representative_capture_ready({"countdown_text": "", "start_gate_visible": False, "game_over_visible": True})
    assert is_representative_capture_ready({"countdown_text": "", "start_gate_visible": False})
    assert is_representative_capture_ready({"countdown_text": "GO!", "start_gate_visible": False})


def test_runtime_liveness_flags_game_over_overlay_as_warning() -> None:
    fatal, warnings = evaluate_runtime_liveness(
        before={
            "boot_ok": True,
            "overlay_visible": False,
            "timer_text": "Time: 60.0",
            "canvas_width": 1280,
            "canvas_height": 720,
            "scroll_height": 720,
            "client_height": 720,
        },
        after={
            "boot_ok": True,
            "overlay_visible": True,
            "overlay_text": "Game Over",
            "timer_text": "Time: 60.0",
            "canvas_width": 1280,
            "canvas_height": 720,
            "scroll_height": 720,
            "client_height": 720,
        },
    )

    assert fatal == []
    assert "overlay_game_over_visible" in warnings
    assert "timer_static_with_overlay" in warnings
    assert "early_session_game_over" in warnings


def test_runtime_liveness_flags_manual_start_overlay_as_warning() -> None:
    fatal, warnings = evaluate_runtime_liveness(
        before={
            "boot_ok": True,
            "overlay_visible": False,
            "timer_text": "Time: 60.0",
            "canvas_width": 1280,
            "canvas_height": 720,
            "scroll_height": 720,
            "client_height": 720,
        },
        after={
            "boot_ok": True,
            "overlay_visible": True,
            "overlay_text": "Tap to start",
            "timer_text": "Time: 60.0",
            "canvas_width": 1280,
            "canvas_height": 720,
            "scroll_height": 720,
            "client_height": 720,
        },
    )

    assert fatal == []
    assert "manual_start_interaction_required" in warnings
    assert "timer_static_manual_start_gate" in warnings


def test_runtime_liveness_flags_overflow_as_warning() -> None:
    fatal, warnings = evaluate_runtime_liveness(
        before={
            "boot_ok": True,
            "overlay_visible": False,
            "timer_text": "Time: 60.0",
            "canvas_width": 1280,
            "canvas_height": 720,
            "scroll_height": 720,
            "client_height": 720,
        },
        after={
            "boot_ok": True,
            "overlay_visible": False,
            "timer_text": "Time: 58.4",
            "canvas_width": 1280,
            "canvas_height": 720,
            "scroll_height": 1600,
            "client_height": 720,
        },
    )

    assert fatal == []
    assert "runtime_layout_scroll_overflow" in warnings


def test_runtime_liveness_detects_game_over_via_visible_text() -> None:
    fatal, warnings = evaluate_runtime_liveness(
        before={
            "boot_ok": True,
            "overlay_visible": False,
            "timer_text": "Time: 60.0",
            "hp_text": "HP: 3",
            "canvas_width": 1280,
            "canvas_height": 720,
            "scroll_height": 720,
            "client_height": 720,
        },
        after={
            "boot_ok": True,
            "overlay_visible": False,
            "game_over_visible": True,
            "visible_ui_text": "Game Over | Restart",
            "timer_text": "Time: 58.7",
            "hp_text": "HP: 0",
            "canvas_width": 1280,
            "canvas_height": 720,
            "scroll_height": 720,
            "client_height": 720,
        },
    )

    assert fatal == []
    assert "immediate_zero_hp_state" in warnings
    assert "game_over_visible_with_runtime_signal" in warnings


def test_runtime_liveness_treats_game_over_text_only_as_warning() -> None:
    fatal, warnings = evaluate_runtime_liveness(
        before={
            "boot_ok": True,
            "overlay_visible": False,
            "timer_text": "Time: 60.0",
            "hp_text": "HP: 3",
            "canvas_width": 1280,
            "canvas_height": 720,
            "scroll_height": 720,
            "client_height": 720,
        },
        after={
            "boot_ok": True,
            "overlay_visible": False,
            "game_over_visible": True,
            "visible_ui_text": "Game Over ruleset",
            "timer_text": "Time: 58.4",
            "hp_text": "HP: 3",
            "canvas_width": 1280,
            "canvas_height": 720,
            "scroll_height": 720,
            "client_height": 720,
        },
    )

    assert fatal == []
    assert "game_over_text_visible_without_failure_signal" in warnings


def test_runtime_liveness_flags_hud_jargon_as_warning() -> None:
    fatal, warnings = evaluate_runtime_liveness(
        before={
            "boot_ok": True,
            "overlay_visible": False,
            "timer_text": "Time: 60.0",
            "hp_text": "HP: 3",
            "score_text": "Score: 0",
            "canvas_width": 1280,
            "canvas_height": 720,
            "scroll_height": 720,
            "client_height": 720,
        },
        after={
            "boot_ok": True,
            "overlay_visible": False,
            "timer_text": "Time: 58.4 · Lv.1 · W1 · XP 20/100",
            "hp_text": "HP: 3 · Relic: 0 · Syn:0",
            "score_text": "Score: 120",
            "canvas_width": 1280,
            "canvas_height": 720,
            "scroll_height": 720,
            "client_height": 720,
        },
    )

    assert fatal == []
    assert "hud_jargon_visible" in warnings


def test_runtime_liveness_does_not_flag_early_session_game_over_after_long_play() -> None:
    fatal, warnings = evaluate_runtime_liveness(
        before={
            "boot_ok": True,
            "overlay_visible": False,
            "timer_text": "Time: 240.0",
            "canvas_width": 1280,
            "canvas_height": 720,
            "scroll_height": 720,
            "client_height": 720,
        },
        after={
            "boot_ok": True,
            "overlay_visible": True,
            "overlay_text": "Game Over",
            "timer_text": "Time: 210.2",
            "canvas_width": 1280,
            "canvas_height": 720,
            "scroll_height": 720,
            "client_height": 720,
        },
    )

    assert fatal == []
    assert "overlay_game_over_visible" in warnings
    assert "early_session_game_over" not in warnings
