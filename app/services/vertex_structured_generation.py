from __future__ import annotations

import logging
import time
from typing import Any, Protocol

from app.core.config import Settings
from app.services.vertex_models import DesignSpecModel, GDDModel, GameConfigModel
from app.services.vertex_types import VertexGenerationResult

logger = logging.getLogger(__name__)


class VertexStructuredGenerationClient(Protocol):
    settings: Settings

    def _is_enabled(self) -> bool: ...

    def _use_genai_sdk(self) -> bool: ...

    def _genai_json(
        self,
        *,
        model_name: str,
        prompt: str,
        schema: type[Any],
        temperature: float,
    ) -> tuple[dict[str, Any], dict[str, int]]: ...

    def _pro_model(self): ...

    def _builder_model(self): ...

    def _builder_model_name(self) -> str: ...

    def _invoke_with_retry(self, runnable: Any, prompt: str) -> Any: ...

    def _gdd_prompt(self, keyword: str) -> str: ...

    def _design_prompt(self, *, keyword: str, visual_style: str, genre: str) -> str: ...

    def _builder_prompt(
        self,
        *,
        keyword: str,
        title: str,
        genre: str,
        objective: str,
        design_spec: dict[str, Any],
        variation_hint: str | None = None,
    ) -> str: ...

    def _fallback_gdd_bundle(self, keyword: str, *, reason: str) -> VertexGenerationResult: ...

    def _fallback_design_spec(self, *, visual_style: str, reason: str = "vertex_not_configured") -> VertexGenerationResult: ...

    def _fallback_game_config(self) -> GameConfigModel: ...

    def _model_to_dict(self, model: Any) -> dict[str, Any]: ...


def generate_gdd_bundle(service: VertexStructuredGenerationClient, keyword: str) -> VertexGenerationResult:
    fallback = service._fallback_gdd_bundle(keyword, reason="vertex_not_configured")
    if not service._is_enabled():
        return fallback

    started = time.perf_counter()
    try:
        prompt = service._gdd_prompt(keyword)
        usage: dict[str, Any] = {}
        if service._use_genai_sdk():
            raw, usage = service._genai_json(
                model_name=service.settings.gemini_pro_model,
                prompt=prompt,
                schema=GDDModel,
                temperature=0.4,
            )
        else:
            model = service._pro_model()
            runnable = model.with_structured_output(GDDModel, method="json_mode")
            raw = service._invoke_with_retry(runnable, prompt)
        parsed = raw if isinstance(raw, GDDModel) else GDDModel.model_validate(raw)
        latency_ms = int((time.perf_counter() - started) * 1000)

        references = parsed.references[:3] or [
            f"{keyword} + score-attack progression",
            f"{keyword} + multi-minute run pacing curve",
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
                "model": service.settings.gemini_pro_model,
                "latency_ms": latency_ms,
                "usage": usage,
            },
        )
    except Exception as exc:  # pragma: no cover - external API path
        logger.warning("Vertex GDD generation failed, using fallback: %s", exc)
        failed = service._fallback_gdd_bundle(keyword, reason=f"vertex_error:{type(exc).__name__}")
        return VertexGenerationResult(
            payload=failed.payload,
            meta={
                **failed.meta,
                "vertex_error": str(exc),
                "model": service.settings.gemini_pro_model,
            },
        )


def generate_design_spec(
    service: VertexStructuredGenerationClient,
    *,
    keyword: str,
    visual_style: str,
    genre: str,
) -> VertexGenerationResult:
    fallback = service._fallback_design_spec(visual_style=visual_style)
    if not service._is_enabled():
        return fallback

    started = time.perf_counter()
    try:
        prompt = service._design_prompt(keyword=keyword, visual_style=visual_style, genre=genre)
        usage: dict[str, Any] = {}
        if service._use_genai_sdk():
            raw, usage = service._genai_json(
                model_name=service.settings.gemini_pro_model,
                prompt=prompt,
                schema=DesignSpecModel,
                temperature=0.3,
            )
        else:
            model = service._pro_model()
            runnable = model.with_structured_output(DesignSpecModel, method="json_mode")
            raw = service._invoke_with_retry(runnable, prompt)
        parsed = raw if isinstance(raw, DesignSpecModel) else DesignSpecModel.model_validate(raw)
        latency_ms = int((time.perf_counter() - started) * 1000)
        return VertexGenerationResult(
            payload=parsed.model_dump(),
            meta={
                "generation_source": "vertex",
                "model": service.settings.gemini_pro_model,
                "latency_ms": latency_ms,
                "usage": usage,
            },
        )
    except Exception as exc:  # pragma: no cover - external API path
        logger.warning("Vertex design generation failed, using fallback: %s", exc)
        failed = service._fallback_design_spec(visual_style=visual_style, reason=f"vertex_error:{type(exc).__name__}")
        return VertexGenerationResult(
            payload=failed.payload,
            meta={
                **failed.meta,
                "vertex_error": str(exc),
                "model": service.settings.gemini_pro_model,
            },
        )


def generate_game_config(
    service: VertexStructuredGenerationClient,
    *,
    keyword: str,
    title: str,
    genre: str,
    objective: str,
    design_spec: dict[str, Any],
    variation_hint: str | None = None,
) -> VertexGenerationResult:
    if not service._is_enabled():
        fallback_payload = service._model_to_dict(service._fallback_game_config())
        return VertexGenerationResult(
            payload=fallback_payload,
            meta={"generation_source": "stub", "reason": "vertex_not_configured"},
        )

    started = time.perf_counter()
    builder_model = service._builder_model_name()
    try:
        prompt = service._builder_prompt(
            keyword=keyword,
            title=title,
            genre=genre,
            objective=objective,
            design_spec=design_spec,
            variation_hint=variation_hint,
        )
        usage: dict[str, Any] = {}
        if service._use_genai_sdk():
            raw, usage = service._genai_json(
                model_name=builder_model,
                prompt=prompt,
                schema=GameConfigModel,
                temperature=0.3,
            )
        else:
            model = service._builder_model()
            runnable = model.with_structured_output(GameConfigModel, method="json_mode")
            raw = service._invoke_with_retry(runnable, prompt)
        parsed = raw if isinstance(raw, GameConfigModel) else GameConfigModel.model_validate(raw)
        latency_ms = int((time.perf_counter() - started) * 1000)

        return VertexGenerationResult(
            payload=parsed.model_dump(),
            meta={
                "generation_source": "vertex",
                "model": builder_model,
                "latency_ms": latency_ms,
                "usage": usage,
            },
        )
    except Exception as exc:  # pragma: no cover - external API path
        logger.warning("Vertex config generation failed, using fallback: %s", exc)
        fallback_payload = service._model_to_dict(service._fallback_game_config())
        return VertexGenerationResult(
            payload=fallback_payload,
            meta={
                "generation_source": "stub",
                "reason": f"vertex_error:{type(exc).__name__}",
                "vertex_error": str(exc),
                "model": builder_model,
            },
        )
