"""PII masking so the LLM never sees raw phone numbers or emails.

The vault swaps each value for a stable token ([PHONE_1], [EMAIL_1]) before
text goes to the model, and swaps it back before a tool call or a reply
reaches the CRM or the user.
"""

import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"(?<![\w+(])(?:\+|\()?\d[\d\s().-]{7,}\d(?!\w)")
DATE_LIKE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _is_phone(candidate: str) -> bool:
    digits = sum(ch.isdigit() for ch in candidate)
    return 9 <= digits <= 15 and not DATE_LIKE.match(candidate)


class PiiVault:
    def __init__(self) -> None:
        self._to_real: dict[str, str] = {}
        self._to_token: dict[str, str] = {}
        self._counts: dict[str, int] = {}

    def _token_for(self, kind: str, real: str) -> str:
        if real not in self._to_token:
            self._counts[kind] = self._counts.get(kind, 0) + 1
            token = f"[{kind}_{self._counts[kind]}]"
            self._to_token[real] = token
            self._to_real[token] = real
        return self._to_token[real]

    def mask(self, text: str) -> str:
        text = EMAIL.sub(lambda m: self._token_for("EMAIL", m.group(0)), text)

        def phone(m: re.Match) -> str:
            value = m.group(0)
            return self._token_for("PHONE", value) if _is_phone(value) else value

        return PHONE.sub(phone, text)

    def unmask(self, text: str) -> str:
        for token, real in self._to_real.items():
            text = text.replace(token, real)
        return text

    def unmask_args(self, args: dict) -> dict:
        return {k: self.unmask(v) if isinstance(v, str) else v for k, v in args.items()}


def contains_pii(text: str) -> bool:
    """True if text still has something that looks like a raw email or phone."""
    if EMAIL.search(text):
        return True
    return any(_is_phone(m.group(0)) for m in PHONE.finditer(text))
