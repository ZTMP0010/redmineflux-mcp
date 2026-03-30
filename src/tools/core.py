"""Redmineflux MCP Server — Core Redmine tools.

Tools for standard Redmine entities: projects, issues, users, time entries,
versions, issue statuses, trackers, and priorities.
"""

from typing import Any

from mcp.server.fastmcp import Context

from ..redmine_client import RedmineClient


def register_core_tools(mcp: Any, client: RedmineClient) -> None:
    """Register all core Redmine tools with the MCP server."""

    # ── Projects ─────────────────────────────────────────────

    @mcp.tool()
    async def redmineflux_core_list_projects(
        ctx: Context,
        limit: int = 25,
        offset: int = 0,
        include: str = "",
    ) -> str:
        """List all projects the API user has access to.

        Args:
            limit: Max results to return (default 25, max 100).
            offset: Skip this many results (for pagination).
            include: Comma-separated extras: trackers, issue_categories, enabled_modules, time_entry_activities.
        """
        params: dict[str, Any] = {"limit": min(limit, 100), "offset": offset}
        if include:
            params["include"] = include
        data = await client.get("/projects.json", params=params)
        projects = data.get("projects", [])
        if not projects:
            return "No projects found."
        lines = [f"Found {data.get('total_count', len(projects))} projects:\n"]
        for p in projects:
            status = "active" if p.get("status") == 1 else "closed/archived"
            lines.append(f"- [{p['identifier']}] {p['name']} (id={p['id']}, {status})")
        return "\n".join(lines)

    @mcp.tool()
    async def redmineflux_core_get_project(
        ctx: Context,
        project_id: str,
        include: str = "",
    ) -> str:
        """Get details of a specific project by ID or identifier.

        Args:
            project_id: Numeric ID or string identifier (e.g. "my-project").
            include: Comma-separated extras: trackers, issue_categories, enabled_modules, time_entry_activities.
        """
        params = {}
        if include:
            params["include"] = include
        data = await client.get(f"/projects/{project_id}.json", params=params)
        p = data["project"]
        lines = [
            f"**{p['name']}** (id={p['id']}, identifier={p['identifier']})",
            f"Description: {p.get('description', 'N/A')}",
            f"Status: {'active' if p.get('status') == 1 else 'closed/archived'}",
            f"Created: {p.get('created_on', 'N/A')}",
            f"Homepage: {p.get('homepage', 'N/A')}",
        ]
        if p.get("parent"):
            lines.append(f"Parent: {p['parent']['name']} (id={p['parent']['id']})")
        return "\n".join(lines)

    # ── Issues ───────────────────────────────────────────────

    @mcp.tool()
    async def redmineflux_core_list_issues(
        ctx: Context,
        project_id: str = "",
        status_id: str = "open",
        tracker_id: int = 0,
        assigned_to_id: int = 0,
        limit: int = 25,
        offset: int = 0,
        sort: str = "updated_on:desc",
    ) -> str:
        """List issues with filters.

        Args:
            project_id: Filter by project identifier or ID. Empty = all projects.
            status_id: "open", "closed", "*" (all), or numeric status ID.
            tracker_id: Filter by tracker ID (0 = all).
            assigned_to_id: Filter by assignee user ID (0 = all).
            limit: Max results (default 25, max 100).
            offset: Pagination offset.
            sort: Sort field:direction, e.g. "priority:desc", "updated_on:desc".
        """
        params: dict[str, Any] = {
            "limit": min(limit, 100),
            "offset": offset,
            "sort": sort,
            "status_id": status_id,
        }
        if project_id:
            params["project_id"] = project_id
        if tracker_id:
            params["tracker_id"] = tracker_id
        if assigned_to_id:
            params["assigned_to_id"] = assigned_to_id
        data = await client.get("/issues.json", params=params)
        issues = data.get("issues", [])
        if not issues:
            return "No issues found matching filters."
        lines = [f"Found {data.get('total_count', len(issues))} issues:\n"]
        for i in issues:
            assignee = i.get("assigned_to", {}).get("name", "unassigned")
            lines.append(
                f"- #{i['id']} [{i['tracker']['name']}] {i['subject']} "
                f"({i['status']['name']}, {i['priority']['name']}, → {assignee})"
            )
        return "\n".join(lines)

    @mcp.tool()
    async def redmineflux_core_get_issue(
        ctx: Context,
        issue_id: int,
        include: str = "",
    ) -> str:
        """Get full details of a specific issue.

        Args:
            issue_id: The issue number.
            include: Comma-separated extras: children, attachments, relations, changesets, journals, watchers, allowed_statuses.
        """
        params = {}
        if include:
            params["include"] = include
        data = await client.get(f"/issues/{issue_id}.json", params=params)
        i = data["issue"]
        assignee = i.get("assigned_to", {}).get("name", "unassigned")
        lines = [
            f"**#{i['id']} {i['subject']}**",
            f"Project: {i['project']['name']}",
            f"Tracker: {i['tracker']['name']}",
            f"Status: {i['status']['name']}",
            f"Priority: {i['priority']['name']}",
            f"Assigned to: {assignee}",
            f"Author: {i['author']['name']}",
            f"Created: {i.get('created_on', 'N/A')}",
            f"Updated: {i.get('updated_on', 'N/A')}",
            f"Done ratio: {i.get('done_ratio', 0)}%",
        ]
        if i.get("estimated_hours"):
            lines.append(f"Estimated: {i['estimated_hours']}h")
        if i.get("description"):
            lines.append(f"\nDescription:\n{i['description']}")
        if i.get("journals"):
            lines.append(f"\n--- Journal ({len(i['journals'])} entries) ---")
            for j in i["journals"][-5:]:  # Last 5 entries
                notes = j.get("notes", "").strip()
                if notes:
                    lines.append(f"  [{j.get('created_on', '')}] {j['user']['name']}: {notes}")
        return "\n".join(lines)

    @mcp.tool()
    async def redmineflux_core_create_issue(
        ctx: Context,
        project_id: str,
        subject: str,
        tracker_id: int = 0,
        description: str = "",
        priority_id: int = 0,
        assigned_to_id: int = 0,
        status_id: int = 0,
        estimated_hours: float = 0,
        parent_issue_id: int = 0,
    ) -> str:
        """Create a new issue.

        Args:
            project_id: Project identifier or numeric ID.
            subject: Issue title.
            tracker_id: Tracker ID (0 = project default).
            description: Issue body text (supports Textile/Markdown).
            priority_id: Priority ID (0 = default).
            assigned_to_id: User ID to assign to (0 = unassigned).
            status_id: Status ID (0 = default).
            estimated_hours: Estimated hours (0 = none).
            parent_issue_id: Parent issue ID for subtasks (0 = none).
        """
        issue: dict[str, Any] = {
            "project_id": project_id,
            "subject": subject,
        }
        if tracker_id:
            issue["tracker_id"] = tracker_id
        if description:
            issue["description"] = description
        if priority_id:
            issue["priority_id"] = priority_id
        if assigned_to_id:
            issue["assigned_to_id"] = assigned_to_id
        if status_id:
            issue["status_id"] = status_id
        if estimated_hours:
            issue["estimated_hours"] = estimated_hours
        if parent_issue_id:
            issue["parent_issue_id"] = parent_issue_id
        data = await client.post("/issues.json", json={"issue": issue})
        i = data["issue"]
        return f"Created issue #{i['id']}: {i['subject']} ({i['status']['name']})"

    @mcp.tool()
    async def redmineflux_core_update_issue(
        ctx: Context,
        issue_id: int,
        subject: str = "",
        description: str = "",
        status_id: int = 0,
        priority_id: int = 0,
        assigned_to_id: int = 0,
        done_ratio: int = -1,
        estimated_hours: float = 0,
        notes: str = "",
    ) -> str:
        """Update an existing issue. Only provided fields are changed.

        Args:
            issue_id: The issue number to update.
            subject: New title (empty = no change).
            description: New description (empty = no change).
            status_id: New status ID (0 = no change).
            priority_id: New priority ID (0 = no change).
            assigned_to_id: New assignee user ID (0 = no change).
            done_ratio: New completion percentage 0-100 (-1 = no change).
            estimated_hours: New estimate (0 = no change).
            notes: Add a journal note/comment.
        """
        issue: dict[str, Any] = {}
        if subject:
            issue["subject"] = subject
        if description:
            issue["description"] = description
        if status_id:
            issue["status_id"] = status_id
        if priority_id:
            issue["priority_id"] = priority_id
        if assigned_to_id:
            issue["assigned_to_id"] = assigned_to_id
        if done_ratio >= 0:
            issue["done_ratio"] = done_ratio
        if estimated_hours:
            issue["estimated_hours"] = estimated_hours
        if notes:
            issue["notes"] = notes
        if not issue:
            return "No fields to update."
        await client.put(f"/issues/{issue_id}.json", json={"issue": issue})
        return f"Updated issue #{issue_id}."

    # ── Time Entries ─────────────────────────────────────────

    @mcp.tool()
    async def redmineflux_core_log_time(
        ctx: Context,
        issue_id: int,
        hours: float,
        activity_id: int,
        comments: str = "",
        spent_on: str = "",
    ) -> str:
        """Log time against an issue.

        Args:
            issue_id: The issue to log time against.
            hours: Hours spent (e.g. 1.5).
            activity_id: Time entry activity ID (use list_time_entry_activities to find IDs).
            comments: Description of work done.
            spent_on: Date in YYYY-MM-DD format (empty = today).
        """
        entry: dict[str, Any] = {
            "issue_id": issue_id,
            "hours": hours,
            "activity_id": activity_id,
        }
        if comments:
            entry["comments"] = comments
        if spent_on:
            entry["spent_on"] = spent_on
        data = await client.post("/time_entries.json", json={"time_entry": entry})
        te = data["time_entry"]
        return f"Logged {te['hours']}h on issue #{issue_id} (entry id={te['id']})"

    @mcp.tool()
    async def redmineflux_core_list_time_entries(
        ctx: Context,
        project_id: str = "",
        issue_id: int = 0,
        user_id: int = 0,
        from_date: str = "",
        to_date: str = "",
        limit: int = 25,
        offset: int = 0,
    ) -> str:
        """List time entries with filters.

        Args:
            project_id: Filter by project (empty = all).
            issue_id: Filter by issue (0 = all).
            user_id: Filter by user (0 = all).
            from_date: Start date YYYY-MM-DD (empty = no filter).
            to_date: End date YYYY-MM-DD (empty = no filter).
            limit: Max results (default 25, max 100).
            offset: Pagination offset.
        """
        params: dict[str, Any] = {"limit": min(limit, 100), "offset": offset}
        if project_id:
            params["project_id"] = project_id
        if issue_id:
            params["issue_id"] = issue_id
        if user_id:
            params["user_id"] = user_id
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        data = await client.get("/time_entries.json", params=params)
        entries = data.get("time_entries", [])
        if not entries:
            return "No time entries found."
        total = sum(e["hours"] for e in entries)
        lines = [f"Found {data.get('total_count', len(entries))} entries (showing {len(entries)}, total: {total}h):\n"]
        for e in entries:
            lines.append(
                f"- {e['spent_on']} | {e['hours']}h | #{e['issue']['id'] if e.get('issue') else 'N/A'} | "
                f"{e['user']['name']} | {e.get('comments', '')}"
            )
        return "\n".join(lines)

    # ── Users ────────────────────────────────────────────────

    @mcp.tool()
    async def redmineflux_core_list_users(
        ctx: Context,
        status: str = "active",
        limit: int = 25,
        offset: int = 0,
    ) -> str:
        """List users (requires admin API key).

        Args:
            status: "active", "registered", "locked", or "*" (all).
            limit: Max results (default 25, max 100).
            offset: Pagination offset.
        """
        params: dict[str, Any] = {"limit": min(limit, 100), "offset": offset}
        if status != "active":
            params["status"] = {"active": 1, "registered": 2, "locked": 3, "*": ""}.get(status, 1)
        data = await client.get("/users.json", params=params)
        users = data.get("users", [])
        if not users:
            return "No users found."
        lines = [f"Found {data.get('total_count', len(users))} users:\n"]
        for u in users:
            lines.append(f"- {u['login']} — {u.get('firstname', '')} {u.get('lastname', '')} (id={u['id']})")
        return "\n".join(lines)

    @mcp.tool()
    async def redmineflux_core_get_current_user(ctx: Context) -> str:
        """Get details of the user associated with the API key."""
        data = await client.get("/users/current.json")
        u = data["user"]
        lines = [
            f"**{u.get('firstname', '')} {u.get('lastname', '')}** (@{u['login']})",
            f"ID: {u['id']}",
            f"Email: {u.get('mail', 'N/A')}",
            f"Admin: {u.get('admin', False)}",
            f"Created: {u.get('created_on', 'N/A')}",
        ]
        return "\n".join(lines)

    # ── Lookups (statuses, trackers, priorities, activities) ─

    @mcp.tool()
    async def redmineflux_core_list_statuses(ctx: Context) -> str:
        """List all issue statuses."""
        data = await client.get("/issue_statuses.json")
        statuses = data.get("issue_statuses", [])
        lines = ["Issue statuses:\n"]
        for s in statuses:
            closed = " (closed)" if s.get("is_closed") else ""
            lines.append(f"- id={s['id']}: {s['name']}{closed}")
        return "\n".join(lines)

    @mcp.tool()
    async def redmineflux_core_list_trackers(ctx: Context) -> str:
        """List all trackers (issue types like Bug, Feature, Task)."""
        data = await client.get("/trackers.json")
        trackers = data.get("trackers", [])
        lines = ["Trackers:\n"]
        for t in trackers:
            lines.append(f"- id={t['id']}: {t['name']}")
        return "\n".join(lines)

    @mcp.tool()
    async def redmineflux_core_list_priorities(ctx: Context) -> str:
        """List all issue priorities."""
        data = await client.get("/enumerations/issue_priorities.json")
        priorities = data.get("issue_priorities", [])
        lines = ["Issue priorities:\n"]
        for p in priorities:
            default = " (default)" if p.get("is_default") else ""
            lines.append(f"- id={p['id']}: {p['name']}{default}")
        return "\n".join(lines)

    @mcp.tool()
    async def redmineflux_core_list_time_entry_activities(ctx: Context) -> str:
        """List available time entry activities (Design, Development, etc.)."""
        data = await client.get("/enumerations/time_entry_activities.json")
        activities = data.get("time_entry_activities", [])
        lines = ["Time entry activities:\n"]
        for a in activities:
            default = " (default)" if a.get("is_default") else ""
            lines.append(f"- id={a['id']}: {a['name']}{default}")
        return "\n".join(lines)

    # ── Versions (Milestones) ────────────────────────────────

    @mcp.tool()
    async def redmineflux_core_list_versions(
        ctx: Context,
        project_id: str,
    ) -> str:
        """List versions/milestones for a project.

        Args:
            project_id: Project identifier or numeric ID.
        """
        data = await client.get(f"/projects/{project_id}/versions.json")
        versions = data.get("versions", [])
        if not versions:
            return f"No versions found for project '{project_id}'."
        lines = [f"Versions for {project_id}:\n"]
        for v in versions:
            due = v.get("due_date", "no due date")
            lines.append(f"- id={v['id']}: {v['name']} ({v['status']}, due: {due})")
        return "\n".join(lines)
