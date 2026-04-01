"""Redmineflux MCP Server — Configuration."""

import logging
import os
from dataclasses import dataclass
from urllib.parse import urlparse

logger = logging.getLogger("redmineflux-mcp")


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

        # S-07: Validate URL scheme to prevent SSRF / key leakage
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                f"REDMINE_URL must use http or https scheme, got: {parsed.scheme}"
            )
        if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1"):
            logger.warning(
                "REDMINE_URL uses HTTP (not HTTPS) for non-localhost host '%s'. "
                "API keys will be sent in plaintext. Use HTTPS for production.",
                parsed.hostname,
            )

        beta_mode = os.environ.get("REDMINEFLUX_BETA", "true").lower() in ("true", "1", "yes")
        feedback_project = os.environ.get("REDMINEFLUX_FEEDBACK_PROJECT", "ztmcp")
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
