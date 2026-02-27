import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def verify_internal_api_token(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> None:
    settings = get_settings()
    expected_token = (settings.internal_api_token or "").strip()

    if not expected_token:
        return

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    provided_token = authorization.split(" ", maxsplit=1)[1].strip()
    if not secrets.compare_digest(provided_token, expected_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")
