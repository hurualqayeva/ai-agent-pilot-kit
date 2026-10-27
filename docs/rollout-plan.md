# Rollout plan

| Wave | Dates | Who sees the bot | Exit criteria |
|---|---|---|---|
| 0. Internal | Week 1 | 2 agency agents test it themselves | Eval suite 90%+, no failures in booking or privacy cases |
| 1. Pilot | Week 2 | 20% of new Telegram chats (by chat id) | Under 2% wrong facts in daily spot check of 20 chats; agents rate handoffs useful |
| 2. Wider | Week 3 | 60% of new chats | First reply under 1 min, 85%+ leads with phone in CRM |
| 3. All | Week 4 | 100% of new chats | Pilot goal metrics met, client sign-off |

## Rollback
Turn the webhook off (`deleteWebhook`) and agents answer in Telegram as before. No data migration needed; leads stay in the CRM.

## Training
- Agents (45 min): what the bot does and does not do, how handoffs arrive, how to correct a lead.
- Office manager (30 min): updating the listings export and viewing slots, reading the weekly report.

## Handover
Runbook, eval suite, and this repo go to the agency's IT contractor at the end of week 4. One post-launch tuning session in week 6.
