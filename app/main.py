"""Webhook service: Telegram in, agent in the middle, CRM and Telegram out.

Run: uvicorn app.main:app --port 8000
"""

import logging
import os
from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException

from app.agent import Agent
from app.anonymize import PiiVault
from app.crm_client import CrmClient
from app.knowledge import Listings
from app.telegram import parse_update, send_message

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


@app.get("/health")
def health() -> dict:
    return {"ok": True}


# Sync handler on purpose: FastAPI runs it in a thread pool, so blocking LLM
# and CRM calls do not stall the event loop.
@app.post("/webhook/telegram")
def telegram_webhook(
    payload: dict,
    agent: Agent = Depends(get_agent),
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    if secret and x_telegram_bot_api_secret_token != secret:
        raise HTTPException(status_code=401, detail="bad secret token")

    message = parse_update(payload)
    if message is None:
        return {"ok": True, "skipped": True}
    if message.update_id in _seen_updates:  # Telegram retries until it gets a 200
        return {"ok": True, "duplicate": True}
    _seen_updates.add(message.update_id)

    vault, history = _conversations.setdefault(message.chat_id, (PiiVault(), []))
    result = agent.run(message.chat_id, message.text, vault, history)
    log.info(
        "chat=%s tools=%s handoff=%s tokens=%s cost=$%.5f",
        message.chat_id, result.tools_called, result.handoff, result.tokens, result.cost_usd,
    )
    send_message(os.getenv("TELEGRAM_BOT_TOKEN", ""), message.chat_id, result.reply)
    return {"ok": True, "reply": result.reply, "tools": result.tools_called, "handoff": result.handoff}
