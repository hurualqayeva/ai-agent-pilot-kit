import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.agent import Agent
from app.crm_client import CrmClient
from app.knowledge import Listings
from mock_crm.app import create_app


def tool_call(call_id: str, name: str, args: dict) -> SimpleNamespace:
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(args)))


def llm_response(content: str | None = None, tool_calls: list | None = None) -> SimpleNamespace:
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=SimpleNamespace(total_tokens=100))


class ScriptedLLM:
    """Returns canned responses in order and records what the model was sent."""

    def __init__(self, responses: list) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(json.loads(json.dumps(kwargs)))  # snapshot, history keeps mutating
        return self.responses.pop(0)


@pytest.fixture
def crm() -> TestClient:
    return TestClient(create_app(":memory:"))


@pytest.fixture
def make_agent(crm):
    def build(responses: list) -> tuple[Agent, ScriptedLLM]:
        llm = ScriptedLLM(responses)
        agent = Agent(crm=CrmClient(crm), listings=Listings(), model="test", complete=llm, cost=lambda r: 0.001)
        return agent, llm

    return build
