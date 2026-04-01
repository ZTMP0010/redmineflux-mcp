"""Shared fixtures for Redmineflux MCP integration tests.

Requires REDMINE_URL and REDMINE_API_KEY env vars pointing to a Docker
Redmine instance with seed data. See docker-compose.yml and scripts/seed_redmine.py.
"""

import os
import pytest

# Set env vars before importing server modules
os.environ.setdefault("REDMINE_URL", "http://localhost:3000")
# API key must be provided via env var — no default to avoid leaking keys
if "REDMINE_API_KEY" not in os.environ:
    pytest.skip("REDMINE_API_KEY not set — skipping integration tests", allow_module_level=True)

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
