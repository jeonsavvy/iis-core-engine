from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential


class ExternalCallError(RuntimeError):
    """Raised when external API requests fail after retries."""


def _method_allows_retry(method: str, headers: dict[str, str] | None) -> bool:
    normalized_method = method.strip().upper()
    if normalized_method in {"GET", "HEAD", "OPTIONS"}:
        return True

    if normalized_method != "POST" or not headers:
        return False

    for key, value in headers.items():
        if key.lower() != "idempotency-key":
            continue
        if value.strip():
            return True
    return False


def _is_retryable_http_error(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return bool(exc.response.status_code == 429 or exc.response.status_code >= 500)

    return isinstance(
        exc,
        (
            httpx.ConnectError,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.RemoteProtocolError,
            httpx.PoolTimeout,
        ),
    )


def request_with_retry(
    method: str,
    url: str,
    *,
    timeout_seconds: float,
    max_retries: int,
    headers: dict[str, str] | None = None,
    json: dict[str, Any] | None = None,
) -> httpx.Response:
    normalized_max_retries = max(1, int(max_retries))
    attempt_limit = normalized_max_retries if _method_allows_retry(method, headers) else 1

    @retry(
        reraise=True,
        stop=stop_after_attempt(attempt_limit),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception(_is_retryable_http_error),
    )
    def _do_request() -> httpx.Response:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.request(method=method, url=url, headers=headers, json=json)
            if response.status_code == 429 or response.status_code >= 500:
                raise httpx.HTTPStatusError(
                    f"{method} {url} failed with server error {response.status_code}",
                    request=response.request,
                    response=response,
                )
            response.raise_for_status()
            return response

    try:
        return _do_request()
    except httpx.HTTPError as exc:  # pragma: no cover - exercised in integration runtime
        raise ExternalCallError(f"{method} {url} failed: {exc}") from exc
