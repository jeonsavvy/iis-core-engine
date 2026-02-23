from typing import Any

from pydantic import BaseModel, Field


class TelegramChat(BaseModel):
    id: int
    type: str | None = None


class TelegramUser(BaseModel):
    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class TelegramMessage(BaseModel):
    message_id: int | None = None
    chat: TelegramChat
    from_user: TelegramUser | None = Field(default=None, alias="from")
    text: str | None = None


class TelegramWebhookUpdate(BaseModel):
    update_id: int | None = None
    message: TelegramMessage | None = None
    edited_message: TelegramMessage | None = None

    def active_message(self) -> TelegramMessage | None:
        return self.message or self.edited_message


class TelegramWebhookResponse(BaseModel):
    ok: bool = True
    status: str
    detail: str | None = None
    pipeline_id: str | None = Field(default=None, description="Set for /run and audit events")
    payload: dict[str, Any] = Field(default_factory=dict)
