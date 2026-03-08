from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any


def _safe_relative_path(raw_path: str) -> Path | None:
    normalized = str(raw_path or "").strip().replace("\\", "/").lstrip("/")
    if not normalized:
        return None
    pure = PurePosixPath(normalized)
    if pure.is_absolute():
        return None
    for part in pure.parts:
        if part in {"", ".", ".."}:
            return None
    return Path(*pure.parts)


def prepare_smoke_workspace(
    *,
    tmp_dir: str,
    html_content: str,
    artifact_files: list[dict[str, Any]] | None,
    entrypoint_path: str | None,
) -> Path:
    root = Path(tmp_dir) / "artifact"
    root.mkdir(parents=True, exist_ok=True)

    written_paths: list[Path] = []
    for row in artifact_files or []:
        if not isinstance(row, dict):
            continue
        rel_path = _safe_relative_path(str(row.get("path", "")))
        content = row.get("content")
        if rel_path is None or not isinstance(content, str):
            continue
        target = root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written_paths.append(target)

    chosen_html_path: Path | None = None
    entry_rel_path = _safe_relative_path(entrypoint_path or "")
    if entry_rel_path is not None:
        normalized_entry_rel_path = (
            entry_rel_path / "index.html"
            if entry_rel_path.suffix.lower() != ".html"
            else entry_rel_path
        )
        candidate = root / normalized_entry_rel_path
        candidate.parent.mkdir(parents=True, exist_ok=True)
        chosen_html_path = candidate
    else:
        existing_html = [path for path in written_paths if path.suffix.lower() == ".html"]
        if existing_html:
            chosen_html_path = existing_html[0]
        else:
            inferred_parent = Path()
            if written_paths:
                inferred_parent = written_paths[0].parent.relative_to(root)
            chosen_html_path = root / inferred_parent / "index.html"

    chosen_html_path.parent.mkdir(parents=True, exist_ok=True)
    chosen_html_path.write_text(html_content, encoding="utf-8")
    return chosen_html_path


def is_non_fatal_runtime_issue(issue: str) -> bool:
    lowered = issue.casefold()
    non_fatal_tokens = (
        "failed to load resource",
        "err_file_not_found",
        "net::err_file_not_found",
        "screenshot_failed",
        "404 (not found)",
        "audiocontext was not allowed to start",
        "the play() request was interrupted",
        "notallowederror",
        "resizeobserver loop limit exceeded",
    )
    return any(token in lowered for token in non_fatal_tokens)


def is_non_fatal_request_failure(*, resource_type: str, url: str, error_text: str) -> bool:
    lowered_error = error_text.casefold()
    lowered_url = url.casefold()
    lowered_resource = resource_type.casefold()
    if lowered_resource in {"image", "media", "font"} and lowered_url.startswith("file://"):
        return True
    if "err_file_not_found" in lowered_error and lowered_url.startswith("file://"):
        return True
    return False


def is_representative_capture_ready(probe: dict[str, object] | None) -> bool:
    if not isinstance(probe, dict):
        return True

    if bool(probe.get("start_gate_visible", False)):
        return False

    countdown_text = str(probe.get("countdown_text", "") or "").strip().casefold()
    return countdown_text in {"", "go!"}


def capture_visual_metrics(page) -> dict[str, float] | None:
    try:
        result = page.evaluate(
            """
            () => {
              const canvases = Array.from(document.querySelectorAll("canvas"));
              if (!canvases.length) return null;
              const off = document.createElement("canvas");
              let best = null;
              let bestScore = -Infinity;
              for (let canvasIndex = 0; canvasIndex < canvases.length; canvasIndex++) {
                const canvas = canvases[canvasIndex];
                const sampleW = Math.max(1, Math.min(160, canvas.width || canvas.clientWidth || 0));
                const sampleH = Math.max(1, Math.min(90, canvas.height || canvas.clientHeight || 0));
                if (!sampleW || !sampleH) continue;
                off.width = sampleW;
                off.height = sampleH;
                const offCtx = off.getContext("2d", { willReadFrequently: true });
                if (!offCtx) continue;
                try {
                  offCtx.clearRect(0, 0, sampleW, sampleH);
                  offCtx.drawImage(canvas, 0, 0, sampleW, sampleH);
                } catch {
                  continue;
                }
                const data = offCtx.getImageData(0, 0, sampleW, sampleH).data;

                let lumSum = 0;
                let lumSqSum = 0;
                let nonDark = 0;
                let edgeAccum = 0;
                let hashAccum = 0;
                const buckets = new Set();

                for (let y = 0; y < sampleH; y++) {
                  for (let x = 0; x < sampleW; x++) {
                    const idx = (y * sampleW + x) * 4;
                    const r = data[idx];
                    const g = data[idx + 1];
                    const b = data[idx + 2];
                    const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
                    lumSum += lum;
                    lumSqSum += lum * lum;
                    if (lum > 24) nonDark += 1;
                    buckets.add(`${r >> 5}-${g >> 5}-${b >> 5}`);
                    hashAccum += lum * (1 + (x % 7) + (y % 5));

                    if (x > 0) {
                      const prevIdx = (y * sampleW + (x - 1)) * 4;
                      const pr = data[prevIdx];
                      const pg = data[prevIdx + 1];
                      const pb = data[prevIdx + 2];
                      const prevLum = 0.2126 * pr + 0.7152 * pg + 0.0722 * pb;
                      edgeAccum += Math.abs(lum - prevLum);
                    }
                    if (y > 0) {
                      const upIdx = ((y - 1) * sampleW + x) * 4;
                      const ur = data[upIdx];
                      const ug = data[upIdx + 1];
                      const ub = data[upIdx + 2];
                      const upLum = 0.2126 * ur + 0.7152 * ug + 0.0722 * ub;
                      edgeAccum += Math.abs(lum - upLum);
                    }
                  }
                }

                const pixels = sampleW * sampleH;
                const mean = lumSum / pixels;
                const variance = Math.max(0, (lumSqSum / pixels) - (mean * mean));
                const std = Math.sqrt(variance);
                const edgeEnergy = edgeAccum / (pixels * 255);
                const candidate = {
                  canvas_width: canvas.width || canvas.clientWidth || sampleW,
                  canvas_height: canvas.height || canvas.clientHeight || sampleH,
                  luminance_mean: Number(mean.toFixed(4)),
                  luminance_std: Number(std.toFixed(4)),
                  non_dark_ratio: Number((nonDark / pixels).toFixed(6)),
                  color_bucket_count: buckets.size,
                  edge_energy: Number(edgeEnergy.toFixed(6)),
                  frame_hash: Number((hashAccum / pixels).toFixed(6)),
                  sampled_canvas_index: canvasIndex,
                  sampled_canvas_count: canvases.length,
                };
                const score = (candidate.luminance_std * 1.3) + (candidate.color_bucket_count * 0.8) + (candidate.edge_energy * 420);
                if (!best || score > bestScore) {
                  best = candidate;
                  bestScore = score;
                }
              }
              return best;
            }
            """
        )
    except Exception:
        return None
    if not isinstance(result, dict):
        return None
    metrics: dict[str, float] = {}
    for key, value in result.items():
        try:
            metrics[str(key)] = float(value)
        except Exception:
            continue
    return metrics or None


def capture_runtime_probe(page) -> dict[str, object] | None:
    try:
        probe = page.evaluate(
            """
            () => {
              const isVisible = (element) => {
                if (!element) return false;
                const style = window.getComputedStyle(element);
                if (!style) return false;
                if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity || "1") <= 0.01) return false;
                const rect = element.getBoundingClientRect();
                return rect.width > 1 && rect.height > 1;
              };
              const collectVisibleText = (selector) => {
                const rows = [];
                document.querySelectorAll(selector).forEach((node) => {
                  if (!isVisible(node)) return;
                  const raw = String(node.textContent ?? "").replace(/\\s+/g, " ").trim();
                  if (!raw) return;
                  rows.push(raw);
                });
                return rows.slice(0, 10).join(" | ").slice(0, 1200);
              };
              const overlay = document.getElementById("overlay");
              const overlayText = document.getElementById("overlay-text")?.textContent ?? "";
              const countdownText = document.getElementById("countdown")?.textContent ?? "";
              const timerText = document.getElementById("timer")?.textContent ?? "";
              const scoreText = document.getElementById("score")?.textContent ?? "";
              const hpText = document.getElementById("hp")?.textContent ?? "";
              const canvas = document.querySelector("canvas");
              const root = document.documentElement;
              const visibleText = collectVisibleText("h1, h2, h3, [role='dialog'], [role='alert'], button, .overlay, .modal, .hud-overlay, #overlay, #overlay-text");
              const visibleTextLower = visibleText.toLowerCase();
              return {
                boot_ok: Boolean(window.__iis_game_boot_ok),
                overlay_visible: Boolean(overlay && overlay.classList.contains("show")),
                overlay_text: String(overlayText),
                countdown_text: String(countdownText),
                timer_text: String(timerText),
                score_text: String(scoreText),
                hp_text: String(hpText),
                visible_ui_text: visibleText,
                game_over_visible: visibleTextLower.includes("game over") || visibleTextLower.includes("최종 점수"),
                start_gate_visible:
                  visibleTextLower.includes("tap to start")
                  || visibleTextLower.includes("click to start")
                  || visibleTextLower.includes("press start")
                  || visibleTextLower.includes("시작하려면"),
                canvas_width: Number(canvas?.width || 0),
                canvas_height: Number(canvas?.height || 0),
                scroll_height: Number(root?.scrollHeight || 0),
                client_height: Number(root?.clientHeight || 0),
              };
            }
            """
        )
    except Exception:
        return None
    if not isinstance(probe, dict):
        return None
    normalized: dict[str, object] = {}
    for key, value in probe.items():
        normalized[str(key)] = value
    return normalized


def _extract_first_number(raw: object) -> float | None:
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    number_chars: list[str] = []
    has_dot = False
    has_digit = False
    for ch in text:
        if ch.isdigit():
            number_chars.append(ch)
            has_digit = True
            continue
        if ch == "." and not has_dot and has_digit:
            number_chars.append(ch)
            has_dot = True
            continue
        if has_digit:
            break
    if not number_chars:
        return None
    try:
        return float("".join(number_chars))
    except Exception:
        return None


def _to_float(raw: object) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return 0.0
        try:
            return float(text)
        except Exception:
            return 0.0
    return 0.0


def evaluate_runtime_liveness(
    *,
    before: dict[str, object] | None,
    after: dict[str, object] | None,
) -> tuple[list[str], list[str]]:
    fatal_errors: list[str] = []
    warnings: list[str] = []

    if not before or not after:
        warnings.append("runtime_probe_unavailable")
        return fatal_errors, warnings

    if not bool(after.get("boot_ok")):
        fatal_errors.append("boot_flag_missing")

    overlay_visible = bool(after.get("overlay_visible"))
    overlay_text = str(after.get("overlay_text", "") or "").casefold()

    if overlay_visible:
        if any(token in overlay_text for token in ("game over", "최종 점수", "실패", "패배")):
            warnings.append("overlay_game_over_visible")
        elif any(token in overlay_text for token in ("tap", "click", "start", "시작")):
            warnings.append("manual_start_interaction_required")
        else:
            warnings.append("startup_overlay_visible")
    if bool(after.get("start_gate_visible")):
        warnings.append("start_gate_visible")

    timer_before = _extract_first_number(before.get("timer_text"))
    timer_after = _extract_first_number(after.get("timer_text"))
    timer_static = False
    if timer_before is not None and timer_after is not None:
        timer_delta = abs(timer_after - timer_before)
        if timer_delta < 0.05:
            timer_static = True
            if bool(after.get("overlay_visible")):
                overlay_text = str(after.get("overlay_text", "") or "").casefold()
                if any(token in overlay_text for token in ("tap", "click", "start", "시작")):
                    warnings.append("timer_static_manual_start_gate")
                else:
                    warnings.append("timer_static_with_overlay")
            else:
                warnings.append("timer_not_progressing")

    hp_before = _extract_first_number(before.get("hp_text"))
    hp_after = _extract_first_number(after.get("hp_text"))
    immediate_zero_hp = False
    if hp_after is not None and hp_after <= 0:
        if hp_before is None or hp_before > 0:
            warnings.append("immediate_zero_hp_state")
            immediate_zero_hp = True
        else:
            warnings.append("zero_hp_state")

    if bool(after.get("game_over_visible")):
        if overlay_visible or timer_static or immediate_zero_hp:
            warnings.append("game_over_visible_with_runtime_signal")
        else:
            warnings.append("game_over_text_visible_without_failure_signal")
    if overlay_visible and any(token in overlay_text for token in ("game over", "최종 점수", "실패", "패배")):
        if timer_before is not None and timer_after is not None:
            elapsed_estimate = max(0.0, timer_before - timer_after)
            if elapsed_estimate <= 8.0:
                warnings.append("early_session_game_over")

    hud_text = " ".join(
        [
            str(after.get("score_text", "") or ""),
            str(after.get("timer_text", "") or ""),
            str(after.get("hp_text", "") or ""),
            str(after.get("overlay_text", "") or ""),
        ]
    ).casefold()
    hud_jargon_tokens = ("relic", "syn", "synergy", "build(", "wave", "xp ", "웨이브", "시너지(", "빌드(")
    hud_jargon_pattern = re.compile(r"\blv\.?\s*\d+\b|\bw\d+\b|\bxp\s*[:/\d]")
    if any(token in hud_text for token in hud_jargon_tokens) or bool(hud_jargon_pattern.search(hud_text)):
        warnings.append("hud_jargon_visible")

    canvas_width = _to_float(after.get("canvas_width", 0))
    canvas_height = _to_float(after.get("canvas_height", 0))

    if canvas_width < 640 or canvas_height < 360:
        fatal_errors.append("runtime_canvas_too_small")

    scroll_height = _to_float(after.get("scroll_height", 0))
    client_height = _to_float(after.get("client_height", 0))
    if client_height > 0 and scroll_height > (client_height * 1.2):
        warnings.append("runtime_layout_scroll_overflow")

    fatal_errors = list(dict.fromkeys(fatal_errors))
    warnings = [item for item in dict.fromkeys(warnings) if item not in set(fatal_errors)]
    return fatal_errors, warnings
