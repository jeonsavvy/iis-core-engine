from __future__ import annotations

from tempfile import TemporaryDirectory
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from app.core.config import Settings
from app.services.quality_gates import (
    evaluate_artifact_contract as evaluate_artifact_contract_gate,
    evaluate_gameplay_gate as evaluate_gameplay_gate_gate,
    evaluate_quality_contract as evaluate_quality_contract_gate,
    evaluate_visual_gate as evaluate_visual_gate_gate,
)
from app.services.quality_smoke import (
    capture_visual_metrics,
    is_non_fatal_request_failure,
    is_non_fatal_runtime_issue,
    prepare_smoke_workspace,
)
from app.services.quality_types import ArtifactContractResult, GameplayGateResult, QualityGateResult, SmokeCheckResult


class QualityService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def run_smoke_check(
        self,
        html_content: str,
        *,
        artifact_files: list[dict[str, Any]] | None = None,
        entrypoint_path: str | None = None,
    ) -> SmokeCheckResult:
        fatal_errors: list[str] = []
        non_fatal_warnings: list[str] = []
        screenshot_bytes = None
        visual_metrics: dict[str, float] | None = None

        try:
            with TemporaryDirectory(prefix="iis-smoke-") as tmp_dir:
                html_path = prepare_smoke_workspace(
                    tmp_dir=tmp_dir,
                    html_content=html_content,
                    artifact_files=artifact_files,
                    entrypoint_path=entrypoint_path,
                )

                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
                    page = browser.new_page()

                    def on_console(msg) -> None:  # pragma: no cover - callback from playwright runtime
                        if msg.type == "error":
                            issue = str(msg.text)
                            if is_non_fatal_runtime_issue(issue):
                                non_fatal_warnings.append(issue)
                            else:
                                fatal_errors.append(issue)

                    def on_page_error(exc) -> None:  # pragma: no cover - callback from playwright runtime
                        issue = str(exc)
                        if is_non_fatal_runtime_issue(issue):
                            non_fatal_warnings.append(issue)
                        else:
                            fatal_errors.append(issue)

                    def on_request_failed(req) -> None:  # pragma: no cover - callback from playwright runtime
                        failure = ""
                        try:
                            failure = str(req.failure.error_text or "")
                        except Exception:
                            failure = ""
                        resource_type = ""
                        try:
                            resource_type = str(req.resource_type or "")
                        except Exception:
                            resource_type = ""
                        url = ""
                        try:
                            url = str(req.url or "")
                        except Exception:
                            url = ""
                        issue = f"request_failed[{resource_type}] {url} {failure}".strip()
                        if is_non_fatal_request_failure(
                            resource_type=resource_type,
                            url=url,
                            error_text=failure,
                        ):
                            non_fatal_warnings.append(issue)
                        else:
                            fatal_errors.append(issue)

                    page.on("console", on_console)
                    page.on("pageerror", on_page_error)
                    page.on("requestfailed", on_request_failed)

                    page.goto(html_path.as_uri(), wait_until="load", timeout=int(self.settings.qa_smoke_timeout_seconds * 1000))
                    page.wait_for_timeout(300)

                    try:
                        canvas = page.locator("canvas")
                        if canvas.count() > 0:
                            screenshot_bytes = canvas.first.screenshot(type="png")
                        else:
                            screenshot_bytes = page.screenshot(type="png")
                        visual_metrics = capture_visual_metrics(page)
                        if visual_metrics:
                            page.wait_for_timeout(120)
                            second_metrics = capture_visual_metrics(page)
                            if second_metrics:
                                motion_delta = abs(
                                    float(second_metrics.get("frame_hash", 0.0))
                                    - float(visual_metrics.get("frame_hash", 0.0))
                                )
                                visual_metrics["motion_delta"] = round(motion_delta, 6)
                    except Exception as e:
                        non_fatal_warnings.append(f"screenshot_failed: {e}")

                    browser.close()
        except PlaywrightError as exc:
            if self.settings.playwright_required:
                return SmokeCheckResult(ok=False, reason=f"playwright_error: {exc}")
            return SmokeCheckResult(ok=True, reason=f"playwright_skipped: {exc}")
        except Exception as exc:  # pragma: no cover - runtime safeguard
            return SmokeCheckResult(ok=False, reason=f"qa_exception: {exc}")

        if fatal_errors:
            return SmokeCheckResult(
                ok=False,
                reason="runtime_console_error",
                console_errors=fatal_errors + non_fatal_warnings,
                fatal_errors=fatal_errors,
                non_fatal_warnings=non_fatal_warnings,
                screenshot_bytes=screenshot_bytes,
                visual_metrics=visual_metrics,
            )

        return SmokeCheckResult(
            ok=True,
            console_errors=non_fatal_warnings or None,
            fatal_errors=None,
            non_fatal_warnings=non_fatal_warnings or None,
            screenshot_bytes=screenshot_bytes,
            visual_metrics=visual_metrics,
        )

    def evaluate_quality_contract(
        self,
        html_content: str,
        *,
        design_spec: dict[str, Any] | None = None,
    ) -> QualityGateResult:
        return evaluate_quality_contract_gate(
            self.settings,
            html_content,
            design_spec=design_spec,
        )

    def evaluate_gameplay_gate(
        self,
        html_content: str,
        *,
        design_spec: dict[str, Any] | None = None,
        genre: str | None = None,
        genre_engine: str | None = None,
        keyword: str | None = None,
    ) -> GameplayGateResult:
        return evaluate_gameplay_gate_gate(
            self.settings,
            html_content,
            design_spec=design_spec,
            genre=genre,
            genre_engine=genre_engine,
            keyword=keyword,
        )

    def evaluate_visual_gate(
        self,
        visual_metrics: dict[str, float] | None,
        *,
        genre_engine: str | None = None,
    ) -> QualityGateResult:
        return evaluate_visual_gate_gate(
            self.settings,
            visual_metrics,
            genre_engine=genre_engine,
        )

    def evaluate_artifact_contract(
        self,
        artifact_manifest: dict[str, Any] | None,
        *,
        art_direction_contract: dict[str, Any] | None = None,
    ) -> ArtifactContractResult:
        return evaluate_artifact_contract_gate(
            self.settings,
            artifact_manifest,
            art_direction_contract=art_direction_contract,
        )
