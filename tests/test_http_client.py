import httpx

from app.services.http_client import ExternalCallError, request_with_retry


def test_request_with_retry_retries_get_until_success(monkeypatch) -> None:
    attempts = {"count": 0}

    def fake_request(self, method: str, url: str, **_kwargs):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise httpx.ConnectError("temporary network issue")
        request = httpx.Request(method, url)
        return httpx.Response(status_code=200, request=request, text="ok")

    monkeypatch.setattr(httpx.Client, "request", fake_request)

    response = request_with_retry(
        "GET",
        "https://example.test/health",
        timeout_seconds=1,
        max_retries=3,
    )

    assert response.status_code == 200
    assert attempts["count"] == 3


def test_request_with_retry_does_not_retry_post_without_idempotency_key(monkeypatch) -> None:
    attempts = {"count": 0}

    def fake_request(self, method: str, url: str, **_kwargs):
        attempts["count"] += 1
        raise httpx.ConnectError("temporary network issue")

    monkeypatch.setattr(httpx.Client, "request", fake_request)

    try:
        request_with_retry(
            "POST",
            "https://example.test/pipelines/trigger",
            timeout_seconds=1,
            max_retries=3,
            json={"keyword": "neon"},
        )
    except ExternalCallError:
        pass
    else:
        raise AssertionError("expected ExternalCallError")

    assert attempts["count"] == 1


def test_request_with_retry_retries_post_with_idempotency_key(monkeypatch) -> None:
    attempts = {"count": 0}

    def fake_request(self, method: str, url: str, **_kwargs):
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise httpx.ConnectError("temporary network issue")
        request = httpx.Request(method, url)
        return httpx.Response(status_code=200, request=request, text="ok")

    monkeypatch.setattr(httpx.Client, "request", fake_request)

    response = request_with_retry(
        "POST",
        "https://example.test/pipelines/trigger",
        timeout_seconds=1,
        max_retries=3,
        headers={"Idempotency-Key": "idem-post-0001"},
        json={"keyword": "neon"},
    )

    assert response.status_code == 200
    assert attempts["count"] == 2
