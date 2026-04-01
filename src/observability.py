"""Redmineflux MCP Server — Observability & Audit Logging.

Logs every MCP tool call as structured JSON Lines for analysis,
debugging, and feedback collection. Implements RMCP-001.
"""

import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .redmine_client import RedmineClient

# Fields that must never appear in logs
REDACTED_FIELDS = {"api_key", "password", "secret", "token", "key", "authorization", "apikey"}


class AuditLogger:
    """Structured JSON audit logger for MCP tool calls."""

    def __init__(self, log_dir: str = "logs", redmine_client: RedmineClient | None = None) -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = f"ses_{uuid.uuid4().hex[:12]}"
        self.tool_call_count = 0
        self._user_cache: dict | None = None
        self._redmine_client = redmine_client
        self._logger = logging.getLogger("redmineflux.audit")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

    def _get_log_file(self) -> Path:
        """Get today's log file path."""
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.log_dir / f"mcp-{date_str}.log"

    def _redact(self, params: dict[str, Any]) -> dict[str, Any]:
        """Remove sensitive fields from parameters."""
        if not params:
            return params
        redacted = {}
        for k, v in params.items():
            if k.lower() in REDACTED_FIELDS:
                redacted[k] = "***REDACTED***"
            elif isinstance(v, dict):
                redacted[k] = self._redact(v)
            elif isinstance(v, list):
                redacted[k] = [
                    self._redact(item) if isinstance(item, dict) else item
                    for item in v
                ]
            else:
                redacted[k] = v
        return redacted

    def _summarize_response(self, text: str) -> dict[str, Any]:
        """Summarize a tool response for logging (avoid storing huge payloads)."""
        if not text:
            return {"length": 0, "preview": ""}

        lines = text.strip().split("\n")
        summary: dict[str, Any] = {"length": len(text), "lines": len(lines)}

        # Extract count if present (e.g., "Found 1594 issues:")
        first_line = lines[0] if lines else ""
        if "Found" in first_line and ("issues" in first_line or "entries" in first_line or "projects" in first_line or "users" in first_line):
            summary["first_line"] = first_line

        # Preview: first 3 data lines (skip header)
        data_lines = [l for l in lines if l.startswith("- ")][:3]
        if data_lines:
            summary["preview"] = data_lines

        return summary

    def _write_entry(self, entry: dict[str, Any]) -> None:
        """Write a single JSON log entry. Never raises — logging failures are silent."""
        try:
            log_file = self._get_log_file()
            with open(log_file, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as e:
            # Logging must never crash tool calls
            print(f"[audit] log write failed: {e}", file=sys.stderr)

    async def resolve_user(self) -> dict | None:
        """Resolve the API key to a user identity. Cached per session."""
        if self._user_cache is not None:
            return self._user_cache
        if self._redmine_client is None:
            return None
        try:
            data = await self._redmine_client.get("/users/current.json")
            user = data.get("user", {})
            self._user_cache = {
                "id": user.get("id"),
                "login": user.get("login"),
                "name": f"{user.get('firstname', '')} {user.get('lastname', '')}".strip(),
            }
        except Exception:
            self._user_cache = {"id": None, "login": "unknown", "name": "unknown"}
        return self._user_cache

    async def log_tool_call(
        self,
        tool_name: str,
        input_params: dict[str, Any],
        response_text: str,
        duration_ms: float,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Log a single tool call."""
        self.tool_call_count += 1
        user = await self.resolve_user()

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "event_type": "tool_call",
            "sequence": self.tool_call_count,
            "tool_name": tool_name,
            "input_params": self._redact(input_params),
            "response_summary": self._summarize_response(response_text) if success else None,
            "duration_ms": round(duration_ms, 1),
            "success": success,
            "error": error,
            "user": user,
        }
        self._write_entry(entry)

    def log_feedback(self, rating: int, comment: str, user: dict | None = None) -> None:
        """Log user feedback."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "event_type": "feedback",
            "rating": rating,
            "comment": comment,
            "tool_calls_in_session": self.tool_call_count,
            "user": user or self._user_cache,
        }
        self._write_entry(entry)

    def log_session_start(self) -> None:
        """Log session start event."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "event_type": "session_start",
        }
        self._write_entry(entry)


def install_audit_middleware(mcp: Any, audit_logger: AuditLogger) -> None:
    """Install server-level middleware that logs ALL tool calls automatically.

    This hooks into FastMCP's call_tool path so every tool is audited
    without needing per-tool decorators. Fixes S-16.
    """
    original_call_tool = mcp.call_tool

    async def audited_call_tool(name: str, arguments: dict | None = None):
        start = time.monotonic()
        input_params = arguments or {}
        try:
            result = await original_call_tool(name, arguments)
            duration_ms = (time.monotonic() - start) * 1000
            # Extract text from result for summary
            contents, _ = result if isinstance(result, tuple) else (result, None)
            response_text = ""
            if contents and hasattr(contents[0], "text"):
                response_text = contents[0].text
            await audit_logger.log_tool_call(
                tool_name=name,
                input_params=input_params,
                response_text=response_text,
                duration_ms=duration_ms,
                success=True,
            )
            return result
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            await audit_logger.log_tool_call(
                tool_name=name,
                input_params=input_params,
                response_text="",
                duration_ms=duration_ms,
                success=False,
                error=type(e).__name__,
            )
            raise

    mcp.call_tool = audited_call_tool
