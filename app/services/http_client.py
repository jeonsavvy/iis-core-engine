from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class ExternalCallError(RuntimeError):
    """Raised when external API requests fail after retries."""


def request_with_retry(
    method: str,
    url: str,
    *,
    timeout_seconds: float,
    max_retries: int,
    headers: dict[str, str] | None = None,
    json: dict[str, Any] | None = None,
) -> httpx.Response:
    @retry(
        reraise=True,
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    def _do_request() -> httpx.Response:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.request(method=method, url=url, headers=headers, json=json)
            response.raise_for_status()
            return response

    try:
        return _do_request()
    except httpx.HTTPError as exc:  # pragma: no cover - exercised in integration runtime
        raise ExternalCallError(f"{method} {url} failed: {exc}") from exc
