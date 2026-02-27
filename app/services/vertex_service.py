from __future__ import annotations

import json
import logging
import os
from typing import Any

from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from app.core.config import Settings
from app.services.vertex_models import GameConfigModel
from app.services.vertex_prompts import (
    build_builder_prompt,
    build_design_prompt,
    build_gdd_prompt,
)
from app.services.vertex_structured_generation import (
    generate_design_spec as generate_design_spec_bundle,
    generate_game_config as generate_game_config_bundle,
    generate_gdd_bundle as generate_gdd_bundle_bundle,
)
from app.services.vertex_text_generation import (
    generate_ai_review as generate_ai_review_text,
    generate_codegen_candidate_artifact as generate_codegen_candidate_artifact_text,
    generate_grounded_ai_review as generate_grounded_ai_review_text,
    generate_marketing_copy as generate_marketing_copy_text,
    polish_hybrid_artifact as polish_hybrid_artifact_text,
)
from app.services.vertex_text_utils import strip_code_fences
from app.services.vertex_types import VertexGenerationResult

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
        self._builder_llm = None
        self._genai_client = None

    def generate_gdd_bundle(self, keyword: str) -> VertexGenerationResult:
        return generate_gdd_bundle_bundle(self, keyword)

    def generate_design_spec(self, *, keyword: str, visual_style: str, genre: str) -> VertexGenerationResult:
        return generate_design_spec_bundle(
            self,
            keyword=keyword,
            visual_style=visual_style,
            genre=genre,
        )

    def generate_game_config(
        self,
        *,
        keyword: str,
        title: str,
        genre: str,
        objective: str,
        design_spec: dict[str, Any],
        variation_hint: str | None = None,
    ) -> VertexGenerationResult:
        return generate_game_config_bundle(
            self,
            keyword=keyword,
            title=title,
            genre=genre,
            objective=objective,
            design_spec=design_spec,
            variation_hint=variation_hint,
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

    def _builder_model_name(self) -> str:
        configured = str(self.settings.gemini_pro_model or "").strip()
        fallback = "gemini-2.5-pro"
        if not configured:
            return fallback
        if self.settings.builder_force_pro_model and "flash" in configured.casefold():
            logger.warning("BUILDER_FORCE_PRO_MODEL enabled, but GEMINI_PRO_MODEL points to flash model: %s", configured)
            return fallback
        return configured

    def _builder_model(self):
        if self._builder_llm is None:
            self._builder_llm = self._build_model(self._builder_model_name(), temperature=0.4)
        return self._builder_llm

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
        text = strip_code_fences(self._coerce_genai_text(response))
        if not text:
            raise ValueError("empty_json_response")
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("json_response_not_object")
        return parsed, usage

    def _genai_text(
        self,
        *,
        model_name: str,
        prompt: str,
        temperature: float,
        max_output_tokens: int | None = None,
    ) -> tuple[str, dict[str, int]]:
        if genai_types is None:  # pragma: no cover - import guard
            raise RuntimeError("google_genai types are not available")
        config_kwargs: dict[str, Any] = {
            "temperature": temperature,
            "response_mime_type": "text/plain",
        }
        if isinstance(max_output_tokens, int) and max_output_tokens > 0:
            config_kwargs["max_output_tokens"] = max_output_tokens
        response = self._genai_generate_with_retry(
            model_name=model_name,
            prompt=prompt,
            config=genai_types.GenerateContentConfig(**config_kwargs),
        )
        usage = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = {
                "prompt_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
                "completion_tokens": getattr(response.usage_metadata, "candidates_token_count", 0),
                "total_tokens": getattr(response.usage_metadata, "total_token_count", 0),
            }
        return strip_code_fences(self._coerce_genai_text(response)), usage

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
        return build_gdd_prompt(keyword)

    @staticmethod
    def _design_prompt(*, keyword: str, visual_style: str, genre: str) -> str:
        return build_design_prompt(keyword=keyword, visual_style=visual_style, genre=genre)

    def generate_marketing_copy(
        self,
        *,
        keyword: str,
        slug: str,
        genre: str,
        game_name: str | None = None,
    ) -> VertexGenerationResult:
        return generate_marketing_copy_text(
            self,
            keyword=keyword,
            slug=slug,
            genre=genre,
            game_name=game_name,
        )

    def generate_ai_review(
        self,
        *,
        keyword: str,
        game_name: str,
        genre: str,
        objective: str,
    ) -> VertexGenerationResult:
        return generate_ai_review_text(
            self,
            keyword=keyword,
            game_name=game_name,
            genre=genre,
            objective=objective,
        )

    def generate_grounded_ai_review(
        self,
        *,
        keyword: str,
        game_name: str,
        genre: str,
        objective: str,
        evidence: dict[str, Any],
    ) -> VertexGenerationResult:
        return generate_grounded_ai_review_text(
            self,
            keyword=keyword,
            game_name=game_name,
            genre=genre,
            objective=objective,
            evidence=evidence,
        )

    def generate_codegen_candidate_artifact(
        self,
        *,
        keyword: str,
        title: str,
        genre: str,
        objective: str,
        core_loop_type: str,
        variation_hint: str,
        design_spec: dict[str, Any],
        asset_pack: dict[str, Any],
        html_content: str,
    ) -> VertexGenerationResult:
        return generate_codegen_candidate_artifact_text(
            self,
            keyword=keyword,
            title=title,
            genre=genre,
            objective=objective,
            core_loop_type=core_loop_type,
            variation_hint=variation_hint,
            design_spec=design_spec,
            asset_pack=asset_pack,
            html_content=html_content,
        )

    def polish_hybrid_artifact(
        self,
        *,
        keyword: str,
        title: str,
        genre: str,
        html_content: str,
    ) -> VertexGenerationResult:
        return polish_hybrid_artifact_text(
            self,
            keyword=keyword,
            title=title,
            genre=genre,
            html_content=html_content,
        )

    @staticmethod
    def _builder_prompt(
        *,
        keyword: str,
        title: str,
        genre: str,
        objective: str,
        design_spec: dict[str, Any],
        variation_hint: str | None = None,
    ) -> str:
        return build_builder_prompt(
            keyword=keyword,
            title=title,
            genre=genre,
            objective=objective,
            design_spec=design_spec,
            variation_hint=variation_hint,
        )

    @staticmethod
    def _fallback_game_config() -> GameConfigModel:
        return GameConfigModel()

    @staticmethod
    def _model_to_dict(model: Any) -> dict[str, Any]:
        model_dump = getattr(model, "model_dump", None)
        if callable(model_dump):
            payload = model_dump()
        else:
            legacy_dict = getattr(model, "dict", None)
            if callable(legacy_dict):
                payload = legacy_dict()
            elif isinstance(model, dict):
                payload = model
            else:
                payload = dict(model)
        return payload if isinstance(payload, dict) else dict(payload)

    @staticmethod
    def _fallback_gdd_bundle(keyword: str, *, reason: str) -> VertexGenerationResult:
        keyword_title = keyword.title()
        research_summary = {
            "intent": f"{keyword} 기반 코어 플레이 루프 아이디어 수집",
            "references": [
                f"{keyword} + score-attack progression",
                f"{keyword} + multi-minute run pacing curve",
                f"{keyword} + mobile-friendly HUD readability",
            ],
        }
        gdd = {
            "title": f"{keyword_title} Infinite",
            "genre": "arcade",
            "objective": "Survive escalating pressure while chaining skill actions for a high score.",
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
