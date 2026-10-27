import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.agent import AgentResult

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


class FakeAgent:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, chat_id, text, vault, history):
        self.calls += 1
        return AgentResult(reply="Here are 1 option: KH-201", tools_called=["search_listings"])


@pytest.fixture
def client(monkeypatch):
    fake = FakeAgent()
    main.app.dependency_overrides[main.get_agent] = lambda: fake
    main._seen_updates.clear()
    main._conversations.clear()
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    yield TestClient(main.app), fake
    main.app.dependency_overrides.clear()


def sample(name: str) -> dict:
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


def test_webhook_answers_text_message(client):
    http, fake = client
    body = http.post("/webhook/telegram", json=sample("telegram_text_message.json")).json()
    assert body["reply"].endswith("KH-201") and fake.calls == 1


def test_webhook_ignores_telegram_retries(client):
    http, fake = client
    http.post("/webhook/telegram", json=sample("telegram_text_message.json"))
    body = http.post("/webhook/telegram", json=sample("telegram_text_message.json")).json()
    assert body["duplicate"] is True and fake.calls == 1


def test_webhook_skips_voice(client):
    http, fake = client
    assert http.post("/webhook/telegram", json=sample("telegram_voice_message.json")).json()["skipped"] is True
    assert fake.calls == 0


def test_webhook_checks_secret(client, monkeypatch):
    http, _ = client
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "s3cret")
    assert http.post("/webhook/telegram", json=sample("telegram_text_message.json")).status_code == 401
    ok = http.post(
        "/webhook/telegram",
        json=sample("telegram_text_message.json"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret"},
    )
    assert ok.status_code == 200


def test_crm_upsert_merges_fields_and_blocks_double_booking(crm):
    first = crm.post("/leads", json={"chat_id": 7, "name": "Olena"}).json()
    second = crm.post("/leads", json={"chat_id": 7, "phone": "+380671234567"}).json()
    assert first["id"] == second["id"] and second["name"] == "Olena"

    viewing = {"lead_id": first["id"], "listing_id": "KH-101", "slot": "2026-11-03 10:00"}
    assert crm.post("/viewings", json=viewing).status_code == 200
    assert crm.post("/viewings", json=viewing).status_code == 409
