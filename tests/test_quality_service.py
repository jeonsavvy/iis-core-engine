from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from typing_extensions import Literal

from pytest import MonkeyPatch

from app.core.config import Settings
from app.services import quality_service
from app.services.quality_service import QualityService


@dataclass
class FakeMouse:
    clicks: list[tuple[int, int]] = field(default_factory=list)

    def click(self, x: int, y: int) -> None:
        self.clicks.append((x, y))


class FakeLocator:
    def __init__(self, page: "FakePage") -> None:
        self._page = page

    def count(self) -> int:
        return 1

    @property
    def first(self) -> "FakeLocator":
        return self

    def screenshot(self, *, type: str = "png") -> bytes:
        assert type == "png"
        self._page.screenshot_taken_at_probe = self._page.last_probe_index
        return b"fake-png"


@dataclass
class FakePage:
    viewport_size: dict[str, int] = field(default_factory=lambda: {"width": 1280, "height": 720})
    mouse: FakeMouse = field(default_factory=FakeMouse)
    wait_calls: list[int] = field(default_factory=list)
    goto_calls: list[tuple[str, str, int]] = field(default_factory=list)
    screenshot_taken_at_probe: int | None = None
    last_probe_index: int = -1

    def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        self.goto_calls.append((url, wait_until, timeout))

    def wait_for_timeout(self, timeout_ms: int) -> None:
        self.wait_calls.append(timeout_ms)

    def evaluate(self, script: str) -> dict[str, Any] | bool:
        if "__iisPreparePresentationCapture" in script:
            return {"hook_present": False, "ready": False, "delay_ms": 0}
        if "Boolean(window.__iisPresentationReady)" in script:
            return False
        raise AssertionError(f"unexpected evaluate script: {script[:80]}")

    def locator(self, selector: str) -> FakeLocator:
        assert selector == "canvas"
        return FakeLocator(self)

    def screenshot(self, *, type: str = "png") -> bytes:
        assert type == "png"
        self.screenshot_taken_at_probe = self.last_probe_index
        return b"fake-page-png"


@dataclass
class FakeBrowser:
    page: FakePage
    closed: bool = False

    def new_page(self) -> FakePage:
        return self.page

    def close(self) -> None:
        self.closed = True


@dataclass
class FakeChromium:
    browser: FakeBrowser

    def launch(self, *, headless: bool, args: list[str]) -> FakeBrowser:
        assert headless is True
        assert args == ["--no-sandbox"]
        return self.browser


@dataclass
class FakePlaywrightContext:
    browser: FakeBrowser

    def __enter__(self) -> Any:
        return type("FakePlaywright", (), {"chromium": FakeChromium(self.browser)})()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> Literal[False]:
        return False


def test_capture_presentation_screenshot_waits_until_countdown_clears_without_hooks(monkeypatch: MonkeyPatch) -> None:
    page = FakePage()
    browser = FakeBrowser(page=page)
    probes = [
        {"start_gate_visible": False, "countdown_text": "2"},
        {"start_gate_visible": False, "countdown_text": "1"},
        {"start_gate_visible": False, "countdown_text": "GO!"},
    ]

    def fake_capture_runtime_probe(_page: FakePage) -> dict[str, object]:
        next_index = min(page.last_probe_index + 1, len(probes) - 1)
        page.last_probe_index = next_index
        return probes[next_index]

    monkeypatch.setattr(quality_service, "sync_playwright", lambda: FakePlaywrightContext(browser))
    monkeypatch.setattr(quality_service, "capture_runtime_probe", fake_capture_runtime_probe)

    service = QualityService(Settings(playwright_required=False, qa_smoke_timeout_seconds=8.0))
    screenshot = service.capture_presentation_screenshot("<html><body>stub</body></html>")

    assert screenshot == b"fake-png"
    assert page.screenshot_taken_at_probe == 2
    assert page.goto_calls
    assert page.wait_calls[0] == 250
    assert browser.closed is True


def test_validate_presentation_contract_reports_missing_hooks_without_running_browser() -> None:
    service = QualityService(Settings(playwright_required=False, qa_smoke_timeout_seconds=8.0))

    ok, issues = service.validate_presentation_contract(
        "<html><body><canvas></canvas><script>window.__iis_game_boot_ok=true;window.IISLeaderboard={};requestAnimationFrame(()=>{});</script></body></html>"
    )

    assert ok is False
    assert "presentation_capture_hook" in issues
    assert "presentation_ready_flag" in issues
