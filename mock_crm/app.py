"""Mock CRM with a REST API, standing in for Bitrix24 / Salesforce / Creatio in the pilot.

Run: uvicorn mock_crm.app:create_app --factory --port 8001
"""

import os
import sqlite3
import threading

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER UNIQUE NOT NULL,
    name TEXT, phone TEXT, budget_usd INTEGER, district TEXT, rooms INTEGER, notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS viewings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL REFERENCES leads(id),
    listing_id TEXT NOT NULL,
    slot TEXT NOT NULL,
    UNIQUE (listing_id, slot)
);
"""


class LeadIn(BaseModel):
    chat_id: int
    name: str | None = None
    phone: str | None = None
    budget_usd: int | None = None
    district: str | None = None
    rooms: int | None = None
    notes: str | None = None


class ViewingIn(BaseModel):
    lead_id: int
    listing_id: str
    slot: str


def create_app(db_path: str | None = None) -> FastAPI:
    db = sqlite3.connect(db_path or os.getenv("CRM_DB_PATH", "crm.sqlite3"), check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    lock = threading.Lock()
    app = FastAPI(title="Mock CRM")

    def lead_by_chat(chat_id: int) -> dict | None:
        row = db.execute("SELECT * FROM leads WHERE chat_id = ?", (chat_id,)).fetchone()
        return dict(row) if row else None

    @app.post("/leads")
    def upsert_lead(lead: LeadIn) -> dict:
        fields = lead.model_dump(exclude_none=True, exclude={"chat_id"})
        with lock:
            if lead_by_chat(lead.chat_id) is None:
                cols = ", ".join(["chat_id", *fields])
                marks = ", ".join("?" * (len(fields) + 1))
                db.execute(f"INSERT INTO leads ({cols}) VALUES ({marks})", [lead.chat_id, *fields.values()])
            elif fields:
                sets = ", ".join(f"{col} = ?" for col in fields)
                db.execute(
                    f"UPDATE leads SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE chat_id = ?",
                    [*fields.values(), lead.chat_id],
                )
            db.commit()
            return lead_by_chat(lead.chat_id)

    @app.get("/leads")
    def list_leads() -> list[dict]:
        return [dict(row) for row in db.execute("SELECT * FROM leads ORDER BY id")]

    @app.post("/viewings")
    def book_viewing(viewing: ViewingIn) -> dict:
        with lock:
            if db.execute("SELECT 1 FROM leads WHERE id = ?", (viewing.lead_id,)).fetchone() is None:
                raise HTTPException(status_code=404, detail="lead not found")
            try:
                cursor = db.execute(
                    "INSERT INTO viewings (lead_id, listing_id, slot) VALUES (?, ?, ?)",
                    (viewing.lead_id, viewing.listing_id, viewing.slot),
                )
            except sqlite3.IntegrityError:
                raise HTTPException(status_code=409, detail="slot already booked")
            db.commit()
            return {"id": cursor.lastrowid, **viewing.model_dump()}

    @app.get("/viewings")
    def list_viewings() -> list[dict]:
        return [dict(row) for row in db.execute("SELECT * FROM viewings ORDER BY id")]

    return app
