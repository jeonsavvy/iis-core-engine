"""Sensitive data redaction helpers.

Always-redacted policy for API responses, persistence payloads, and logs.
"""

from __future__ import annotations

import re
from typing import Any

_REPLACEMENT = "[REDACTED]"

_TOKEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(bearer\s+)[a-z0-9._\-+/=]{8,}"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password|passwd)\b\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)\b(authorization)\b\s*[:=]\s*[^\s,;]+"),
)

_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4}\b")

_SENSITIVE_KEYWORDS = {
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "secret",
    "password",
    "authorization",
    "bearer",
    "system_prompt",
    "prompt_template",
    "private_key",
    "service_role_key",
    "phone",
    "email",
}


def _redact_string(value: str) -> str:
    redacted = value
    for pattern in _TOKEN_PATTERNS:
        redacted = pattern.sub(lambda m: f"{m.group(1) if m.lastindex else ''}{_REPLACEMENT}".strip(), redacted)

    redacted = _EMAIL_PATTERN.sub(_REPLACEMENT, redacted)
    redacted = _PHONE_PATTERN.sub(_REPLACEMENT, redacted)
    return redacted


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower()
    return normalized in _SENSITIVE_KEYWORDS or any(token in normalized for token in ("token", "secret", "password", "api_key", "apikey", "authorization"))


def redact_sensitive_data(value: Any) -> Any:
    """Recursively redact sensitive data from common payload structures."""
    if isinstance(value, str):
        return _redact_string(value)

    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            if _is_sensitive_key(key_str):
                sanitized[key_str] = _REPLACEMENT
            else:
                sanitized[key_str] = redact_sensitive_data(item)
        return sanitized

    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]

    if isinstance(value, tuple):
        return tuple(redact_sensitive_data(item) for item in value)

    if isinstance(value, set):
        return {redact_sensitive_data(item) for item in value}

    return value
