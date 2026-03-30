"""Redmineflux MCP Server — Agile Board Plugin Tools.

Tools for sprint management, kanban board state, and agile workflows.
Only registered if the agile_board plugin is detected.

Key design: The Agile Board is a VIEW over issues. Agents read board state
via these tools and manipulate issues via core tools. Creating an issue
on the board = redmineflux_core_create_issue with the right version/sprint.

Spec: RMCP-008
"""

from typing import Any

from mcp.server.fastmcp import Context

from ..redmine_client import RedmineClient

TOOL_COUNT = 5


def register_agile_tools(mcp: Any, client: RedmineClient) -> int:
    """Register Agile Board plugin tools. Returns count of tools registered."""

    @mcp.tool()
    async def redmineflux_agile_board(
        ctx: Context,
        project_id: str = "",
    ) -> str:
        """Get the agile/kanban board overview — columns with issue counts.

        Shows the current state of the board: which columns exist,
        how many issues are in each, and any WIP limit breaches.

        Args:
            project_id: Optional project filter.
        """
        params: dict[str, Any] = {}
        if project_id:
            params["project_id"] = project_id

        data = await client.get("/agile_board.json", params=params)
        board = data.get("board", data)

        if not board:
            return "No agile board data found." + (
                f" (project: {project_id})" if project_id else ""
            )

        lines = ["Agile Board:\n"]

        columns = board.get("columns", board.get("board_columns", []))
        if columns:
            for col in columns:
                name = col.get("name", col.get("status_name", "?"))
                count = col.get("issue_count", col.get("count", 0))
                wip = col.get("wip_limit", 0)

                wip_str = ""
                if wip and count > wip:
                    wip_str = f" ⚠ WIP EXCEEDED (limit: {wip})"
                elif wip:
                    wip_str = f" (WIP limit: {wip})"

                lines.append(f"  [{name}]: {count} issues{wip_str}")
        else:
            lines.append("  No columns configured.")

        total = sum(c.get("issue_count", c.get("count", 0)) for c in columns) if columns else 0
        lines.append(f"\n  Total: {total} issues on board")

        return "\n".join(lines)

    @mcp.tool()
    async def redmineflux_agile_sprints(
        ctx: Context,
        project_id: str = "",
    ) -> str:
        """List sprints/iterations with status, dates, and issue counts.

        Shows current, upcoming, and past sprints. Use this to understand
        sprint planning and velocity.

        Args:
            project_id: Optional project filter.
        """
        params: dict[str, Any] = {}
        if project_id:
            params["project_id"] = project_id

        data = await client.get("/sprint_crafts/fetch_sprints.json", params=params)
        sprints = data.get("sprints", data.get("sprint_crafts", []))

        if not sprints:
            return "No sprints found." + (
                f" (project: {project_id})" if project_id else ""
            )

        lines = ["Sprints:\n"]
        for s in sprints:
            status = s.get("status", "open")
            status_icon = {"open": "●", "closed": "○", "locked": "🔒"}.get(status, "?")
            name = s.get("name", "Unnamed Sprint")
            start = s.get("start_date", s.get("effective_date", "?"))
            end = s.get("due_date", s.get("end_date", "?"))
            issue_count = s.get("issue_count", s.get("issues_count", "?"))

            lines.append(
                f"  {status_icon} {name} [{status}]"
            )
            lines.append(
                f"    {start} → {end} | {issue_count} issues"
            )

            if s.get("story_points"):
                lines.append(f"    Story points: {s['story_points']}")

        return "\n".join(lines)

    @mcp.tool()
    async def redmineflux_agile_columns(
        ctx: Context,
        project_id: str = "",
    ) -> str:
        """Get board column configuration — status mapping and WIP limits.

        Shows which issue statuses map to which board columns,
        and what WIP limits are set.

        Args:
            project_id: Optional project filter.
        """
        params: dict[str, Any] = {}
        if project_id:
            params["project_id"] = project_id

        data = await client.get("/board_column_values.json", params=params)
        columns = data.get("columns", data.get("board_columns", []))

        if not columns:
            return "No board columns configured." + (
                f" (project: {project_id})" if project_id else ""
            )

        lines = ["Board Columns:\n"]
        for i, col in enumerate(columns, 1):
            name = col.get("name", col.get("status_name", "?"))
            wip = col.get("wip_limit", 0)
            status_id = col.get("status_id", "?")

            lines.append(f"  {i}. {name}")
            lines.append(f"     Status ID: {status_id}")
            if wip:
                lines.append(f"     WIP limit: {wip}")

        return "\n".join(lines)

    @mcp.tool()
    async def redmineflux_agile_permissions(
        ctx: Context,
        project_id: str = "",
    ) -> str:
        """Check agile board permissions for the current user.

        Shows what the current API user can do on the agile board.

        Args:
            project_id: Project to check permissions for.
        """
        params: dict[str, Any] = {}
        if project_id:
            params["project_id"] = project_id

        data = await client.get("/agile/user_permissions.json", params=params)
        perms = data.get("permissions", data)

        if not perms:
            return "No agile permissions data available."

        lines = ["Agile Board Permissions:\n"]
        if isinstance(perms, dict):
            for perm, value in perms.items():
                icon = "✓" if value else "✗"
                lines.append(f"  {icon} {perm}")
        elif isinstance(perms, list):
            for perm in perms:
                lines.append(f"  ✓ {perm}")

        return "\n".join(lines)

    @mcp.tool()
    async def redmineflux_agile_sprint_detail(
        ctx: Context,
        project_id: str = "",
    ) -> str:
        """Get detailed sprint data — issues in current sprint with status and assignee.

        Shows the sprint backlog with story points, status, and who's working on what.
        Useful for standup summaries and sprint reviews.

        Args:
            project_id: Project to get sprint data for.
        """
        params: dict[str, Any] = {}
        if project_id:
            params["project_id"] = project_id

        data = await client.get("/agile_versions/sprints.json", params=params)
        sprints = data.get("sprints", data.get("versions", []))

        if not sprints:
            return "No sprint detail available." + (
                f" (project: {project_id})" if project_id else ""
            )

        lines = []
        for sprint in sprints[:3]:  # Show last 3 sprints max
            name = sprint.get("name", "Unnamed Sprint")
            status = sprint.get("status", "open")
            lines.append(f"\n{name} [{status}]:")

            issues = sprint.get("issues", [])
            if not issues:
                lines.append("  No issues in this sprint.")
                continue

            for issue in issues:
                status_name = issue.get("status", {}).get("name", "?")
                assignee = issue.get("assigned_to", {}).get("name", "Unassigned")
                sp = issue.get("story_points", "")
                sp_str = f" ({sp} pts)" if sp else ""

                lines.append(
                    f"  #{issue.get('id')} [{status_name}] "
                    f"{issue.get('subject', 'Untitled')}{sp_str}"
                )
                lines.append(f"    → {assignee}")

        return "\n".join(lines)

    return TOOL_COUNT
