#!/usr/bin/env python3
"""Role-based scenario tests for Redmineflux MCP Server.

Tests real-world scenarios that different roles would perform through
natural language via Claude + MCP tools. 51 scenarios across 10+ roles,
including 10 access control / permission denial scenarios.

Each scenario has:
  - A natural language question (what a human would ask)
  - Expected tools to be called
  - Validation criteria for the response

Usage:
    ANTHROPIC_API_KEY=sk-... REDMINE_API_KEY=... python tests/test_role_scenarios.py
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("REDMINE_URL", "http://localhost:3000")
os.environ.setdefault("REDMINE_API_KEY", "9041d40945d754c1c71c37d647d3802e6bb5c2da")

from anthropic import Anthropic
from src.server import create_server

SCENARIOS = [
    # ── PROJECT MANAGER ─────────────────────────────────────
    {
        "role": "Project Manager",
        "name": "PM: Sprint status report",
        "prompt": (
            "I'm Sarah Mitchell, PM for the Phoenix Platform project. "
            "Give me a status report: how many issues are open vs closed, "
            "what's the current sprint milestone status, and who has the most work assigned?"
        ),
        "validate": ["phoenix", "open", "closed", "version"],
    },
    {
        "role": "Project Manager",
        "name": "PM: Cross-project dependency check",
        "prompt": (
            "I need to understand the dependencies between Phoenix Platform and Mercury Mobile. "
            "Are there any blockers? What's the status of Atlas Cloud Migration — "
            "is it on track or are there risks that could delay Phoenix?"
        ),
        "validate": ["phoenix", "mercury", "atlas"],
    },
    {
        "role": "Project Manager",
        "name": "PM: Resource allocation across projects",
        "prompt": (
            "Show me which team members are assigned to the most issues across all projects. "
            "I need to check if anyone is overloaded."
        ),
        "validate": ["issues", "assigned"],
    },
    # ── DEVELOPER ────────────────────────────────────────────
    {
        "role": "Developer",
        "name": "Dev: My open tasks",
        "prompt": (
            "I'm Emma Larsson, a full stack developer. "
            "What issues are assigned to me across all projects? "
            "Prioritize them — what should I work on first?"
        ),
        "validate": ["emma", "priority"],
    },
    {
        "role": "Developer",
        "name": "Dev: Bug triage for Phoenix",
        "prompt": (
            "Show me all open bugs in the Phoenix Platform project, sorted by priority. "
            "Which ones are Urgent or Immediate?"
        ),
        "validate": ["bug", "phoenix"],
    },
    {
        "role": "Developer",
        "name": "Dev: Log work and update progress",
        "prompt": (
            "I just finished 4 hours of Development work on issue #50 in Phoenix Platform. "
            "Log the time with comment 'Completed API endpoint refactoring and added tests'. "
            "Also update the issue to 80% done."
        ),
        "validate": ["logged", "updated", "80"],
    },
    {
        "role": "Developer",
        "name": "Dev: Create a bug from code review",
        "prompt": (
            "During code review I found a race condition in the payment-gateway service "
            "in the Phoenix Platform project. Create a High priority Bug issue for it "
            "and assign it to Sneha Patil."
        ),
        "validate": ["created", "bug", "race condition"],
    },
    # ── QA LEAD ──────────────────────────────────────────────
    {
        "role": "QA Lead",
        "name": "QA: Issues awaiting verification",
        "prompt": (
            "I'm Claire Dubois, QA Lead. Show me all Resolved issues across all projects "
            "that need my verification before they can be closed."
        ),
        "validate": ["resolved"],
    },
    {
        "role": "QA Lead",
        "name": "QA: Bug trend analysis",
        "prompt": (
            "How many bugs are currently open across all six projects? "
            "Which project has the most bugs? Are we trending up or down "
            "compared to what's already been closed?"
        ),
        "validate": ["bug"],
    },
    # ── DIGITAL MARKETING ────────────────────────────────────
    {
        "role": "Digital Marketing",
        "name": "Marketing: Product feature discovery",
        "prompt": (
            "I'm Olivia Bennett from the marketing team. We're creating a landing page "
            "for the Phoenix Platform launch. What are the top features being built? "
            "I need to understand the product capabilities so I can write compelling copy."
        ),
        "validate": ["phoenix", "feature"],
    },
    {
        "role": "Digital Marketing",
        "name": "Marketing: Release timeline for campaigns",
        "prompt": (
            "I'm Alex Morgan, Marketing Lead. I need to plan our campaign calendar. "
            "What are the upcoming release milestones across all projects? "
            "When are the next major launches?"
        ),
        "validate": ["version", "launch"],
    },
    # ── SALES ────────────────────────────────────────────────
    {
        "role": "Sales",
        "name": "Sales: CRM project status for customer demo",
        "prompt": (
            "I'm Michael Torres, Sales Director. I need to demo the Orion CRM to a prospect next week. "
            "What features are already built (closed), what's in progress, and what's coming next?"
        ),
        "validate": ["orion", "closed"],
    },
    {
        "role": "Sales",
        "name": "Sales: Product readiness check",
        "prompt": (
            "A customer is asking about the Mercury Mobile App. "
            "How far along is it? What percentage of features are complete? "
            "When is the App Store launch planned?"
        ),
        "validate": ["mercury", "mobile"],
    },
    # ── HR ───────────────────────────────────────────────────
    {
        "role": "HR",
        "name": "HR: Portal development progress",
        "prompt": (
            "I'm Karen Anderson, HR Manager. How is the Helios HR Portal development going? "
            "What features are done and what's still pending? "
            "When can we expect the company rollout?"
        ),
        "validate": ["helios", "rollout"],
    },
    # ── AI AGENT ─────────────────────────────────────────────
    {
        "role": "AI Agent",
        "name": "Agent PM: Daily standup summary",
        "prompt": (
            "Generate a daily standup summary for the Phoenix Platform project. "
            "What changed in the last 24 hours? Any new issues? "
            "Any issues that moved to In Progress or got resolved?"
        ),
        "validate": ["phoenix"],
    },
    {
        "role": "AI Agent",
        "name": "Agent QA: Test coverage gap analysis",
        "prompt": (
            "As the QA Agent, analyze the Helios HR Portal project. "
            "How many issues have no estimated hours (might be underspecified)? "
            "How many features vs bugs are open? Are there any Support issues that suggest "
            "missing documentation?"
        ),
        "validate": ["helios", "feature", "bug"],
    },
    # ── TIMESHEET WORKFLOWS ─────────────────────────────────
    {
        "role": "Developer",
        "name": "Timesheet: Log work and check weekly summary",
        "prompt": (
            "I just spent 3 hours on issue #42 doing code review. Log that time. "
            "Then show me my timesheet for this week — how many hours have I logged total? "
            "Do I need to submit it for approval?"
        ),
        "validate": ["logged", "hours"],
    },
    {
        "role": "Project Manager",
        "name": "Timesheet: Check who hasn't submitted timesheets",
        "prompt": (
            "It's Friday afternoon. Show me the approval dashboard — "
            "which timesheets are pending my approval? "
            "And are there any team members who haven't submitted yet this week?"
        ),
        "validate": ["approval", "timesheet"],
    },
    {
        "role": "Project Manager",
        "name": "Timesheet: Approve timesheets in bulk",
        "prompt": (
            "I see three timesheets pending my approval. "
            "Show me the details — who submitted, how many hours each, "
            "and for which projects. I want to approve them."
        ),
        "validate": ["approval", "hours"],
    },
    {
        "role": "Finance",
        "name": "Timesheet: Audit trail for billing",
        "prompt": (
            "I need to prepare the monthly invoice for the Phoenix Platform project. "
            "Show me the timesheet audit log — all approved timesheets for this month "
            "with total hours per user. I need this for the client billing report."
        ),
        "validate": ["audit", "hours"],
    },
    # ── WORKLOAD & CAPACITY PLANNING ────────────────────────
    {
        "role": "Project Manager",
        "name": "Workload: Before assigning a new task",
        "prompt": (
            "I need to assign a critical bug fix that will take about 16 hours. "
            "Before I assign it, show me the team's current workload — "
            "who has the most capacity this week? I don't want to overload anyone."
        ),
        "validate": ["capacity", "workload"],
    },
    {
        "role": "Project Manager",
        "name": "Workload: Team utilization report",
        "prompt": (
            "Give me a workload report for the team. "
            "Who's overloaded? Who has spare capacity? "
            "Are there any holidays coming up I should plan around?"
        ),
        "validate": ["workload"],
    },
    {
        "role": "Developer",
        "name": "Workload: My assignments and remaining capacity",
        "prompt": (
            "What's my current workload? Show me all issues assigned to me "
            "with estimated vs spent hours. How much of my capacity is used this week?"
        ),
        "validate": ["issues", "hours"],
    },
    {
        "role": "Scrum Master",
        "name": "Workload: Sprint planning capacity check",
        "prompt": (
            "We're planning next sprint. Show me the team's workload data — "
            "how many hours does each team member have available next week? "
            "Also check the holiday calendar for any days off."
        ),
        "validate": ["workload"],
    },
    # ── AGILE BOARD & SPRINT MANAGEMENT ─────────────────────
    {
        "role": "Scrum Master",
        "name": "Agile: Daily standup board overview",
        "prompt": (
            "It's standup time. Show me the agile board — "
            "how many issues are in each column? "
            "Are there any WIP limit breaches? "
            "What moved since yesterday?"
        ),
        "validate": ["board", "column"],
    },
    {
        "role": "Scrum Master",
        "name": "Agile: Sprint progress and velocity",
        "prompt": (
            "Show me the current sprint details — "
            "what issues are in this sprint, who's working on what, "
            "and how many story points are done vs remaining?"
        ),
        "validate": ["sprint"],
    },
    {
        "role": "Project Manager",
        "name": "Agile: Create a task and add to sprint",
        "prompt": (
            "We just discovered a security vulnerability in the login page. "
            "Create a High priority bug in Phoenix Platform, "
            "assign it to the current sprint, and assign it to Sneha Patil. "
            "Then show me the updated board."
        ),
        "validate": ["created", "bug"],
    },
    {
        "role": "Developer",
        "name": "Agile: What should I work on next",
        "prompt": (
            "I just finished my current task. What's next on the board for me? "
            "Show me the 'To Do' column and help me pick the highest priority item "
            "that matches my skills."
        ),
        "validate": ["board"],
    },
    # ── KNOWLEDGE BASE ──────────────────────────────────────
    {
        "role": "Developer",
        "name": "KB: Search for API documentation",
        "prompt": (
            "I need to integrate with the payment gateway. "
            "Search the knowledge base for any API documentation, "
            "integration guides, or architecture docs about payments."
        ),
        "validate": ["knowledge", "search"],
    },
    {
        "role": "Developer",
        "name": "KB: Create a technical document",
        "prompt": (
            "I just finished setting up the CI/CD pipeline for Phoenix Platform. "
            "Create a knowledge base page documenting the setup: "
            "GitHub Actions workflow, deployment steps, environment variables needed, "
            "and how to troubleshoot failed builds."
        ),
        "validate": ["created", "knowledge"],
    },
    {
        "role": "Project Manager",
        "name": "KB: Find and update process docs",
        "prompt": (
            "Search the knowledge base for our release process documentation. "
            "If it exists, show me the content. "
            "I need to update it with the new approval steps we added."
        ),
        "validate": ["knowledge", "search"],
    },
    {
        "role": "New Team Member",
        "name": "KB: Onboarding — find all project docs",
        "prompt": (
            "I'm new to the team and just joined today. "
            "Show me all the knowledge base spaces and pages available. "
            "I want to read through the documentation to understand the project."
        ),
        "validate": ["knowledge", "space"],
    },
    # ── DEVOPS ──────────────────────────────────────────────
    {
        "role": "Developer",
        "name": "DevOps: Check why the build failed",
        "prompt": (
            "My PR just failed the CI build. Show me the recent builds "
            "for the Phoenix Platform project — which ones failed and on which branch? "
            "I need to understand what went wrong."
        ),
        "validate": ["build", "failed"],
    },
    {
        "role": "Developer",
        "name": "DevOps: Check build status for my issue",
        "prompt": (
            "I'm working on issue #100 in Phoenix Platform. "
            "Are there any CI builds linked to this issue? What's their status? "
            "Has my code been tested?"
        ),
        "validate": ["build"],
    },
    {
        "role": "DevOps Engineer",
        "name": "DevOps: Project health overview",
        "prompt": (
            "Give me a DevOps summary for the Phoenix Platform project — "
            "how are the recent builds doing? Pass rate? "
            "How many PRs are open? Any failed builds I should look at?"
        ),
        "validate": ["devops", "build"],
    },
    {
        "role": "DevOps Engineer",
        "name": "DevOps: Connected repositories check",
        "prompt": (
            "Which source code repositories are connected to our projects? "
            "Show me all connected repos with their providers and webhook status. "
            "I want to make sure all webhooks are working."
        ),
        "validate": ["repositor"],
    },
    # ── CROSS-PLUGIN WORKFLOWS ──────────────────────────────
    {
        "role": "Project Manager",
        "name": "Cross-plugin: Full project health check",
        "prompt": (
            "Give me a complete health check for the Phoenix Platform project: "
            "1. How many issues are open vs closed? "
            "2. Is the team overloaded — show workload capacity "
            "3. What does the agile board look like — sprint progress "
            "4. Any failed CI builds we should worry about? "
            "5. How many hours were logged this week?"
        ),
        "validate": ["phoenix", "issue"],
    },
    {
        "role": "CEO",
        "name": "Cross-plugin: Executive weekly summary",
        "prompt": (
            "I'm the CEO and I need a 2-minute weekly summary for the board: "
            "How many projects are active? Total team size? "
            "Overall issue completion rate? Any blocked items? "
            "What shipped this week?"
        ),
        "validate": ["project"],
    },
    {
        "role": "AI Agent",
        "name": "Agent: Autonomous sprint close workflow",
        "prompt": (
            "As the Sprint Agent, I need to help close the current sprint. "
            "Check the agile board — are all issues in the sprint either done or moved out? "
            "Check if all timesheets for the sprint period are submitted and approved. "
            "Generate a sprint summary with: completed issues, hours logged, and any carryover items."
        ),
        "validate": ["sprint"],
    },
    {
        "role": "AI Agent",
        "name": "Agent: New developer onboarding",
        "prompt": (
            "A new developer just joined the team. Help onboard them: "
            "1. List all active projects they need to know about "
            "2. Show the knowledge base documentation they should read "
            "3. Show the agile board so they understand current sprint "
            "4. Check the team workload to find who can mentor them"
        ),
        "validate": ["project"],
    },
    {
        "role": "AI Agent",
        "name": "Agent: End-of-day automation",
        "prompt": (
            "Run the end-of-day check: "
            "1. Are there any critical or urgent issues without an assignee? "
            "2. Are there any builds that failed today? "
            "3. Are there any issues that have been 'In Progress' for more than 5 days? "
            "4. Generate a brief daily summary for the team."
        ),
        "validate": ["issue", "critical"],
    },
    # ── ACCESS CONTROL & PERMISSION DENIAL ─────────────────
    {
        "role": "Developer",
        "name": "ACL: Project they are not a member of",
        "prompt": (
            "Show me the status of the 'top-secret-project' project. "
            "Give me issue counts and milestone dates."
        ),
        "validate": ["not found", "permission"],
    },
    {
        "role": "Developer",
        "name": "ACL: Issue that does not exist or no access",
        "prompt": (
            "Show me the full details of issue #99999. "
            "I need to check its status and who is assigned."
        ),
        "validate": ["not found"],
    },
    {
        "role": "Marketing",
        "name": "ACL: Cross-project query with partial access",
        "prompt": (
            "I'm from marketing. Compare the issue status across ALL projects in the company. "
            "How many are open vs closed in each? "
            "Note: I may not have access to all projects."
        ),
        "validate": ["project"],
    },
    {
        "role": "New Joiner",
        "name": "ACL: First day orientation with limited access",
        "prompt": (
            "I just joined the company today, my name is Test User. "
            "What projects do I have access to? What issues are assigned to me? "
            "I'm not sure if my account has been fully set up yet."
        ),
        "validate": ["project"],
    },
    {
        "role": "Developer",
        "name": "ACL: Create issue in project without write access",
        "prompt": (
            "Create a Bug issue in the 'restricted-project' project with subject "
            "'Test bug for access control' and assign it to user ID 1."
        ),
        "validate": ["not found", "permission"],
    },
    {
        "role": "Developer",
        "name": "ACL: Version listing for inaccessible project",
        "prompt": (
            "Show me all milestones and version dates for the 'classified-ops' project. "
            "When is their next release?"
        ),
        "validate": ["not found", "permission"],
    },
    {
        "role": "Contractor",
        "name": "ACL: Time entries for another user (restricted)",
        "prompt": (
            "Show me all time entries logged by user ID 999 across all projects this month. "
            "I need to check their hours for the billing report."
        ),
        "validate": ["time"],
    },
    {
        "role": "Developer",
        "name": "ACL: Update issue in read-only project",
        "prompt": (
            "Update issue #99999 in the restricted project — set it to 'In Progress' "
            "and add a note 'Starting work on this'. Also update done ratio to 30%."
        ),
        "validate": ["not found", "permission"],
    },
    {
        "role": "Developer",
        "name": "ACL: Graceful handling then recovery",
        "prompt": (
            "First show me the status of 'nonexistent-project'. "
            "If that doesn't work, show me what projects I DO have access to instead."
        ),
        "validate": ["project"],
    },
    {
        "role": "PM",
        "name": "ACL: Admin operation with non-admin key",
        "prompt": (
            "List all registered users in the system — "
            "I need the full team directory with emails. "
            "Then show me which users are locked or inactive."
        ),
        "validate": ["user"],
    },
]


async def run_scenario(client, server, tools, scenario):
    """Run a single scenario and return results."""
    messages = [{"role": "user", "content": scenario["prompt"]}]
    tools_called = []
    final_response = ""

    for turn in range(10):
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            system=(
                "You are an AI assistant connected to a Redmine project management system via MCP tools. "
                "The system belongs to NovaCrest Technologies with 22 team members and 6 active projects. "
                "Answer the user's question using the available tools. Be specific with data and numbers."
            ),
            tools=tools,
            messages=messages,
        )

        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        tool_uses = [b for b in assistant_content if b.type == "tool_use"]
        if not tool_uses:
            text_blocks = [b.text for b in assistant_content if b.type == "text"]
            final_response = "\n".join(text_blocks)
            break

        tool_results = []
        for tu in tool_uses:
            tools_called.append(tu.name)
            try:
                result = await server.call_tool(tu.name, tu.input)
                contents, _ = result
                text = contents[0].text if contents else ""
                tool_results.append({"type": "tool_result", "tool_use_id": tu.id, "content": text})
            except Exception as e:
                tool_results.append({"type": "tool_result", "tool_use_id": tu.id, "content": f"Error: {e}", "is_error": True})

        messages.append({"role": "user", "content": tool_results})

    # Validate
    response_lower = final_response.lower()
    missing = [v for v in scenario["validate"] if v.lower() not in response_lower]
    passed = len(missing) == 0

    return {
        "role": scenario["role"],
        "name": scenario["name"],
        "passed": passed,
        "tools_called": tools_called,
        "missing_validation": missing,
        "response": final_response,
    }


async def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        # Try reading from common key file locations
        key_paths = [
            os.path.expanduser("~/.anthropic-api.key"),
            os.path.expanduser("~/project/hypersignal/data/anthropic-api.key"),
        ]
        for key_file in key_paths:
            if os.path.exists(key_file):
                with open(key_file) as f:
                    content = f.read().strip()
                    if "=" in content:
                        api_key = content.split("=", 1)[1].strip('"')
                    else:
                        api_key = content
                if api_key:
                    break
        if not api_key:
            print("ERROR: ANTHROPIC_API_KEY not set. Set env var or place key in ~/.anthropic-api.key")
            sys.exit(1)

    print("=" * 70)
    print("Redmineflux MCP — Role-Based Scenario Tests")
    print("=" * 70)

    anthropic_client = Anthropic(api_key=api_key)
    server = create_server()
    mcp_tools = await server.list_tools()
    tools = [{"name": t.name, "description": t.description or "", "input_schema": t.inputSchema} for t in mcp_tools]

    print(f"\n{len(tools)} MCP tools available")
    print(f"Running {len(SCENARIOS)} scenarios across {len(set(s['role'] for s in SCENARIOS))} roles...\n")

    results = []
    by_role = {}

    for i, scenario in enumerate(SCENARIOS, 1):
        print(f"[{i}/{len(SCENARIOS)}] {scenario['name']}...", end=" ", flush=True)
        try:
            result = await run_scenario(anthropic_client, server, tools, scenario)
            results.append(result)

            role = result["role"]
            by_role.setdefault(role, {"passed": 0, "failed": 0})

            if result["passed"]:
                by_role[role]["passed"] += 1
                print(f"PASS ({len(result['tools_called'])} tools)")
            else:
                by_role[role]["failed"] += 1
                print(f"FAIL (missing: {result['missing_validation']})")
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({"role": scenario["role"], "name": scenario["name"], "passed": False, "error": str(e)})

    # Summary
    passed = sum(1 for r in results if r.get("passed"))
    failed = len(results) - passed

    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed, {len(results)} total")
    print("=" * 70)

    print("\nBy Role:")
    for role, counts in sorted(by_role.items()):
        total = counts["passed"] + counts["failed"]
        print(f"  {role}: {counts['passed']}/{total} passed")

    # Save full results
    report_path = os.path.join(os.path.dirname(__file__), "..", "test-results-role-scenarios.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nFull results: {report_path}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
