from __future__ import annotations

from app.orchestration.nodes.builder_parts.html_runtime_shell import RUNTIME_DOCUMENT_CLOSE, build_runtime_document_open


def test_runtime_document_open_contains_expected_shell_tokens() -> None:
    html = build_runtime_document_open(
        title="Sample",
        genre="arcade",
        slug="sample-game",
        accent_color="#22c55e",
        viewport_width=1280,
        viewport_height=720,
        safe_area_padding=24,
        min_font_size_px=14,
        text_overflow_policy="ellipsis-clamp",
        mode_label="Arcade",
        mode_objective="Survive",
        mode_controls="Arrow keys",
        asset_pack={
            "bg_top": "#111111",
            "bg_bottom": "#000000",
            "hud_primary": "#ffffff",
            "hud_muted": "#cccccc",
        },
    )
    assert html.startswith("<!doctype html>")
    assert "<title>Sample</title>" in html
    assert ">Arrow keys</p>" in html
    assert ">Arcade</p>" not in html
    assert "sample-game" not in html
    assert "aspect-ratio: 16 / 9;" not in html
    assert "<canvas id=\"game\" width=\"1280\" height=\"720\"></canvas>" in html
    assert html.rstrip().endswith("<script>")


def test_runtime_document_close_matches_expected_footer() -> None:
    assert RUNTIME_DOCUMENT_CLOSE == "    </script>\n  </body>\n</html>\n"
