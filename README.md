# AI Agent Pilot Kit

[![CI](https://github.com/hurualqayeva/ai-agent-pilot-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/hurualqayeva/ai-agent-pilot-kit/actions/workflows/ci.yml)

A Telegram lead assistant for a real estate agency, delivered the way a real client deployment runs: discovery, spec, data cleaning, integration, evals, waves, weekly status.

> Kyiv Homes is a fictional client. Listings, leads and the numbers in the status report are sample data, made up to show the full delivery flow end to end.

## What it does
A client writes in Telegram: *"2-room apartment in Pechersk up to 1500 USD, must have a generator"*. The agent:
1. searches the listings with real filters (no invented apartments),
2. saves the client as a lead in the CRM once it has name and phone,
3. books a viewing only in a slot the agency published,
4. hands off to a human for legal questions, complaints and anything off-topic.

```
Telegram --webhook--> FastAPI --XADD--> Redis Stream --consumer group--> Worker(s)
          (200 in ms)    |                                                  |
                         +-- dedup by update_id (Redis SET NX)              v
                                                 Agent (LiteLLM tool-calling loop) --> Mock CRM REST API
                                                   |                                   (/leads, /viewings)
                                                   +-- listings.json (filters + keyword score)
                                                   +-- PII vault: phones/emails masked before the LLM,
                                                       unmasked only for the CRM call
```
Without `REDIS_URL` the webhook runs the agent inline, which is handy for local development.

## What a delivery manager would look at
| Delivery step | Where |
|---|---|
| Spec with measurable targets and out-of-scope | [docs/spec.md](docs/spec.md) |
| Clean and anonymize a messy client export, report gaps | [scripts/clean_and_anonymize.py](scripts/clean_and_anonymize.py) |
| Test cases the client signs | [docs/test-cases.md](docs/test-cases.md) |
| Scope changes in writing | [docs/change-log.md](docs/change-log.md) |
| Quality and cost check before clients see it | [evals/](evals/) |
| Rollout in waves, rollback, training | [docs/rollout-plan.md](docs/rollout-plan.md) |
| Weekly client status | [docs/weekly-status-example.md](docs/weekly-status-example.md) |
| Playbook for the next deployment | [docs/playbook.md](docs/playbook.md) |

## Engineering details
- **Webhook:** reads Telegram update payloads, skips edits, voice and bot messages, checks the secret token, ignores Telegram retries by `update_id`. Real payloads in [samples/](samples/).
- **Queue:** the webhook only validates and enqueues to a Redis Stream, so Telegram gets its 200 fast even when the LLM is slow. Workers read as a consumer group, ack only after the reply is sent, reclaim messages from crashed workers (`XAUTOCLAIM`), and move an update that fails 3 times to a dead-letter stream. Dedup by `update_id` lives in Redis, so it works across webhook replicas.
- **Agent:** plain tool-calling loop on LiteLLM, so any provider works by changing `MODEL`. Turn cap per message, bad tool arguments return an error to the model instead of crashing.
- **Privacy:** the model never sees a raw phone or email. The eval suite checks this on every case.
- **Guardrails in code, not just in the prompt:** booking is refused without a phone or with a slot that does not exist; double booking returns 409 from the CRM.
- **Evals:** 14 cases (search, facts, booking, privacy, handoff, prompt injection, Ukrainian) with pass rate, tokens and cost per case. Exits non-zero under 90%, so it gates the manual [Evals workflow](.github/workflows/evals.yml), which posts the report to the job summary.
- **CI:** every push runs the tests (no API key needed) and builds the Docker image.

## MCP server: evals from your coding agent
[`mcp_server/server.py`](mcp_server/server.py) exposes the pilot to any MCP client (Claude Code, Cursor, VS Code). Change the prompt, then ask your coding agent *"run the booking evals and tell me what got worse"* without leaving the editor.

| Tool | What it does |
|---|---|
| `run_evals(model?, cases?)` | Runs the eval suite (or a subset) and returns pass rate, cost per conversation and failures per case |
| `list_eval_cases()` | Case ids and what each one checks |
| `search_listings(...)` | Same search the agent uses, to check what it should have answered |
| `list_leads()` / `list_viewings()` | Read the CRM to verify what the agent actually wrote |
| `clean_export(csv_path)` | Clean and anonymize a client export, return the data gaps |

Connect it (stdio):
```json
{
  "mcpServers": {
    "pilot-kit": {
      "command": "/path/to/ai-agent-pilot-kit/.venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/ai-agent-pilot-kit"
    }
  }
}
```
Library output during an eval run is redirected to stderr so it cannot corrupt the stdio channel; `clean_export` only reads CSVs inside the repo.

## Run it
```bash
python -m venv .venv && .venv/Scripts/activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                                  # add an LLM API key

pytest                                                # 31 tests, no API key needed
python -m mcp_server.server                           # MCP server over stdio
python scripts/clean_and_anonymize.py data/raw/leads_export.csv data/clean
python -m evals.run_evals                             # needs an API key, writes evals/report.md

uvicorn mock_crm.app:create_app --factory --port 8001
uvicorn app.main:app --port 8000
curl -X POST localhost:8000/webhook/telegram -H "Content-Type: application/json" -d @samples/telegram_text_message.json
```
Or the whole stack (webhook, worker, Redis, mock CRM) in Docker:
```bash
cp .env.example .env                                  # add an LLM API key
docker compose up --build
curl -X POST localhost:8000/webhook/telegram -H "Content-Type: application/json" -d @samples/telegram_text_message.json
docker compose logs -f worker                         # the agent's tool calls, tokens and cost
```

To run the evals in GitHub Actions, add an `ANTHROPIC_API_KEY` repository secret and start the **Evals** workflow.

To connect a real bot, expose port 8000 (e.g. ngrok) and call Telegram `setWebhook` with your URL and `secret_token`.

## Next steps
- Replace the mock CRM with a Bitrix24 or Creatio adapter behind the same two endpoints.
- Move conversation state and the PII vault into Redis, so several workers can share a chat (today one worker per deployment keeps it consistent).
- Mask names in free text; voice messages via speech-to-text (phase 2 in the change log).
