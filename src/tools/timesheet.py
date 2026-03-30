"""Redmineflux MCP Server — Timesheet Plugin Tools.

Tools for timesheet submission, approval workflows, and audit trails.
Only registered if the redmineflux_timesheet plugin is detected.

Note: Time logging itself uses core redmineflux_core_log_time —
the Timesheet plugin sees it automatically. These tools add the
WORKFLOW layer: submit, approve, reject, dashboard.

Spec: RMCP-006
"""

from typing import Any

from mcp.server.fastmcp import Context

from ..redmine_client import RedmineClient

TOOL_COUNT = 6


def register_timesheet_tools(mcp: Any, client: RedmineClient) -> int:
    """Register Timesheet plugin tools. Returns count of tools registered."""

    @mcp.tool()
    async def redmineflux_timesheet_list(
        ctx: Context,
        limit: int = 25,
        offset: int = 0,
    ) -> str:
        """List timesheets for the current user.

        Returns timesheets with their submission status, period, and total hours.
        Use this to check what timesheets exist before submitting.

        Args:
            limit: Max results (default 25, max 100).
            offset: Skip results for pagination.
        """
        params: dict[str, Any] = {"limit": min(limit, 100), "offset": offset}
        data = await client.get("/api/timesheets.json", params=params)
        timesheets = data.get("timesheets", [])
        total = data.get("total_count", len(timesheets))

        if not timesheets:
            return "No timesheets found for the current user."

        lines = [f"Timesheets ({total} total):\n"]
        for ts in timesheets:
            status_icon = {
                "draft": "○",
                "submitted": "⟳",
                "approved": "✓",
                "rejected": "✗",
            }.get(ts.get("status", ""), "?")

            lines.append(
                f"  {status_icon} ID:{ts.get('id')} "
                f"[{ts.get('status', 'unknown')}] "
                f"{ts.get('period_start', '?')} → {ts.get('period_end', '?')} "
                f"({ts.get('total_hours', 0)}h)"
            )

        if total > len(timesheets):
            lines.append(f"\nShowing {len(timesheets)} of {total}.")

        return "\n".join(lines)

    @mcp.tool()
    async def redmineflux_timesheet_submit(
        ctx: Context,
        timesheet_id: int,
    ) -> str:
        """Submit a draft timesheet for manager approval.

        The timesheet must be in 'draft' status. Once submitted, time entries
        may be locked depending on plugin settings.

        Args:
            timesheet_id: The timesheet ID to submit.
        """
        try:
            data = await client.post(
                f"/api/timesheets/{timesheet_id}/submit.json",
                json={},
            )
            return f"Timesheet #{timesheet_id} submitted for approval."
        except Exception as exc:
            error_msg = str(exc)
            if "404" in error_msg:
                return f"Timesheet #{timesheet_id} not found."
            if "422" in error_msg or "unprocessable" in error_msg.lower():
                return f"Cannot submit timesheet #{timesheet_id} — it may not be in 'draft' status."
            if "403" in error_msg:
                return "Access denied. You can only submit your own timesheets."
            return f"Failed to submit timesheet #{timesheet_id}: {error_msg}"

    @mcp.tool()
    async def redmineflux_timesheet_approval_dashboard(
        ctx: Context,
    ) -> str:
        """Get the approval dashboard — lists all timesheets pending your approval.

        Only shows submissions where the current user is the designated approver
        at the current approval level.
        """
        data = await client.get("/approvals/dashboard.json")
        submissions = data.get("submissions", data.get("pending", []))

        if not submissions:
            return "No timesheets pending your approval."

        lines = ["Timesheets pending your approval:\n"]
        for s in submissions:
            user = s.get("user", {})
            user_name = user.get("name", user.get("login", f"User #{s.get('user_id', '?')}"))
            lines.append(
                f"  ⟳ ID:{s.get('id')} — {user_name} "
                f"({s.get('period_start', '?')} → {s.get('period_end', '?')}) "
                f"{s.get('total_hours', 0)}h"
            )
            if s.get("current_level"):
                lines.append(f"    Approval level: {s['current_level']}")

        return "\n".join(lines)

    @mcp.tool()
    async def redmineflux_timesheet_approve(
        ctx: Context,
        timesheet_id: int,
        comment: str = "",
    ) -> str:
        """Approve a submitted timesheet.

        If multi-level approval is configured, this advances to the next level.
        When the final level approves, the timesheet status changes to 'approved'
        and time entries are locked.

        Args:
            timesheet_id: The timesheet/submission ID to approve.
            comment: Optional approval comment.
        """
        payload: dict[str, Any] = {}
        if comment:
            payload["comment"] = comment

        try:
            data = await client.post(
                f"/api/timesheets/{timesheet_id}/approve.json",
                json=payload,
            )
            return f"Timesheet #{timesheet_id} approved." + (
                f" Comment: {comment}" if comment else ""
            )
        except Exception as exc:
            error_msg = str(exc)
            if "404" in error_msg:
                return f"Timesheet #{timesheet_id} not found."
            if "403" in error_msg:
                return "Access denied. You are not the designated approver for this timesheet."
            if "422" in error_msg:
                return f"Cannot approve timesheet #{timesheet_id} — it may not be in 'submitted' status."
            return f"Failed to approve timesheet #{timesheet_id}: {error_msg}"

    @mcp.tool()
    async def redmineflux_timesheet_reject(
        ctx: Context,
        timesheet_id: int,
        comment: str = "",
    ) -> str:
        """Reject a submitted timesheet and send it back to the submitter.

        The timesheet returns to 'draft' status and time entries are unlocked.
        A comment explaining the rejection reason is recommended.

        Args:
            timesheet_id: The timesheet/submission ID to reject.
            comment: Rejection reason (recommended).
        """
        payload: dict[str, Any] = {}
        if comment:
            payload["comment"] = comment

        try:
            data = await client.post(
                f"/api/timesheets/{timesheet_id}/reject.json",
                json=payload,
            )
            return f"Timesheet #{timesheet_id} rejected." + (
                f" Reason: {comment}" if comment else ""
            )
        except Exception as exc:
            error_msg = str(exc)
            if "404" in error_msg:
                return f"Timesheet #{timesheet_id} not found."
            if "403" in error_msg:
                return "Access denied. You are not the designated approver for this timesheet."
            return f"Failed to reject timesheet #{timesheet_id}: {error_msg}"

    @mcp.tool()
    async def redmineflux_timesheet_audit_log(
        ctx: Context,
        limit: int = 25,
        offset: int = 0,
    ) -> str:
        """Query the timesheet audit trail — every submission, approval, and rejection.

        Returns timestamped entries showing who did what and when.
        Useful for compliance reviews and tracking approval history.

        Args:
            limit: Max results (default 25, max 100).
            offset: Skip results for pagination.
        """
        params: dict[str, Any] = {"limit": min(limit, 100), "offset": offset}
        data = await client.get("/audit_logs.json", params=params)
        logs = data.get("audit_logs", data.get("logs", []))
        total = data.get("total_count", len(logs))

        if not logs:
            return "No audit log entries found."

        lines = [f"Timesheet Audit Log ({total} entries):\n"]
        for entry in logs:
            user = entry.get("user", {})
            user_name = user.get("name", user.get("login", f"User #{entry.get('user_id', '?')}"))
            lines.append(
                f"  [{entry.get('created_at', '?')[:16]}] "
                f"{entry.get('action', '?').upper()} "
                f"— {user_name}"
            )
            if entry.get("entity_type"):
                lines.append(
                    f"    {entry['entity_type']} #{entry.get('entity_id', '?')}"
                )
            if entry.get("comment"):
                lines.append(f"    Comment: {entry['comment']}")

        if total > len(logs):
            lines.append(f"\nShowing {len(logs)} of {total}.")

        return "\n".join(lines)

    return TOOL_COUNT
