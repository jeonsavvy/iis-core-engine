"""Codegen Agent — interactive game code generation via LLM.

Responsibilities:
  - Generate initial game code from a user prompt
  - Modify existing game code based on user or QA agent feedback
  - Multi-turn conversation with history context
  - Streaming output for real-time UI updates
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from app.agents.genre_briefs import build_genre_brief, scaffold_seed_for_brief
from app.agents.scaffolds import get_scaffold_seed
from app.services.vertex_service import VertexCapacityExhausted

logger = logging.getLogger(__name__)

_THREE_CDN = "https://unpkg.com/three@0.169.0/build/three.module.js"
_PHASER_CDN = "https://cdn.jsdelivr.net/npm/phaser@3.90.0/dist/phaser.min.js"


@dataclass
class CodegenResult:
    html: str
    generation_source: str = "vertex"
    model_name: str = ""
    model_location: str = ""
    fallback_used: bool = False
    fallback_rank: int = 0
    tokens_used: int = 0
    error: str = ""


@dataclass
class ConversationMessage:
    role: str  # "user" | "assistant" | "system" | "visual_qa" | "playtester"
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _decode_data_url_image(data_url: str) -> bytes:
    if ";base64," not in data_url:
        raise ValueError("invalid_image_data_url")
    _, encoded = data_url.split(";base64,", 1)
    return base64.b64decode(encoded)


class CodegenAgent:
    """Interactive codegen agent for game generation/modification.

    Unlike the old batch pipeline builder, this agent:
    - Takes multi-turn conversation history
    - Can modify existing code (not just generate from scratch)
    - Streams output for real-time UI
    - Uses a clean, concise prompt (not 300+ lines of contracts)
    """

    def __init__(self, *, vertex_service: Any) -> None:
        self._vertex = vertex_service

    async def generate(
        self,
        *,
        user_prompt: str,
        history: list[ConversationMessage] | None = None,
        current_html: str = "",
        genre_hint: str = "",
        image_attachment: dict[str, str] | None = None,
    ) -> CodegenResult:
        """Generate or modify game code based on user prompt.

        Args:
            user_prompt: What the user wants (e.g. "make a space shooter")
            history: Previous conversation messages for context
            current_html: Existing game HTML to modify (empty for new games)
            genre_hint: Optional genre hint from initial analysis
        """
        prompt = self._build_prompt(
            user_prompt=user_prompt,
            history=history or [],
            current_html=current_html,
            genre_hint=genre_hint,
            image_attachment=image_attachment,
        )

        if not self._vertex._is_enabled():
            logger.error("Vertex AI not configured — fail-fast for code generation")
            return CodegenResult(
                html=current_html,
                generation_source="error",
                error="vertex_not_configured",
            )

        try:
            max_tokens = getattr(
                self._vertex.settings, "builder_codegen_max_output_tokens", 48_000
            )
            if self._vertex._use_genai_sdk():
                route_result = self._vertex.generate_builder_text_with_fallback(
                    prompt=prompt,
                    temperature=0.7,
                    max_output_tokens=max_tokens,
                    image_bytes=_decode_data_url_image(str(image_attachment.get("data_url", "")))
                    if image_attachment
                    else None,
                    mime_type=str(image_attachment.get("mime_type", "image/png")) if image_attachment else None,
                )
                raw_text = str(route_result.get("text", ""))
                usage = route_result.get("usage", {}) if isinstance(route_result.get("usage"), dict) else {}
                model_name = str(route_result.get("model_name", ""))
                model_location = str(route_result.get("location", ""))
                fallback_used = bool(route_result.get("fallback_used", False))
                fallback_rank = int(route_result.get("fallback_rank", 0) or 0)
            else:
                model_name = self._vertex._builder_model_name()
                raw_text, usage = self._vertex._genai_text(
                    model_name=model_name,
                    prompt=prompt,
                    temperature=0.7,
                    max_output_tokens=max_tokens,
                )
                model_location = str(self._vertex.settings.vertex_location or "")
                fallback_used = False
                fallback_rank = 0
            html = self._extract_html(str(raw_text).strip())
            total_tokens = 0
            if isinstance(usage, dict):
                value = usage.get("total_tokens", 0)
                if isinstance(value, int):
                    total_tokens = value
            return CodegenResult(
                html=html,
                generation_source="vertex",
                model_name=model_name,
                model_location=model_location,
                fallback_used=fallback_used,
                fallback_rank=fallback_rank,
                tokens_used=total_tokens,
            )
        except VertexCapacityExhausted:
            raise
        except Exception as exc:
            logger.exception("Codegen generation failed: %s", exc)
            return CodegenResult(
                html=current_html,
                generation_source="error",
                error=str(exc)[:200],
            )

    async def generate_streaming(
        self,
        *,
        user_prompt: str,
        history: list[ConversationMessage] | None = None,
        current_html: str = "",
        genre_hint: str = "",
    ) -> AsyncIterator[str]:
        """Stream game code generation for real-time UI updates."""
        prompt = self._build_prompt(
            user_prompt=user_prompt,
            history=history or [],
            current_html=current_html,
            genre_hint=genre_hint,
        )

        if not self._vertex._is_enabled():
            raise RuntimeError("vertex_not_configured")

        model_name = self._vertex._builder_model_name()
        max_tokens = getattr(
            self._vertex.settings, "builder_codegen_max_output_tokens", 48_000
        )

        try:
            client = self._vertex._client()
            if client is None:
                raise RuntimeError("vertex_client_unavailable")

            config = {"temperature": 0.7, "max_output_tokens": max_tokens}
            async for chunk in client.models.generate_content_stream(
                model=model_name,
                contents=prompt,
                config=config,
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
            logger.exception("Streaming codegen failed: %s", exc)
            yield f"<!-- Generation error: {str(exc)[:100]} -->"

    def _build_prompt(
        self,
        *,
        user_prompt: str,
        history: list[ConversationMessage],
        current_html: str,
        genre_hint: str,
        image_attachment: dict[str, str] | None = None,
    ) -> str:
        """Build a clean, concise prompt for game generation.

        Key difference from legacy: no 300-line contract soup.
        LLM gets freedom to create, with only essential constraints.
        """
        is_modification = bool(current_html.strip())
        genre_brief = build_genre_brief(user_prompt=user_prompt, genre_hint=genre_hint)
        scaffold_seed = scaffold_seed_for_brief(genre_brief)
        scaffold = get_scaffold_seed(str(genre_brief.get("scaffold_key", "")).strip()) if scaffold_seed else None

        history_section = ""
        if history:
            recent = history[-10:]  # Keep last 10 messages for context
            history_lines = []
            for msg in recent:
                role_label = msg.role.upper()
                history_lines.append(f"[{role_label}]: {msg.content[:500]}")
                attachment_meta = msg.metadata.get("attachment") if isinstance(msg.metadata, dict) else None
                if isinstance(attachment_meta, dict) and attachment_meta.get("has_image"):
                    history_lines.append(
                        f"[{role_label}_IMAGE]: {attachment_meta.get('name', 'attachment')} ({attachment_meta.get('mime_type', 'image')})"
                    )
            history_section = (
                "=== Conversation History ===\n"
                + "\n".join(history_lines)
                + "\n\n"
            )

        image_context = ""
        if image_attachment:
            image_context = (
                "Reference image is attached with this request.\n"
                f"- attachment_name: {image_attachment.get('name', 'attachment')}\n"
                f"- mime_type: {image_attachment.get('mime_type', 'image/png')}\n"
                "Use it as visual guidance for composition, styling, and correction targets when relevant.\n\n"
            )

        if is_modification:
            return (
                "You are a principal web game engineer.\n"
                "Modify the existing game based on the user's request.\n"
                "Work in a DIFF mindset: keep the current game structure unless the request requires a local replacement.\n\n"
                f"{history_section}"
                f"{image_context}"
                f"User request: {user_prompt}\n\n"
                f"Genre brief JSON: {json.dumps(genre_brief, ensure_ascii=False)}\n"
                f"{'Active scaffold JSON: ' + json.dumps(scaffold_seed, ensure_ascii=False) + chr(10) if scaffold_seed else ''}\n"
                "Rules:\n"
                "- Return the COMPLETE modified HTML (not a diff)\n"
                "- Preserve working game mechanics unless asked to change them\n"
                "- Prefer surgical edits over wholesale rewrites\n"
                "- Keep unchanged systems intact if they already work\n"
                "- Keep window.__iis_game_boot_ok = true\n"
                "- Keep window.IISLeaderboard contract\n"
                "- Preserve window.__iisPresentationReady and window.__iisPreparePresentationCapture when present, and keep them working for deterministic publish thumbnails\n"
                "- Keep the scaffold's genre fantasy intact; do not simplify it into a lower-fidelity genre\n"
                "- Return only HTML, no markdown fences\n\n"
                f"Current game HTML:\n{current_html}"
            )

        if scaffold is not None:
            degradation_guards = [
                str(item).strip()
                for item in genre_brief.get("degradation_guard", [])
                if str(item).strip()
            ]
            first_frame_requirements = [
                str(item).strip()
                for item in genre_brief.get("first_frame_requirements", [])
                if str(item).strip()
            ]
            preserve_systems = [
                str(item).strip()
                for item in genre_brief.get("must_have_mechanics", [])
                if str(item).strip()
            ]
            structural_contracts = [
                str(item).strip()
                for item in genre_brief.get("structural_contracts", [])
                if str(item).strip()
            ]
            visual_contracts = [
                str(item).strip()
                for item in genre_brief.get("visual_contracts", [])
                if str(item).strip()
            ]
            asset_pack_key = str(genre_brief.get("asset_pack_key", "") or "").strip()
            degradation_section = "".join(f"- Degradation guard: {guard}\n" for guard in degradation_guards)
            first_frame_section = "".join(f"- First frame requirement: {requirement}\n" for requirement in first_frame_requirements)
            preserve_section = "".join(f"- Preserve system: {item}\n" for item in preserve_systems)
            contract_section = "".join(f"- Structural contract: {item}\n" for item in structural_contracts)
            visual_section = "".join(f"- Visual contract: {item}\n" for item in visual_contracts)
            return (
                "You are a principal web game engineer.\n"
                "You are extending a production baseline, not inventing a new game from scratch.\n"
                "Specialize and expand the provided hard scaffold into a polished browser game.\n\n"
                f"{history_section}"
                f"{image_context}"
                f"User request: {user_prompt}\n"
                f"{'Genre hint: ' + genre_hint if genre_hint else ''}\n\n"
                f"Genre brief JSON: {json.dumps(genre_brief, ensure_ascii=False)}\n"
                f"Scaffold seed JSON: {json.dumps(scaffold_seed, ensure_ascii=False)}\n"
                "Generation mode: initial_from_scaffold\n\n"
                "Rules:\n"
                "- Start from the scaffold HTML below; do not ignore it\n"
                "- Preserve the scaffold's core systems, controls, loop, HUD contract, and genre-defining structure\n"
                "- Keep localized changes; do not replace the whole architecture\n"
                "- Expand the fantasy, polish, track/enemy layout, and presentation to fit the user request\n"
                "- Prefer extending the scaffold over rewriting it from scratch\n"
                "- Keep window.__iis_game_boot_ok = true when ready\n"
                "- Keep window.IISLeaderboard contract\n"
                "- Preserve and keep working deterministic thumbnail hooks window.__iisPresentationReady / window.__iisPreparePresentationCapture\n"
                "- Never violate degradation guards from the genre brief\n"
                f"{'Asset pack key: ' + asset_pack_key + chr(10) if asset_pack_key else ''}"
                f"{preserve_section}"
                f"{contract_section}"
                f"{visual_section}"
                f"{degradation_section}"
                "- The first visible frame must sell the fantasy immediately\n"
                f"{first_frame_section}"
                "- Return only the final HTML document, no markdown fences\n\n"
                f"Base scaffold HTML:\n{scaffold.html}"
            )

        return (
            "You are a principal web game engineer.\n"
            "Create a complete, high-quality, playable HTML5 browser game.\n\n"
            f"{history_section}"
            f"{image_context}"
            f"User request: {user_prompt}\n"
            f"{'Genre hint: ' + genre_hint if genre_hint else ''}\n\n"
            f"Genre brief JSON: {json.dumps(genre_brief, ensure_ascii=False)}\n"
            f"{'Scaffold seed JSON: ' + json.dumps(scaffold_seed, ensure_ascii=False) + chr(10) if scaffold_seed else ''}\n"
            "Requirements:\n"
            "- Single complete HTML document with inline JS and CSS\n"
            "- Use Three.js (import from CDN) for 3D games\n"
            "- Use Phaser.js (script from CDN) for 2D games\n"
            "- Choose 3D or 2D based on the game concept\n"
            "- Must include: game loop, keyboard/mouse controls, score system, "
            "restart on game-over\n"
            "- Must set window.__iis_game_boot_ok = true when ready\n"
            "- Must expose window.IISLeaderboard = { postScore: (s) => "
            "console.log('IIS:score', s) }\n"
            "- Production quality: custom shaders/particles, rich visuals, "
            "smooth animations\n"
            "- No external image dependencies — use procedural graphics\n"
            "- Must work in an embedded iframe\n"
            "- Respect the genre brief and scaffold seed when provided\n"
            "- Never collapse a racing brief into an endless obstacle dodger\n"
            "- Never collapse a dogfight brief into a simple forward auto-scroll shooter\n"
            "- Never collapse a twin-stick brief into a basic 8-way clicker shooter\n"
            "- Return only the HTML document, no markdown fences\n\n"
            f"Three.js CDN: {_THREE_CDN}\n"
            f"Phaser CDN: {_PHASER_CDN}\n"
        )

    @staticmethod
    def _extract_html(raw: str) -> str:
        """Extract HTML from LLM response, stripping markdown fences."""
        text = raw.strip()
        for fence in ("```html", "```HTML"):
            if text.startswith(fence):
                text = text[len(fence) :]
                break
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        # Ensure it looks like HTML
        if not text.lower().startswith(("<!doctype", "<html", "<head")):
            # Try to find HTML in the response
            for marker in ("<!doctype", "<!DOCTYPE", "<html"):
                idx = text.find(marker)
                if idx >= 0:
                    text = text[idx:]
                    break
        return text

    @staticmethod
    def _stub_html(prompt: str) -> str:
        """Minimal stub for when Vertex AI is not available."""
        return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<title>IIS Game Stub</title>
<style>
html, body {{ margin: 0; height: 100%; background: #0a0a1a; color: #e2e8f0;
  font-family: system-ui; display: grid; place-items: center; }}
.stub {{ text-align: center; padding: 2rem; }}
h1 {{ color: #60a5fa; }}
</style>
</head>
<body>
<div class="stub">
  <h1>🎮 Game Generation Pending</h1>
  <p>Prompt: {prompt[:200]}</p>
  <p>Vertex AI is not configured. Connect your API credentials to generate games.</p>
</div>
<script>
window.__iis_game_boot_ok = true;
window.IISLeaderboard = {{ postScore: (s) => console.log('IIS:score', s) }};
</script>
</body>
</html>"""
