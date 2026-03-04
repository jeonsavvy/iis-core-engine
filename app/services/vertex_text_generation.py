from __future__ import annotations

import logging
import time
from typing import Any, Protocol

from app.core.config import Settings
from app.services.vertex_fallback_text import (
    build_ai_review_fallback,
    build_grounded_ai_review_fallback,
    build_marketing_fallback_copy,
)
from app.services.vertex_prompts import (
    build_ai_review_prompt,
    build_codegen_prompt,
    build_grounded_ai_review_prompt,
    build_marketing_copy_prompt,
    build_polish_prompt,
)
from app.services.vertex_text_utils import (
    compile_generated_artifact,
    coerce_message_text,
    looks_like_playable_artifact,
    playable_artifact_missing_requirements,
    strip_code_fences,
)
from app.services.vertex_types import VertexGenerationResult

logger = logging.getLogger(__name__)


class VertexTextGenerationClient(Protocol):
    settings: Settings

    def _is_enabled(self) -> bool: ...

    def _use_genai_sdk(self) -> bool: ...

    def _genai_text(
        self,
        *,
        model_name: str,
        prompt: str,
        temperature: float,
        max_output_tokens: int | None = None,
    ) -> tuple[str, dict[str, int]]: ...

    def _flash_model(self): ...

    def _builder_model(self): ...

    def _builder_model_name(self) -> str: ...


def generate_marketing_copy(
    service: VertexTextGenerationClient,
    *,
    keyword: str,
    slug: str,
    genre: str,
    game_name: str | None = None,
) -> VertexGenerationResult:
    display_name = (game_name or "").strip() or slug
    if not service._is_enabled():
        fallback_text = build_marketing_fallback_copy(
            display_name=display_name,
            keyword=keyword,
            genre=genre,
        )
        return VertexGenerationResult(
            payload={"marketing_copy": fallback_text},
            meta={"generation_source": "stub", "reason": "vertex_not_configured"},
        )
    prompt = build_marketing_copy_prompt(keyword=keyword, display_name=display_name, genre=genre)
    started = time.perf_counter()
    try:
        usage: dict[str, Any] = {}
        if service._use_genai_sdk():
            text, usage = service._genai_text(
                model_name=service.settings.gemini_flash_model,
                prompt=prompt,
                temperature=0.7,
            )
        else:
            model = service._flash_model()
            from langchain_core.messages import HumanMessage

            result = model.invoke([HumanMessage(content=prompt)])
            text = strip_code_fences(coerce_message_text(result.content))
        latency_ms = int((time.perf_counter() - started) * 1000)
        return VertexGenerationResult(
            payload={"marketing_copy": text},
            meta={
                "generation_source": "vertex",
                "model": service.settings.gemini_flash_model,
                "latency_ms": latency_ms,
                "usage": usage,
            },
        )
    except Exception as exc:
        logger.warning("Vertex marketing generation failed: %s", exc)
        fallback_text = build_marketing_fallback_copy(
            display_name=display_name,
            keyword=keyword,
            genre=genre,
        )
        return VertexGenerationResult(
            payload={"marketing_copy": fallback_text},
            meta={
                "generation_source": "stub",
                "reason": f"vertex_error:{type(exc).__name__}",
                "vertex_error": str(exc),
            },
        )


def generate_ai_review(
    service: VertexTextGenerationClient,
    *,
    keyword: str,
    game_name: str,
    genre: str,
    objective: str,
) -> VertexGenerationResult:
    if not service._is_enabled():
        fallback_text = build_ai_review_fallback(
            keyword=keyword,
            game_name=game_name,
            genre=genre,
            objective=objective,
        )
        return VertexGenerationResult(
            payload={"ai_review": fallback_text},
            meta={"generation_source": "stub", "reason": "vertex_not_configured"},
        )
    prompt = build_ai_review_prompt(
        keyword=keyword,
        game_name=game_name,
        genre=genre,
        objective=objective,
    )
    started = time.perf_counter()
    try:
        usage: dict[str, Any] = {}
        if service._use_genai_sdk():
            text, usage = service._genai_text(
                model_name=service.settings.gemini_flash_model,
                prompt=prompt,
                temperature=0.5,
            )
        else:
            model = service._flash_model()
            from langchain_core.messages import HumanMessage

            result = model.invoke([HumanMessage(content=prompt)])
            text = strip_code_fences(coerce_message_text(result.content))
        latency_ms = int((time.perf_counter() - started) * 1000)
        return VertexGenerationResult(
            payload={"ai_review": text},
            meta={
                "generation_source": "vertex",
                "model": service.settings.gemini_flash_model,
                "latency_ms": latency_ms,
                "usage": usage,
            },
        )
    except Exception as exc:
        logger.warning("Vertex AI review generation failed: %s", exc)
        fallback_text = build_ai_review_fallback(
            keyword=keyword,
            game_name=game_name,
            genre=genre,
            objective=objective,
        )
        return VertexGenerationResult(
            payload={"ai_review": fallback_text},
            meta={
                "generation_source": "stub",
                "reason": f"vertex_error:{type(exc).__name__}",
                "vertex_error": str(exc),
            },
        )


def generate_grounded_ai_review(
    service: VertexTextGenerationClient,
    *,
    keyword: str,
    game_name: str,
    genre: str,
    objective: str,
    evidence: dict[str, Any],
) -> VertexGenerationResult:
    if not service._is_enabled():
        fallback_text = build_grounded_ai_review_fallback(
            objective=objective,
            evidence=evidence,
        )
        return VertexGenerationResult(
            payload={"ai_review": fallback_text},
            meta={"generation_source": "stub", "reason": "vertex_not_configured"},
        )
    prompt = build_grounded_ai_review_prompt(
        keyword=keyword,
        game_name=game_name,
        genre=genre,
        objective=objective,
        evidence=evidence,
    )
    started = time.perf_counter()
    try:
        usage: dict[str, Any] = {}
        if service._use_genai_sdk():
            text, usage = service._genai_text(
                model_name=service.settings.gemini_flash_model,
                prompt=prompt,
                temperature=0.35,
                max_output_tokens=1024,
            )
        else:
            model = service._flash_model()
            from langchain_core.messages import HumanMessage

            result = model.invoke([HumanMessage(content=prompt)])
            text = strip_code_fences(coerce_message_text(result.content))
        normalized = text.strip()
        if not normalized:
            raise ValueError("empty_grounded_review")
        latency_ms = int((time.perf_counter() - started) * 1000)
        return VertexGenerationResult(
            payload={"ai_review": normalized},
            meta={
                "generation_source": "vertex",
                "model": service.settings.gemini_flash_model,
                "latency_ms": latency_ms,
                "usage": usage,
            },
        )
    except Exception as exc:
        logger.warning("Vertex grounded review generation failed: %s", exc)
        fallback_text = build_grounded_ai_review_fallback(
            objective=objective,
            evidence=evidence,
        )
        return VertexGenerationResult(
            payload={"ai_review": fallback_text},
            meta={
                "generation_source": "stub",
                "reason": f"vertex_error:{type(exc).__name__}",
                "vertex_error": str(exc),
            },
        )


def generate_codegen_candidate_artifact(
    service: VertexTextGenerationClient,
    *,
    keyword: str,
    title: str,
    genre: str,
    objective: str,
    core_loop_type: str,
    runtime_engine_mode: str,
    variation_hint: str,
    design_spec: dict[str, Any],
    asset_pack: dict[str, Any],
    intent_contract: dict[str, Any] | None,
    synapse_contract: dict[str, Any] | None,
    shared_generation_contract: dict[str, Any] | None,
    html_content: str,
) -> VertexGenerationResult:
    if not service.settings.builder_codegen_enabled:
        return VertexGenerationResult(
            payload={"artifact_html": ""},
            meta={"generation_source": "stub", "reason": "builder_codegen_disabled"},
        )
    if not service._is_enabled():
        return VertexGenerationResult(
            payload={"artifact_html": ""},
            meta={"generation_source": "stub", "reason": "vertex_not_configured"},
        )

    prompt = build_codegen_prompt(
        keyword=keyword,
        title=title,
        genre=genre,
        objective=objective,
        core_loop_type=core_loop_type,
        runtime_engine_mode=runtime_engine_mode,
        variation_hint=variation_hint,
        design_spec=design_spec,
        asset_pack=asset_pack,
        intent_contract=intent_contract,
        synapse_contract=synapse_contract,
        shared_generation_contract=shared_generation_contract,
        html_content=html_content,
    )
    started = time.perf_counter()
    builder_model = service._builder_model_name()
    try:
        usage: dict[str, Any] = {}
        if service._use_genai_sdk():
            generated_html, usage = service._genai_text(
                model_name=builder_model,
                prompt=prompt,
                temperature=0.42,
                max_output_tokens=service.settings.builder_codegen_max_output_tokens,
            )
        else:
            model = service._builder_model()
            from langchain_core.messages import HumanMessage

            result = model.invoke([HumanMessage(content=prompt)])
            generated_html = strip_code_fences(coerce_message_text(result.content))

        normalized = generated_html.strip()
        compiled_artifact, compile_meta = compile_generated_artifact(normalized)
        if not looks_like_playable_artifact(compiled_artifact):
            missing_requirements = playable_artifact_missing_requirements(compiled_artifact)
            detail = ",".join(missing_requirements[:8]) if missing_requirements else "unknown"
            raise ValueError(f"invalid_codegen_artifact:{detail}")

        latency_ms = int((time.perf_counter() - started) * 1000)
        return VertexGenerationResult(
            payload={"artifact_html": compiled_artifact},
            meta={
                "generation_source": "vertex",
                "model": builder_model,
                "latency_ms": latency_ms,
                "usage": usage,
                "model_name": builder_model,
                "max_output_tokens": service.settings.builder_codegen_max_output_tokens,
                "prompt_contract_version": "synapse_visual_v3",
                "runtime_compiler": compile_meta,
            },
        )
    except Exception as exc:
        logger.warning("Vertex codegen artifact generation failed: %s", exc)
        validation_failures: list[str] = []
        if isinstance(exc, ValueError):
            text = str(exc)
            if text.startswith("invalid_codegen_artifact:"):
                raw_items = text.split(":", 1)[1]
                validation_failures = [item.strip() for item in raw_items.split(",") if item.strip()]
        return VertexGenerationResult(
            payload={"artifact_html": ""},
            meta={
                "generation_source": "stub",
                "reason": f"vertex_error:{type(exc).__name__}",
                "vertex_error": str(exc),
                "model": builder_model,
                "validation_failures": validation_failures,
                "model_name": builder_model,
                "max_output_tokens": service.settings.builder_codegen_max_output_tokens,
                "prompt_contract_version": "synapse_visual_v3",
            },
        )


def polish_hybrid_artifact(
    service: VertexTextGenerationClient,
    *,
    keyword: str,
    title: str,
    genre: str,
    html_content: str,
) -> VertexGenerationResult:
    if not service._is_enabled():
        return VertexGenerationResult(
            payload={"artifact_html": ""},
            meta={"generation_source": "stub", "reason": "vertex_not_configured"},
        )

    prompt = build_polish_prompt(
        keyword=keyword,
        title=title,
        genre=genre,
        html_content=html_content,
    )
    started = time.perf_counter()
    builder_model = service._builder_model_name()
    try:
        usage: dict[str, Any] = {}
        if service._use_genai_sdk():
            polished_html, usage = service._genai_text(
                model_name=builder_model,
                prompt=prompt,
                temperature=0.35,
                max_output_tokens=service.settings.builder_codegen_max_output_tokens,
            )
        else:
            model = service._builder_model()
            from langchain_core.messages import HumanMessage

            result = model.invoke([HumanMessage(content=prompt)])
            polished_html = strip_code_fences(coerce_message_text(result.content))

        if not polished_html.strip():
            raise ValueError("empty_polish_result")

        latency_ms = int((time.perf_counter() - started) * 1000)
        return VertexGenerationResult(
            payload={"artifact_html": polished_html},
            meta={
                "generation_source": "vertex",
                "model": builder_model,
                "latency_ms": latency_ms,
                "usage": usage,
            },
        )
    except Exception as exc:
        logger.warning("Vertex artifact polish failed: %s", exc)
        return VertexGenerationResult(
            payload={"artifact_html": ""},
            meta={
                "generation_source": "stub",
                "reason": f"vertex_error:{type(exc).__name__}",
                "vertex_error": str(exc),
                "model": builder_model,
            },
        )
