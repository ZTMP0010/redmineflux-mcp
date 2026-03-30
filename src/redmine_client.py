"""Redmineflux MCP Server — Redmine REST API client."""

from typing import Any

import httpx

from .config import RedmineConfig


class RedmineClient:
    """Thin wrapper around Redmine REST API.

    Creates a new httpx client per request to avoid event loop issues
    when used across different async contexts.
    """

    def __init__(self, config: RedmineConfig) -> None:
        self.config = config
        self._headers = {
            "X-Redmine-API-Key": config.api_key,
            "Content-Type": "application/json",
        }

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.config.url,
            headers=self._headers,
            timeout=30.0,
        )

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        """GET request to Redmine API."""
        async with self._client() as client:
            response = await client.get(path, params=params)
            response.raise_for_status()
            return response.json()

    async def post(self, path: str, json: dict[str, Any]) -> dict:
        """POST request to Redmine API."""
        async with self._client() as client:
            response = await client.post(path, json=json)
            response.raise_for_status()
            return response.json()

    async def put(self, path: str, json: dict[str, Any]) -> dict | None:
        """PUT request to Redmine API."""
        async with self._client() as client:
            response = await client.put(path, json=json)
            response.raise_for_status()
            if response.content:
                return response.json()
            return None

    async def delete(self, path: str) -> None:
        """DELETE request to Redmine API."""
        async with self._client() as client:
            response = await client.delete(path)
            response.raise_for_status()

    def probe_sync(self, path: str, timeout: float = 2.0) -> int:
        """Synchronous GET for plugin detection. Returns HTTP status code.

        Uses sync httpx.Client (not async) to avoid event loop conflicts
        with FastMCP's transport. Each call creates its own client instance
        for thread safety (used with ThreadPoolExecutor).
        """
        try:
            with httpx.Client(
                base_url=self.config.url,
                headers=self._headers,
                timeout=timeout,
            ) as client:
                response = client.get(path)
                return response.status_code
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError):
            return 0  # Unreachable or timed out
