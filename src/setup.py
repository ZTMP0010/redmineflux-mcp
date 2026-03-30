"""Redmineflux MCP Server — Setup helper.

Generates .mcp.json configuration for team members.
Admin runs this once, sends the output to the team.
Each person plugs in their own API key.
"""

import json
import os
import sys
from pathlib import Path


def get_mcp_server_path() -> str:
    """Auto-detect the redmineflux-mcp installation path."""
    # Walk up from this file to the project root
    return str(Path(__file__).resolve().parent.parent)


def generate_mcp_config(
    redmine_url: str,
    api_key: str = "YOUR_API_KEY",
    server_path: str | None = None,
) -> dict:
    """Generate .mcp.json config with real paths."""
    cwd = server_path or get_mcp_server_path()
    return {
        "mcpServers": {
            "redmineflux": {
                "command": "python3",
                "args": ["-m", "src.server"],
                "cwd": cwd,
                "env": {
                    "REDMINE_URL": redmine_url,
                    "REDMINE_API_KEY": api_key,
                },
            }
        }
    }


def write_mcp_json(config: dict, output_path: str) -> None:
    """Write .mcp.json file."""
    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def main() -> None:
    """Interactive setup — generates .mcp.json for team distribution."""
    print("=" * 60)
    print("  Redmineflux MCP Server — Setup")
    print("=" * 60)
    print()

    # Auto-detect server path
    server_path = get_mcp_server_path()
    print(f"  MCP server path: {server_path}")
    print()

    # Get Redmine URL
    default_url = os.environ.get("REDMINE_URL", "")
    if default_url:
        print(f"  Redmine URL (from env): {default_url}")
        redmine_url = input(f"  Redmine URL [{default_url}]: ").strip() or default_url
    else:
        redmine_url = input("  Redmine URL (e.g. https://redmine.example.com): ").strip()

    if not redmine_url:
        print("\n  Error: Redmine URL is required.")
        sys.exit(1)

    # Ask for API key (optional — team members add their own)
    print()
    print("  API key is optional here. If you leave it blank,")
    print("  team members will add their own key to the config.")
    api_key = input("  Redmine API key [YOUR_API_KEY]: ").strip() or "YOUR_API_KEY"

    # Generate config
    config = generate_mcp_config(
        redmine_url=redmine_url,
        api_key=api_key,
        server_path=server_path,
    )

    # Choose output
    print()
    print("  Where to save?")
    print("  1. Current directory (.mcp.json)")
    print("  2. Print to screen (for email/Slack)")
    print("  3. Custom path")
    choice = input("  Choice [2]: ").strip() or "2"

    config_json = json.dumps(config, indent=2)

    if choice == "1":
        output_path = os.path.join(os.getcwd(), ".mcp.json")
        write_mcp_json(config, output_path)
        print(f"\n  Saved to: {output_path}")
    elif choice == "3":
        output_path = input("  Path: ").strip()
        write_mcp_json(config, output_path)
        print(f"\n  Saved to: {output_path}")
    else:
        print()
        print("-" * 60)
        print("  Copy this into .mcp.json in any project directory:")
        print("-" * 60)
        print()
        print(config_json)
        print()
        print("-" * 60)

    # Team instructions
    print()
    print("  === Instructions for team members ===")
    print()
    print("  1. Copy the JSON above into .mcp.json in your project folder")
    if api_key == "YOUR_API_KEY":
        print("  2. Replace YOUR_API_KEY with your Redmine API key")
        print("     (Redmine → My Account → API access key → Show)")
    else:
        print("  2. API key is pre-filled (admin key)")
        print("     For personal keys: replace the API key with your own")
        print("     (Redmine → My Account → API access key → Show)")
    print("  3. Restart Claude Code / your AI agent")
    print("  4. Ask: \"What projects do I have access to?\"")
    print()


if __name__ == "__main__":
    main()
