"""Redmineflux MCP Server — Feedback tool.

Allows users to rate their MCP session and provide comments.
Part of RMCP-001 Observability & Feedback Loop.
"""

from typing import Any

from mcp.server.fastmcp import Context

from ..observability import AuditLogger


def register_feedback_tools(mcp: Any, audit_logger: AuditLogger) -> None:
    """Register feedback tools with the MCP server."""

    @mcp.tool()
    async def redmineflux_system_feedback(
        ctx: Context,
        rating: int,
        comment: str = "",
    ) -> str:
        """Submit feedback about your MCP session quality.

        Call this after using Redmineflux tools to help us improve.
        Your feedback is logged locally and never shared externally.

        Args:
            rating: Quality rating from 1 (poor) to 5 (excellent).
            comment: Optional comment about what worked or didn't.
        """
        if rating < 1 or rating > 5:
            return "Rating must be between 1 and 5."

        audit_logger.log_feedback(rating=rating, comment=comment)

        labels = {1: "poor", 2: "fair", 3: "good", 4: "very good", 5: "excellent"}
        return (
            f"Thank you for your feedback! Rated: {rating}/5 ({labels.get(rating, '')})."
            + (f" Comment: {comment}" if comment else "")
            + f" Session had {audit_logger.tool_call_count} tool calls."
        )
