"""Redmineflux MCP Server — Workload Plugin Tools.

Tools for capacity planning, team workload, holidays, and resource reports.
Only registered if the redmineflux_workload plugin is detected.

Key agent use case: "Before assigning this task, check who has capacity."

Spec: RMCP-007
"""

from typing import Any

from mcp.server.fastmcp import Context

from ..redmine_client import RedmineClient

TOOL_COUNT = 5


def register_workload_tools(mcp: Any, client: RedmineClient) -> int:
    """Register Workload plugin tools. Returns count of tools registered."""

    @mcp.tool()
    async def redmineflux_workload_capacity(
        ctx: Context,
        project_id: str = "",
    ) -> str:
        """Get team workload and capacity data.

        Shows each team member's daily/weekly hour allocation, assigned work,
        and available capacity. Use this before assigning tasks to find
        who has bandwidth.

        Args:
            project_id: Optional project filter. If empty, shows all projects.
        """
        params: dict[str, Any] = {}
        if project_id:
            params["project_id"] = project_id

        data = await client.get("/workloads/data.json", params=params)
        users = data.get("users", data.get("data", []))

        if not users:
            return "No workload data found." + (
                f" (project: {project_id})" if project_id else ""
            )

        lines = ["Team Workload & Capacity:\n"]
        for u in users:
            name = u.get("name", u.get("login", f"User #{u.get('id', '?')}"))
            allocated = u.get("allocated_hours", u.get("total_hours", 0))
            capacity = u.get("capacity_hours", u.get("available_hours", 0))
            utilization = u.get("utilization", 0)

            bar = "█" * min(int(utilization / 10), 10) if utilization else ""
            lines.append(
                f"  {name}: {allocated}h allocated / {capacity}h capacity "
                f"({utilization}%) {bar}"
            )

            if u.get("overloaded") or utilization > 100:
                lines.append("    ⚠ OVERLOADED")

        return "\n".join(lines)

    @mcp.tool()
    async def redmineflux_workload_user_issues(
        ctx: Context,
        user_id: int = 0,
        start_date: str = "",
        end_date: str = "",
    ) -> str:
        """Get issues assigned to a user within a time period with estimated/spent hours.

        Shows what a person is working on and how their time is allocated.
        If no user_id, returns data for the current user.

        Args:
            user_id: Redmine user ID (0 = current user).
            start_date: Period start (ISO 8601: YYYY-MM-DD). Defaults to start of current week.
            end_date: Period end (ISO 8601: YYYY-MM-DD). Defaults to end of current week.
        """
        params: dict[str, Any] = {}
        if user_id:
            params["user_id"] = user_id
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        data = await client.get(
            "/workload_apis/user_issues_with_period.json", params=params
        )
        issues = data.get("issues", [])

        if not issues:
            who = f"User #{user_id}" if user_id else "current user"
            return f"No issues found for {who} in the specified period."

        total_estimated = sum(i.get("estimated_hours", 0) or 0 for i in issues)
        total_spent = sum(i.get("spent_hours", 0) or 0 for i in issues)

        lines = [f"Issues assigned ({len(issues)} total, {total_estimated}h estimated, {total_spent}h spent):\n"]
        for i in issues:
            est = i.get("estimated_hours", 0) or 0
            spent = i.get("spent_hours", 0) or 0
            lines.append(
                f"  #{i.get('id')} [{i.get('status', {}).get('name', '?')}] "
                f"{i.get('subject', 'Untitled')}"
            )
            lines.append(
                f"    Est: {est}h | Spent: {spent}h | "
                f"Remaining: {max(est - spent, 0)}h"
            )

        return "\n".join(lines)

    @mcp.tool()
    async def redmineflux_workload_teams(
        ctx: Context,
    ) -> str:
        """Get workload team data — teams, members, and their allocations.

        Shows how teams are structured and who belongs to which team.
        """
        data = await client.get("/workload_teams/teams_data.json")
        teams = data.get("teams", [])

        if not teams:
            return "No workload teams configured."

        lines = ["Workload Teams:\n"]
        for t in teams:
            member_count = len(t.get("members", []))
            lines.append(f"  {t.get('name', 'Unnamed')} ({member_count} members)")
            for m in t.get("members", [])[:10]:
                name = m.get("name", m.get("login", "?"))
                lines.append(f"    - {name}")
            if member_count > 10:
                lines.append(f"    ... and {member_count - 10} more")

        return "\n".join(lines)

    @mcp.tool()
    async def redmineflux_workload_holidays(
        ctx: Context,
    ) -> str:
        """Get the holiday calendar — upcoming holidays and affected users.

        Important for capacity planning — holidays reduce available hours.
        """
        data = await client.get("/user_holidays.json")
        holidays = data.get("holidays", data.get("user_holidays", []))

        if not holidays:
            return "No holidays configured."

        lines = ["Holiday Calendar:\n"]
        for h in holidays:
            name = h.get("name", h.get("holiday_name", "Holiday"))
            date = h.get("date", h.get("start_date", "?"))
            end_date = h.get("end_date", "")
            date_str = f"{date} → {end_date}" if end_date and end_date != date else date
            lines.append(f"  {date_str}: {name}")

        return "\n".join(lines)

    @mcp.tool()
    async def redmineflux_workload_report(
        ctx: Context,
        project_id: str = "",
    ) -> str:
        """Get workload report data — planned hours, available hours, team distribution.

        Provides chart-ready data for resource planning and utilization analysis.

        Args:
            project_id: Optional project filter.
        """
        params: dict[str, Any] = {}
        if project_id:
            params["project_id"] = project_id

        data = await client.get(
            "/workload_reports/workload_chart_data.json", params=params
        )

        if not data or (isinstance(data, dict) and not data.get("data") and not data.get("chart_data")):
            return "No workload report data available." + (
                f" (project: {project_id})" if project_id else ""
            )

        lines = ["Workload Report:\n"]

        chart_data = data.get("chart_data", data.get("data", data))
        if isinstance(chart_data, dict):
            for key, value in chart_data.items():
                if isinstance(value, (int, float)):
                    lines.append(f"  {key}: {value}")
                elif isinstance(value, list):
                    lines.append(f"  {key}: {len(value)} entries")

        planned = data.get("planned_hours", data.get("total_planned", 0))
        available = data.get("available_hours", data.get("total_available", 0))
        if planned or available:
            lines.append(f"\n  Planned hours:   {planned}")
            lines.append(f"  Available hours: {available}")
            if available:
                util = round((planned / available) * 100, 1)
                lines.append(f"  Utilization:     {util}%")

        return "\n".join(lines)

    return TOOL_COUNT
