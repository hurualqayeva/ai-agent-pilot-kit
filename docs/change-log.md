# Change log (scope changes after sign-off)

Each change: who asked, what changes, impact on dates and cost, and who approved it in writing.

## CR-1: Ukrainian replies (2026-10-21)
- **Asked by:** agency owner, after reviewing the first demo.
- **Change:** reply in the client's language, Ukrainian or English. Was English only.
- **Impact:** prompt change plus 1 eval case. No date change. Cost per conversation +~5% (longer Ukrainian tokens).
- **Approved:** owner, by email 2026-10-21.

## CR-2: Name masking postponed (2026-10-22)
- **Asked by:** delivery, after discovery.
- **Change:** phones and emails are masked before the LLM; names in free text are not, because reliable Ukrainian name detection needs a separate model.
- **Impact:** documented privacy gap for the pilot; revisit before production.
- **Approved:** owner and the agency's data contact, in the pilot chat 2026-10-22.

## CR-3: Voice messages (requested 2026-10-24, NOT accepted for pilot)
- **Asked by:** senior agent.
- **Change:** transcribe voice messages.
- **Decision:** moved to phase 2. Adds a speech-to-text vendor and ~1 week. Bot ignores voice for now; managers answer them as today.
- **Approved:** owner, by email 2026-10-24.
