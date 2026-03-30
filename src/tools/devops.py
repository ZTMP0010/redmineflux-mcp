"""Redmineflux MCP Server — DevOps Plugin Tools.

Tools for CI/CD builds, commits, pull requests, and repositories.
Only registered if the redmineflux_devops plugin is detected on the
target Redmine instance (capability injection via plugin_registry.py).

Spec: RMCP-005
"""

from typing import Any

from mcp.server.fastmcp import Context

from ..redmine_client import RedmineClient

TOOL_COUNT = 8


def register_devops_tools(mcp: Any, client: RedmineClient) -> int:
    """Register all DevOps plugin tools with the MCP server.

    Returns the number of tools registered (for startup logging).
    """

    # ── Builds ──────────────────────────────────────────────────

    @mcp.tool()
    async def redmineflux_devops_list_builds(
        ctx: Context,
        project_id: str,
        status: str = "",
        branch: str = "",
        limit: int = 25,
        offset: int = 0,
    ) -> str:
        """List CI/CD builds for a project. Filter by status or branch.

        Args:
            project_id: Redmine project ID or identifier (e.g., "phoenix-api" or "3").
            status: Filter by build status: pending, running, success, failed, cancelled.
            branch: Filter by branch name (e.g., "main", "develop").
            limit: Max results (default 25, max 100).
            offset: Skip this many results for pagination.
        """
        params: dict[str, Any] = {
            "project_id": project_id,
            "limit": min(limit, 100),
            "offset": offset,
        }
        if status:
            params["status"] = status
        if branch:
            params["branch"] = branch

        data = await client.get("/devops/builds.json", params=params)
        builds = data.get("builds", [])
        total = data.get("total_count", len(builds))

        if not builds:
            return f"No builds found for project '{project_id}'." + (
                f" (filter: status={status})" if status else ""
            ) + (f" (filter: branch={branch})" if branch else "")

        lines = [f"CI/CD Builds for project '{project_id}' ({total} total):\n"]
        for b in builds:
            status_icon = {
                "success": "✓",
                "failed": "✗",
                "running": "⟳",
                "pending": "○",
                "cancelled": "—",
            }.get(b.get("status", ""), "?")

            duration = ""
            if b.get("duration_seconds"):
                mins, secs = divmod(b["duration_seconds"], 60)
                duration = f" ({mins}m{secs}s)" if mins else f" ({secs}s)"

            lines.append(
                f"  {status_icon} #{b.get('build_number', '?')} "
                f"[{b.get('status', 'unknown')}] "
                f"{b.get('branch', '?')}"
                f"{duration} "
                f"— {b.get('commit_sha', '')[:8]} "
                f"({b.get('created_at', '')[:10]})"
            )

            if b.get("issue_id"):
                lines.append(f"    Linked to issue #{b['issue_id']}")

        if total > len(builds):
            lines.append(f"\nShowing {len(builds)} of {total}. Use offset={offset + limit} for next page.")

        return "\n".join(lines)

    # ── Build Detail ────────────────────────────────────────────

    @mcp.tool()
    async def redmineflux_devops_get_build(
        ctx: Context,
        project_id: str,
        build_id: int,
    ) -> str:
        """Get detailed information about a specific CI/CD build.

        Args:
            project_id: Redmine project identifier.
            build_id: The build's database ID.
        """
        try:
            data = await client.get(
                f"/projects/{project_id}/devops_builds/{build_id}.json"
            )
        except Exception:
            return f"Build #{build_id} not found in project '{project_id}'."

        b = data.get("build", data)
        lines = [
            f"Build #{b.get('build_number', build_id)} — {b.get('status', 'unknown').upper()}",
            f"  Provider:   {b.get('provider', '?')}",
            f"  Branch:     {b.get('branch', '?')}",
            f"  Commit:     {b.get('commit_sha', '?')}",
            f"  Trigger:    {b.get('trigger', '?')}",
            f"  Started:    {b.get('started_at', '—')}",
            f"  Finished:   {b.get('finished_at', '—')}",
        ]

        if b.get("duration_seconds"):
            mins, secs = divmod(b["duration_seconds"], 60)
            lines.append(f"  Duration:   {mins}m {secs}s")

        if b.get("url"):
            lines.append(f"  CI URL:     {b['url']}")

        if b.get("issue_id"):
            lines.append(f"  Issue:      #{b['issue_id']}")

        return "\n".join(lines)

    # ── Commits ─────────────────────────────────────────────────

    @mcp.tool()
    async def redmineflux_devops_list_commits(
        ctx: Context,
        project_id: str,
        limit: int = 25,
        offset: int = 0,
    ) -> str:
        """List recent commits linked to a project.

        Args:
            project_id: Redmine project ID or identifier.
            limit: Max results (default 25, max 100).
            offset: Skip this many results for pagination.
        """
        params: dict[str, Any] = {
            "project_id": project_id,
            "limit": min(limit, 100),
            "offset": offset,
        }
        data = await client.get("/devops/commits.json", params=params)
        commits = data.get("commits", [])
        total = data.get("total_count", len(commits))

        if not commits:
            return f"No commits found for project '{project_id}'."

        lines = [f"Recent commits for project '{project_id}' ({total} total):\n"]
        for c in commits:
            sha = c.get("sha", "")[:8]
            msg = c.get("message", "").split("\n")[0][:80]
            author = c.get("author_name", c.get("author", "?"))
            date = c.get("committed_at", c.get("created_at", ""))[:10]
            lines.append(f"  {sha} {msg}")
            lines.append(f"         — {author} ({date})")

            issue_ids = c.get("issue_ids", [])
            if issue_ids:
                lines.append(f"         Issues: {', '.join(f'#{i}' for i in issue_ids)}")

        if total > len(commits):
            lines.append(f"\nShowing {len(commits)} of {total}.")

        return "\n".join(lines)

    # ── Pull Requests ───────────────────────────────────────────

    @mcp.tool()
    async def redmineflux_devops_list_pull_requests(
        ctx: Context,
        project_id: str,
        state: str = "",
        limit: int = 25,
        offset: int = 0,
    ) -> str:
        """List pull requests / merge requests linked to a project.

        Args:
            project_id: Redmine project ID or identifier.
            state: Filter by state: open, closed, merged.
            limit: Max results (default 25, max 100).
            offset: Skip this many results for pagination.
        """
        params: dict[str, Any] = {
            "project_id": project_id,
            "limit": min(limit, 100),
            "offset": offset,
        }
        if state:
            params["state"] = state

        data = await client.get("/devops/pull_requests.json", params=params)
        prs = data.get("pull_requests", [])
        total = data.get("total_count", len(prs))

        if not prs:
            return f"No pull requests found for project '{project_id}'." + (
                f" (filter: state={state})" if state else ""
            )

        lines = [f"Pull Requests for project '{project_id}' ({total} total):\n"]
        for pr in prs:
            state_icon = {"open": "●", "closed": "○", "merged": "✓"}.get(
                pr.get("state", ""), "?"
            )
            lines.append(
                f"  {state_icon} #{pr.get('number', '?')} "
                f"[{pr.get('state', '?')}] "
                f"{pr.get('title', 'Untitled')}"
            )
            lines.append(
                f"    {pr.get('source_branch', '?')} → {pr.get('target_branch', '?')} "
                f"by {pr.get('author', '?')} "
                f"({pr.get('created_at', '')[:10]})"
            )

            issue_ids = pr.get("issue_ids", [])
            if issue_ids:
                lines.append(f"    Issues: {', '.join(f'#{i}' for i in issue_ids)}")

        if total > len(prs):
            lines.append(f"\nShowing {len(prs)} of {total}.")

        return "\n".join(lines)

    # ── Repositories ────────────────────────────────────────────

    @mcp.tool()
    async def redmineflux_devops_list_repositories(
        ctx: Context,
        project_id: str,
    ) -> str:
        """List connected source code repositories for a project.

        Args:
            project_id: Redmine project ID or identifier.
        """
        params: dict[str, Any] = {"project_id": project_id}
        data = await client.get("/devops/repositories.json", params=params)
        repos = data.get("repositories", [])

        if not repos:
            return f"No DevOps repositories connected to project '{project_id}'."

        lines = [f"Connected repositories for project '{project_id}':\n"]
        for r in repos:
            lines.append(
                f"  [{r.get('provider', '?').upper()}] "
                f"{r.get('name', 'Unnamed')}"
            )
            lines.append(f"    URL:     {r.get('url', '—')}")
            lines.append(f"    Branch:  {r.get('default_branch', 'main')}")
            if r.get("webhook_active"):
                lines.append("    Webhook: Active ✓")
            else:
                lines.append("    Webhook: Not configured")

        return "\n".join(lines)

    # ── Trigger Build ───────────────────────────────────────────

    @mcp.tool()
    async def redmineflux_devops_trigger_build(
        ctx: Context,
        project_id: str,
        build_id: int,
    ) -> str:
        """Trigger a rebuild for a specific CI/CD build.

        Rate limited to 5 manual triggers per project per hour.

        Args:
            project_id: Redmine project identifier.
            build_id: The build's database ID to re-trigger.
        """
        try:
            data = await client.post(
                f"/projects/{project_id}/devops_builds/{build_id}/trigger.json",
                json={},
            )
            return f"Build #{build_id} triggered successfully in project '{project_id}'."
        except Exception as exc:
            error_msg = str(exc)
            if "rate" in error_msg.lower() or "limit" in error_msg.lower():
                return (
                    f"Build trigger rate limited for project '{project_id}'. "
                    "Max 5 manual triggers per project per hour. Try again later."
                )
            if "403" in error_msg or "forbidden" in error_msg.lower():
                return (
                    f"Access denied. You need 'trigger_builds' permission "
                    f"in project '{project_id}' to trigger builds."
                )
            if "404" in error_msg:
                return f"Build #{build_id} not found in project '{project_id}'."
            return f"Failed to trigger build #{build_id}: {error_msg}"

    # ── Project Summary ─────────────────────────────────────────

    @mcp.tool()
    async def redmineflux_devops_project_summary(
        ctx: Context,
        project_id: str,
    ) -> str:
        """Get a DevOps overview for a project: recent builds, commits, PRs, repos.

        Aggregates data from multiple DevOps endpoints into a single summary.
        Use this instead of calling each tool separately for a quick overview.

        Args:
            project_id: Redmine project ID or identifier.
        """
        params: dict[str, Any] = {"project_id": project_id, "limit": 10}

        # Fetch all four data sources (best-effort — any can fail)
        builds_data: dict = {}
        commits_data: dict = {}
        prs_data: dict = {}
        repos_data: dict = {}

        try:
            builds_data = await client.get("/devops/builds.json", params=params)
        except Exception:
            pass
        try:
            commits_data = await client.get("/devops/commits.json", params=params)
        except Exception:
            pass
        try:
            prs_data = await client.get("/devops/pull_requests.json", params=params)
        except Exception:
            pass
        try:
            repos_data = await client.get(
                "/devops/repositories.json", params={"project_id": project_id}
            )
        except Exception:
            pass

        builds = builds_data.get("builds", [])
        commits = commits_data.get("commits", [])
        prs = prs_data.get("pull_requests", [])
        repos = repos_data.get("repositories", [])

        if not any([builds, commits, prs, repos]):
            return f"No DevOps data found for project '{project_id}'. Is the DevOps plugin configured for this project?"

        lines = [f"DevOps Summary — Project '{project_id}'\n"]

        # Build stats
        if builds:
            total_builds = builds_data.get("total_count", len(builds))
            passed = sum(1 for b in builds if b.get("status") == "success")
            failed = sum(1 for b in builds if b.get("status") == "failed")
            running = sum(1 for b in builds if b.get("status") == "running")
            lines.append(f"  Builds:  {total_builds} total (recent: {passed} passed, {failed} failed, {running} running)")
            latest = builds[0] if builds else None
            if latest:
                lines.append(
                    f"  Latest:  #{latest.get('build_number', '?')} "
                    f"[{latest.get('status', '?')}] "
                    f"on {latest.get('branch', '?')} "
                    f"({latest.get('created_at', '')[:10]})"
                )
        else:
            lines.append("  Builds:  None")

        # Commit stats
        if commits:
            total_commits = commits_data.get("total_count", len(commits))
            lines.append(f"  Commits: {total_commits} total")
            latest_c = commits[0] if commits else None
            if latest_c:
                lines.append(
                    f"  Latest:  {latest_c.get('sha', '')[:8]} "
                    f"— {latest_c.get('message', '').split(chr(10))[0][:60]}"
                )
        else:
            lines.append("  Commits: None")

        # PR stats
        if prs:
            total_prs = prs_data.get("total_count", len(prs))
            open_prs = sum(1 for p in prs if p.get("state") == "open")
            merged_prs = sum(1 for p in prs if p.get("state") == "merged")
            lines.append(f"  PRs:     {total_prs} total ({open_prs} open, {merged_prs} merged)")
        else:
            lines.append("  PRs:     None")

        # Repos
        lines.append(f"  Repos:   {len(repos)} connected")
        for r in repos:
            lines.append(f"           [{r.get('provider', '?').upper()}] {r.get('name', '?')}")

        return "\n".join(lines)

    # ── Build Status on Issue ───────────────────────────────────

    @mcp.tool()
    async def redmineflux_devops_issue_builds(
        ctx: Context,
        project_id: str,
        issue_id: int,
    ) -> str:
        """Get CI/CD build status for a specific issue.

        Shows all builds linked to this issue via commit messages or branch names.

        Args:
            project_id: Redmine project ID or identifier.
            issue_id: The Redmine issue ID to check builds for.
        """
        params: dict[str, Any] = {
            "project_id": project_id,
            "issue_id": issue_id,
            "limit": 20,
        }
        data = await client.get("/devops/builds.json", params=params)
        builds = data.get("builds", [])

        if not builds:
            return f"No CI/CD builds linked to issue #{issue_id}."

        lines = [f"Builds linked to issue #{issue_id}:\n"]
        for b in builds:
            status_icon = {
                "success": "✓",
                "failed": "✗",
                "running": "⟳",
                "pending": "○",
            }.get(b.get("status", ""), "?")

            duration = ""
            if b.get("duration_seconds"):
                mins, secs = divmod(b["duration_seconds"], 60)
                duration = f" ({mins}m{secs}s)"

            lines.append(
                f"  {status_icon} #{b.get('build_number', '?')} "
                f"[{b.get('status', '?')}] "
                f"{b.get('branch', '?')}{duration} "
                f"({b.get('created_at', '')[:10]})"
            )

        return "\n".join(lines)

    return TOOL_COUNT
