"""Shared fixtures for Redmineflux MCP integration tests."""

import os
import pytest

# Set env vars before importing server modules
os.environ.setdefault("REDMINE_URL", "http://localhost:3000")
os.environ.setdefault("REDMINE_API_KEY", "9041d40945d754c1c71c37d647d3802e6bb5c2da")

from src.server import create_server


@pytest.fixture(scope="session")
def mcp_server():
    """Create the MCP server once for all tests."""
    return create_server()


@pytest.fixture
def call_tool(mcp_server):
    """Helper to call an MCP tool and extract the text result."""
    async def _call(name: str, args: dict | None = None) -> str:
        result = await mcp_server.call_tool(name, args or {})
        contents, _ = result
        return contents[0].text if contents else ""
    return _call
