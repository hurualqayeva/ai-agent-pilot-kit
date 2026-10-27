import json
from pathlib import Path

from app.telegram import parse_update

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def load(name: str) -> dict:
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


def test_text_message_is_parsed():
    message = parse_update(load("telegram_text_message.json"))
    assert message.chat_id == 555000111
    assert message.update_id == 900000101
    assert "Pechersk" in message.text


def test_edited_and_voice_messages_are_skipped():
    assert parse_update(load("telegram_edited_message.json")) is None
    assert parse_update(load("telegram_voice_message.json")) is None


def test_messages_from_bots_are_skipped():
    payload = load("telegram_text_message.json")
    payload["message"]["from"]["is_bot"] = True
    assert parse_update(payload) is None
