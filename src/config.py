"""Redmineflux MCP Server — Configuration."""

import os
from dataclasses import dataclass, field


@dataclass
class RedmineConfig:
    """Redmine connection settings."""

    url: str
    api_key: str
    beta_mode: bool = True
    beta_notice: str = ""
    feedback_project: str = ""

    @classmethod
    def from_env(cls) -> "RedmineConfig":
        url = os.environ.get("REDMINE_URL", "http://localhost:3000")
        api_key = os.environ.get("REDMINE_API_KEY", "")
        if not api_key:
            raise ValueError("REDMINE_API_KEY environment variable is required")

        beta_mode = os.environ.get("REDMINEFLUX_BETA", "true").lower() in ("true", "1", "yes")
        feedback_project = os.environ.get("REDMINEFLUX_FEEDBACK_PROJECT", "redmineflux-mcp")
        beta_notice = os.environ.get(
            "REDMINEFLUX_BETA_NOTICE",
            f"This is a BETA version of Redmineflux MCP Server. "
            f"If you encounter any issues or have feedback, please log a ticket "
            f"on the '{feedback_project}' project in Redmine.",
        )

        return cls(
            url=url.rstrip("/"),
            api_key=api_key,
            beta_mode=beta_mode,
            beta_notice=beta_notice,
            feedback_project=feedback_project,
        )
