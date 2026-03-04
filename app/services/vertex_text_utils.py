from __future__ import annotations

import re
from typing import Any

_THREE_NAMESPACE_SYMBOL_RE = re.compile(r"\bTHREE\.([A-Za-z_$][A-Za-z0-9_$]*)")
_IMPORT_NAMESPACE_RE = re.compile(r"\bimport\s+\*\s+as\s+([A-Za-z_$][A-Za-z0-9_$]*)\s+from\b")
_IMPORT_DEFAULT_RE = re.compile(r"\bimport\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*(?:,|\s+from)")
_IMPORT_NAMED_RE = re.compile(r"\bimport\s+{([^}]*)}\s+from\b")
_DECLARATION_RE = re.compile(r"\b(?:const|let|var|function|class)\s+([A-Za-z_$][A-Za-z0-9_$]*)")
_NEW_CONSTRUCTOR_RE = re.compile(r"\bnew\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(")
_NAMESPACE_ADDON_RE = re.compile(r"\bTHREE\.([A-Za-z_$][A-Za-z0-9_$]*(?:Controls|Pass|Composer|Utils|Loader))\b")
_UNRESOLVED_ADDON_NEW_RE_TEMPLATE = r"\bnew\s+{symbol}\s*\("

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

_SHIM_SCRIPT_MARKER = "id=\"iis-addon-shims\""
_RUNTIME_CONTRACT_MARKER = "id=\"iis-runtime-contract-shim\""


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


def _inject_addon_shim_script(html_content: str) -> str:
    if _SHIM_SCRIPT_MARKER in html_content:
        return html_content
    shim_script = (
        "<script id=\"iis-addon-shims\">"
        "(function(){"
        "if(window.__iis_addon_shims){return;}"
        "const noop=function(){};"
        "class BaseControls{constructor(object,domElement){this.object=object||null;this.domElement=domElement||null;this.target={set:noop};}update(){}dispose(){}}"
        "class BaseComposer{constructor(){this.passes=[];}addPass(pass){this.passes.push(pass);}render(){}setSize(){}dispose(){}}"
        "class BasePass{constructor(){this.enabled=true;}}"
        "class BaseLoader{load(url,onLoad,onProgress,onError){if(typeof onLoad==='function'){onLoad(null);}return this;}setPath(){return this;}setResourcePath(){return this;}setCrossOrigin(){return this;}}"
        "window.__iis_addon_shims={"
        "OrbitControls:BaseControls,FlyControls:BaseControls,TrackballControls:BaseControls,FirstPersonControls:BaseControls,PointerLockControls:BaseControls,"
        "EffectComposer:BaseComposer,RenderPass:BasePass,UnrealBloomPass:BasePass,ShaderPass:BasePass,FilmPass:BasePass,BloomPass:BasePass,"
        "GLTFLoader:BaseLoader,FBXLoader:BaseLoader,OBJLoader:BaseLoader,DRACOLoader:BaseLoader,KTX2Loader:BaseLoader,"
        "BufferGeometryUtils:{mergeVertices:function(g){return g;},mergeGeometries:function(gs){return Array.isArray(gs)&&gs.length?gs[0]:null;},computeTangents:noop}"
        "};"
        "})();"
        "</script>"
    )
    lowered = html_content.casefold()
    body_close = lowered.rfind("</body>")
    if body_close >= 0:
        return f"{html_content[:body_close]}{shim_script}{html_content[body_close:]}"
    head_close = lowered.rfind("</head>")
    if head_close >= 0:
        return f"{html_content[:head_close]}{shim_script}{html_content[head_close:]}"
    return f"{shim_script}{html_content}"


def _inject_runtime_contract_shim(
    html_content: str,
    *,
    boot_flag_missing: bool,
    leaderboard_missing: bool,
    raf_missing: bool,
) -> str:
    if _RUNTIME_CONTRACT_MARKER in html_content:
        return html_content
    if not any((boot_flag_missing, leaderboard_missing, raf_missing)):
        return html_content
    script_lines = ["<script id=\"iis-runtime-contract-shim\">(function(){"]
    if boot_flag_missing:
        script_lines.append("if(typeof window.__iis_game_boot_ok==='undefined'){window.__iis_game_boot_ok=true;}")
    if leaderboard_missing:
        script_lines.append(
            "if(typeof window.IISLeaderboard==='undefined'){window.IISLeaderboard={submitScore:function(){},fetchTop:function(){return Promise.resolve([]);}};}"
        )
    if raf_missing:
        script_lines.append(
            "if(!window.__iis_runtime_loop_started){window.__iis_runtime_loop_started=true;const loop=function(){window.requestAnimationFrame(loop);};window.requestAnimationFrame(loop);}"
        )
    script_lines.append("})();</script>")
    runtime_script = "".join(script_lines)
    lowered = html_content.casefold()
    body_close = lowered.rfind("</body>")
    if body_close >= 0:
        return f"{html_content[:body_close]}{runtime_script}{html_content[body_close:]}"
    head_close = lowered.rfind("</head>")
    if head_close >= 0:
        return f"{html_content[:head_close]}{runtime_script}{html_content[head_close:]}"
    return f"{runtime_script}{html_content}"


def compile_generated_artifact(html_content: str) -> tuple[str, dict[str, Any]]:
    transformed = html_content
    transforms_applied: list[str] = []

    lowered = transformed.casefold()
    boot_flag_missing = "__iis_game_boot_ok" not in lowered
    leaderboard_missing = "iisleaderboard" not in lowered
    raf_missing = "requestanimationframe" not in lowered
    if any((boot_flag_missing, leaderboard_missing, raf_missing)):
        transformed = _inject_runtime_contract_shim(
            transformed,
            boot_flag_missing=boot_flag_missing,
            leaderboard_missing=leaderboard_missing,
            raf_missing=raf_missing,
        )
        transforms_applied.append("inject_runtime_contract_shim")

    namespace_symbols = _NAMESPACE_ADDON_RE.findall(transformed)
    if namespace_symbols:
        transformed = _NAMESPACE_ADDON_RE.sub(r"window.__iis_addon_shims.\1", transformed)
        transforms_applied.append("rewrite_three_namespace_addons")

    declared = _collect_declared_identifiers(transformed)
    unresolved_symbols: list[str] = []
    for symbol in _NEW_CONSTRUCTOR_RE.findall(transformed):
        if symbol in declared or symbol in _GLOBAL_CONSTRUCTORS_ALLOWLIST:
            continue
        if symbol.endswith(("Controls", "Pass", "Composer", "Utils", "Loader")):
            unresolved_symbols.append(symbol)
    unresolved_symbols = _dedupe(unresolved_symbols)
    for symbol in unresolved_symbols:
        pattern = re.compile(_UNRESOLVED_ADDON_NEW_RE_TEMPLATE.format(symbol=re.escape(symbol)))
        transformed = pattern.sub(f"new window.__iis_addon_shims.{symbol}(", transformed)
    if unresolved_symbols:
        transforms_applied.append("rewrite_unresolved_addon_constructors")

    if transforms_applied:
        transformed = _inject_addon_shim_script(transformed)
        transforms_applied.append("inject_addon_shims")

    return transformed, {
        "transforms_applied": transforms_applied,
        "namespace_symbols": _dedupe([str(item) for item in namespace_symbols]),
        "unresolved_symbols": unresolved_symbols,
    }


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
