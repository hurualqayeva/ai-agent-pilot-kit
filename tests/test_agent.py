import json

from app.anonymize import PiiVault
from tests.conftest import llm_response, tool_call


def test_search_then_answer(make_agent):
    agent, llm = make_agent([
        llm_response(tool_calls=[tool_call("c1", "search_listings", {"district": "Pechersk", "rooms": 2, "max_price_usd": 1500})]),
        llm_response("KH-201 on Lesi Ukrainky, 1400 USD, has a generator."),
    ])
    result = agent.run(1, "2 rooms in Pechersk up to 1500", PiiVault(), [])

    assert result.tools_called == ["search_listings"]
    assert "KH-201" in result.reply
    assert result.tokens == 200 and result.cost_usd == 0.002
    tool_output = json.loads(llm.calls[1]["messages"][-1]["content"])
    assert [hit["id"] for hit in tool_output["results"]] == ["KH-201"]


def test_model_sees_tokens_but_crm_gets_real_phone(make_agent, crm):
    agent, llm = make_agent([
        llm_response(tool_calls=[tool_call("c1", "save_lead", {"name": "Olena", "phone": "[PHONE_1]"})]),
        llm_response("Saved! We will call you at [PHONE_1]."),
    ])
    result = agent.run(1, "Olena, +380 67 123 45 67", PiiVault(), [])

    sent_to_model = json.dumps(llm.calls)
    assert "+380" not in sent_to_model and "[PHONE_1]" in sent_to_model
    assert crm.get("/leads").json()[0]["phone"] == "+380 67 123 45 67"
    assert result.reply == "Saved! We will call you at +380 67 123 45 67."


def test_booking_requires_phone_and_valid_slot(make_agent, crm):
    agent, _ = make_agent([
        llm_response(tool_calls=[tool_call("c1", "book_viewing", {"listing_id": "KH-101", "slot": "2026-11-03 10:00"})]),
        llm_response(tool_calls=[tool_call("c2", "book_viewing", {"listing_id": "KH-101", "slot": "2026-12-31 10:00"})]),
        llm_response("Please share your phone number."),
    ])
    history: list[dict] = []
    agent.run(1, "book KH-101", PiiVault(), history)

    tool_outputs = [json.loads(m["content"]) for m in history if m["role"] == "tool"]
    assert "save the client's name and phone" in tool_outputs[0]["error"]
    assert tool_outputs[1]["error"] == "slot not available"
    assert crm.get("/viewings").json() == []


def test_full_booking(make_agent, crm):
    agent, _ = make_agent([
        llm_response(tool_calls=[
            tool_call("c1", "save_lead", {"name": "Olena", "phone": "[PHONE_1]"}),
            tool_call("c2", "book_viewing", {"listing_id": "KH-101", "slot": "2026-11-03 10:00"}),
        ]),
        llm_response("Booked for 3 Nov at 10:00."),
    ])
    result = agent.run(1, "Olena 0671234567, KH-101 at 2026-11-03 10:00", PiiVault(), [])

    assert result.tools_called == ["save_lead", "book_viewing"]
    assert crm.get("/viewings").json()[0]["listing_id"] == "KH-101"


def test_turn_limit_hands_off(make_agent):
    looping = [llm_response(tool_calls=[tool_call(f"c{i}", "search_listings", {})]) for i in range(5)]
    agent, _ = make_agent(looping)
    result = agent.run(1, "hello", PiiVault(), [])

    assert result.handoff is True
    assert "manager" in result.reply


def test_bad_tool_arguments_do_not_crash(make_agent):
    bad = tool_call("c1", "search_listings", {})
    bad.function.arguments = "{not json"
    agent, _ = make_agent([llm_response(tool_calls=[bad]), llm_response("Could you rephrase?")])
    assert agent.run(1, "hi", PiiVault(), []).reply == "Could you rephrase?"
