import httpx
import pytest
from fastapi.testclient import TestClient

from smartval.api import app
from smartval.mcp_server import build_server


@pytest.fixture
def api():
    return TestClient(app)


@pytest.fixture
def mcp_server():
    """MCP server wired to the FastAPI app in-process (no network needed)."""
    def factory():
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    return build_server(http_client_factory=factory)
