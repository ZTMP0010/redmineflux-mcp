"""Redmineflux MCP Server — Plugin Registry & Capability Injection.

Detects installed Redmineflux plugins on the target Redmine instance and
loads only the MCP tool modules for detected plugins. Core tools always load.

Architecture:
  - Each plugin module lives in src/tools/{plugin}.py
  - Each module exposes register_{plugin}_tools(mcp, client) -> int
  - The registry probes detection endpoints at startup (sync, parallel)
  - Only detected plugins get their tools registered with FastMCP
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable

from .redmine_client import RedmineClient

logger = logging.getLogger("redmineflux-mcp")


@dataclass
class PluginModule:
    """Registration record for a Redmineflux plugin."""

    name: str
    """Short name used in logs and detection (e.g., 'devops')."""

    registered_name: str
    """Full Redmine plugin name (e.g., 'redmineflux_devops')."""

    detection_endpoint: str
    """REST API path to probe. 404 = not installed, anything else = installed."""

    register_fn: Callable[[Any, Any], int]
    """Function that registers tools with FastMCP. Returns count of tools registered."""

    description: str
    """Human-readable description for startup log."""


# Master list of all supported plugins.
# Import and append at module load time (bottom of file).
PLUGIN_MODULES: list[PluginModule] = []


def detect_installed_plugins(client: RedmineClient) -> list[str]:
    """Probe each plugin's detection endpoint in parallel. Returns names of installed plugins.

    Uses synchronous httpx.Client via ThreadPoolExecutor to avoid event loop
    conflicts with FastMCP's async transport. Each thread gets its own client
    instance (httpx.Client is not thread-safe).

    Timeout: 2s per probe, all probes run in parallel. Worst case: 2s total.
    """
    if not PLUGIN_MODULES:
        return []

    installed: list[str] = []

    def _probe(module: PluginModule) -> tuple[str, bool]:
        status_code = client.probe_sync(module.detection_endpoint, timeout=2.0)
        # 404 = not installed. 0 = unreachable/timeout.
        # 200 is installed. 401/403 = installed but auth issue (still counts).
        is_installed = status_code not in (0, 404)
        return module.name, is_installed

    with ThreadPoolExecutor(max_workers=min(len(PLUGIN_MODULES), 8)) as pool:
        futures = {pool.submit(_probe, m): m for m in PLUGIN_MODULES}
        for future in as_completed(futures):
            try:
                name, is_installed = future.result()
                if is_installed:
                    installed.append(name)
            except Exception as exc:
                module = futures[future]
                logger.debug("Plugin detection failed for %s: %s", module.name, exc)

    return installed


def load_plugin_modules(
    mcp: Any,
    client: RedmineClient,
    installed_plugins: list[str],
) -> dict[str, int]:
    """Register tools for each installed plugin. Returns {plugin_name: tool_count}.

    Only loads modules for plugins that were detected as installed.
    Core tools are loaded separately (not managed by this registry).
    """
    loaded: dict[str, int] = {}

    for module in PLUGIN_MODULES:
        if module.name in installed_plugins:
            try:
                count = module.register_fn(mcp, client)
                loaded[module.name] = count
                logger.info(
                    "Loaded plugin: %s — %d tools (%s)",
                    module.name,
                    count,
                    module.description,
                )
            except Exception as exc:
                logger.error("Failed to load plugin %s: %s", module.name, exc)
        else:
            logger.info("Plugin not detected: %s (skipped)", module.name)

    return loaded


# ── Plugin Module Imports ──────────────────────────────────────
# Each import adds to PLUGIN_MODULES. Order doesn't matter.

try:
    from .tools.devops import register_devops_tools

    PLUGIN_MODULES.append(
        PluginModule(
            name="devops",
            registered_name="redmineflux_devops",
            detection_endpoint="/devops/builds.json",
            register_fn=register_devops_tools,
            description="CI/CD builds, commits, pull requests, repositories",
        )
    )
except ImportError:
    pass  # Module not present — skip

try:
    from .tools.timesheet import register_timesheet_tools

    PLUGIN_MODULES.append(
        PluginModule(
            name="timesheet",
            registered_name="redmineflux_timesheet",
            detection_endpoint="/api/timesheets.json",
            register_fn=register_timesheet_tools,
            description="Timesheet submission, approval workflows, audit trail",
        )
    )
except ImportError:
    pass

try:
    from .tools.workload import register_workload_tools

    PLUGIN_MODULES.append(
        PluginModule(
            name="workload",
            registered_name="redmineflux_workload",
            detection_endpoint="/workloads/data.json",
            register_fn=register_workload_tools,
            description="Capacity planning, teams, holidays, resource reports",
        )
    )
except ImportError:
    pass

try:
    from .tools.agile import register_agile_tools

    PLUGIN_MODULES.append(
        PluginModule(
            name="agile",
            registered_name="agile_board",
            detection_endpoint="/agile_board.json",
            register_fn=register_agile_tools,
            description="Kanban boards, sprints, story points, WIP limits",
        )
    )
except ImportError:
    pass

try:
    from .tools.knowledgebase import register_knowledgebase_tools

    PLUGIN_MODULES.append(
        PluginModule(
            name="knowledgebase",
            registered_name="redmineflux_knowledgebase",
            detection_endpoint="/spaces_data_knowledgebase.json",
            register_fn=register_knowledgebase_tools,
            description="Knowledge base pages, spaces, search, versioning",
        )
    )
except ImportError:
    pass

# Future plugins:
# - CRM (needs deals/leads API built first)
# - Testcase Management (needs suite CRUD API built first)
# - Helpdesk (biggest API gap — needs ticket lifecycle API)
# - Dashboard (needs chart data rendering API)
