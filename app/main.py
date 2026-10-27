"""Webhook service: Telegram in, agent in the middle, CRM and Telegram out.

Run: uvicorn app.main:app --port 8000

With REDIS_URL set, the webhook only enqueues and `python -m app.worker` runs
the agent. Without it, the agent runs inline in the request (local dev, tests).
"""

import logging
import os
from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException

from app.agent import Agent
from app.anonymize import PiiVault
from app.crm_client import CrmClient
from app.knowledge import Listings
from app.queue import UpdateQueue
from app.telegram import IncomingMessage, parse_update, send_message

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("pilot")

app = FastAPI(title="AI Agent Pilot Kit")

# Per-chat state for the pilot. Masked history only; the vault holds the real values.
_conversations: dict[int, tuple[PiiVault, list[dict]]] = {}
_seen_updates: set[int] = set()


@lru_cache
def get_agent() -> Agent:
    return Agent(
        crm=CrmClient.from_url(os.getenv("CRM_BASE_URL", "http://localhost:8001")),
        listings=Listings(),
        model=os.getenv("MODEL", "anthropic/claude-haiku-5-5"),
        max_turns=int(os.getenv("AGENT_MAX_TURNS", "5")),
    )


@lru_cache
def get_queue() -> UpdateQueue | None:
    url = os.getenv("REDIS_URL")
    return UpdateQueue.from_url(url) if url else None


def handle_message(agent: Agent, message: IncomingMessage) -> dict:
    """Run the agent for one message and send the reply. Used inline and by the worker."""
    vault, history = _conversations.setdefault(message.chat_id, (PiiVault(), []))
    result = agent.run(message.chat_id, message.text, vault, history)
    log.info(
        "chat=%s tools=%s handoff=%s tokens=%s cost=$%.5f",
        message.chat_id, result.tools_called, result.handoff, result.tokens, result.cost_usd,
    )
    send_message(os.getenv("TELEGRAM_BOT_TOKEN", ""), message.chat_id, result.reply)
    return {"ok": True, "reply": result.reply, "tools": result.tools_called, "handoff": result.handoff}


@app.get("/health")
def health() -> dict:
    return {"ok": True}


# Sync handler on purpose: FastAPI runs it in a thread pool, so blocking LLM
# and CRM calls do not stall the event loop when the agent runs inline.
@app.post("/webhook/telegram")
def telegram_webhook(
    payload: dict,
    agent: Agent = Depends(get_agent),
    queue: UpdateQueue | None = Depends(get_queue),
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    if secret and x_telegram_bot_api_secret_token != secret:
        raise HTTPException(status_code=401, detail="bad secret token")

    message = parse_update(payload)
    if message is None:
        return {"ok": True, "skipped": True}

    # Telegram retries until it gets a 200, so every path dedups by update_id.
    if queue is not None:
        if not queue.first_time(message.update_id):
            return {"ok": True, "duplicate": True}
        queue.enqueue(message)
        return {"ok": True, "queued": True}

    if message.update_id in _seen_updates:
        return {"ok": True, "duplicate": True}
    _seen_updates.add(message.update_id)
    return handle_message(agent, message)
