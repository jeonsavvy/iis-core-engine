from __future__ import annotations

from app.services.vertex_text_utils import coerce_message_text, looks_like_playable_artifact, strip_code_fences


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
