import csv
from pathlib import Path

from scripts.clean_and_anonymize import main

RAW = Path(__file__).resolve().parent.parent / "data" / "raw" / "leads_export.csv"


def test_clean_export(tmp_path):
    main(str(RAW), str(tmp_path))
    rows = list(csv.DictReader(open(tmp_path / "leads_clean.csv", encoding="utf-8")))
    text = (tmp_path / "leads_clean.csv").read_text(encoding="utf-8")
    gaps = (tmp_path / "gaps.md").read_text(encoding="utf-8")

    assert len(rows) == 6  # 8 rows: 1 duplicate merged, 1 uncontactable dropped
    assert "Kovalenko" not in text and "@" not in text and "0441234567" not in text
    olena = next(r for r in rows if r["initials"] == "O.K.")
    assert olena["sources"] == "Telegram+Website" and olena["budget_usd"] == "1200"
    assert olena["notes"] == "needs generator; duplicate from website form"
    assert next(r for r in rows if r["initials"] == "S.M.")["budget_usd"] == "3000"
    assert "duplicate" in gaps and "no phone or email" in gaps
