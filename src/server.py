"""Redmineflux MCP Server — Main entry point.

Connects AI agents to Redmine via the Model Context Protocol.
Capability injection: detects installed Redmineflux plugins at startup
and loads only the relevant tool modules.
"""

import logging

from mcp.server.fastmcp import FastMCP

from .config import RedmineConfig
from .observability import AuditLogger
from .plugin_registry import PLUGIN_MODULES, detect_installed_plugins, load_plugin_modules
from .redmine_client import RedmineClient
from .tools.convenience import register_convenience_tools
from .tools.core import register_core_tools
from .tools.feedback import register_feedback_tools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("redmineflux-mcp")

CORE_TOOL_COUNT = 21  # 15 core + 5 convenience + 1 feedback


def create_server() -> FastMCP:
    """Create and configure the MCP server with capability injection."""
    config = RedmineConfig.from_env()
    client = RedmineClient(config)
    audit = AuditLogger(redmine_client=client)

    mcp = FastMCP(
        "Redmineflux",
        instructions=(
            "AI agent access to Redmine project management data. "
            "Use convenience tools (project_stats, my_workload, project_summary, "
            "system_onboard, critical_issues) for common queries — they are faster "
            "and return better-formatted results than multiple individual calls. "
            "Use core tools for specific CRUD operations. "
            "Plugin-specific tools (devops_, timesheet_, workload_, etc.) are "
            "available only if the corresponding Redmineflux plugin is installed."
        ),
    )

    # ── Always load core tools ──────────────────────────────────
    register_core_tools(mcp, client)
    register_convenience_tools(mcp, client)
    register_feedback_tools(mcp, audit)

    # ── Capability injection: detect and load plugin modules ────
    plugin_tool_count = 0
    installed_plugins: list[str] = []

    if PLUGIN_MODULES:
        logger.info(
            "Detecting installed plugins (%d known)...",
            len(PLUGIN_MODULES),
        )
        installed_plugins = detect_installed_plugins(client)
        loaded = load_plugin_modules(mcp, client, installed_plugins)
        plugin_tool_count = sum(loaded.values())

    total_tools = CORE_TOOL_COUNT + plugin_tool_count
    plugins_str = ", ".join(installed_plugins) if installed_plugins else "none"

    logger.info(
        "Redmineflux MCP: %d tools (%d core + %d plugin). "
        "Detected plugins: %s (%d/%d).",
        total_tools,
        CORE_TOOL_COUNT,
        plugin_tool_count,
        plugins_str,
        len(installed_plugins),
        len(PLUGIN_MODULES),
    )

    audit.log_session_start()
    logger.info(
        "Server initialized (%s) — session %s",
        config.url,
        audit.session_id,
    )
    return mcp


def main() -> None:
    """Run the MCP server (stdio transport)."""
    server = create_server()
    server.run()


if __name__ == "__main__":
    main()
