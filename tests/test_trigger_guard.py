from app.services.trigger_guard import make_safe_slug, validate_keyword


def test_validate_keyword_normalizes_and_builds_slug() -> None:
    normalized, slug = validate_keyword("  neon   puzzle  ")

    assert normalized == "neon puzzle"
    assert slug == "neon-puzzle"


def test_validate_keyword_blocks_forbidden_term() -> None:
    try:
        validate_keyword("secret dungeon", forbidden_terms={"secret"})
    except ValueError as exc:
        assert str(exc) == "keyword_contains_blocked_term"
        return

    raise AssertionError("expected ValueError")


def test_make_safe_slug_uses_hash_for_non_ascii_keyword() -> None:
    slug = make_safe_slug("한글 게임")
    assert slug.startswith("game-")
    assert len(slug) == 17
