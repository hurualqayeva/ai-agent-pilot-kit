import asyncio
import json

from evals.run_evals import run_suite
from mcp_server.server import server
from tests.conftest import ScriptedLLM, llm_response, tool_call


def call(name: str, args: dict | None = None) -> dict:
    result = asyncio.run(server.call_tool(name, args or {}))
    return json.loads(result.content[0].text)


def test_exposes_the_pilot_tools():
    names = {tool.name for tool in asyncio.run(server.list_tools())}
    assert names == {"search_listings", "list_leads", "list_viewings", "list_eval_cases", "run_evals", "clean_export"}


def test_search_listings_matches_the_agent_knowledge_base():
    body = call("search_listings", {"district": "Pechersk", "rooms": 2, "max_price_usd": 1500})
    assert [hit["id"] for hit in body["results"]] == ["KH-201"]


def test_list_eval_cases():
    ids = [case["id"] for case in call("list_eval_cases")["cases"]]
    assert "book-happy-path" in ids and len(ids) == 14


def test_crm_down_returns_a_helpful_error(monkeypatch):
    monkeypatch.setenv("CRM_BASE_URL", "http://127.0.0.1:9")
    assert "CRM not reachable" in call("list_leads")["error"]


def test_clean_export_stays_inside_the_repo():
    assert "error" in call("clean_export", {"csv_path": "../../secrets.csv"})
    assert call("clean_export")["leads_out"] == 6


def test_unknown_eval_case_is_an_error_not_a_crash():
    assert "no cases match" in call("run_evals", {"cases": ["nope"]})["error"]


def test_eval_harness_scores_a_scripted_model(tmp_path):
    llm = ScriptedLLM([
        llm_response(tool_calls=[tool_call("c1", "search_listings", {"district": "Pechersk", "rooms": 2, "max_price_usd": 1500})]),
        llm_response("KH-201 on Lesi Ukrainky, 1400 USD, with a generator."),
    ])
    summary = run_suite("scripted", only=["search-basic"], complete=llm, verbose=False, report_dir=tmp_path)
    assert summary["passed"] == 1 and summary["failures"] == {}
    assert "search-basic | Core use case" in (tmp_path / "report.md").read_text(encoding="utf-8")
