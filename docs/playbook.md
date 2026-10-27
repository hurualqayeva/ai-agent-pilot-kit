# Delivery playbook: deploying an AI agent for a new client

What we do on every deployment, in order. Update this file after each one.

## 1. Discovery (days 1-3)
- Sit in on real conversations: read 50+ recent chats before writing any prompt.
- Map the process today: who answers, what they look up, where it gets written down, what goes wrong.
- List data sources, their owner, format and refresh rate. Ask for an export, not live access, first.
- Clean and anonymize the export (`scripts/clean_and_anonymize.py`), send the gaps report back to the client.

## 2. Plan (days 3-5)
- Write the spec with 3-5 measurable targets and a clear out-of-scope list.
- Turn the 10-15 most common real conversations into test cases before building.
- Agree scope in writing. Anything after that is a change request with its impact on dates and cost.

## 3. Configure and connect (week 1)
- Prompt, tools and knowledge base. Every fact the bot says must come from a tool result.
- Integrations: webhook in, CRM out. Handle retries, duplicates and the CRM being down.
- Run the eval suite on every change. Track pass rate and cost per conversation together.

## 4. Pilot and go live (weeks 2-4)
- Roll out in waves by share of new chats; each wave has exit criteria.
- Daily spot check of 20 conversations in wave 1, then twice a week.
- Weekly status to the client: numbers vs targets, issues with fixes, decisions needed.

## 5. After launch
- Tuning session at week 6.
- Feed back to product: what we had to build by hand that the platform should do.

## Lessons so far
- Clients describe the process they wish they had. The chat history shows the real one.
- Booking flows break on the second message (client sends phone later). Always test multi-turn.
- Cost surprises come from tool loops, not long replies. Cap turns per message.
