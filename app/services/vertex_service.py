from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from app.core.config import Settings

try:  # pragma: no cover - import availability differs across environments
    from langchain_google_vertexai import ChatVertexAI
except Exception:  # pragma: no cover - runtime safeguard
    ChatVertexAI = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VertexGenerationResult:
    payload: dict[str, Any]
    meta: dict[str, Any]


@dataclass(frozen=True)
class VertexTextResult:
    text: str
    meta: dict[str, Any]


class _GDDModel(BaseModel):
    title: str
    genre: str
    objective: str
    visual_style: str = "neon-minimal"
    research_intent: str
    references: list[str] = Field(default_factory=list)


class _DesignSpecModel(BaseModel):
    visual_style: str
    palette: list[str]
    hud: str
    viewport_width: int = 1280
    viewport_height: int = 720
    safe_area_padding: int = 24
    min_font_size_px: int = 14
    text_overflow_policy: str = "ellipsis-clamp"
    typography: str = "inter-bold-hud"
    thumbnail_concept: str = "High-contrast action scene"


def _coerce_message_text(raw: Any) -> str:
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


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    return cleaned.strip()


class VertexService:
    """Vertex wrapper with safe fallbacks for GDD/design/code generation.

    NOTE:
      - Uses `ChatVertexAI` from `langchain-google-vertexai` for repo compatibility.
      - LangChain docs mark `ChatVertexAI` as deprecated in favor of `langchain-google-genai`,
        but we intentionally keep current dependency until repo-wide migration is approved.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._pro_llm = None
        self._flash_llm = None

    def generate_gdd_bundle(self, keyword: str) -> VertexGenerationResult:
        fallback = self._fallback_gdd_bundle(keyword, reason="vertex_not_configured")
        if not self._is_enabled():
            return fallback

        started = time.perf_counter()
        try:
            model = self._pro_model()
            prompt = self._gdd_prompt(keyword)
            runnable = model.with_structured_output(_GDDModel, method="json_mode")
            raw = self._invoke_with_retry(runnable, prompt)
            parsed = raw if isinstance(raw, _GDDModel) else _GDDModel.model_validate(raw)
            latency_ms = int((time.perf_counter() - started) * 1000)

            references = parsed.references[:3] or [
                f"{keyword} + score-attack progression",
                f"{keyword} + 90-second arcade pacing",
                f"{keyword} + mobile-friendly HUD readability",
            ]
            research_summary = {
                "intent": parsed.research_intent,
                "references": references,
            }
            gdd = {
                "title": parsed.title,
                "genre": parsed.genre,
                "objective": parsed.objective,
                "visual_style": parsed.visual_style,
            }
            return VertexGenerationResult(
                payload={"research_summary": research_summary, "gdd": gdd},
                meta={
                    "generation_source": "vertex",
                    "model": self.settings.gemini_pro_model,
                    "latency_ms": latency_ms,
                },
            )
        except Exception as exc:  # pragma: no cover - external API path
            logger.warning("Vertex GDD generation failed, using fallback: %s", exc)
            failed = self._fallback_gdd_bundle(keyword, reason=f"vertex_error:{type(exc).__name__}")
            return VertexGenerationResult(
                payload=failed.payload,
                meta={
                    **failed.meta,
                    "vertex_error": str(exc),
                    "model": self.settings.gemini_pro_model,
                },
            )

    def generate_design_spec(self, *, keyword: str, visual_style: str, genre: str) -> VertexGenerationResult:
        fallback = self._fallback_design_spec(visual_style=visual_style)
        if not self._is_enabled():
            return fallback

        started = time.perf_counter()
        try:
            model = self._flash_model()
            prompt = self._design_prompt(keyword=keyword, visual_style=visual_style, genre=genre)
            runnable = model.with_structured_output(_DesignSpecModel, method="json_mode")
            raw = self._invoke_with_retry(runnable, prompt)
            parsed = raw if isinstance(raw, _DesignSpecModel) else _DesignSpecModel.model_validate(raw)
            latency_ms = int((time.perf_counter() - started) * 1000)
            return VertexGenerationResult(
                payload=parsed.model_dump(),
                meta={
                    "generation_source": "vertex",
                    "model": self.settings.gemini_flash_model,
                    "latency_ms": latency_ms,
                },
            )
        except Exception as exc:  # pragma: no cover - external API path
            logger.warning("Vertex design generation failed, using fallback: %s", exc)
            failed = self._fallback_design_spec(visual_style=visual_style, reason=f"vertex_error:{type(exc).__name__}")
            return VertexGenerationResult(
                payload=failed.payload,
                meta={
                    **failed.meta,
                    "vertex_error": str(exc),
                    "model": self.settings.gemini_flash_model,
                },
            )

    def generate_single_file_game(
        self,
        *,
        keyword: str,
        title: str,
        genre: str,
        objective: str,
        design_spec: dict[str, Any],
    ) -> VertexTextResult:
        if not self._is_enabled():
            return VertexTextResult(
                text="",
                meta={"generation_source": "stub", "reason": "vertex_not_configured"},
            )

        started = time.perf_counter()
        try:
            model = self._pro_model()
            prompt = self._builder_prompt(
                keyword=keyword,
                title=title,
                genre=genre,
                objective=objective,
                design_spec=design_spec,
            )
            raw = self._invoke_with_retry(model, prompt)
            content = _strip_code_fences(_coerce_message_text(getattr(raw, "content", raw)))
            latency_ms = int((time.perf_counter() - started) * 1000)
            if not content:
                raise ValueError("empty_builder_response")

            return VertexTextResult(
                text=content,
                meta={
                    "generation_source": "vertex",
                    "model": self.settings.gemini_pro_model,
                    "latency_ms": latency_ms,
                },
            )
        except Exception as exc:  # pragma: no cover - external API path
            logger.warning("Vertex builder generation failed, using fallback template: %s", exc)
            return VertexTextResult(
                text="",
                meta={
                    "generation_source": "stub",
                    "reason": f"vertex_error:{type(exc).__name__}",
                    "vertex_error": str(exc),
                    "model": self.settings.gemini_pro_model,
                },
            )

    def _is_enabled(self) -> bool:
        if not self.settings.vertex_project_id:
            return False
        if ChatVertexAI is None:
            return False
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        if not credentials_path:
            return False
        return os.path.exists(credentials_path)

    def _pro_model(self):
        if self._pro_llm is None:
            self._pro_llm = self._build_model(self.settings.gemini_pro_model, temperature=0.4)
        return self._pro_llm

    def _flash_model(self):
        if self._flash_llm is None:
            self._flash_llm = self._build_model(self.settings.gemini_flash_model, temperature=0.3)
        return self._flash_llm

    def _build_model(self, model_name: str, *, temperature: float):
        if ChatVertexAI is None:  # pragma: no cover - import guard
            raise RuntimeError("langchain_google_vertexai is not available")
        return ChatVertexAI(
            model_name=model_name,
            project=self.settings.vertex_project_id,
            location=self.settings.vertex_location,
            temperature=temperature,
            timeout=self.settings.http_timeout_seconds,
        )

    @retry(
        reraise=True,
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=3),
    )
    def _invoke_with_retry(self, runnable, prompt: str):
        return runnable.invoke(prompt)

    @staticmethod
    def _gdd_prompt(keyword: str) -> str:
        return (
            "You are an expert arcade game designer. "
            "Return JSON only.\n"
            "Create a compact GDD for a browser game generated by AI.\n"
            f"Keyword: {keyword}\n"
            "Constraints:\n"
            "- genre must be one of: arcade, puzzle, survival, score-attack\n"
            "- objective must fit a short 60~120 second session\n"
            "- visual_style should be concise (e.g., neon-minimal, pixel-retro)\n"
            "- references should be 3 short reference ideas (strings)\n"
            "- research_intent should explain what references target\n"
        )

    @staticmethod
    def _design_prompt(*, keyword: str, visual_style: str, genre: str) -> str:
        return (
            "You are a game UI/UX stylist for web arcade games. "
            "Return JSON only.\n"
            f"Keyword: {keyword}\n"
            f"Genre: {genre}\n"
            f"Requested visual style: {visual_style}\n"
            "Output fields exactly: visual_style, palette (list of hex colors), hud, viewport_width, "
            "viewport_height, safe_area_padding, min_font_size_px, text_overflow_policy, typography, thumbnail_concept.\n"
            "Constraints:\n"
            "- viewport_width: 960~1600\n"
            "- viewport_height: 540~900\n"
            "- safe_area_padding: 8~40\n"
            "- min_font_size_px: 12~20\n"
            "- text_overflow_policy: one short token like ellipsis-clamp\n"
            "- palette must have 4 colors\n"
        )

    @staticmethod
    def _builder_prompt(
        *,
        keyword: str,
        title: str,
        genre: str,
        objective: str,
        design_spec: dict[str, Any],
    ) -> str:
        spec_json = json.dumps(design_spec, ensure_ascii=False)
        return (
            "Generate a single-file browser game as HTML (inline CSS + JS) and return ONLY HTML.\n"
            "No markdown fences. No explanations.\n\n"
            "Requirements:\n"
            "- Must include <!doctype html>\n"
            "- Must include <meta name=\"viewport\">\n"
            "- Must set window.__iis_game_boot_ok = true\n"
            "- Must define window.IISLeaderboard.submitScore usage contract (call-safe wrapper)\n"
            "- Should be playable with mouse or keyboard\n"
            "- Keep scope simple and stable (arcade prototype)\n"
            "- Use dark theme and readable HUD text\n"
            "- Avoid external assets/CDNs\n\n"
            f"Keyword: {keyword}\n"
            f"Title: {title}\n"
            f"Genre: {genre}\n"
            f"Objective: {objective}\n"
            f"DesignSpec JSON: {spec_json}\n"
        )

    @staticmethod
    def _fallback_gdd_bundle(keyword: str, *, reason: str) -> VertexGenerationResult:
        keyword_title = keyword.title()
        research_summary = {
            "intent": f"{keyword} 기반 코어 플레이 루프 아이디어 수집",
            "references": [
                f"{keyword} + score-attack progression",
                f"{keyword} + 90-second arcade pacing",
                f"{keyword} + mobile-friendly HUD readability",
            ],
        }
        gdd = {
            "title": f"{keyword_title} Infinite",
            "genre": "arcade",
            "objective": "Get highest score possible in 90 seconds.",
            "visual_style": "neon-minimal",
        }
        return VertexGenerationResult(
            payload={"research_summary": research_summary, "gdd": gdd},
            meta={"generation_source": "stub", "reason": reason},
        )

    @staticmethod
    def _fallback_design_spec(*, visual_style: str, reason: str = "vertex_not_configured") -> VertexGenerationResult:
        return VertexGenerationResult(
            payload={
                "visual_style": visual_style or "neon-minimal",
                "palette": ["#0EA5E9", "#111827", "#22C55E", "#F8FAFC"],
                "hud": "score-top-left / timer-top-right / combo-bottom",
                "viewport_width": 1280,
                "viewport_height": 720,
                "safe_area_padding": 24,
                "min_font_size_px": 14,
                "text_overflow_policy": "ellipsis-clamp",
                "typography": "inter-bold-hud",
                "thumbnail_concept": "Neon particle burst with score counter.",
            },
            meta={"generation_source": "stub", "reason": reason},
        )
