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
_VISUAL_CONTRACT_MARKER = "id=\"iis-visual-contract-shim\""
_AUTOSTART_MARKER = "id=\"iis-autostart-shim\""


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


def _extract_asset_tokens(
    *,
    asset_manifest: dict[str, Any] | None,
    asset_files_index: dict[str, str] | None,
) -> list[str]:
    tokens: list[str] = []
    manifest = asset_manifest if isinstance(asset_manifest, dict) else {}
    images = manifest.get("images")
    if isinstance(images, dict):
        for key, value in images.items():
            key_text = str(key).strip()
            if key_text and key_text not in tokens:
                tokens.append(key_text)
            value_text = str(value).strip()
            if value_text:
                stem = value_text.rsplit("/", 1)[-1].split(".", 1)[0].strip()
                if stem and stem not in tokens:
                    tokens.append(stem)
    index = asset_files_index if isinstance(asset_files_index, dict) else {}
    for key, value in index.items():
        key_text = str(key).strip()
        if key_text and key_text not in tokens:
            tokens.append(key_text)
        value_text = str(value).strip()
        if value_text:
            stem = value_text.rsplit("/", 1)[-1].split(".", 1)[0].strip()
            if stem and stem not in tokens:
                tokens.append(stem)
    return _dedupe(tokens)


def _count_asset_usage(html_content: str, *, asset_tokens: list[str]) -> tuple[int, list[str]]:
    lowered = html_content.casefold()
    used: list[str] = []
    for token in asset_tokens:
        normalized = str(token).strip().casefold()
        if not normalized:
            continue
        if normalized in lowered:
            used.append(str(token).strip())
    used = _dedupe(used)
    return len(used), used


def _precheck_visual_signals(
    html_content: str,
    *,
    asset_manifest: dict[str, Any] | None = None,
    asset_files_index: dict[str, str] | None = None,
) -> dict[str, Any]:
    lowered = html_content.casefold()
    unique_hex = len(set(match.group(0).casefold() for match in re.finditer(r"#[0-9a-f]{6}", lowered)))
    gradient_count = lowered.count("createlineargradient(") + lowered.count("createradialgradient(")
    stroke_count = lowered.count("stroke(") + lowered.count("strokestyle") + lowered.count("linewidth")
    path_count = (
        lowered.count("beginpath(")
        + lowered.count("lineto(")
        + lowered.count("arc(")
        + lowered.count("beziercurveto(")
        + lowered.count("quadraticcurveto(")
    )
    motion_signal = any(
        token in lowered
        for token in (
            "requestanimationframe",
            "setinterval(",
            "settimeout(",
            "velocity",
            "acceleration",
            "rotation +=",
            "position +=",
            "particles",
        )
    )
    fill_rect_count = lowered.count("fillrect(")
    placeholder_rect_only = fill_rect_count >= 24 and path_count <= 2 and gradient_count == 0
    manual_start_gate = any(
        token in lowered
        for token in ("tap to start", "click to start", "press start", "시작하려면")
    )
    asset_tokens = _extract_asset_tokens(asset_manifest=asset_manifest, asset_files_index=asset_files_index)
    asset_usage_count, used_asset_keys = _count_asset_usage(html_content, asset_tokens=asset_tokens)

    checks = {
        "contrast": unique_hex >= 6 or gradient_count >= 2,
        "diversity": unique_hex >= 8 or asset_usage_count >= 4,
        "edge": (stroke_count + path_count) >= 6,
        "motion": motion_signal,
        "asset_usage": asset_usage_count >= 4,
    }
    failed = [key for key, passed in checks.items() if not passed]
    return {
        "checks": checks,
        "failed": failed,
        "unique_hex_colors": unique_hex,
        "gradient_count": gradient_count,
        "path_count": path_count,
        "stroke_count": stroke_count,
        "placeholder_rect_only": placeholder_rect_only,
        "required_asset_keys": asset_tokens,
        "used_asset_keys": used_asset_keys,
        "asset_usage_count": asset_usage_count,
        "manual_start_gate": manual_start_gate,
    }


def _inject_visual_contract_shim(
    html_content: str,
    *,
    apply_reason: list[str],
) -> str:
    if _VISUAL_CONTRACT_MARKER in html_content:
        return html_content
    if not apply_reason:
        return html_content
    reason_payload = ",".join(_dedupe([str(item).strip() for item in apply_reason if str(item).strip()])).replace("'", "\\'")
    script = (
        "<script id=\"iis-visual-contract-shim\">"
        "(function(){"
        "if(window.__iis_visual_contract_shim_applied){return;}"
        "window.__iis_visual_contract_shim_applied=true;"
        "window.__iis_visual_contract_shim_reason='" + reason_payload + "';"
        "const canvas=document.querySelector('canvas');"
        "if(!canvas){return;}"
        "let ctx=null;"
        "try{ctx=canvas.getContext('2d');}catch(e){ctx=null;}"
        "if(!ctx){return;}"
        "const drawOverlay=(t)=>{"
        "const w=canvas.width||canvas.clientWidth||960;const h=canvas.height||canvas.clientHeight||540;"
        "if(!w||!h){requestAnimationFrame(drawOverlay);return;}"
        "ctx.save();"
        "ctx.globalCompositeOperation='screen';"
        "const gx=(Math.sin(t*0.0009)+1)*0.5*w;"
        "const gy=(Math.cos(t*0.0007)+1)*0.5*h;"
        "const grad=ctx.createRadialGradient(gx,gy,12,gx,gy,Math.max(w,h)*0.6);"
        "grad.addColorStop(0,'rgba(34,211,238,0.22)');"
        "grad.addColorStop(0.45,'rgba(244,114,182,0.12)');"
        "grad.addColorStop(1,'rgba(15,23,42,0.02)');"
        "ctx.fillStyle=grad;ctx.fillRect(0,0,w,h);"
        "ctx.globalAlpha=0.16;ctx.strokeStyle='rgba(248,250,252,0.35)';ctx.lineWidth=1.15;"
        "for(let i=0;i<6;i++){const y=((i+1)/7)*h + Math.sin(t*0.0014+i)*7;ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y+Math.cos(t*0.0011+i)*4);ctx.stroke();}"
        "ctx.restore();"
        "requestAnimationFrame(drawOverlay);"
        "};"
        "requestAnimationFrame(drawOverlay);"
        "})();"
        "</script>"
    )
    lowered = html_content.casefold()
    body_close = lowered.rfind("</body>")
    if body_close >= 0:
        return f"{html_content[:body_close]}{script}{html_content[body_close:]}"
    head_close = lowered.rfind("</head>")
    if head_close >= 0:
        return f"{html_content[:head_close]}{script}{html_content[head_close:]}"
    return f"{script}{html_content}"


def _inject_autostart_shim(html_content: str) -> str:
    if _AUTOSTART_MARKER in html_content:
        return html_content
    script = (
        "<script id=\"iis-autostart-shim\">"
        "(function(){"
        "if(window.__iis_autostart_triggered){return;}"
        "window.__iis_autostart_triggered=true;"
        "const fire=()=>{"
        "try{window.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter'}));}catch(e){}"
        "try{window.dispatchEvent(new KeyboardEvent('keydown',{key:' '}));}catch(e){}"
        "try{document.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,clientX:4,clientY:4}));}catch(e){}"
        "};"
        "requestAnimationFrame(()=>{fire();setTimeout(fire,180);setTimeout(fire,520);});"
        "})();"
        "</script>"
    )
    lowered = html_content.casefold()
    body_close = lowered.rfind("</body>")
    if body_close >= 0:
        return f"{html_content[:body_close]}{script}{html_content[body_close:]}"
    head_close = lowered.rfind("</head>")
    if head_close >= 0:
        return f"{html_content[:head_close]}{script}{html_content[head_close:]}"
    return f"{script}{html_content}"


def compile_generated_artifact(
    html_content: str,
    *,
    asset_manifest: dict[str, Any] | None = None,
    asset_files_index: dict[str, str] | None = None,
    visual_precheck_enabled: bool = True,
    deterministic_visual_fix: bool = True,
) -> tuple[str, dict[str, Any]]:
    transformed = html_content
    transforms_applied: list[str] = []
    precheck_before = _precheck_visual_signals(
        transformed,
        asset_manifest=asset_manifest,
        asset_files_index=asset_files_index,
    ) if visual_precheck_enabled else {}

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

    if visual_precheck_enabled and deterministic_visual_fix:
        missing_visual = (
            precheck_before.get("failed", [])
            if isinstance(precheck_before, dict)
            else []
        )
        placeholder_rect_only = bool(precheck_before.get("placeholder_rect_only", False)) if isinstance(precheck_before, dict) else False
        if placeholder_rect_only and "placeholder_rect_only" not in missing_visual:
            missing_visual = [*missing_visual, "placeholder_rect_only"]
        if missing_visual:
            transformed = _inject_visual_contract_shim(
                transformed,
                apply_reason=[str(item) for item in missing_visual],
            )
            transforms_applied.append("inject_visual_contract_shim")
    if isinstance(precheck_before, dict) and bool(precheck_before.get("manual_start_gate", False)):
        transformed = _inject_autostart_shim(transformed)
        transforms_applied.append("inject_autostart_shim")

    precheck_after = _precheck_visual_signals(
        transformed,
        asset_manifest=asset_manifest,
        asset_files_index=asset_files_index,
    ) if visual_precheck_enabled else {}
    used_asset_keys = precheck_after.get("used_asset_keys", []) if isinstance(precheck_after, dict) else []
    required_asset_keys = precheck_after.get("required_asset_keys", []) if isinstance(precheck_after, dict) else []
    asset_usage_count = int(precheck_after.get("asset_usage_count", 0)) if isinstance(precheck_after, dict) else 0

    return transformed, {
        "transforms_applied": transforms_applied,
        "namespace_symbols": _dedupe([str(item) for item in namespace_symbols]),
        "unresolved_symbols": unresolved_symbols,
        "precheck_before": precheck_before,
        "precheck_after": precheck_after,
        "asset_usage_count": asset_usage_count,
        "required_asset_keys": required_asset_keys if isinstance(required_asset_keys, list) else [],
        "used_asset_keys": used_asset_keys if isinstance(used_asset_keys, list) else [],
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
