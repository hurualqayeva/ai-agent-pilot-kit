"""Clean a client's raw lead export, remove PII, and list the data gaps.

Usage: python scripts/clean_and_anonymize.py data/raw/leads_export.csv data/clean

Writes:
  leads_clean.csv  normalized, deduplicated, anonymized leads (safe to share with the AI team)
  gaps.md          what is missing or broken, to send back to the client
"""

import csv
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.anonymize import PiiVault  # noqa: E402

DISTRICTS = ["Podil", "Pechersk", "Obolon", "Shevchenkivskyi", "Darnytskyi"]
EMAIL_OK = re.compile(r"^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$")


def normalize_phone(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10 and digits.startswith("0"):
        digits = "38" + digits
    if len(digits) == 12 and digits.startswith("380"):
        return "+" + digits
    return None


def parse_budget(raw: str) -> int | None:
    text = (raw or "").lower().replace(",", "").replace("usd", "").replace("$", "").strip()
    if not text:
        return None
    multiplier = 1000 if text.endswith("k") else 1
    try:
        return int(float(text.rstrip("k")) * multiplier)
    except ValueError:
        return None


def parse_rooms(raw: str) -> tuple[int | None, str]:
    numbers = [int(n) for n in re.findall(r"\d+", raw or "")]
    if not numbers:
        return None, ""
    return min(numbers), (f"open to {min(numbers)}-{max(numbers)} rooms" if len(numbers) > 1 else "")


def normalize_district(raw: str) -> str | None:
    value = (raw or "").strip().lower()
    return next((d for d in DISTRICTS if d.lower() == value), None)


def lead_ref(key: str) -> str:
    return "L-" + hashlib.sha256(key.encode()).hexdigest()[:8]


def clean(rows: list[dict]) -> tuple[list[dict], list[str]]:
    leads: dict[str, dict] = {}
    gaps: list[str] = []

    for line_no, row in enumerate(rows, start=2):
        name = " ".join((row.get("Name") or "").split()).title()
        phone = normalize_phone(row.get("Phone", ""))
        email = (row.get("Email") or "").strip().lower()
        if email and not EMAIL_OK.match(email):
            gaps.append(f"Row {line_no} ({name}): invalid email, dropped")
            email = ""
        if row.get("Phone") and not phone:
            gaps.append(f"Row {line_no} ({name}): phone '{row['Phone']}' is not a valid UA number")
        key = phone or email
        if not key:
            gaps.append(f"Row {line_no} ({name}): no phone or email, lead cannot be contacted, skipped")
            continue

        budget = parse_budget(row.get("Budget", ""))
        rooms, rooms_note = parse_rooms(row.get("Rooms", ""))
        district = normalize_district(row.get("District", ""))
        # Free-text comments can hide phone numbers ("call me at ..."), so mask them too.
        comment = PiiVault().mask((row.get("Comment") or "").strip())
        notes = "; ".join(n for n in [comment, rooms_note] if n)

        if key in leads:
            lead = leads[key]
            lead["sources"].add(row.get("Source", "").strip())
            if notes and notes not in lead["notes"]:
                lead["notes"] = "; ".join(n for n in [lead["notes"], notes] if n)
            gaps.append(f"Row {line_no} ({name}): duplicate of an earlier row, merged")
            continue

        if budget is None:
            gaps.append(f"Row {line_no} ({name}): budget missing or unreadable")
        if district is None:
            gaps.append(f"Row {line_no} ({name}): district '{row.get('District')}' not in the service area")

        leads[key] = {
            "lead_ref": lead_ref(key),
            "initials": "".join(part[0] + "." for part in name.split()) or "?",
            "has_phone": bool(phone),
            "has_email": bool(email),
            "budget_usd": budget,
            "district": district,
            "rooms": rooms,
            "notes": notes,
            "sources": {row.get("Source", "").strip()},
        }

    cleaned = [{**lead, "sources": "+".join(sorted(lead["sources"]))} for lead in leads.values()]
    return cleaned, gaps


def main(src: str, out_dir: str) -> None:
    with open(src, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    cleaned, gaps = clean(rows)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "leads_clean.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(cleaned[0]))
        writer.writeheader()
        writer.writerows(cleaned)

    report = [
        "# Data gaps found in the lead export",
        "",
        f"Input rows: {len(rows)}. Clean unique leads: {len(cleaned)}.",
        "",
        *[f"- {gap}" for gap in gaps],
        "",
        "Names, phones and emails were removed from leads_clean.csv. Raw data stays with the client.",
    ]
    (out / "gaps.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"{len(rows)} rows in, {len(cleaned)} clean leads out, {len(gaps)} gaps. See {out}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
