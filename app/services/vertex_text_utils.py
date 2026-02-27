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


def looks_like_playable_artifact(html_content: str) -> bool:
    lowered = html_content.casefold()
    return all(
        token in lowered
        for token in (
            "<html",
            "window.__iis_game_boot_ok",
            "window.iisleaderboard",
            "requestanimationframe",
            "<canvas",
        )
    )
