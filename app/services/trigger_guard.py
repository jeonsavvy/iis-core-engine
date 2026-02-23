from __future__ import annotations

import hashlib
import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1F\x7F]")
_ASCII_SLUG_RE = re.compile(r"[^a-z0-9]+")


def normalize_keyword(keyword: str) -> str:
    normalized = unicodedata.normalize("NFKC", keyword)
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
    return normalized


def make_safe_slug(keyword: str) -> str:
    slug = _ASCII_SLUG_RE.sub("-", keyword.lower()).strip("-")
    digest = hashlib.sha1(keyword.encode("utf-8")).hexdigest()[:12]

    if slug:
        slug = slug[:80]
        # Avoid low-entropy slugs such as "3d" from non-ASCII prompts.
        if len(slug) < 4:
            return f"{slug}-{digest[:6]}"
        return slug

    return f"game-{digest}"


def validate_keyword(
    keyword: str,
    *,
    forbidden_terms: set[str] | None = None,
    min_length: int = 1,
    max_length: int = 200,
) -> tuple[str, str]:
    normalized = normalize_keyword(keyword)

    if len(normalized) < min_length:
        raise ValueError("keyword_too_short")
    if len(normalized) > max_length:
        raise ValueError("keyword_too_long")
    if _CONTROL_CHAR_RE.search(normalized):
        raise ValueError("keyword_contains_control_characters")

    lowered = normalized.casefold()
    for term in forbidden_terms or set():
        term_stripped = term.strip().casefold()
        if not term_stripped:
            continue
        if term_stripped in lowered:
            raise ValueError("keyword_contains_blocked_term")

    slug = make_safe_slug(normalized)
    if not slug:
        raise ValueError("keyword_slug_generation_failed")

    return normalized, slug
