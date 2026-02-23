from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from app.core.config import Settings


@dataclass
class SmokeCheckResult:
    ok: bool
    reason: str | None = None
    console_errors: list[str] | None = None
    screenshot_bytes: bytes | None = None


@dataclass
class QualityGateResult:
    ok: bool
    score: int
    threshold: int
    failed_checks: list[str]
    checks: dict[str, bool]


class QualityService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run_smoke_check(self, html_content: str) -> SmokeCheckResult:
        console_errors: list[str] = []
        page_errors: list[str] = []

        try:
            with TemporaryDirectory(prefix="iis-smoke-") as tmp_dir:
                html_path = Path(tmp_dir) / "index.html"
                html_path.write_text(html_content, encoding="utf-8")

                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
                    page = browser.new_page()

                    def on_console(msg) -> None:  # pragma: no cover - callback from playwright runtime
                        if msg.type == "error":
                            console_errors.append(msg.text)

                    def on_page_error(exc) -> None:  # pragma: no cover - callback from playwright runtime
                        page_errors.append(str(exc))

                    page.on("console", on_console)
                    page.on("pageerror", on_page_error)

                    page.goto(html_path.as_uri(), wait_until="load", timeout=int(self.settings.qa_smoke_timeout_seconds * 1000))
                    page.wait_for_timeout(300)
                    
                    # Capture screenshot if possible
                    screenshot_bytes = None
                    try:
                        canvas = page.locator("canvas")
                        if canvas.count() > 0:
                            screenshot_bytes = canvas.first.screenshot(type="png")
                        else:
                            screenshot_bytes = page.screenshot(type="png")
                    except Exception as e:
                        page_errors.append(f"screenshot_failed: {e}")
                        
                    browser.close()
        except PlaywrightError as exc:
            if self.settings.playwright_required:
                return SmokeCheckResult(ok=False, reason=f"playwright_error: {exc}")
            return SmokeCheckResult(ok=True, reason=f"playwright_skipped: {exc}")
        except Exception as exc:  # pragma: no cover - runtime safeguard
            return SmokeCheckResult(ok=False, reason=f"qa_exception: {exc}")

        combined_errors = console_errors + page_errors
        if combined_errors:
            return SmokeCheckResult(ok=False, reason="runtime_console_error", console_errors=combined_errors, screenshot_bytes=screenshot_bytes)

        return SmokeCheckResult(ok=True, screenshot_bytes=screenshot_bytes)

    def evaluate_quality_contract(
        self,
        html_content: str,
        *,
        design_spec: dict[str, Any] | None = None,
    ) -> QualityGateResult:
        spec = design_spec or {}

        checks: list[tuple[str, bool, int]] = [
            ("boot_flag", "window.__iis_game_boot_ok" in html_content, 20),
            ("viewport_meta", "<meta name=\"viewport\"" in html_content, 20),
            ("leaderboard_contract", "window.IISLeaderboard" in html_content, 20),
            ("overflow_guard", "overflow-guard" in html_content, 15),
            ("overflow_policy", "data-overflow-policy" in html_content, 10),
            ("safe_area", "--safe-area-padding" in html_content, 15),
            ("canvas_present", "<canvas" in html_content.lower(), 20),
            ("game_loop_raf", "requestanimationframe" in html_content.lower(), 20),
            ("keyboard_input", "keydown" in html_content.lower(), 15),
            ("game_state_logic", "game over" in html_content.lower() or "overlay" in html_content.lower(), 10),
        ]

        viewport_width = spec.get("viewport_width")
        viewport_height = spec.get("viewport_height")
        min_font_size_px = spec.get("min_font_size_px")

        if isinstance(viewport_width, int):
            checks.append(("viewport_width_match", f"--viewport-width: {viewport_width}" in html_content, 10))
        if isinstance(viewport_height, int):
            checks.append(("viewport_height_match", f"--viewport-height: {viewport_height}" in html_content, 10))
        if isinstance(min_font_size_px, int):
            checks.append(("min_font_match", f"--min-font-size: {min_font_size_px}" in html_content, 10))

        total_weight = sum(weight for _, _, weight in checks)
        passed_weight = sum(weight for _, passed, weight in checks if passed)
        score = int(round((passed_weight / total_weight) * 100)) if total_weight else 0
        threshold = self.settings.qa_min_quality_score
        check_map = {name: passed for name, passed, _ in checks}
        failed_checks = [name for name, passed, _ in checks if not passed]

        hard_failures: list[str] = []
        lowered = html_content.lower()
        if "+100 score" in lowered and "requestanimationframe" not in lowered:
            hard_failures.append("trivial_score_button_template")
        if "addEventListener(\"click\")" in html_content and "keydown" not in lowered and "<canvas" not in lowered:
            hard_failures.append("click_only_interaction")

        if hard_failures:
            failed_checks.extend(hard_failures)
            for failure in hard_failures:
                check_map[failure] = False

        return QualityGateResult(
            ok=(score >= threshold) and not hard_failures,
            score=score,
            threshold=threshold,
            failed_checks=failed_checks,
            checks=check_map,
        )
