"""MCP server that exposes the SmartValGuiden REST API as tools for AI agents.

Any MCP client (Claude Desktop, VS Code, the Ollama agent in this repo, ...)
can connect and call these tools.

    python -m smartval.mcp_server                 # stdio transport
    python -m smartval.mcp_server --http          # streamable HTTP on :8001/mcp
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

API_URL = os.environ.get("SMARTVAL_API_URL", "http://localhost:8000")


def make_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=API_URL, timeout=10.0)


def build_server(http_client_factory=make_http_client) -> MCPServer:
    """Create the MCP server. The HTTP client factory is injectable for tests."""
    server = MCPServer(
        name="smartval",
        instructions=(
            "Tools for searching and comparing consumer electronics in the "
            "SmartValGuiden.se catalogue. Prices are in SEK. Always base answers "
            "on tool results and cite product ids."
        ),
    )

    async def get(path: str, params: dict[str, Any] | None = None) -> Any:
        params = {k: v for k, v in (params or {}).items() if v is not None}
        async with http_client_factory() as client:
            resp = await client.get(path, params=params)
            if resp.status_code == 404:
                return {"error": resp.json().get("detail", "not found")}
            resp.raise_for_status()
            return resp.json()

    @server.tool()
    async def search_products(query: str, category: str | None = None,
                              max_price_sek: int | None = None, limit: int = 5) -> str:
        """Search the product catalogue with a free-text query (Swedish or English).

        Use this first to find relevant products. Optionally filter by category
        (laptop, phone, headphones, monitor, tablet) and a maximum price in SEK.
        """
        hits = await get("/search", {"q": query, "category": category,
                                     "max_price": max_price_sek, "limit": limit})
        return json.dumps(hits, ensure_ascii=False)

    @server.tool()
    async def list_products(category: str | None = None, brand: str | None = None,
                            max_price_sek: int | None = None, sort: str = "price") -> str:
        """List products filtered by category, brand and max price. sort: price, rating or name."""
        products = await get("/products", {"category": category, "brand": brand,
                                           "max_price": max_price_sek, "sort": sort})
        return json.dumps(products, ensure_ascii=False)

    @server.tool()
    async def get_product(product_id: str) -> str:
        """Get full details and specs for one product by its id (e.g. 'lap-001')."""
        return json.dumps(await get(f"/products/{product_id}"), ensure_ascii=False)

    @server.tool()
    async def compare_products(product_ids: list[str]) -> str:
        """Compare two or more products side by side (price, rating and specs)."""
        return json.dumps(await get("/compare", {"ids": ",".join(product_ids)}), ensure_ascii=False)

    @server.tool()
    async def list_categories() -> str:
        """List all product categories in the catalogue."""
        return json.dumps(await get("/categories"), ensure_ascii=False)

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="SmartValGuiden MCP server")
    parser.add_argument("--http", action="store_true", help="serve over streamable HTTP instead of stdio")
    parser.add_argument("--host", default=os.environ.get("MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MCP_PORT", "8001")))
    args = parser.parse_args()
    server = build_server()
    if args.http:
        server.run("streamable-http", host=args.host, port=args.port)
    else:
        server.run("stdio")


if __name__ == "__main__":
    main()
