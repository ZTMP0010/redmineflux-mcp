"""Redmineflux MCP Server — Redmine REST API client."""

from typing import Any

import httpx

from .config import RedmineConfig


class RedmineAccessError(Exception):
    """Raised when the API key lacks permission for the requested resource.

    Provides a human-readable message that AI agents can relay to users,
    explaining what they don't have access to and how to fix it.
    """

    def __init__(self, status_code: int, path: str, method: str = "GET") -> None:
        self.status_code = status_code
        self.path = path
        self.method = method
        self.message = self._build_message()
        super().__init__(self.message)

    def _build_message(self) -> str:
        resource = self._identify_resource()

        if self.status_code == 401:
            return (
                f"Authentication failed. Your API key is invalid or expired. "
                f"Please check your REDMINE_API_KEY. "
                f"You can find your key at: Redmine → My Account → API access key."
            )

        if self.status_code == 403:
            return (
                f"Access denied: you don't have permission to {self._describe_action()} {resource}. "
                f"Your API key only provides access to projects and resources that your "
                f"Redmine user account has been granted. Ask your Redmine administrator "
                f"to add you to the relevant project or assign the required role. "
                f"To see what you DO have access to, try listing your projects or "
                f"checking your current user details."
            )

        if self.status_code == 404:
            return (
                f"Not found: {resource} does not exist, or you don't have permission to see it. "
                f"Redmine returns 404 for both missing resources and resources you lack access to "
                f"(this is intentional — it prevents information leaking about what exists). "
                f"Verify the ID/identifier is correct. If it exists but you can't see it, "
                f"ask your Redmine administrator for access."
            )

        if self.status_code == 422:
            return (
                f"Validation error on {resource}. The data you provided was rejected by Redmine. "
                f"This could mean a required field is missing, a value is out of range, "
                f"or you're trying to set a status/field that your role doesn't allow."
            )

        return f"Redmine API error {self.status_code} on {self.method} {self.path}."

    def _identify_resource(self) -> str:
        """Extract a human-readable resource name from the API path."""
        path = self.path.rstrip("/").replace(".json", "")
        parts = [p for p in path.split("/") if p]

        if not parts:
            return "the requested resource"

        # Common patterns: /projects/foo, /issues/123, /users/5
        resource_map = {
            "projects": "project",
            "issues": "issue",
            "users": "user",
            "time_entries": "time entry",
            "versions": "version/milestone",
            "memberships": "project membership",
            "issue_statuses": "issue statuses",
            "trackers": "trackers",
            "enumerations": "enumeration",
            "devops": "DevOps resource",
        }

        for key, label in resource_map.items():
            if key in parts:
                idx = parts.index(key)
                if idx + 1 < len(parts) and not parts[idx + 1].startswith("?"):
                    return f"{label} '{parts[idx + 1]}'"
                return f"{label}s"

        return f"'{'/'.join(parts)}'"

    def _describe_action(self) -> str:
        """Map HTTP method to a human-readable action."""
        return {
            "GET": "view",
            "POST": "create",
            "PUT": "update",
            "PATCH": "update",
            "DELETE": "delete",
        }.get(self.method, "access")


def _handle_response(response: httpx.Response, path: str, method: str) -> None:
    """Check response status and raise RedmineAccessError for permission issues."""
    if response.status_code in (401, 403, 404, 422):
        raise RedmineAccessError(response.status_code, path, method)
    response.raise_for_status()


class RedmineClient:
    """Thin wrapper around Redmine REST API.

    Creates a new httpx client per request to avoid event loop issues
    when used across different async contexts.

    Permission errors (401, 403, 404) are raised as RedmineAccessError
    with human-readable messages that AI agents can relay to users.
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
            _handle_response(response, path, "GET")
            return response.json()

    async def post(self, path: str, json: dict[str, Any]) -> dict:
        """POST request to Redmine API."""
        async with self._client() as client:
            response = await client.post(path, json=json)
            _handle_response(response, path, "POST")
            return response.json()

    async def put(self, path: str, json: dict[str, Any]) -> dict | None:
        """PUT request to Redmine API."""
        async with self._client() as client:
            response = await client.put(path, json=json)
            _handle_response(response, path, "PUT")
            if response.content:
                return response.json()
            return None

    async def delete(self, path: str) -> None:
        """DELETE request to Redmine API."""
        async with self._client() as client:
            response = await client.delete(path)
            _handle_response(response, path, "DELETE")

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
