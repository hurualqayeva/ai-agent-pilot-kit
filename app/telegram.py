"""Telegram Bot API: read a webhook update, send a reply."""

import logging
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)


@dataclass
class IncomingMessage:
    chat_id: int
    text: str
    update_id: int


def parse_update(payload: dict) -> IncomingMessage | None:
    """Return the text message in a Telegram update, or None if there is nothing to answer.

    Skipped on purpose: edited messages, channel posts, stickers/photos/voice,
    and messages from other bots.
    """
    message = payload.get("message")
    if not message or "text" not in message:
        return None
    if message.get("from", {}).get("is_bot"):
        return None
    return IncomingMessage(chat_id=message["chat"]["id"], text=message["text"], update_id=payload["update_id"])


def send_message(token: str, chat_id: int, text: str) -> None:
    if not token:
        log.info("TELEGRAM_BOT_TOKEN not set, reply to %s not sent: %s", chat_id, text)
        return
    response = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=10,
    )
    response.raise_for_status()
