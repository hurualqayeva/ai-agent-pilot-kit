# AI Agent Pilot Kit

A Telegram lead assistant for a real estate agency, delivered the way a real client deployment runs: discovery, spec, data cleaning, integration, evals, waves, weekly status.

> Kyiv Homes is a fictional client. Listings, leads and the numbers in the status report are sample data, made up to show the full delivery flow end to end.

## What it does
A client writes in Telegram: *"2-room apartment in Pechersk up to 1500 USD, must have a generator"*. The agent:
1. searches the listings with real filters (no invented apartments),
2. saves the client as a lead in the CRM once it has name and phone,
3. books a viewing only in a slot the agency published,
4. hands off to a human for legal questions, complaints and anything off-topic.

```
Telegram --webhook--> FastAPI --> Agent (LiteLLM tool-calling loop) --> Mock CRM REST API
                         |             |                                 (/leads, /viewings)
                         |             +-- listings.json (filters + keyword score)
                         +-- PII vault: phones/emails masked before the LLM, unmasked only for the CRM call
```

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
- **Agent:** plain tool-calling loop on LiteLLM, so any provider works by changing `MODEL`. Turn cap per message, bad tool arguments return an error to the model instead of crashing.
- **Privacy:** the model never sees a raw phone or email. The eval suite checks this on every case.
- **Guardrails in code, not just in the prompt:** booking is refused without a phone or with a slot that does not exist; double booking returns 409 from the CRM.
- **Evals:** 14 cases (search, facts, booking, privacy, handoff, prompt injection, Ukrainian) with pass rate, tokens and cost per case. Exits non-zero under 90%, so it can gate CI.

## Run it
```bash
python -m venv .venv && .venv/Scripts/activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                                  # add an LLM API key

pytest                                                # 19 unit tests, no API key needed
python scripts/clean_and_anonymize.py data/raw/leads_export.csv data/clean
python -m evals.run_evals                             # needs an API key, writes evals/report.md

uvicorn mock_crm.app:create_app --factory --port 8001
uvicorn app.main:app --port 8000
curl -X POST localhost:8000/webhook/telegram -H "Content-Type: application/json" -d @samples/telegram_text_message.json
```
To connect a real bot, expose port 8000 (e.g. ngrok) and call Telegram `setWebhook` with your URL and `secret_token`.

## Next steps
- Replace the mock CRM with a Bitrix24 or Creatio adapter behind the same two endpoints.
- Persist conversations (Redis or Postgres) instead of process memory.
- Mask names in free text; voice messages via speech-to-text (phase 2 in the change log).
