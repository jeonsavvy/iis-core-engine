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

try:  # pragma: no cover - import availability differs across environments
    from google import genai as google_genai
    from google.genai import types as genai_types
except Exception:  # pragma: no cover - runtime safeguard
    google_genai = None  # type: ignore[assignment]
    genai_types = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VertexGenerationResult:
    payload: dict[str, Any]
    meta: dict[str, Any]


@dataclass(frozen=True)
class VertexTextResult:
    text: str
    meta: dict[str, Any]


class _EnemyConfig(BaseModel):
    hp: int = 1
    speed_min: int = 100
    speed_max: int = 220
    spawn_rate_sec: float = 1.0

class _PlayerConfig(BaseModel):
    hp: int = 3
    speed: int = 240
    attack_cooldown_sec: float = 0.5
    
class _GameConfigModel(BaseModel):
    player_hp: int = 3
    player_speed: int = 240
    player_attack_cooldown: float = 0.5
    enemy_hp: int = 1
    enemy_speed_min: int = 100
    enemy_speed_max: int = 220
    enemy_spawn_rate: float = 1.0
    time_limit_sec: int = 60
    base_score_value: int = 10


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
        self._genai_client = None

    def generate_gdd_bundle(self, keyword: str) -> VertexGenerationResult:
        fallback = self._fallback_gdd_bundle(keyword, reason="vertex_not_configured")
        if not self._is_enabled():
            return fallback

        started = time.perf_counter()
        try:
            prompt = self._gdd_prompt(keyword)
            usage = {}
            if self._use_genai_sdk():
                raw, usage = self._genai_json(
                    model_name=self.settings.gemini_pro_model,
                    prompt=prompt,
                    schema=_GDDModel,
                    temperature=0.4,
                )
            else:
                model = self._pro_model()
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
                    "usage": usage,
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
            prompt = self._design_prompt(keyword=keyword, visual_style=visual_style, genre=genre)
            usage = {}
            if self._use_genai_sdk():
                raw, usage = self._genai_json(
                    model_name=self.settings.gemini_flash_model,
                    prompt=prompt,
                    schema=_DesignSpecModel,
                    temperature=0.3,
                )
            else:
                model = self._flash_model()
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
                    "usage": usage,
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

    def generate_game_config(
        self,
        *,
        keyword: str,
        title: str,
        genre: str,
        objective: str,
        design_spec: dict[str, Any],
    ) -> VertexGenerationResult:
        if not self._is_enabled():
            return VertexGenerationResult(
                payload=self._fallback_game_config().dict(),
                meta={"generation_source": "stub", "reason": "vertex_not_configured"},
            )

        started = time.perf_counter()
        try:
            prompt = self._builder_prompt(
                keyword=keyword,
                title=title,
                genre=genre,
                objective=objective,
                design_spec=design_spec,
            )
            usage = {}
            if self._use_genai_sdk():
                raw, usage = self._genai_json(
                    model_name=self.settings.gemini_pro_model,
                    prompt=prompt,
                    schema=_GameConfigModel,
                    temperature=0.3,
                )
            else:
                model = self._pro_model()
                runnable = model.with_structured_output(_GameConfigModel, method="json_mode")
                raw = self._invoke_with_retry(runnable, prompt)
            parsed = raw if isinstance(raw, _GameConfigModel) else _GameConfigModel.model_validate(raw)
            latency_ms = int((time.perf_counter() - started) * 1000)

            return VertexGenerationResult(
                payload=parsed.model_dump(),
                meta={
                    "generation_source": "vertex",
                    "model": self.settings.gemini_pro_model,
                    "latency_ms": latency_ms,
                    "usage": usage,
                },
            )
        except Exception as exc:  # pragma: no cover - external API path
            logger.warning("Vertex config generation failed, using fallback: %s", exc)
            return VertexGenerationResult(
                payload=self._fallback_game_config().dict(),
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
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        if not credentials_path:
            return False
        if not os.path.exists(credentials_path):
            return False
        return (google_genai is not None and genai_types is not None) or ChatVertexAI is not None

    def _use_genai_sdk(self) -> bool:
        if google_genai is None or genai_types is None:
            return False
        if not self.settings.vertex_project_id:
            return False
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        return bool(credentials_path and os.path.exists(credentials_path))

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

    def _client(self):
        if self._genai_client is None:
            if google_genai is None:  # pragma: no cover - import guard
                raise RuntimeError("google_genai is not available")
            self._genai_client = google_genai.Client(
                vertexai=True,
                project=self.settings.vertex_project_id,
                location=self.settings.vertex_location,
            )
        return self._genai_client

    def _genai_json(self, *, model_name: str, prompt: str, schema: type[BaseModel], temperature: float) -> tuple[dict[str, Any], dict[str, int]]:
        if genai_types is None:  # pragma: no cover - import guard
            raise RuntimeError("google_genai types are not available")
        response = self._genai_generate_with_retry(
            model_name=model_name,
            prompt=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        usage = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = {
                "prompt_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
                "completion_tokens": getattr(response.usage_metadata, "candidates_token_count", 0),
                "total_tokens": getattr(response.usage_metadata, "total_token_count", 0),
            }
        text = _strip_code_fences(self._coerce_genai_text(response))
        if not text:
            raise ValueError("empty_json_response")
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("json_response_not_object")
        return parsed, usage

    def _genai_text(self, *, model_name: str, prompt: str, temperature: float) -> tuple[str, dict[str, int]]:
        if genai_types is None:  # pragma: no cover - import guard
            raise RuntimeError("google_genai types are not available")
        response = self._genai_generate_with_retry(
            model_name=model_name,
            prompt=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="text/plain",
            ),
        )
        usage = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = {
                "prompt_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
                "completion_tokens": getattr(response.usage_metadata, "candidates_token_count", 0),
                "total_tokens": getattr(response.usage_metadata, "total_token_count", 0),
            }
        return _strip_code_fences(self._coerce_genai_text(response)), usage

    def _coerce_genai_text(self, response: Any) -> str:
        try:
            text = getattr(response, "text", "")
            if isinstance(text, str) and text.strip():
                return text
        except Exception:
            pass

        candidates = getattr(response, "candidates", None) or []
        parts: list[str] = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            content_parts = getattr(content, "parts", None) or []
            for part in content_parts:
                text = getattr(part, "text", None)
                if isinstance(text, str):
                    parts.append(text)
        if parts:
            return "\n".join(parts).strip()
        return str(response)

    @retry(
        reraise=True,
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=3),
    )
    def _invoke_with_retry(self, runnable, prompt: str):
        return runnable.invoke(prompt)

    @retry(
        reraise=True,
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.5, max=3),
    )
    def _genai_generate_with_retry(self, *, model_name: str, prompt: str, config: Any):
        client = self._client()
        return client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )

    @staticmethod
    def _gdd_prompt(keyword: str) -> str:
        return (
            "You are a principal game designer for a viral browser arcade studio. "
            "Return JSON only.\n"
            "Create a compact but production-usable GDD for an AI-generated browser game.\n"
            f"Keyword: {keyword}\n"
            "Constraints:\n"
            "- genre must be one of: arcade, puzzle, survival, score-attack\n"
            "- objective must fit a short 60~120 second session\n"
            "- visual_style should be concise (e.g., neon-minimal, pixel-retro)\n"
            "- references should be 3 short reference ideas (strings)\n"
            "- research_intent should explain what references target\n"
            "- title should preserve the spirit of the keyword and feel marketable\n"
            "- objective should imply clear win/lose pressure, not only idle score clicking\n"
            "- prefer mechanics with movement, timing, dodging, aiming, combo, or enemy pressure\n"
            "- avoid concepts that collapse into a single button increment toy\n"
            "Design quality bar:\n"
            "- The player must have a meaningful verb loop (move/aim/attack/evade/collect)\n"
            "- The fantasy implied by the keyword should be visible in the core loop\n"
            "- The game should be understandable within 5 seconds and replayable within 90 seconds\n"
        )

    @staticmethod
    def _design_prompt(*, keyword: str, visual_style: str, genre: str) -> str:
        return (
            "You are a senior game UI/UX and visual direction stylist for web arcade games. "
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
            "Quality bar:\n"
            "- Prioritize gameplay readability over decoration (enemy/projectile/player contrast)\n"
            "- HUD must communicate score + timer/HP/round at a glance\n"
            "- Visual style should match keyword fantasy, not generic dark UI only\n"
            "- Thumbnail concept should describe a dynamic action moment with clear focal point\n"
        )

    def generate_marketing_copy(self, *, keyword: str, slug: str, genre: str) -> VertexGenerationResult:
        prompt = (
            f"Write a short, engaging, 1-2 sentence AI designer review and promotional tweet "
            f"for an indie arcade game named '{slug}'. The genre is '{genre}' and the keyword is '{keyword}'. "
            f"Include emojis and #indiegame #html5. Return ONLY the text, nothing else."
        )
        started = time.perf_counter()
        try:
            usage = {}
            if self._use_genai_sdk():
                text, usage = self._genai_text(
                    model_name=self.settings.gemini_flash_model,
                    prompt=prompt,
                    temperature=0.7,
                )
            else:
                model = self._flash_model()
                from langchain_core.messages import HumanMessage
                result = model.invoke([HumanMessage(content=prompt)])
                text = _strip_code_fences(_coerce_message_text(result.content))
            latency_ms = int((time.perf_counter() - started) * 1000)
            return VertexGenerationResult(
                payload={"marketing_copy": text},
                meta={
                    "generation_source": "vertex",
                    "model": self.settings.gemini_flash_model,
                    "latency_ms": latency_ms,
                    "usage": usage,
                },
            )
        except Exception as exc:
            logger.warning("Vertex marketing generation failed: %s", exc)
            fallback_text = f"New game launched: {slug} #indiegame #html5 based on '{keyword}'!"
            return VertexGenerationResult(
                payload={"marketing_copy": fallback_text},
                meta={
                    "generation_source": "stub",
                    "reason": f"vertex_error:{type(exc).__name__}",
                    "vertex_error": str(exc),
                },
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
            "You are a master game balancer and level designer for arcade games. "
            "Return JSON only.\n"
            f"Keyword: {keyword}\n"
            f"Title: {title}\n"
            f"Genre: {genre}\n"
            f"Objective: {objective}\n"
            f"DesignSpec JSON: {spec_json}\n\n"
            "Based on the game's theme, objective, and pace, provide a fine-tuned configuration JSON "
            "that defines the balance and mechanics of the game. Output fields exactly according to the schema:\n"
            "- player_hp: integer (e.g. 1 to 5, default 3)\n"
            "- player_speed: integer (e.g. 150 to 400, default 240)\n"
            "- player_attack_cooldown: float (e.g. 0.2 to 1.5, default 0.5)\n"
            "- enemy_hp: integer (e.g. 1 to 20, default 1)\n"
            "- enemy_speed_min: integer (e.g. 50 to 150, default 100)\n"
            "- enemy_speed_max: integer (e.g. 150 to 300, default 220)\n"
            "- enemy_spawn_rate: float (sec between spawns, e.g. 0.3 to 2.0, default 1.0)\n"
            "- time_limit_sec: integer (e.g. 30 to 120, default 60)\n"
            "- base_score_value: integer (e.g. 10 to 100, default 10)\n\n"
            "Quality bar:\n"
            "- If the game is a fast-paced racing game, increase speeds and lower HP.\n"
            "- If the game is a brawl, increase enemy HP and adjust attack cooldowns.\n"
            "- Ensure values provide a fair but challenging experience suitable for a 90-second arcade game."
        )

    @staticmethod
    def _fallback_game_config() -> _GameConfigModel:
        return _GameConfigModel()

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
