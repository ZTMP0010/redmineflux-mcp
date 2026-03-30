#!/usr/bin/env python3
"""Claude API end-to-end test for Redmineflux MCP Server.

Connects Claude to the MCP server and has it perform real PM tasks.
This validates that Claude can discover tools, understand their schemas,
and use them to accomplish multi-step workflows.

Prerequisites:
    - ANTHROPIC_API_KEY env var set
    - Docker Redmine running (docker compose up -d)
    - Seed data loaded (python scripts/seed_redmine.py --key ...)

Usage:
    ANTHROPIC_API_KEY=sk-... REDMINE_API_KEY=... python tests/test_claude_api.py
"""

import asyncio
import json
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("REDMINE_URL", "http://localhost:3000")
os.environ.setdefault("REDMINE_API_KEY", "da0147b1522b5c7f2fc56ffde7f8d9f58161b32d")

from anthropic import Anthropic

from src.server import create_server

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Build tool definitions from MCP server
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def get_tool_definitions() -> tuple:
    """Extract Anthropic-format tool definitions from the MCP server."""
    server = create_server()
    mcp_tools = await server.list_tools()

    anthropic_tools = []
    for tool in mcp_tools:
        anthropic_tools.append({
            "name": tool.name,
            "description": tool.description or "",
            "input_schema": tool.inputSchema,
        })

    return server, anthropic_tools


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Test scenarios
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCENARIOS = [
    {
        "name": "Project Discovery",
        "prompt": "List all available projects and tell me which ones exist. Then get details about the first project.",
        "expected_tools": ["redmineflux_core_list_projects", "redmineflux_core_get_project"],
        "expected_in_response": ["alpha-web", "Alpha Web Platform"],
    },
    {
        "name": "Bug Triage",
        "prompt": "Find all bugs across all projects. Which one has the highest priority? Give me its full details.",
        "expected_tools": ["redmineflux_core_list_issues", "redmineflux_core_get_issue"],
        "expected_in_response": ["Bug", "Urgent"],
    },
    {
        "name": "Create and Track Work",
        "prompt": (
            "Create a new Feature issue in the alpha-web project titled "
            "'Add WebSocket support for real-time updates' with High priority. "
            "Then move it to In Progress status and log 3 hours of Development time "
            "with the comment 'Initial WebSocket server implementation'."
        ),
        "expected_tools": [
            "redmineflux_core_create_issue",
            "redmineflux_core_update_issue",
            "redmineflux_core_log_time",
        ],
        "expected_in_response": ["Created", "WebSocket"],
    },
    {
        "name": "Time Report",
        "prompt": (
            "Generate a time report: how many total hours have been logged across all projects? "
            "Break it down by what work was done."
        ),
        "expected_tools": ["redmineflux_core_list_time_entries"],
        "expected_in_response": ["hours", "h"],
    },
    {
        "name": "Sprint Planning",
        "prompt": (
            "I'm planning a sprint for the alpha-web project. "
            "First, what are the current versions/milestones? "
            "Then list all open issues. "
            "Finally, what trackers and priorities are available?"
        ),
        "expected_tools": [
            "redmineflux_core_list_versions",
            "redmineflux_core_list_issues",
            "redmineflux_core_list_trackers",
            "redmineflux_core_list_priorities",
        ],
        "expected_in_response": ["MVP Launch", "Feature"],
    },
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Test runner
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def run_scenario(
    client: Anthropic,
    server,
    tools: list,
    scenario: dict,
) -> dict:
    """Run a single test scenario through Claude + MCP tools."""
    result = {
        "name": scenario["name"],
        "passed": False,
        "tools_called": [],
        "tool_errors": [],
        "missing_tools": [],
        "missing_content": [],
        "turns": 0,
        "final_response": "",
    }

    messages = [{"role": "user", "content": scenario["prompt"]}]

    # Agentic loop — let Claude call tools until it's done
    for turn in range(10):  # Max 10 turns to prevent runaway
        result["turns"] = turn + 1

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system="You are testing the Redmineflux MCP server. Use the available tools to complete the task. Be concise.",
            tools=tools,
            messages=messages,
        )

        # Process response
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        # Check if Claude wants to use tools
        tool_uses = [block for block in assistant_content if block.type == "tool_use"]

        if not tool_uses:
            # Claude is done — extract final text
            text_blocks = [block.text for block in assistant_content if block.type == "text"]
            result["final_response"] = "\n".join(text_blocks)
            break

        # Execute tool calls
        tool_results = []
        for tool_use in tool_uses:
            result["tools_called"].append(tool_use.name)
            try:
                mcp_result = await server.call_tool(tool_use.name, tool_use.input)
                contents, _ = mcp_result
                tool_output = contents[0].text if contents else ""
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": tool_output,
                })
            except Exception as e:
                error_msg = f"Tool error: {e}"
                result["tool_errors"].append({"tool": tool_use.name, "error": str(e), "input": tool_use.input})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": error_msg,
                    "is_error": True,
                })

        messages.append({"role": "user", "content": tool_results})

    # Validate expected tools were called
    called_set = set(result["tools_called"])
    for expected in scenario["expected_tools"]:
        if expected not in called_set:
            result["missing_tools"].append(expected)

    # Validate expected content in final response
    full_text = result["final_response"].lower()
    for expected in scenario["expected_in_response"]:
        if expected.lower() not in full_text:
            result["missing_content"].append(expected)

    result["passed"] = (
        len(result["missing_tools"]) == 0
        and len(result["tool_errors"]) == 0
        and len(result["missing_content"]) == 0
    )

    return result


async def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        print("Usage: ANTHROPIC_API_KEY=sk-... python tests/test_claude_api.py")
        sys.exit(1)

    print("=" * 70)
    print("Redmineflux MCP — Claude API End-to-End Test")
    print("=" * 70)

    # Setup
    anthropic_client = Anthropic(api_key=api_key)
    server, tools = await get_tool_definitions()

    print(f"\nRegistered {len(tools)} MCP tools")
    print(f"Running {len(SCENARIOS)} scenarios...\n")

    # Run scenarios
    results = []
    passed = 0
    failed = 0

    for i, scenario in enumerate(SCENARIOS, 1):
        print(f"[{i}/{len(SCENARIOS)}] {scenario['name']}...", end=" ", flush=True)
        try:
            result = await run_scenario(anthropic_client, server, tools, scenario)
            results.append(result)

            if result["passed"]:
                passed += 1
                print(f"PASS ({result['turns']} turns, {len(result['tools_called'])} tool calls)")
            else:
                failed += 1
                print(f"FAIL")
                if result["missing_tools"]:
                    print(f"    Missing tools: {result['missing_tools']}")
                if result["tool_errors"]:
                    for err in result["tool_errors"]:
                        print(f"    Tool error: {err['tool']} — {err['error']}")
                        print(f"      Input: {json.dumps(err['input'], indent=2)}")
                if result["missing_content"]:
                    print(f"    Missing in response: {result['missing_content']}")
                    print(f"    Response preview: {result['final_response'][:200]}...")
        except Exception as e:
            failed += 1
            print(f"ERROR: {e}")
            results.append({"name": scenario["name"], "passed": False, "error": str(e)})

    # Summary
    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed, {len(SCENARIOS)} total")
    print("=" * 70)

    # Detailed results
    print("\n--- Detailed Results ---\n")
    for r in results:
        status = "PASS" if r.get("passed") else "FAIL"
        print(f"[{status}] {r['name']}")
        if r.get("tools_called"):
            print(f"  Tools called: {', '.join(r['tools_called'])}")
        if r.get("tool_errors"):
            print(f"  ERRORS:")
            for err in r["tool_errors"]:
                print(f"    {err['tool']}: {err['error']}")

    # Write results to file
    report_path = os.path.join(os.path.dirname(__file__), "..", "test-results-claude-api.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nFull results written to: {report_path}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
