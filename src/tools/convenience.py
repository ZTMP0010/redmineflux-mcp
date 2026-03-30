"""Redmineflux MCP Server — Convenience tools.

Higher-level tools that wrap common multi-call patterns into single calls.
Designed from live testing observations (RMCP-002). Each tool replaces
4-12 individual API calls with one aggregated response.
"""

from typing import Any

from mcp.server.fastmcp import Context

from ..redmine_client import RedmineClient


def register_convenience_tools(mcp: Any, client: RedmineClient) -> None:
    """Register convenience tools with the MCP server."""

    # ── Project Stats ────────────────────────────────────────

    @mcp.tool()
    async def redmineflux_core_project_stats(
        ctx: Context,
        project_id: str = "",
    ) -> str:
        """Get issue count statistics grouped by status for one or all projects.

        Returns total, open, in-progress, resolved, feedback, and closed counts.
        Much faster than calling list_issues multiple times. Use this when someone
        asks "how many issues?", "what's the progress?", or "give me numbers."

        Args:
            project_id: Project identifier. Empty = stats for ALL projects.
        """
        statuses = {1: "New", 2: "In Progress", 3: "Resolved", 4: "Feedback", 5: "Closed", 6: "Rejected"}

        if project_id:
            # Fetch project to get display name
            proj_data = await client.get(f"/projects/{project_id}.json")
            projects = [proj_data["project"]]
        else:
            data = await client.get("/projects.json", params={"limit": 100})
            projects = data.get("projects", [])

        lines = []
        grand_total = 0
        grand_closed = 0

        for proj in projects:
            pid = proj["identifier"]
            counts = {}
            # Get total count
            data = await client.get("/issues.json", params={
                "project_id": pid, "status_id": "*", "limit": 1,
            })
            total = data.get("total_count", 0)
            grand_total += total

            # Get counts per status
            for sid, sname in statuses.items():
                data = await client.get("/issues.json", params={
                    "project_id": pid, "status_id": sid, "limit": 1,
                })
                counts[sname] = data.get("total_count", 0)

            closed = counts.get("Closed", 0) + counts.get("Rejected", 0)
            grand_closed += closed
            pct = f"{closed * 100 // total}%" if total > 0 else "0%"

            lines.append(f"**{proj.get('name', pid)}** — {total} issues ({pct} complete)")
            for sname, count in counts.items():
                if count > 0:
                    lines.append(f"  {sname}: {count}")
            lines.append("")

        if len(projects) > 1:
            grand_pct = f"{grand_closed * 100 // grand_total}%" if grand_total > 0 else "0%"
            lines.insert(0, f"**All Projects** — {grand_total} total issues ({grand_pct} complete)\n")

        return "\n".join(lines) if lines else "No projects found."

    # ── My Workload ──────────────────────────────────────────

    @mcp.tool()
    async def redmineflux_core_my_workload(
        ctx: Context,
        limit: int = 15,
    ) -> str:
        """Get the current user's assigned issues across all projects, sorted by priority.

        Use this when someone asks "what should I work on?", "what's on my plate?",
        or "my tasks". Returns top issues sorted by priority (Immediate first).

        Args:
            limit: Maximum issues to return (default 15). Use 5 for quick overview.
        """
        # Resolve current user
        user_data = await client.get("/users/current.json")
        user = user_data["user"]
        user_id = user["id"]
        user_name = f"{user.get('firstname', '')} {user.get('lastname', '')}".strip()

        # Get assigned open issues sorted by priority
        data = await client.get("/issues.json", params={
            "assigned_to_id": user_id,
            "status_id": "open",
            "sort": "priority:desc",
            "limit": min(limit, 100),
        })
        issues = data.get("issues", [])
        total = data.get("total_count", 0)

        if not issues:
            return f"No open issues assigned to {user_name}."

        # Group by project
        by_project: dict[str, list] = {}
        for i in issues:
            proj_name = i["project"]["name"]
            by_project.setdefault(proj_name, []).append(i)

        lines = [f"**{user_name}** — {total} open issues assigned (showing top {len(issues)}):\n"]

        for proj_name, proj_issues in by_project.items():
            lines.append(f"**{proj_name}** ({len(proj_issues)} shown):")
            for i in proj_issues:
                est = f", est {i['estimated_hours']}h" if i.get("estimated_hours") else ""
                lines.append(
                    f"  - #{i['id']} [{i['priority']['name']}] {i['subject']} "
                    f"({i['status']['name']}{est})"
                )
            lines.append("")

        return "\n".join(lines)

    # ── Project Summary ──────────────────────────────────────

    @mcp.tool()
    async def redmineflux_core_project_summary(
        ctx: Context,
        project_id: str,
    ) -> str:
        """Get a comprehensive summary of a project in one call.

        Returns: description, issue counts by status, version milestones,
        and recent activity. Use this when someone asks "tell me about this project",
        "what's the status of X?", or "give me an overview."

        Args:
            project_id: Project identifier or numeric ID.
        """
        # Project details
        proj_data = await client.get(f"/projects/{project_id}.json", params={"include": "trackers"})
        proj = proj_data["project"]

        # Issue counts
        statuses = {1: "New", 2: "In Progress", 3: "Resolved", 4: "Feedback", 5: "Closed"}
        counts = {}
        total_data = await client.get("/issues.json", params={
            "project_id": project_id, "status_id": "*", "limit": 1,
        })
        total = total_data.get("total_count", 0)

        for sid, sname in statuses.items():
            data = await client.get("/issues.json", params={
                "project_id": project_id, "status_id": sid, "limit": 1,
            })
            counts[sname] = data.get("total_count", 0)

        # Versions
        ver_data = await client.get(f"/projects/{project_id}/versions.json")
        versions = ver_data.get("versions", [])

        # Recent issues (last 5 updated)
        recent_data = await client.get("/issues.json", params={
            "project_id": project_id, "status_id": "*", "sort": "updated_on:desc", "limit": 5,
        })
        recent = recent_data.get("issues", [])

        # Build summary
        closed = counts.get("Closed", 0)
        pct = f"{closed * 100 // total}%" if total > 0 else "0%"

        lines = [
            f"# {proj['name']}",
            f"",
            f"{proj.get('description', 'No description.')}",
            f"",
            f"## Progress: {total} issues ({pct} complete)",
            f"",
        ]
        for sname, count in counts.items():
            bar = "█" * (count * 20 // max(total, 1))
            lines.append(f"  {sname:15s} {count:>5d}  {bar}")

        lines.append(f"\n## Milestones")
        if versions:
            for v in versions:
                status_icon = "✓" if v["status"] == "closed" else "○"
                lines.append(f"  {status_icon} {v['name']} — due {v.get('due_date', 'TBD')} ({v['status']})")
        else:
            lines.append("  No milestones defined.")

        lines.append(f"\n## Recent Activity")
        for i in recent:
            lines.append(
                f"  - #{i['id']} [{i['tracker']['name']}] {i['subject']} "
                f"({i['status']['name']}, {i['priority']['name']})"
            )

        return "\n".join(lines)

    # ── System Onboard ───────────────────────────────────────

    @mcp.tool()
    async def redmineflux_system_onboard(
        ctx: Context,
    ) -> str:
        """Get orientation information for the current user.

        Use this when someone is new, confused, or asks "where do I start?",
        "what should I do?", or "help me get started." Returns: who you are,
        your projects, your assigned tasks, and your teammates.
        """
        # Who am I?
        user_data = await client.get("/users/current.json")
        user = user_data["user"]
        user_name = f"{user.get('firstname', '')} {user.get('lastname', '')}".strip()

        # All projects
        proj_data = await client.get("/projects.json", params={"limit": 100})
        projects = proj_data.get("projects", [])

        # My assigned issues (top 10)
        issues_data = await client.get("/issues.json", params={
            "assigned_to_id": user["id"],
            "status_id": "open",
            "sort": "priority:desc",
            "limit": 10,
        })
        my_issues = issues_data.get("issues", [])
        my_total = issues_data.get("total_count", 0)

        # Team directory
        users_data = await client.get("/users.json", params={"limit": 100})
        all_users = users_data.get("users", [])

        lines = [
            f"# Welcome, {user_name}!",
            f"",
            f"**Your ID:** {user['id']}",
            f"**Login:** {user['login']}",
            f"**Email:** {user.get('mail', 'N/A')}",
            f"**Admin:** {user.get('admin', False)}",
            f"",
            f"## Your Projects ({len(projects)} total)",
            f"",
        ]
        for p in projects:
            lines.append(f"  - **{p['name']}** ({p['identifier']}): {p.get('description', '')[:80]}")

        lines.append(f"\n## Your Top Tasks ({my_total} total assigned)")
        if my_issues:
            for i in my_issues:
                lines.append(
                    f"  - #{i['id']} [{i['priority']['name']}] {i['subject']} "
                    f"— {i['project']['name']} ({i['status']['name']})"
                )
        else:
            lines.append("  No issues assigned to you yet.")

        lines.append(f"\n## Team Directory ({len(all_users)} members)")
        for u in all_users:
            name = f"{u.get('firstname', '')} {u.get('lastname', '')}".strip()
            lines.append(f"  - {name} (@{u['login']}, id={u['id']})")

        lines.append(f"\n## Quick Start")
        lines.append(f"  - To see your tasks: ask about issues assigned to you")
        lines.append(f"  - To log time: tell me the issue number, hours, and what you did")
        lines.append(f"  - To check a project: ask for a project summary")
        lines.append(f"  - To find bugs: ask about open bugs in any project")

        return "\n".join(lines)

    # ── Critical Issues ──────────────────────────────────────

    @mcp.tool()
    async def redmineflux_core_critical_issues(
        ctx: Context,
        project_id: str = "",
        limit: int = 20,
    ) -> str:
        """Get Urgent and Immediate priority open issues.

        Use this during incidents, fire drills, or when someone asks
        "what's critical?", "what's on fire?", or "show me the emergencies."
        Returns only the highest priority open issues.

        Args:
            project_id: Filter to one project (empty = all projects).
            limit: Maximum issues (default 20).
        """
        all_critical = []

        # Priority IDs: 4 = Urgent, 5 = Immediate (Redmine defaults)
        for priority_id in [5, 4]:  # Immediate first
            params: dict[str, Any] = {
                "status_id": "open",
                "priority_id": priority_id,
                "sort": "updated_on:desc",
                "limit": min(limit, 100),
            }
            if project_id:
                params["project_id"] = project_id

            data = await client.get("/issues.json", params=params)
            for issue in data.get("issues", []):
                all_critical.append(issue)

        if not all_critical:
            scope = f"in {project_id}" if project_id else "across all projects"
            return f"No critical issues (Urgent/Immediate) {scope}. All clear."

        lines = [f"**{len(all_critical)} critical issues** (Urgent + Immediate):\n"]

        # Group by project
        by_project: dict[str, list] = {}
        for i in all_critical:
            proj_name = i["project"]["name"]
            by_project.setdefault(proj_name, []).append(i)

        for proj_name, issues in by_project.items():
            lines.append(f"**{proj_name}** ({len(issues)} critical):")
            for i in issues[:limit]:
                assignee = i.get("assigned_to", {}).get("name", "unassigned")
                lines.append(
                    f"  - #{i['id']} [{i['priority']['name']}] {i['subject']} "
                    f"({i['status']['name']}, → {assignee})"
                )
            lines.append("")

        return "\n".join(lines)
