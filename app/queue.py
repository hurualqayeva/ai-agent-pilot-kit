"""Redis Streams queue between the webhook and the agent.

The webhook only validates and enqueues, so Telegram gets its 200 in
milliseconds even when the LLM is slow. Workers read the stream as a consumer
group: each update goes to one worker, is acked only after the reply is sent,
and a crashed worker's messages are reclaimed by another one. An update that
keeps failing goes to a dead-letter stream instead of blocking the queue.
"""

import logging
from collections.abc import Callable

import redis

from app.telegram import IncomingMessage

log = logging.getLogger(__name__)

STREAM = "telegram:updates"
DEAD_LETTERS = "telegram:dead"
GROUP = "agents"


class UpdateQueue:
    def __init__(self, client: redis.Redis, max_attempts: int = 3, dedup_ttl_s: int = 86_400) -> None:
        self.redis = client
        self.max_attempts = max_attempts
        self.dedup_ttl_s = dedup_ttl_s

    @classmethod
    def from_url(cls, url: str, **kwargs) -> "UpdateQueue":
        return cls(redis.Redis.from_url(url, decode_responses=True), **kwargs)

    def ensure_group(self) -> None:
        try:
            self.redis.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def first_time(self, update_id: int) -> bool:
        """True the first time an update id is seen. Shared by every webhook replica."""
        return bool(self.redis.set(f"telegram:seen:{update_id}", 1, nx=True, ex=self.dedup_ttl_s))

    def enqueue(self, message: IncomingMessage) -> str:
        fields = {"update_id": message.update_id, "chat_id": message.chat_id, "text": message.text}
        return self.redis.xadd(STREAM, fields)

    def process(
        self,
        consumer: str,
        handle: Callable[[IncomingMessage], None],
        count: int = 10,
        block_ms: int = 5000,
        reclaim_idle_ms: int = 60_000,
    ) -> int:
        """Handle one batch: messages stuck with dead or failed consumers first, then new ones.

        Returns how many messages were handled successfully.
        """
        self.ensure_group()
        _, stuck, _ = self.redis.xautoclaim(STREAM, GROUP, consumer, min_idle_time=reclaim_idle_ms, count=count)
        batch = list(stuck)
        if not batch:
            for _, entries in self.redis.xreadgroup(GROUP, consumer, {STREAM: ">"}, count=count, block=block_ms) or []:
                batch.extend(entries)

        done = 0
        for entry_id, fields in batch:
            message = IncomingMessage(
                chat_id=int(fields["chat_id"]), text=fields["text"], update_id=int(fields["update_id"])
            )
            try:
                handle(message)
            except Exception as exc:  # left pending, retried after reclaim_idle_ms
                self._failed(entry_id, fields, exc)
                continue
            self.redis.xack(STREAM, GROUP, entry_id)
            self.redis.hdel("telegram:attempts", entry_id)
            done += 1
        return done

    def _failed(self, entry_id: str, fields: dict, exc: Exception) -> None:
        attempts = self.redis.hincrby("telegram:attempts", entry_id, 1)
        log.warning("update %s failed (attempt %s/%s): %s", fields["update_id"], attempts, self.max_attempts, exc)
        if attempts >= self.max_attempts:
            self.redis.xadd(DEAD_LETTERS, {**fields, "error": str(exc)[:500], "attempts": attempts})
            self.redis.xack(STREAM, GROUP, entry_id)
            self.redis.hdel("telegram:attempts", entry_id)
