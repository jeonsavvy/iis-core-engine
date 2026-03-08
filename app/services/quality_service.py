from __future__ import annotations

import math
from tempfile import TemporaryDirectory
from typing import Any, cast

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from app.core.config import Settings
from app.services.quality_gates import (
    evaluate_artifact_contract as evaluate_artifact_contract_gate,
    evaluate_gameplay_gate as evaluate_gameplay_gate_gate,
    evaluate_intent_gate as evaluate_intent_gate_gate,
    evaluate_quality_contract as evaluate_quality_contract_gate,
    evaluate_visual_gate as evaluate_visual_gate_gate,
)
from app.services.quality_smoke import (
    capture_runtime_probe,
    capture_visual_metrics,
    evaluate_runtime_liveness,
    is_representative_capture_ready,
    is_non_fatal_request_failure,
    is_non_fatal_runtime_issue,
    prepare_smoke_workspace,
)
from app.services.quality_types import ArtifactContractResult, GameplayGateResult, QualityGateResult, SmokeCheckResult


def _safe_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            numeric = float(text)
        except ValueError:
            return None
    else:
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _aggregate_visual_metrics(samples: list[dict[str, float]]) -> dict[str, object] | None:
    if not samples:
        return None
    first = samples[0]
    aggregated: dict[str, object] = dict(first)
    for key in ("luminance_std", "non_dark_ratio", "color_bucket_count", "edge_energy", "frame_hash"):
        values: list[float] = []
        for row in samples:
            numeric = _safe_float(row.get(key))
            if numeric is not None:
                values.append(round(numeric, 6))
        if values:
            aggregated[f"{key}_samples"] = values
            aggregated[key] = round(sum(values) / len(values), 6)

    frame_hash_values = [
        value
        for value in [
            _safe_float(row.get("frame_hash"))
            for row in samples
        ]
        if value is not None
    ]
    motion_samples = [
        round(abs(frame_hash_values[index + 1] - frame_hash_values[index]), 6)
        for index in range(len(frame_hash_values) - 1)
    ]
    if motion_samples:
        sorted_motion = sorted(motion_samples)
        p90_index = max(0, min(len(sorted_motion) - 1, int(round((len(sorted_motion) - 1) * 0.9))))
        aggregated["motion_delta_samples"] = motion_samples
        aggregated["motion_delta"] = round(max(motion_samples), 6)
        aggregated["motion_delta_p90"] = round(sorted_motion[p90_index], 6)
    aggregated["frame_probe_count"] = len(samples)
    return aggregated


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
        visual_metrics: dict[str, object] | None = None
        runtime_probe_summary: dict[str, object] | None = None

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
                    page.wait_for_timeout(250)
                    probe_before = capture_runtime_probe(page)
                    input_sequence = ["ArrowUp", "ArrowLeft", "ArrowRight", "Space", "KeyR"]
                    executed_inputs: list[str] = []
                    input_failures: list[str] = []
                    for key in input_sequence:
                        try:
                            page.keyboard.press(key)
                            executed_inputs.append(key)
                        except Exception:
                            input_failures.append(key)
                        page.wait_for_timeout(180)
                    if input_failures:
                        non_fatal_warnings.append("input_probe_keypress_failed")
                    page.wait_for_timeout(1200)
                    probe_mid = capture_runtime_probe(page)
                    runtime_fatal, runtime_warnings = evaluate_runtime_liveness(before=probe_before, after=probe_mid)
                    fatal_errors.extend(runtime_fatal)
                    non_fatal_warnings.extend(runtime_warnings)

                    page.wait_for_timeout(2200)
                    probe_after = capture_runtime_probe(page)
                    runtime_fatal_late, runtime_warnings_late = evaluate_runtime_liveness(
                        before=probe_mid or probe_before,
                        after=probe_after,
                    )
                    fatal_errors.extend(runtime_fatal_late)
                    non_fatal_warnings.extend(runtime_warnings_late)
                    timer_before = str((probe_before or {}).get("timer_text", "")).strip()
                    timer_after = str((probe_after or {}).get("timer_text", "")).strip()
                    score_before = str((probe_before or {}).get("score_text", "")).strip()
                    score_after = str((probe_after or {}).get("score_text", "")).strip()
                    hp_before = str((probe_before or {}).get("hp_text", "")).strip()
                    hp_after = str((probe_after or {}).get("hp_text", "")).strip()
                    overlay_before = bool((probe_before or {}).get("overlay_visible", False))
                    overlay_after = bool((probe_after or {}).get("overlay_visible", False))
                    start_gate_active = any(
                        bool((probe or {}).get("start_gate_visible", False))
                        for probe in (probe_before, probe_mid, probe_after)
                    )
                    countdown_active = any(
                        str((probe or {}).get("countdown_text", "")).strip()
                        not in {"", "GO!"}
                        for probe in (probe_before, probe_mid, probe_after)
                    )
                    input_reaction_ok = any(
                        (
                            timer_before != timer_after,
                            score_before != score_after,
                            hp_before != hp_after,
                            overlay_before != overlay_after,
                        )
                    )
                    if not input_reaction_ok and not start_gate_active and not countdown_active:
                        non_fatal_warnings.append("input_reaction_missing")
                    runtime_probe_summary = {
                        "probe_before": probe_before or {},
                        "probe_mid": probe_mid or {},
                        "probe_after": probe_after or {},
                        "executed_inputs": executed_inputs,
                        "input_failures": input_failures,
                        "input_reaction_ok": input_reaction_ok,
                        "start_gate_active": start_gate_active,
                        "countdown_active": countdown_active,
                    }

                    try:
                        capture_probe = probe_after or probe_mid or probe_before
                        settle_attempts = 0
                        while settle_attempts < 10 and not is_representative_capture_ready(capture_probe):
                            page.wait_for_timeout(400)
                            capture_probe = capture_runtime_probe(page)
                            settle_attempts += 1

                        canvas = page.locator("canvas")
                        if canvas.count() > 0:
                            screenshot_bytes = canvas.first.screenshot(type="png")
                        else:
                            screenshot_bytes = page.screenshot(type="png")
                        frame_samples: list[dict[str, float]] = []
                        for attempt in range(4):
                            captured = capture_visual_metrics(page)
                            if captured:
                                frame_samples.append(captured)
                            if attempt < 3:
                                page.wait_for_timeout(140)
                        visual_metrics = _aggregate_visual_metrics(frame_samples)
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
                runtime_probe_summary=runtime_probe_summary,
            )

        return SmokeCheckResult(
            ok=True,
            console_errors=non_fatal_warnings or None,
            fatal_errors=None,
            non_fatal_warnings=non_fatal_warnings or None,
            screenshot_bytes=screenshot_bytes,
            visual_metrics=visual_metrics,
            runtime_probe_summary=runtime_probe_summary,
        )

    def evaluate_quality_contract(
        self,
        html_content: str,
        *,
        design_spec: dict[str, Any] | None = None,
        genre: str | None = None,
        genre_engine: str | None = None,
        runtime_engine_mode: str | None = None,
        keyword: str | None = None,
        intent_contract: dict[str, Any] | None = None,
        synapse_contract: dict[str, Any] | None = None,
    ) -> QualityGateResult:
        return cast(
            QualityGateResult,
            evaluate_quality_contract_gate(
                self.settings,
                html_content,
                design_spec=design_spec,
                genre=genre,
                genre_engine=genre_engine,
                runtime_engine_mode=runtime_engine_mode,
                keyword=keyword,
                intent_contract=intent_contract,
                synapse_contract=synapse_contract,
            ),
        )

    def evaluate_gameplay_gate(
        self,
        html_content: str,
        *,
        design_spec: dict[str, Any] | None = None,
        genre: str | None = None,
        genre_engine: str | None = None,
        keyword: str | None = None,
        intent_contract: dict[str, Any] | None = None,
        synapse_contract: dict[str, Any] | None = None,
    ) -> GameplayGateResult:
        return cast(
            GameplayGateResult,
            evaluate_gameplay_gate_gate(
                self.settings,
                html_content,
                design_spec=design_spec,
                genre=genre,
                genre_engine=genre_engine,
                keyword=keyword,
                intent_contract=intent_contract,
                synapse_contract=synapse_contract,
            ),
        )

    def evaluate_visual_gate(
        self,
        visual_metrics: dict[str, Any] | None,
        *,
        genre_engine: str | None = None,
        runtime_engine_mode: str | None = None,
    ) -> QualityGateResult:
        return cast(
            QualityGateResult,
            evaluate_visual_gate_gate(
                self.settings,
                visual_metrics,
                genre_engine=genre_engine,
                runtime_engine_mode=runtime_engine_mode,
            ),
        )

    def evaluate_artifact_contract(
        self,
        artifact_manifest: dict[str, Any] | None,
        *,
        art_direction_contract: dict[str, Any] | None = None,
    ) -> ArtifactContractResult:
        return cast(
            ArtifactContractResult,
            evaluate_artifact_contract_gate(
                self.settings,
                artifact_manifest,
                art_direction_contract=art_direction_contract,
            ),
        )

    def evaluate_intent_gate(
        self,
        html_content: str,
        *,
        intent_contract: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            evaluate_intent_gate_gate(
                html_content,
                intent_contract=intent_contract,
            ),
        )
