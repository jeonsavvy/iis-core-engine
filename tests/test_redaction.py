from app.services.redaction import redact_sensitive_data


def test_redaction_masks_tokens_emails_and_phone() -> None:
    payload = {
        "authorization": "Bearer abcdefghijklmnopqrstuvwxyz",
        "api_key": "abc123",
        "text": "contact me at test.user@example.com or +1-202-555-0123",
    }

    sanitized = redact_sensitive_data(payload)

    assert sanitized["authorization"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert "example.com" not in sanitized["text"]
    assert "+1-202-555-0123" not in sanitized["text"]
    assert "[REDACTED]" in sanitized["text"]


def test_redaction_masks_nested_sensitive_keys() -> None:
    payload = {
        "metadata": {
            "nested": {
                "secret": "value",
                "token_value": "sensitive",
                "safe": "ok",
            }
        }
    }

    sanitized = redact_sensitive_data(payload)

    nested = sanitized["metadata"]["nested"]
    assert nested["secret"] == "[REDACTED]"
    assert nested["token_value"] == "[REDACTED]"
    assert nested["safe"] == "ok"
