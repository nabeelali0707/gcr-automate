from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx


@dataclass(frozen=True)
class InlineButton:
    label: str
    callback_data: str


@dataclass(frozen=True)
class TelegramMessage:
    text: str
    buttons: tuple[InlineButton, ...]


def digest_ready_message(
    *,
    assignment_title: str,
    course_name: str,
    due_at: datetime,
    agent_run_id: str,
) -> TelegramMessage:
    text = f"{assignment_title} for {course_name} is due {due_at.isoformat()}. Digest and scaffold are ready."
    return TelegramMessage(
        text=text,
        buttons=(
            InlineButton("View Digest", f"digest:{agent_run_id}"),
            InlineButton("Get Scaffold", f"scaffold:{agent_run_id}"),
            InlineButton("Ignore", f"ignore:{agent_run_id}"),
        ),
    )


def ready_to_submit_message(*, assignment_title: str, agent_run_id: str) -> TelegramMessage:
    return TelegramMessage(
        text=f"{assignment_title} has user-uploaded files ready for submission.",
        buttons=(
            InlineButton("Submit", f"submit:{agent_run_id}"),
            InlineButton("View Files", f"files:{agent_run_id}"),
            InlineButton("Cancel", f"cancel:{agent_run_id}"),
        ),
    )


class TelegramBotClient:
    def __init__(self, token: str) -> None:
        self.base_url = f"https://api.telegram.org/bot{token}"

    async def send_message(self, chat_id: str, message: TelegramMessage) -> dict:
        payload = {
            "chat_id": chat_id,
            "text": message.text,
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": button.label, "callback_data": button.callback_data}]
                    for button in message.buttons
                ]
            },
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(f"{self.base_url}/sendMessage", json=payload)
            response.raise_for_status()
            return response.json()
