from __future__ import annotations


def _normalize_escaped_braces(js_block: str) -> str:
    return js_block.replace("{{", "{").replace("}}", "}")
