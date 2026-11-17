import json

import pytest
from mcp import Client

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_tools_are_listed(mcp_server):
    async with Client(mcp_server) as client:
        names = {t.name for t in (await client.list_tools()).tools}
    assert {"search_products", "get_product", "compare_products", "list_products", "list_categories"} <= names


async def test_search_tool_returns_json(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool("search_products", {"query": "OLED laptop", "max_price_sek": 10000})
    hits = json.loads(result.content[0].text)
    assert hits[0]["product"]["id"] == "lap-001"


async def test_get_product_not_found(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool("get_product", {"product_id": "nope"})
    assert "error" in json.loads(result.content[0].text)
