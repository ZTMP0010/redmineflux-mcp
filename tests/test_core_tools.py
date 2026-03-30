"""Integration tests for Redmineflux MCP tools.

Runs against a live Docker Redmine instance with NovaCrest enterprise data.
Prerequisites:
    - docker compose up -d
    - python scripts/seed_enterprise.py --key <api_key>

Enterprise data (NovaCrest Technologies):
    - 6 projects: phoenix-platform, mercury-mobile, atlas-cloud, orion-crm, nova-marketing, helios-hr
    - 22 users including 3 AI agents (agent-pm, agent-qa, agent-hr)
    - 3,500+ issues, 1,800+ time entries, 27 versions
    - Trackers: Bug(1), Feature(2), Support(3)
    - Priorities: Low(1), Normal(2), High(3), Urgent(4), Immediate(5)
    - Activities: Design(8), Development(9)
    - Statuses: New(1), In Progress(2), Resolved(3), Feedback(4), Closed(5), Rejected(6)
"""

import pytest


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PROJECTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestListProjects:
    async def test_returns_all_projects(self, call_tool):
        result = await call_tool("redmineflux_core_list_projects")
        assert "phoenix-platform" in result
        assert "mercury-mobile" in result
        assert "atlas-cloud" in result
        assert "orion-crm" in result
        assert "nova-marketing" in result
        assert "helios-hr" in result

    async def test_pagination_limit(self, call_tool):
        result = await call_tool("redmineflux_core_list_projects", {"limit": 2})
        lines = [l for l in result.split("\n") if l.startswith("- [")]
        assert len(lines) == 2

    async def test_pagination_offset(self, call_tool):
        result = await call_tool("redmineflux_core_list_projects", {"limit": 1, "offset": 5})
        lines = [l for l in result.split("\n") if l.startswith("- [")]
        assert len(lines) == 1


class TestGetProject:
    async def test_by_identifier(self, call_tool):
        result = await call_tool("redmineflux_core_get_project", {"project_id": "phoenix-platform"})
        assert "Phoenix Platform" in result

    async def test_by_numeric_id(self, call_tool):
        result = await call_tool("redmineflux_core_get_project", {"project_id": "1"})
        assert "Phoenix Platform" in result or "Atlas" in result  # ID depends on creation order

    async def test_nonexistent_project(self, call_tool):
        with pytest.raises(Exception):
            await call_tool("redmineflux_core_get_project", {"project_id": "nonexistent-xyz"})

    async def test_includes_description(self, call_tool):
        result = await call_tool("redmineflux_core_get_project", {"project_id": "phoenix-platform"})
        assert "Description:" in result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ISSUES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestListIssues:
    async def test_returns_issues(self, call_tool):
        result = await call_tool("redmineflux_core_list_issues")
        assert "Found" in result

    async def test_filter_by_project(self, call_tool):
        result = await call_tool("redmineflux_core_list_issues", {"project_id": "phoenix-platform"})
        assert "Found" in result

    async def test_filter_by_tracker_bug(self, call_tool):
        result = await call_tool("redmineflux_core_list_issues", {"tracker_id": 1})
        assert "[Bug]" in result

    async def test_filter_by_tracker_feature(self, call_tool):
        result = await call_tool("redmineflux_core_list_issues", {"tracker_id": 2})
        assert "[Feature]" in result

    async def test_pagination(self, call_tool):
        result = await call_tool("redmineflux_core_list_issues", {"limit": 3})
        lines = [l for l in result.split("\n") if l.startswith("- #")]
        assert len(lines) == 3

    async def test_all_statuses(self, call_tool):
        result = await call_tool("redmineflux_core_list_issues", {"status_id": "*"})
        assert "Found" in result

    async def test_sort_by_priority(self, call_tool):
        result = await call_tool("redmineflux_core_list_issues", {"sort": "priority:desc", "limit": 5})
        assert "Found" in result


class TestGetIssue:
    async def test_issue_details(self, call_tool):
        result = await call_tool("redmineflux_core_get_issue", {"issue_id": 1})
        assert "Project:" in result
        assert "Status:" in result
        assert "Priority:" in result

    async def test_nonexistent_issue(self, call_tool):
        with pytest.raises(Exception):
            await call_tool("redmineflux_core_get_issue", {"issue_id": 99999})


class TestCreateIssue:
    async def test_create_simple_issue(self, call_tool):
        result = await call_tool("redmineflux_core_create_issue", {
            "project_id": "phoenix-platform",
            "subject": "Test: Simple issue creation",
        })
        assert "Created issue #" in result

    async def test_create_full_issue(self, call_tool):
        result = await call_tool("redmineflux_core_create_issue", {
            "project_id": "phoenix-platform",
            "subject": "Test: Full issue with all fields",
            "tracker_id": 1,
            "description": "Created by MCP integration test suite.",
            "priority_id": 3,
            "estimated_hours": 4.5,
        })
        assert "Created issue #" in result

    async def test_create_with_invalid_project(self, call_tool):
        with pytest.raises(Exception):
            await call_tool("redmineflux_core_create_issue", {
                "project_id": "nonexistent-project",
                "subject": "Should fail",
            })


class TestUpdateIssue:
    async def test_update_status_and_verify(self, call_tool):
        create_result = await call_tool("redmineflux_core_create_issue", {
            "project_id": "atlas-cloud",
            "subject": "Test: Update status",
        })
        issue_id = int(create_result.split("#")[1].split(":")[0])

        result = await call_tool("redmineflux_core_update_issue", {
            "issue_id": issue_id,
            "status_id": 2,
        })
        assert f"Updated issue #{issue_id}" in result

        detail = await call_tool("redmineflux_core_get_issue", {"issue_id": issue_id})
        assert "In Progress" in detail

    async def test_update_no_fields(self, call_tool):
        result = await call_tool("redmineflux_core_update_issue", {"issue_id": 1})
        assert "No fields to update" in result

    async def test_update_nonexistent_issue(self, call_tool):
        with pytest.raises(Exception):
            await call_tool("redmineflux_core_update_issue", {"issue_id": 99999, "subject": "Fail"})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TIME ENTRIES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestLogTime:
    async def test_log_time(self, call_tool):
        result = await call_tool("redmineflux_core_log_time", {
            "issue_id": 1,
            "hours": 2.0,
            "activity_id": 9,
            "comments": "Test: time logging via MCP",
        })
        assert "Logged 2.0h on issue #1" in result

    async def test_log_time_invalid_issue(self, call_tool):
        with pytest.raises(Exception):
            await call_tool("redmineflux_core_log_time", {"issue_id": 99999, "hours": 1.0, "activity_id": 9})


class TestListTimeEntries:
    async def test_list_all(self, call_tool):
        result = await call_tool("redmineflux_core_list_time_entries")
        assert "Found" in result

    async def test_filter_by_date_range(self, call_tool):
        result = await call_tool("redmineflux_core_list_time_entries", {
            "from_date": "2025-10-01", "to_date": "2026-03-27",
        })
        assert "Found" in result

    async def test_empty_result(self, call_tool):
        result = await call_tool("redmineflux_core_list_time_entries", {
            "from_date": "2020-01-01", "to_date": "2020-01-02",
        })
        assert "No time entries" in result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# USERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestListUsers:
    async def test_list_active_users(self, call_tool):
        result = await call_tool("redmineflux_core_list_users", {"limit": 100})
        assert "james.harrison" in result
        assert "emma.larsson" in result
        assert "agent-pm" in result

    async def test_pagination(self, call_tool):
        result = await call_tool("redmineflux_core_list_users", {"limit": 2})
        lines = [l for l in result.split("\n") if l.startswith("- ")]
        assert len(lines) == 2


class TestGetCurrentUser:
    async def test_returns_admin(self, call_tool):
        result = await call_tool("redmineflux_core_get_current_user")
        assert "Admin" in result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOOKUPS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestLookups:
    async def test_statuses(self, call_tool):
        result = await call_tool("redmineflux_core_list_statuses")
        assert "New" in result
        assert "Closed" in result

    async def test_trackers(self, call_tool):
        result = await call_tool("redmineflux_core_list_trackers")
        assert "Bug" in result
        assert "Feature" in result

    async def test_priorities(self, call_tool):
        result = await call_tool("redmineflux_core_list_priorities")
        assert "Normal" in result
        assert "Urgent" in result

    async def test_activities(self, call_tool):
        result = await call_tool("redmineflux_core_list_time_entry_activities")
        assert "Design" in result
        assert "Development" in result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VERSIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestListVersions:
    async def test_phoenix_versions(self, call_tool):
        result = await call_tool("redmineflux_core_list_versions", {"project_id": "phoenix-platform"})
        assert "Architecture" in result
        assert "Production Launch" in result

    async def test_nonexistent_project(self, call_tool):
        with pytest.raises(Exception):
            await call_tool("redmineflux_core_list_versions", {"project_id": "nonexistent"})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONVENIENCE TOOLS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestProjectStats:
    async def test_all_projects(self, call_tool):
        result = await call_tool("redmineflux_core_project_stats")
        assert "All Projects" in result
        assert "Phoenix Platform" in result
        assert "complete" in result

    async def test_single_project(self, call_tool):
        result = await call_tool("redmineflux_core_project_stats", {"project_id": "orion-crm"})
        assert "Orion CRM" in result
        assert "Closed" in result


class TestMyWorkload:
    async def test_returns_workload(self, call_tool):
        result = await call_tool("redmineflux_core_my_workload", {"limit": 5})
        # Admin has no assigned issues, so should say "No open issues"
        assert "open issues" in result.lower()


class TestProjectSummary:
    async def test_phoenix_summary(self, call_tool):
        result = await call_tool("redmineflux_core_project_summary", {"project_id": "phoenix-platform"})
        assert "Phoenix Platform" in result
        assert "Milestones" in result
        assert "Recent Activity" in result
        assert "complete" in result


class TestSystemOnboard:
    async def test_onboard(self, call_tool):
        result = await call_tool("redmineflux_system_onboard")
        assert "Welcome" in result
        assert "Projects" in result
        assert "Team Directory" in result
        assert "Quick Start" in result


class TestCriticalIssues:
    async def test_all_critical(self, call_tool):
        result = await call_tool("redmineflux_core_critical_issues")
        assert "critical" in result.lower()

    async def test_single_project(self, call_tool):
        result = await call_tool("redmineflux_core_critical_issues", {"project_id": "phoenix-platform"})
        assert "critical" in result.lower() or "All clear" in result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FEEDBACK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestFeedback:
    async def test_submit_feedback(self, call_tool):
        result = await call_tool("redmineflux_system_feedback", {"rating": 4, "comment": "Good experience"})
        assert "4/5" in result
        assert "very good" in result

    async def test_invalid_rating(self, call_tool):
        result = await call_tool("redmineflux_system_feedback", {"rating": 0})
        assert "must be between" in result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WORKFLOWS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestWorkflows:
    async def test_create_and_track_issue(self, call_tool):
        create = await call_tool("redmineflux_core_create_issue", {
            "project_id": "phoenix-platform",
            "subject": "Workflow: Test create-track-resolve",
            "tracker_id": 2,
            "priority_id": 3,
            "estimated_hours": 6,
        })
        issue_id = int(create.split("#")[1].split(":")[0])

        await call_tool("redmineflux_core_update_issue", {"issue_id": issue_id, "status_id": 2, "done_ratio": 30})
        await call_tool("redmineflux_core_log_time", {"issue_id": issue_id, "hours": 2.5, "activity_id": 9, "comments": "Workflow test"})
        await call_tool("redmineflux_core_update_issue", {"issue_id": issue_id, "status_id": 3, "done_ratio": 100, "notes": "Done"})

        detail = await call_tool("redmineflux_core_get_issue", {"issue_id": issue_id, "include": "journals"})
        assert "Resolved" in detail
        assert "100%" in detail

    async def test_project_status_report(self, call_tool):
        stats = await call_tool("redmineflux_core_project_stats", {"project_id": "phoenix-platform"})
        assert "Phoenix Platform" in stats
        assert "complete" in stats

        versions = await call_tool("redmineflux_core_list_versions", {"project_id": "phoenix-platform"})
        assert "Production Launch" in versions
