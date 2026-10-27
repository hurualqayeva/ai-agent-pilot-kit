# Spec: Telegram lead assistant for Kyiv Homes (pilot)

Version 1.1, agreed 2026-10-20. Changes after sign-off go to [change-log.md](change-log.md).

## Problem
Kyiv Homes gets ~120 rental enquiries a week in Telegram. Two agents answer by hand, first reply takes 3-5 hours in the evening, and about a third of leads never reach the CRM.

## Goal of the pilot (4 weeks)
| Metric | Today | Pilot target |
|---|---|---|
| First reply time | 3-5 h | under 1 min |
| Enquiries saved to CRM with phone | ~65% | 90% |
| Viewings booked without an agent | 0 | 25% of booked viewings |
| Wrong facts in replies (price, pets, slots) | n/a | 0 in eval suite, under 2% in spot checks |
| LLM cost per conversation | n/a | under $0.02 |

## In scope
- Answer rental questions in Telegram (Ukrainian and English) from the listings export.
- Collect name, phone, budget, district, rooms; create or update the lead in the CRM.
- Book viewings into slots the agency has published per listing.
- Hand off to a human: legal questions, deposits, complaints, anything off-topic.

## Out of scope (pilot)
- Sales listings, Lviv/other cities, voice messages, photos.
- Payments, contracts, price negotiation.
- Writing to the real CRM. The pilot writes to a staging CRM; production write access is phase 2.

## Data and privacy
- Listings: weekly CSV export from the agency, ~50 rows. Owner: office manager.
- Leads: raw export cleaned and anonymized with `scripts/clean_and_anonymize.py` before anyone outside the agency sees it.
- Phones and emails are masked before text reaches the LLM provider ([PHONE_1], [EMAIL_1]) and unmasked only inside the CRM call.
- Known gap: names typed in free text are not masked. Accepted by the client for the pilot (see change log, CR-2).

## Integration
- Telegram webhook (`POST /webhook/telegram`) with secret token check. Telegram retries are de-duplicated by `update_id`.
- CRM REST API: `POST /leads` (upsert by chat), `POST /viewings` (409 if the slot is taken).

## Acceptance
Pilot goes to wave 1 when the eval suite passes at 90%+ with zero failures in the booking and privacy cases, and the agency signs off [test-cases.md](test-cases.md).
