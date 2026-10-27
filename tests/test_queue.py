import json
from pathlib import Path

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app import main
from app.queue import DEAD_LETTERS, GROUP, STREAM, UpdateQueue
from app.telegram import IncomingMessage

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


@pytest.fixture
def queue() -> UpdateQueue:
    return UpdateQueue(fakeredis.FakeRedis(decode_responses=True), max_attempts=2)


def message(update_id: int = 1) -> IncomingMessage:
    return IncomingMessage(chat_id=42, text="2 rooms in Pechersk", update_id=update_id)


def test_worker_handles_and_acks(queue):
    queue.enqueue(message())
    seen = []
    assert queue.process("w1", seen.append, block_ms=1) == 1
    assert seen[0].text == "2 rooms in Pechersk" and seen[0].chat_id == 42
    assert queue.redis.xpending(STREAM, GROUP)["pending"] == 0


def test_failed_update_is_retried_then_dead_lettered(queue):
    queue.enqueue(message())

    def boom(_):
        raise RuntimeError("LLM timeout")

    assert queue.process("w1", boom, block_ms=1) == 0
    assert queue.redis.xpending(STREAM, GROUP)["pending"] == 1  # kept for a retry

    assert queue.process("w2", boom, block_ms=1, reclaim_idle_ms=0) == 0  # another worker reclaims it
    assert queue.redis.xpending(STREAM, GROUP)["pending"] == 0
    [(_, dead)] = queue.redis.xrange(DEAD_LETTERS)
    assert dead["error"] == "LLM timeout" and dead["attempts"] == "2"


def test_crashed_worker_messages_are_reclaimed(queue):
    queue.enqueue(message())
    queue.ensure_group()
    queue.redis.xreadgroup(GROUP, "crashed", {STREAM: ">"}, count=1)  # read, never acked

    seen = []
    assert queue.process("w2", seen.append, block_ms=1, reclaim_idle_ms=0) == 1
    assert seen[0].update_id == 1


def test_dedup_is_shared(queue):
    assert queue.first_time(7) is True
    assert UpdateQueue(queue.redis).first_time(7) is False  # a second webhook replica


def test_webhook_enqueues_when_redis_is_configured(queue, monkeypatch):
    calls = []

    class Agent:
        def run(self, *args):
            calls.append(args)

    main.app.dependency_overrides[main.get_agent] = Agent
    main.app.dependency_overrides[main.get_queue] = lambda: queue
    monkeypatch.delenv("TELEGRAM_WEBHOOK_SECRET", raising=False)
    try:
        http = TestClient(main.app)
        update = json.loads((SAMPLES / "telegram_text_message.json").read_text(encoding="utf-8"))
        assert http.post("/webhook/telegram", json=update).json() == {"ok": True, "queued": True}
        assert http.post("/webhook/telegram", json=update).json()["duplicate"] is True
    finally:
        main.app.dependency_overrides.clear()
    assert queue.redis.xlen(STREAM) == 1 and calls == []
