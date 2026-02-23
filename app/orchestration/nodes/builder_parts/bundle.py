from __future__ import annotations

import re


def _extract_hybrid_bundle_from_inline_html(
    *,
    slug: str,
    inline_html: str,
    asset_bank_files: list[dict[str, str]] | None = None,
    runtime_asset_manifest: dict[str, object] | None = None,
) -> tuple[list[dict[str, str]], dict[str, object]] | None:
    style_match = re.search(r"<style>\s*(.*?)\s*</style>", inline_html, flags=re.DOTALL)
    script_match = re.search(r"<script>\s*(.*?)\s*</script>\s*</body>", inline_html, flags=re.DOTALL)
    if not style_match or not script_match:
        return None

    styles_css = style_match.group(1).strip()
    game_js = script_match.group(1).strip()
    if not styles_css or not game_js:
        return None

    index_html = inline_html
    index_html = index_html.replace(style_match.group(0), '    <link rel="stylesheet" href="./styles.css" />', 1)
    index_html = index_html.replace(
        script_match.group(0),
        '    <script src="./game.js"></script>\n  </body>',
        1,
    )

    artifact_files = [
        {
            "path": f"games/{slug}/index.html",
            "content": index_html,
            "content_type": "text/html; charset=utf-8",
        },
        {
            "path": f"games/{slug}/styles.css",
            "content": styles_css,
            "content_type": "text/css; charset=utf-8",
        },
        {
            "path": f"games/{slug}/game.js",
            "content": game_js,
            "content_type": "application/javascript; charset=utf-8",
        },
    ]
    files_by_path = {row["path"]: row for row in artifact_files}
    for row in asset_bank_files or []:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path", "")).strip()
        content = str(row.get("content", ""))
        content_type = str(row.get("content_type", "")).strip()
        if not path.startswith(f"games/{slug}/"):
            continue
        if not content or not content_type:
            continue
        files_by_path[path] = {
            "path": path,
            "content": content,
            "content_type": content_type,
        }
    artifact_files = list(files_by_path.values())

    resolved_asset_manifest: dict[str, object] = {}
    if isinstance(runtime_asset_manifest, dict):
        resolved_asset_manifest = dict(runtime_asset_manifest)

    image_manifest = resolved_asset_manifest.get("images")
    if not isinstance(image_manifest, dict):
        image_manifest = {}
    for row in artifact_files:
        path = str(row["path"])
        if not path.endswith(".svg"):
            continue
        filename = path.rsplit("/", 1)[-1]
        image_key = filename[:-4]
        image_manifest.setdefault(image_key, f"./{filename}")
    resolved_asset_manifest["images"] = image_manifest
    resolved_asset_manifest["styles"] = ["./styles.css"]
    resolved_asset_manifest["scripts"] = ["./game.js"]

    runtime_hooks = [
        "requestAnimationFrame",
        "loadSprites",
        "pickWeighted",
        "applyRelicSynergy",
        "spawnMiniBoss",
        "renderWebglBackground",
        "drawPostFx",
        "spawnEnemy",
        "stepProgression",
        "update",
        "draw",
        "playSfx",
    ]
    artifact_manifest = {
        "schema_version": 1,
        "entrypoint": f"games/{slug}/index.html",
        "files": [row["path"] for row in artifact_files],
        "bundle_kind": "hybrid_engine",
        "modules": [
            "runtime_bootstrap",
            "input_controls",
            "spawn_system",
            "combat_or_navigation_loop",
            "render_pipeline",
            "hud_overlay",
            "audio_feedback",
        ],
        "runtime_hooks": runtime_hooks,
        "asset_manifest": resolved_asset_manifest,
    }
    return artifact_files, artifact_manifest
