import pytest
from mcp import Client

from smartval.agent import run_agent

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeLLM:
    """Scripted stand-in for Ollama: first requests a tool call, then answers."""

    def __init__(self):
        self.calls = []

    async def chat(self, model, messages, tools):
        self.calls.append(messages)
        if len(self.calls) == 1:
            assert any(t["function"]["name"] == "search_products" for t in tools)
            return {"message": {"content": "", "tool_calls": [
                {"function": {"name": "search_products", "arguments": {"query": "laptop programmering", "max_price_sek": 10000}}}
            ]}}
        tool_msg = messages[-1]
        assert tool_msg["role"] == "tool" and "lap-001" in tool_msg["content"]
        return {"message": {"content": "Jag rekommenderar lap-001 (8990 kr)."}}


async def test_agent_calls_tool_then_answers(mcp_server):
    llm = FakeLLM()
    async with Client(mcp_server) as client:
        answer = await run_agent("Bästa laptop under 10000 kr?", client, llm, model="fake")
    assert "lap-001" in answer
    assert len(llm.calls) == 2
