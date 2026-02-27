from __future__ import annotations

from app.core.config import Settings
from app.services.publisher_service import PublisherService


def _make_service_stub() -> PublisherService:
    service = PublisherService.__new__(PublisherService)
    service.settings = Settings()
    service.client = None
    return service


def test_normalize_storage_path_accepts_games_prefix() -> None:
    assert PublisherService._normalize_storage_path("games/neon-run/index.html", "neon-run") == "neon-run/index.html"


def test_normalize_storage_path_rejects_other_slug() -> None:
    try:
        PublisherService._normalize_storage_path("games/other-run/index.html", "neon-run")
    except ValueError as exc:
        assert "outside game slug prefix" in str(exc)
    else:
        raise AssertionError("expected ValueError for mismatched slug")


def test_normalize_artifact_files_falls_back_to_html_when_missing() -> None:
    service = _make_service_stub()
    rows = service._normalize_artifact_files(slug="neon-run", html_content="<html>ok</html>", artifact_files=None)

    assert rows == [
        {
            "storage_path": "neon-run/index.html",
            "content": "<html>ok</html>",
            "content_type": "text/html; charset=utf-8",
        }
    ]


def test_normalize_artifact_files_applies_content_type_guess() -> None:
    service = _make_service_stub()
    rows = service._normalize_artifact_files(
        slug="neon-run",
        html_content="<html>fallback</html>",
        artifact_files=[
            {"path": "games/neon-run/index.html", "content": "<html>index</html>"},
            {"path": "games/neon-run/game.js", "content": "console.log(1);"},
            {"path": "games/neon-run/styles.css", "content": "body{}"},
            {"path": "games/neon-run/empty.txt", "content": ""},
        ],
    )

    assert rows == [
        {
            "storage_path": "neon-run/index.html",
            "content": "<html>index</html>",
            "content_type": "text/html; charset=utf-8",
        },
        {
            "storage_path": "neon-run/game.js",
            "content": "console.log(1);",
            "content_type": "application/javascript; charset=utf-8",
        },
        {
            "storage_path": "neon-run/styles.css",
            "content": "body{}",
            "content_type": "text/css; charset=utf-8",
        },
    ]


def test_resolve_public_url_returns_none_for_non_string() -> None:
    class FakeBucket:
        def get_public_url(self, _path: str):
            return {"url": "https://example.com/not-string"}

    assert PublisherService._resolve_public_url(FakeBucket(), "neon-run/index.html") is None
