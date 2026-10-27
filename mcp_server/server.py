"""MCP server: lets an AI coding tool (Claude Code, Cursor, any MCP client) work with the pilot.

The main use: change the prompt or a tool, then ask your coding agent
"run the evals and tell me what got worse", without leaving the editor.

Run: python -m mcp_server.server   (stdio transport)
"""

import contextlib
import os
import sys
from pathlib import Path

import httpx
from mcp.server.mcpserver import MCPServer

from app.crm_client import CrmClient, CrmError
from app.knowledge import Listings
from evals.run_evals import HERE as EVALS_DIR, run_suite
from scripts.clean_and_anonymize import clean_file

ROOT = Path(__file__).resolve().parent.parent

server = MCPServer(
    name="ai-agent-pilot-kit",
    instructions=(
        "Tools for the Kyiv Homes lead assistant pilot. Use run_evals after any change to the agent "
        "prompt, tools or model, and compare pass rate and cost with the previous run. run_evals calls "
        "a paid LLM API, so run a few cases with `cases` while iterating and the full suite before merging."
    ),
)
_listings = Listings()


def _crm() -> CrmClient:
    return CrmClient.from_url(os.getenv("CRM_BASE_URL", "http://localhost:8001"), timeout=5)


@server.tool()
def search_listings(
    district: str | None = None,
    max_price_usd: int | None = None,
    rooms: int | None = None,
    pets_allowed: bool | None = None,
    query: str | None = None,
) -> dict:
    """Search the listings knowledge base exactly as the agent does. Useful to check what the agent should have answered."""
    hits = _listings.search(district, max_price_usd, rooms, pets_allowed, query)
    return {"count": len(hits), "results": hits}


@server.tool()
def list_leads() -> dict:
    """List leads in the CRM (needs the mock CRM running at CRM_BASE_URL)."""
    try:
        return {"leads": _crm().list_leads()}
    except (httpx.HTTPError, CrmError) as exc:
        return {"error": f"CRM not reachable: {exc}. Start it with: uvicorn mock_crm.app:create_app --factory --port 8001"}


@server.tool()
def list_viewings() -> dict:
    """List booked viewings in the CRM (needs the mock CRM running at CRM_BASE_URL)."""
    try:
        return {"viewings": _crm().list_viewings()}
    except (httpx.HTTPError, CrmError) as exc:
        return {"error": f"CRM not reachable: {exc}"}


@server.tool()
def list_eval_cases() -> dict:
    """List eval case ids with what each one checks."""
    import json

    cases = json.loads((EVALS_DIR / "cases.json").read_text(encoding="utf-8"))
    return {"cases": [{"id": c["id"], "why": c["why"], "turns": len(c["turns"])} for c in cases]}


@server.tool()
def run_evals(model: str | None = None, cases: list[str] | None = None, min_pass: float = 0.9) -> dict:
    """Run the agent eval suite against a real LLM and return pass rate, cost and failures per case.

    Calls a paid API. Pass `cases` (ids from list_eval_cases) to run a subset. Writes evals/report.md.
    """
    model = model or os.getenv("MODEL", "anthropic/claude-haiku-5-5")
    # stdout is the MCP channel; anything a library prints must go to stderr.
    with contextlib.redirect_stdout(sys.stderr):
        try:
            return run_suite(model, min_pass, only=cases, verbose=False)
        except ValueError as exc:
            return {"error": str(exc)}


@server.tool()
def clean_export(csv_path: str = "data/raw/leads_export.csv") -> dict:
    """Clean and anonymize a client lead export (CSV inside this repo). Returns counts and the data gaps to send back to the client."""
    src = (ROOT / csv_path).resolve()
    if ROOT not in src.parents or src.suffix.lower() != ".csv" or not src.exists():
        return {"error": "csv_path must be an existing .csv file inside the repo"}
    summary = clean_file(str(src), str(ROOT / "data" / "clean"))
    return {**summary, "output": "data/clean/leads_clean.csv", "gaps_report": "data/clean/gaps.md"}


if __name__ == "__main__":
    server.run("stdio")
