from pathlib import Path

from app.services.quality_smoke import (
    evaluate_runtime_liveness,
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


def test_runtime_liveness_detects_immediate_game_over_overlay() -> None:
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

    assert "immediate_game_over_overlay" in fatal
    assert warnings == ["timer_static_with_overlay"]


def test_runtime_liveness_flags_manual_start_overlay_as_fatal() -> None:
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

    assert "manual_start_interaction_required" in fatal
    assert "timer_static_manual_start_gate" in fatal
    assert warnings == []


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
