from __future__ import annotations

import re
from typing import Any


def coerce_message_text(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        parts: list[str] = []
        for item in raw:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()
    return str(raw)


def strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    return cleaned.strip()


def playable_artifact_missing_requirements(html_content: str) -> list[str]:
    lowered = html_content.casefold()
    missing: list[str] = []

    if "<html" not in lowered:
        missing.append("html_document")
    if "__iis_game_boot_ok" not in lowered:
        missing.append("boot_flag")
    if "iisleaderboard" not in lowered:
        missing.append("leaderboard_contract")
    if "requestanimationframe" not in lowered:
        missing.append("realtime_loop")

    has_canvas_runtime = any(
        token in lowered
        for token in (
            "<canvas",
            "createelement(\"canvas\")",
            "createelement('canvas')",
            "webglrenderer(",
            "getcontext(\"webgl",
            "getcontext('webgl",
            "new phaser.game",
        )
    )
    if not has_canvas_runtime:
        missing.append("canvas_or_render_runtime")

    return missing


def looks_like_playable_artifact(html_content: str) -> bool:
    return not playable_artifact_missing_requirements(html_content)
