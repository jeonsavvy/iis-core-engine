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
_PRESENTATION_CONTRACT_MARKER = "id=\"iis-presentation-contract-shim\""
_RESTART_CONTRACT_MARKER = "id=\"iis-restart-contract-shim\""
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


def build_presentation_contract_script(
    *,
    script_id: str,
    reason: str,
    force_override: bool,
) -> str:
    assignment_open = "" if force_override else "if(typeof window.__iisPreparePresentationCapture!=='function'){"
    assignment_close = "" if force_override else "}"
    return (
        f"<script id=\"{script_id}\">(function(){{"
        "if(typeof window.__iisPresentationReady==='undefined'){window.__iisPresentationReady=false;}"
        "const hideSelectors=['#title-screen','#start-screen','#start-overlay','#game-over','#game-over-screen','#overlay','#overlay-text','#countdown','[data-iis-title-screen]','[data-iis-start-screen]','[data-iis-start-button]','[data-iis-restart-button]','[data-iis-countdown]','[data-iis-overlay]','[data-iis-game-over]','[data-screen=\"title\"]','[data-screen=\"start\"]','[data-screen=\"game-over\"]','[data-role=\"countdown\"]','.title-screen','.start-screen','.start-overlay','.game-over','.game-over-screen','.countdown','.countdown-overlay'];"
        "const buttonSelectors='button,[role=\"button\"],input[type=\"button\"],input[type=\"submit\"],[data-iis-start-button],[data-iis-restart-button],[data-action]';"
        "const startTokens=['start','play','begin','launch','continue','resume','tap to start','click to start','press start','start run','start game','play now','시작','플레이','계속'];"
        "const restartTokens=['restart','retry','again','respawn','new run','reset','다시','재시작','재도전'];"
        "const visible=(node)=>{if(!node||!(node instanceof HTMLElement)){return false;}const style=window.getComputedStyle(node);if(!style){return false;}if(style.display==='none'||style.visibility==='hidden'||Number(style.opacity||'1')<=0.01){return false;}const rect=node.getBoundingClientRect();return rect.width>1&&rect.height>1;};"
        "const readText=(node)=>{if(!node){return '';}const value=('value' in node&&typeof node.value==='string')?node.value:'';const label=(typeof node.getAttribute==='function'&&typeof node.getAttribute('aria-label')==='string')?node.getAttribute('aria-label'):'';return String(node.textContent||value||label||'').replace(/\\s+/g,' ').trim().toLowerCase();};"
        "const hideNode=(node)=>{if(node&&node instanceof HTMLElement){node.dataset.iisPresentationHidden='1';node.style.display='none';node.style.visibility='hidden';node.style.opacity='0';node.style.pointerEvents='none';}};"
        "const hideKnownScreens=()=>{hideSelectors.forEach((selector)=>{document.querySelectorAll(selector).forEach((node)=>hideNode(node));});};"
        "const clearCountdown=()=>{['#countdown','[data-iis-countdown]','[data-role=\"countdown\"]','.countdown','.countdown-overlay'].forEach((selector)=>{document.querySelectorAll(selector).forEach((node)=>{if(node&&node instanceof HTMLElement){node.textContent='';hideNode(node);}});});};"
        "const clickMatchingButtons=(tokens)=>{Array.from(document.querySelectorAll(buttonSelectors)).forEach((node)=>{if(!(node instanceof HTMLElement)||!visible(node)){return;}const lowered=readText(node);if(!tokens.some((token)=>lowered.includes(token))){return;}try{node.click();}catch(_){try{node.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));}catch(__){}}});};"
        "const hidePromptLikeText=()=>{Array.from(document.querySelectorAll('h1,h2,h3,dialog,[role=\"dialog\"],section,article,div,p,span')).forEach((node)=>{if(!(node instanceof HTMLElement)||!visible(node)){return;}const lowered=readText(node);if(!lowered){return;}if(startTokens.some((token)=>lowered.includes(token))||restartTokens.some((token)=>lowered.includes(token))||lowered.includes('game over')||lowered.includes('tap anywhere')||lowered.includes('click anywhere')){hideNode(node.closest('dialog,[role=\"dialog\"],section,article,div')||node);}});};"
        "const synthInput=()=>{try{window.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',bubbles:true}));}catch(_){ }try{window.dispatchEvent(new KeyboardEvent('keydown',{key:' ',code:'Space',bubbles:true}));}catch(_){ }try{const centerX=Math.max(4,Math.floor(window.innerWidth/2));const centerY=Math.max(4,Math.floor(window.innerHeight/2));const target=document.elementFromPoint(centerX,centerY)||document.body;target.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,clientX:centerX,clientY:centerY}));target.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:centerX,clientY:centerY}));}catch(_){ }};"
        "const settle=()=>{hideKnownScreens();clearCountdown();hidePromptLikeText();clickMatchingButtons(startTokens);clickMatchingButtons(restartTokens);};"
        "window.__iisRunPresentationCleanup=settle;"
        f"{assignment_open}"
        "window.__iisPreparePresentationCapture=function(){"
        "window.__iisPresentationReady=false;"
        "settle();"
        "synthInput();"
        "requestAnimationFrame(()=>{"
        "settle();"
        "synthInput();"
        "setTimeout(()=>{"
        "settle();"
        "window.__iisPresentationReady=true;"
        "},220);"
        "});"
        f"return {{delay_ms:320,reason:'{reason}'}};"
        "};"
        f"{assignment_close}"
        "})();</script>"
    )


def _inject_presentation_contract_shim(
    html_content: str,
    *,
    presentation_ready_missing: bool,
    presentation_hook_missing: bool,
) -> str:
    if _PRESENTATION_CONTRACT_MARKER in html_content:
        return html_content
    if not (presentation_ready_missing or presentation_hook_missing):
        return html_content

    presentation_script = build_presentation_contract_script(
        script_id="iis-presentation-contract-shim",
        reason="auto_presentation_contract_shim",
        force_override=False,
    )
    lowered = html_content.casefold()
    body_close = lowered.rfind("</body>")
    if body_close >= 0:
        return f"{html_content[:body_close]}{presentation_script}{html_content[body_close:]}"
    head_close = lowered.rfind("</head>")
    if head_close >= 0:
        return f"{html_content[:head_close]}{presentation_script}{html_content[head_close:]}"
    return f"{presentation_script}{html_content}"


def _inject_restart_contract_shim(html_content: str) -> str:
    if _RESTART_CONTRACT_MARKER in html_content:
        return html_content
    script = (
        "<script id=\"iis-restart-contract-shim\">"
        "(function(){"
        "if(window.__iis_restart_contract_installed){return;}"
        "window.__iis_restart_contract_installed=true;"
        "const normalize=()=>{"
        "try{if(typeof gameState!=='undefined'&&gameState&&typeof gameState==='object'){"
        "if(typeof gameState.maxHp==='number'&&typeof gameState.hp==='number'&&gameState.hp<=0){gameState.hp=Math.max(1,gameState.maxHp);}"
        "if(typeof gameState.max_hp==='number'&&typeof gameState.hp==='number'&&gameState.hp<=0){gameState.hp=Math.max(1,gameState.max_hp);}"
        "if(typeof gameState.wave==='number'&&gameState.wave<1){gameState.wave=1;}"
        "}}catch(_){}"
        "try{if(typeof state!=='undefined'&&state&&typeof state==='object'){"
        "if(typeof state.shield==='number'&&state.shield<=0){state.shield=100;}"
        "if(typeof state.hp==='number'&&state.hp<=0&&typeof state.maxHp==='number'){state.hp=Math.max(1,state.maxHp);}"
        "if(typeof state.wave==='number'&&state.wave<1){state.wave=1;}"
        "}}catch(_){}"
        "};"
        "const wrap=(name)=>{"
        "try{const fn=globalThis[name];if(typeof fn!=='function'||fn.__iis_wrapped_restart){return;}"
        "const wrapped=function(){const result=fn.apply(this,arguments);setTimeout(normalize,0);setTimeout(normalize,180);return result;};"
        "wrapped.__iis_wrapped_restart=true;globalThis[name]=wrapped;}catch(_){}};"
        "['resetArena','resetFight','restartRun','restartGame','beginRun'].forEach(wrap);"
        "window.addEventListener('keydown',function(event){if(event&&((event.key==='r')||(event.key==='R')||(event.code==='KeyR'))){setTimeout(normalize,0);setTimeout(normalize,180);}},true);"
        "['#restart-button','#start-button'].forEach(function(selector){const node=document.querySelector(selector);if(node&&node instanceof HTMLElement){node.addEventListener('click',function(){setTimeout(normalize,0);setTimeout(normalize,180);},true);node.addEventListener('pointerdown',function(){setTimeout(normalize,0);setTimeout(normalize,180);},true);}});"
        "setTimeout(normalize,0);setTimeout(normalize,220);"
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
        "const palette=['#22d3ee','#f472b6','#facc15','#60a5fa','#a78bfa','#34d399','#fb7185','#f8fafc','#0f172a'];"
        "const particles=Array.from({length:28},(_,i)=>({x:(i*37)%1,y:(i*53)%1,s:0.5+((i*17)%11)/10,v:0.18+((i*13)%7)/10}));"
        "const drawOverlay=(t)=>{"
        "const w=canvas.width||canvas.clientWidth||960;const h=canvas.height||canvas.clientHeight||540;"
        "if(!w||!h){requestAnimationFrame(drawOverlay);return;}"
        "const tt=t*0.001;"
        "ctx.save();"
        "ctx.globalCompositeOperation='screen';"
        "const base=ctx.createLinearGradient(0,0,w,h);"
        "base.addColorStop(0,'rgba(14,25,48,0.20)');"
        "base.addColorStop(0.35,'rgba(15,118,110,0.10)');"
        "base.addColorStop(0.7,'rgba(124,58,237,0.10)');"
        "base.addColorStop(1,'rgba(248,113,113,0.08)');"
        "ctx.fillStyle=base;ctx.fillRect(0,0,w,h);"
        "const gx=(Math.sin(tt*1.1)+1)*0.5*w;"
        "const gy=(Math.cos(tt*0.9)+1)*0.45*h;"
        "const glow=ctx.createRadialGradient(gx,gy,8,gx,gy,Math.max(w,h)*0.55);"
        "glow.addColorStop(0,'rgba(34,211,238,0.30)');"
        "glow.addColorStop(0.4,'rgba(244,114,182,0.16)');"
        "glow.addColorStop(0.75,'rgba(250,204,21,0.10)');"
        "glow.addColorStop(1,'rgba(15,23,42,0.02)');"
        "ctx.fillStyle=glow;ctx.fillRect(0,0,w,h);"
        "ctx.globalAlpha=0.18;ctx.lineWidth=1.1;"
        "for(let i=0;i<10;i++){"
        "const x=((i/10)*w + (tt*26*(i%3+1)))%w;"
        "ctx.strokeStyle=i%2?palette[0]:palette[5];"
        "ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x+Math.sin(tt+i)*14,h);ctx.stroke();"
        "}"
        "for(let i=0;i<8;i++){"
        "const y=((i/8)*h + (tt*18*(i%2?1:-1)))%h;"
        "ctx.strokeStyle=i%2?palette[1]:palette[3];"
        "ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y+Math.cos(tt+i*0.7)*10);ctx.stroke();"
        "}"
        "ctx.globalAlpha=0.24;"
        "ctx.fillStyle='rgba(15,23,42,0.42)';"
        "ctx.beginPath();ctx.moveTo(0,h*0.82);ctx.lineTo(w*0.2,h*(0.72+Math.sin(tt*0.7)*0.02));ctx.lineTo(w*0.44,h*(0.78+Math.cos(tt*0.6)*0.02));ctx.lineTo(w*0.66,h*(0.70+Math.sin(tt*0.9)*0.02));ctx.lineTo(w,h*0.80);ctx.lineTo(w,h);ctx.lineTo(0,h);ctx.closePath();ctx.fill();"
        "ctx.globalAlpha=0.26;ctx.strokeStyle='rgba(248,250,252,0.42)';ctx.lineWidth=1.4;"
        "ctx.beginPath();ctx.moveTo(0,h*0.82);ctx.lineTo(w*0.2,h*(0.72+Math.sin(tt*0.7)*0.02));ctx.lineTo(w*0.44,h*(0.78+Math.cos(tt*0.6)*0.02));ctx.lineTo(w*0.66,h*(0.70+Math.sin(tt*0.9)*0.02));ctx.lineTo(w,h*0.80);ctx.stroke();"
        "ctx.globalAlpha=0.34;"
        "for(let i=0;i<particles.length;i++){"
        "const p=particles[i];"
        "p.y += (0.0008+p.v*0.0007);"
        "p.x += Math.sin(tt*0.7+i)*0.0006;"
        "if(p.y>1.05){p.y=-0.05;p.x=(Math.sin(tt+i*13)+1)*0.5;}"
        "const px=(p.x%1)*w;const py=(p.y%1)*h;const r=1.2+p.s*1.8;"
        "ctx.fillStyle=i%3===0?palette[2]:(i%3===1?palette[7]:palette[4]);"
        "ctx.beginPath();ctx.arc(px,py,r,0,Math.PI*2);ctx.fill();"
        "}"
        "ctx.globalAlpha=0.2;ctx.lineWidth=2;"
        "ctx.strokeStyle='rgba(96,165,250,0.42)';"
        "ctx.beginPath();"
        "for(let i=0;i<=24;i++){const x=(i/24)*w;const y=h*(0.58+Math.sin(tt*1.6+i*0.45)*0.05);if(i===0){ctx.moveTo(x,y);}else{ctx.lineTo(x,y);}}"
        "ctx.stroke();"
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
    presentation_ready_missing = "__iispresentationready" not in lowered
    presentation_hook_missing = "__iispreparepresentationcapture" not in lowered
    raf_missing = "requestanimationframe" not in lowered
    if any((boot_flag_missing, leaderboard_missing, raf_missing)):
        transformed = _inject_runtime_contract_shim(
            transformed,
            boot_flag_missing=boot_flag_missing,
            leaderboard_missing=leaderboard_missing,
            raf_missing=raf_missing,
        )
        transforms_applied.append("inject_runtime_contract_shim")

    if presentation_ready_missing or presentation_hook_missing:
        transformed = _inject_presentation_contract_shim(
            transformed,
            presentation_ready_missing=presentation_ready_missing,
            presentation_hook_missing=presentation_hook_missing,
        )
        transforms_applied.append("inject_presentation_contract_shim")

    restart_signal = any(token in lowered for token in ("restart", "reset", "game over", "gameover", "hp", "shield", "wave"))
    if restart_signal:
        transformed = _inject_restart_contract_shim(transformed)
        transforms_applied.append("inject_restart_contract_shim")

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
    if "__iispresentationready" not in lowered:
        missing.append("presentation_ready_flag")
    if "__iispreparepresentationcapture" not in lowered:
        missing.append("presentation_capture_hook")
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
