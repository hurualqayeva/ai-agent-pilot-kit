"""Listings knowledge base: structured filters plus simple keyword scoring.

Kept deliberately small. For a pilot with ~50 listings, filters on price,
rooms and district beat embeddings, and every answer is traceable to a row.
"""

import json
import re
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "listings.json"
WORD = re.compile(r"\w+", re.UNICODE)


class Listings:
    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        self.items: list[dict] = json.loads(Path(path).read_text(encoding="utf-8"))
        self.by_id = {item["id"]: item for item in self.items}

    def search(
        self,
        district: str | None = None,
        max_price_usd: int | None = None,
        rooms: int | None = None,
        pets_allowed: bool | None = None,
        query: str | None = None,
        limit: int = 3,
    ) -> list[dict]:
        hits = []
        for item in self.items:
            if district and district.lower() not in item["district"].lower():
                continue
            if max_price_usd is not None and item["price_usd"] > max_price_usd:
                continue
            if rooms is not None and item["rooms"] != rooms:
                continue
            if pets_allowed is not None and item["pets_allowed"] != pets_allowed:
                continue
            hits.append((self._score(item, query), item))
        hits.sort(key=lambda pair: (-pair[0], pair[1]["price_usd"]))
        return [item for _, item in hits[:limit]]

    @staticmethod
    def _score(item: dict, query: str | None) -> int:
        if not query:
            return 0
        text = " ".join([item["title"], item["description"], " ".join(item["features"])]).lower()
        return sum(1 for word in WORD.findall(query.lower()) if len(word) > 2 and word in text)
