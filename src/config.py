"""Redmineflux MCP Server — Configuration."""

import os
from dataclasses import dataclass


@dataclass
class RedmineConfig:
    """Redmine connection settings."""

    url: str
    api_key: str

    @classmethod
    def from_env(cls) -> "RedmineConfig":
        url = os.environ.get("REDMINE_URL", "http://localhost:3000")
        api_key = os.environ.get("REDMINE_API_KEY", "")
        if not api_key:
            raise ValueError("REDMINE_API_KEY environment variable is required")
        return cls(url=url.rstrip("/"), api_key=api_key)
