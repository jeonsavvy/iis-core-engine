from __future__ import annotations

import re
from typing import Any

_THREE_NAMESPACE_SYMBOL_RE = re.compile(r"\bTHREE\.([A-Za-z_$][A-Za-z0-9_$]*)")
_IMPORT_NAMESPACE_RE = re.compile(r"\bimport\s+\*\s+as\s+([A-Za-z_$][A-Za-z0-9_$]*)\s+from\b")
_IMPORT_DEFAULT_RE = re.compile(r"\bimport\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*(?:,|\s+from)")
_IMPORT_NAMED_RE = re.compile(r"\bimport\s+{([^}]*)}\s+from\b")
_DECLARATION_RE = re.compile(r"\b(?:const|let|var|function|class)\s+([A-Za-z_$][A-Za-z0-9_$]*)")
_NEW_CONSTRUCTOR_RE = re.compile(r"\bnew\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(")

_CORE_THREE_NAMESPACE_LOADERS = {
    "AudioLoader",
    "BufferGeometryLoader",
    "CubeTextureLoader",
    "FileLoader",
    "ImageBitmapLoader",
    "ImageLoader",
    "Loader",
    "LoaderUtils",
    "MaterialLoader",
    "ObjectLoader",
    "TextureLoader",
}

_GLOBAL_CONSTRUCTORS_ALLOWLIST = {
    "Array",
    "ArrayBuffer",
    "Audio",
    "Blob",
    "Date",
    "Error",
    "Event",
    "Float32Array",
    "Image",
    "Map",
    "Object",
    "Promise",
    "RegExp",
    "Set",
    "URL",
    "Uint8Array",
}


def _dedupe(rows: list[str]) -> list[str]:
    deduped: list[str] = []
    for row in rows:
        if row and row not in deduped:
            deduped.append(row)
    return deduped


def _extract_named_import_alias(token: str) -> str:
    normalized = token.strip()
    if not normalized:
        return ""
    if " as " in normalized:
        alias = normalized.split(" as ", 1)[1].strip()
        return alias
    return normalized


def _collect_declared_identifiers(source: str) -> set[str]:
    identifiers: set[str] = set()
    for match in _IMPORT_NAMESPACE_RE.findall(source):
        identifiers.add(match)
    for match in _IMPORT_DEFAULT_RE.findall(source):
        if match != "from":
            identifiers.add(match)
    for named in _IMPORT_NAMED_RE.findall(source):
        parts = [part.strip() for part in named.split(",") if part.strip()]
        for part in parts:
            alias = _extract_named_import_alias(part)
            if alias:
                identifiers.add(alias)
    for match in _DECLARATION_RE.findall(source):
        identifiers.add(match)
    return identifiers


def _detect_three_namespace_addon_usage(source: str) -> list[str]:
    failures: list[str] = []
    for symbol in _THREE_NAMESPACE_SYMBOL_RE.findall(source):
        if symbol == "BufferGeometryUtils":
            failures.append("unsupported_three_buffergeometryutils")
            failures.append("unsupported_three_namespace_addon_utils")
            continue
        if symbol.endswith("Controls"):
            failures.append("unsupported_three_namespace_addon_controls")
            continue
        if symbol.endswith("Pass") or symbol.endswith("Composer"):
            failures.append("unsupported_three_namespace_addon_postfx")
            continue
        if symbol.endswith("Utils"):
            failures.append("unsupported_three_namespace_addon_utils")
            continue
        if symbol.endswith("Loader") and symbol not in _CORE_THREE_NAMESPACE_LOADERS:
            failures.append("unsupported_three_namespace_addon_loader")
    return _dedupe(failures)


def _detect_unresolved_addon_constructors(source: str) -> list[str]:
    declared = _collect_declared_identifiers(source)
    failures: list[str] = []
    for symbol in _NEW_CONSTRUCTOR_RE.findall(source):
        if symbol in declared or symbol in _GLOBAL_CONSTRUCTORS_ALLOWLIST:
            continue
        if symbol.endswith("Controls"):
            failures.append("unresolved_addon_constructor_controls")
            continue
        if symbol.endswith("Pass") or symbol.endswith("Composer"):
            failures.append("unresolved_addon_constructor_postfx")
            continue
        if symbol.endswith("Utils"):
            failures.append("unresolved_addon_constructor_utils")
            continue
        if symbol.endswith("Loader"):
            failures.append("unresolved_addon_constructor_loader")
    return _dedupe(failures)


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

    missing.extend(_detect_three_namespace_addon_usage(html_content))
    missing.extend(_detect_unresolved_addon_constructors(html_content))

    return _dedupe(missing)


def looks_like_playable_artifact(html_content: str) -> bool:
    return not playable_artifact_missing_requirements(html_content)
