"""Thin HTTP client for the CRM. Swap the base URL to point at a real CRM adapter."""

import httpx


class CrmError(Exception):
    pass


class CrmClient:
    def __init__(self, http: httpx.Client) -> None:
        self.http = http

    @classmethod
    def from_url(cls, base_url: str, timeout: float = 10.0) -> "CrmClient":
        return cls(httpx.Client(base_url=base_url, timeout=timeout))

    def upsert_lead(self, chat_id: int, **fields) -> dict:
        return self._call("POST", "/leads", json={"chat_id": chat_id, **fields})

    def book_viewing(self, lead_id: int, listing_id: str, slot: str) -> dict:
        return self._call("POST", "/viewings", json={"lead_id": lead_id, "listing_id": listing_id, "slot": slot})

    def list_leads(self) -> list[dict]:
        return self._call("GET", "/leads")

    def list_viewings(self) -> list[dict]:
        return self._call("GET", "/viewings")

    def _call(self, method: str, path: str, **kwargs) -> dict | list:
        response = self.http.request(method, path, **kwargs)
        if response.status_code >= 400:
            raise CrmError(f"{response.status_code}: {response.text}")
        return response.json()
