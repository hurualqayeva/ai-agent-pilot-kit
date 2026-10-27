"""Run the eval suite against a real model and write evals/report.md.

Usage: python -m evals.run_evals [--model anthropic/claude-haiku-5-5] [--min-pass 0.9]

Every case runs against a fresh in-memory CRM. On top of each case's own
checks, every case also checks that no raw phone or email reached the model.
Exits non-zero if the pass rate is under --min-pass, so it can gate CI.
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.agent import Agent
from app.anonymize import PiiVault, contains_pii
from app.crm_client import CrmClient
from app.knowledge import Listings
from mock_crm.app import create_app

HERE = Path(__file__).resolve().parent
CYRILLIC = re.compile(r"[а-яіїєґ]", re.IGNORECASE)


def check(expect: dict, reply: str, tools: list[str], handoff: bool, crm: TestClient, history: list[dict]) -> list[str]:
    failures = []
    low = reply.lower()
    for tool in expect.get("tools_include", []):
        if tool not in tools:
            failures.append(f"tool {tool} not called")
    if "reply_any" in expect and not any(s.lower() in low for s in expect["reply_any"]):
        failures.append(f"reply has none of {expect['reply_any']}")
    for s in expect.get("reply_none", []):
        if s.lower() in low:
            failures.append(f"reply contains forbidden '{s}'")
    if expect.get("reply_cyrillic") and not CYRILLIC.search(reply):
        failures.append("reply not in Ukrainian")
    if "handoff" in expect and handoff != expect["handoff"]:
        failures.append(f"handoff={handoff}, expected {expect['handoff']}")
    if "crm_viewings" in expect:
        count = len(crm.get("/viewings").json())
        if count != expect["crm_viewings"]:
            failures.append(f"{count} viewings in CRM, expected {expect['crm_viewings']}")
    if "crm_lead_phone" in expect:
        phones = [lead.get("phone") for lead in crm.get("/leads").json()]
        if expect["crm_lead_phone"] not in phones:
            failures.append(f"CRM phones {phones}, expected {expect['crm_lead_phone']}")
    model_saw = json.dumps(history, ensure_ascii=False)
    if contains_pii(model_saw):
        failures.append("raw PII reached the model")
    return failures


def run_suite(
    model: str,
    min_pass: float = 0.9,
    only: list[str] | None = None,
    complete=None,
    verbose: bool = True,
    report_dir: Path = HERE,
) -> dict:
    """Run the cases (all, or the ids in `only`), write evals/report.md and return a summary."""
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    if only:
        cases = [case for case in cases if case["id"] in only]
        if not cases:
            raise ValueError(f"no cases match {only}")
    listings = Listings()
    rows, total_cost, total_tokens, passed = [], 0.0, 0, 0
    agent_kwargs = {"complete": complete} if complete else {}

    for case in cases:
        crm = TestClient(create_app(":memory:"))
        agent = Agent(crm=CrmClient(crm), listings=listings, model=model, **agent_kwargs)
        vault, history = PiiVault(), []
        tools, handoff, cost, tokens, reply = [], False, 0.0, 0, ""
        started = time.perf_counter()
        try:
            for turn in case["turns"]:
                result = agent.run(chat_id=1, text=turn, vault=vault, history=history)
                tools += result.tools_called
                handoff = handoff or result.handoff
                cost += result.cost_usd
                tokens += result.tokens
                reply = result.reply
            failures = check(case["expect"], reply, tools, handoff, crm, history)
        except Exception as exc:  # a crash is a failed case, not a crashed suite
            failures = [f"error: {exc}"]
        seconds = time.perf_counter() - started

        passed += not failures
        total_cost += cost
        total_tokens += tokens
        rows.append((case, failures, tokens, cost, seconds))
        if verbose:
            print(f"{'PASS' if not failures else 'FAIL'}  {case['id']}  {'; '.join(failures)}")

    rate = passed / len(cases)
    lines = [
        "# Eval report",
        "",
        f"Model: `{model}`  ",
        f"Pass rate: **{passed}/{len(cases)} ({rate:.0%})**, gate {min_pass:.0%}  ",
        f"Total cost: ${total_cost:.4f}, avg per conversation ${total_cost / len(cases):.5f}  ",
        f"Total tokens: {total_tokens}",
        "",
        "| Case | Why | Result | Tokens | Cost | Time |",
        "|---|---|---|---|---|---|",
    ]
    for case, failures, tokens, cost, seconds in rows:
        result = "pass" if not failures else "FAIL: " + "; ".join(failures).replace("|", "/")
        lines.append(f"| {case['id']} | {case['why']} | {result} | {tokens} | ${cost:.5f} | {seconds:.1f}s |")
    (report_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "model": model,
        "passed": passed,
        "total": len(cases),
        "pass_rate": round(rate, 3),
        "gate_passed": rate >= min_pass,
        "total_cost_usd": round(total_cost, 5),
        "avg_cost_per_conversation_usd": round(total_cost / len(cases), 5),
        "total_tokens": total_tokens,
        "failures": {case["id"]: failures for case, failures, *_ in rows if failures},
        "report": "evals/report.md",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.getenv("MODEL", "anthropic/claude-haiku-5-5"))
    parser.add_argument("--min-pass", type=float, default=0.9)
    args = parser.parse_args()

    summary = run_suite(args.model, args.min_pass)
    print(f"\n{summary['passed']}/{summary['total']} passed, ${summary['total_cost_usd']:.4f} total. Report: evals/report.md")
    sys.exit(0 if summary["gate_passed"] else 1)


if __name__ == "__main__":
    main()
