<p align="center">
  <strong>Redmineflux MCP Server</strong><br/>
  <em>Connect AI agents to your Redmine project data through the Model Context Protocol</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white" alt="Python 3.12+" />
  <img src="https://img.shields.io/badge/MCP-1.26-blueviolet" alt="MCP SDK" />
  <img src="https://img.shields.io/badge/Redmine-5.x%20%7C%206.x-red?logo=ruby&logoColor=white" alt="Redmine" />
  <img src="https://img.shields.io/badge/Version-0.1.0-green" alt="Version 0.1.0" />
  <img src="https://img.shields.io/badge/License-Commercial-lightgrey" alt="License" />
</p>

<p align="center">
  <a href="https://www.redmineflux.com">Website</a> &middot;
  <a href="https://www.redmineflux.com/knowledge-base">Knowledge Base</a> &middot;
  <a href="https://www.redmineflux.com/support">Support</a>
</p>

---

## Why Redmineflux MCP Server?

Redmine holds your project data — issues, time entries, milestones, workload, agile boards, knowledge base articles. But accessing that data means clicking through multiple pages, running custom queries, and switching between plugins.

**Redmineflux MCP Server makes all of that accessible to AI agents.** Your team asks questions in natural language and gets answers backed by live project data. AI agents can read, create, and update issues, log time, check workload, and query across all your projects — in seconds.

```
Team member asks a question → AI Agent → MCP Server → Redmine REST API → Answer
```

Redmine holds the data. Redmineflux plugins enrich it. The MCP server makes it accessible to AI agents. Your team keeps working the way they always have — but now they can ask *"what should I work on first?"* or *"how many bugs are open in Phoenix?"* and get answers in seconds.

---

## Why a Standalone Service? Why Python?

If you're a Redmineflux customer, you're used to plugins: drop into `plugins/`, run migrations, restart Redmine, done. So why is the MCP server different?

**MCP servers and Redmine plugins serve different audiences through different protocols.** A Redmine plugin renders HTML for humans in browsers over HTTP. An MCP server streams structured data to AI agents over stdio/SSE. These are fundamentally different runtime models — combining them would compromise both.

| Factor | Redmine Plugin (Ruby) | MCP Server (Python) |
|--------|----------------------|---------------------|
| **Serves** | Humans via browsers | AI agents via MCP protocol |
| **Protocol** | HTTP request/response | stdio streams / server-sent events |
| **Lifecycle** | Tied to Redmine process | Independent — update without restarting Redmine |
| **MCP SDK** | Does not exist for Ruby | Official Anthropic SDK (`mcp` package) |
| **Ecosystem** | 0 MCP reference servers | 100+ MCP reference servers |

**Why Python specifically:**
- **Official SDK** — Anthropic maintains the MCP Python SDK. Protocol changes are handled upstream. A Ruby implementation would mean building and maintaining the protocol from scratch.
- **Ecosystem** — every major MCP server (GitHub, Slack, Notion, Linear) is Python or TypeScript. Customers using AI agents already expect this pattern.
- **Async HTTP** — Python's httpx provides native async/await for efficient Redmine API communication.
- **AI/ML ready** — if we add features like embeddings or summarization later, the Python ecosystem is already there.

**Your Redmine stays untouched.** The MCP server is a *companion service* that connects to Redmine through its standard REST API — the same API your browser uses. No database access, no Redmine internals, no risk to your existing setup.

> For the full architectural decision record, see the [Decision Document](https://github.com/zehntech/redmineflux-mcp/wiki/DECISION-MCP-EXTERNAL-ARCHITECTURE).

---

## Key Features

- **51 MCP Tools** — full CRUD for issues, projects, time entries, users, versions, plus plugin-specific tools for DevOps, Timesheet, Workload, Agile Board, and Knowledge Base
- **Capability Injection** — auto-detects which Redmineflux plugins are installed on your Redmine instance and loads only the relevant tools
- **Natural Language Access** — ask questions about projects, issues, time, and milestones without learning Redmine's UI
- **Cross-Project Queries** — "compare bugs across all 6 projects" in one question instead of 6 browser tabs
- **One-Sentence Actions** — "log 4 hours and update to 80% done" replaces two separate Redmine forms
- **Observability** — every tool call logged as JSON Lines with session tracking, user identity, and timing
- **MCP Standard** — works with Claude Code, ChatGPT, GitHub Copilot, and any MCP-compatible AI agent

---

## Tools

### Core Tools (15)

| Tool | Description |
|------|-------------|
| `redmineflux_core_list_projects` | List all projects with pagination |
| `redmineflux_core_get_project` | Get project details by ID or identifier |
| `redmineflux_core_list_issues` | List issues with filters (project, status, tracker, assignee, priority) |
| `redmineflux_core_get_issue` | Get full issue details with journals, relations, attachments |
| `redmineflux_core_create_issue` | Create a new issue with all fields |
| `redmineflux_core_update_issue` | Update issue status, assignee, progress, add notes |
| `redmineflux_core_log_time` | Log time against an issue |
| `redmineflux_core_list_time_entries` | List time entries with date/project/user filters |
| `redmineflux_core_list_users` | List all users |
| `redmineflux_core_get_current_user` | Get the authenticated user's details |
| `redmineflux_core_list_versions` | List project versions/milestones |
| `redmineflux_core_list_statuses` | List all issue statuses |
| `redmineflux_core_list_trackers` | List all trackers (Bug, Feature, Support) |
| `redmineflux_core_list_priorities` | List all priorities (Low through Immediate) |
| `redmineflux_core_list_time_entry_activities` | List time entry activities (Design, Development) |

### Convenience Tools (5)

| Tool | Description | Replaces |
|------|-------------|----------|
| `redmineflux_core_project_stats` | Issue counts by status for one or all projects | 12 API calls |
| `redmineflux_core_my_workload` | Current user's tasks across all projects, priority-sorted | 4 API calls |
| `redmineflux_core_project_summary` | Full project overview: description, stats, milestones, activity | 5 API calls |
| `redmineflux_system_onboard` | New user orientation: projects, tasks, team directory | 4 API calls |
| `redmineflux_core_critical_issues` | Urgent/Immediate priority open issues across all projects | 2 API calls |

### System Tools (1)

| Tool | Description |
|------|-------------|
| `redmineflux_system_feedback` | Rate your MCP session (1-5) and leave feedback |

### Plugin Tools (30)

Plugin tools are automatically loaded when the corresponding Redmineflux plugin is detected on your Redmine instance.

| Plugin | Tools | Description |
|--------|:-----:|-------------|
| **DevOps** | 8 | Builds, commits, pull requests, deployments, environments, releases, DORA metrics, alerts |
| **Timesheet** | 6 | Timesheets, submissions, approvals, team timesheets, settings |
| **Workload** | 5 | Resource allocation, capacity, team workload, utilization, forecasting |
| **Agile Board** | 5 | Board management, sprints, cards, swimlanes, WIP limits |
| **Knowledge Base** | 6 | Articles, categories, search, versions, attachments, popular articles |

---

## Screenshots

*Screenshots coming soon — the MCP server is in active development.*

---

## Requirements

| Component | Version |
|-----------|---------|
| Python | 3.12+ |
| Redmine | 5.x or 6.x |
| MCP SDK | 1.26+ |
| httpx | 0.27+ |

---

## Installation

### 1. Clone

```bash
git clone https://github.com/zehntech/redmineflux-mcp.git
cd redmineflux-mcp
```

### 2. Install Dependencies

```bash
pip install -e .
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your Redmine URL and API key
```

| Variable | Description | Example |
|----------|-------------|---------|
| `REDMINE_URL` | Your Redmine instance URL | `https://redmine.example.com` |
| `REDMINE_API_KEY` | Admin or user API key (My Account → API access key) | `abc123...` |

### 4. Connect to Your AI Agent

**Claude Code** — add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "redmineflux": {
      "command": "python3",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/redmineflux-mcp",
      "env": {
        "REDMINE_URL": "https://redmine.example.com",
        "REDMINE_API_KEY": "your_api_key"
      }
    }
  }
}
```

The server communicates over **stdio** (standard MCP transport). Any MCP-compatible AI agent can connect using the same command.

### 5. Auto-Start on Boot (Optional)

If you're running the MCP server on a shared team server, you'll want it to start automatically.

**Linux (systemd):**

Create `/etc/systemd/system/redmineflux-mcp.service`:

```ini
[Unit]
Description=Redmineflux MCP Server
After=network.target

[Service]
Type=simple
User=redmine
WorkingDirectory=/opt/redmineflux-mcp
ExecStart=/opt/redmineflux-mcp/.venv/bin/python -m src.server
EnvironmentFile=/opt/redmineflux-mcp/.env
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable redmineflux-mcp
sudo systemctl start redmineflux-mcp

# Check status
sudo systemctl status redmineflux-mcp
```

**macOS (launchd):**

Create `~/Library/LaunchAgents/com.redmineflux.mcp.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.redmineflux.mcp</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/redmineflux-mcp/.venv/bin/python</string>
        <string>-m</string>
        <string>src.server</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/opt/redmineflux-mcp</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>REDMINE_URL</key>
        <string>https://redmine.example.com</string>
        <key>REDMINE_API_KEY</key>
        <string>your_api_key</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/redmineflux-mcp.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/redmineflux-mcp.error.log</string>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.redmineflux.mcp.plist

# Check status
launchctl list | grep redmineflux
```

**Docker:**

```bash
docker run -d --name redmineflux-mcp \
  --restart unless-stopped \
  -e REDMINE_URL=https://redmine.example.com \
  -e REDMINE_API_KEY=your_api_key \
  redmineflux/mcp-server:latest
```

> **Note:** For Claude Code's `.mcp.json` integration, auto-start is not needed — Claude Code launches the MCP server process automatically when it connects. Auto-start is for shared team servers where the MCP server runs as an HTTP/SSE endpoint for multiple agents.

---

## Usage

Once connected, ask questions naturally:

```
You: What's the status of the Phoenix Platform project?
AI:  Phoenix Platform has 1,594 issues — 33% complete.
     New: 537 | In Progress: 304 | Resolved: 93 | Closed: 538
     Next milestone: v0.4 Frontend Shell (due 2026-03-31)

You: Show me critical bugs
AI:  10 critical issues (Urgent + Immediate) across 4 projects...

You: Log 4 hours of Development on issue #50, comment "API refactoring complete"
AI:  Logged 4.0h on issue #50 (entry id=1846)

You: I just joined the team, where do I start?
AI:  Welcome! You're assigned to 3 projects with 42 open issues...
```

---

## Who Is This For?

| Role | What They Can Do |
|------|-----------------|
| **Developers** | Check assigned issues, log time, update progress, triage bugs — all from the terminal |
| **Project Managers** | Instant project stats, milestone tracking, cross-project comparison, resource allocation |
| **QA Engineers** | Query bugs by priority/status, track regression patterns, monitor test coverage |
| **Marketing & Sales** | Discover what features are being built, check release timelines, track product progress |
| **AI Agents** | Autonomous task execution, spec-to-ticket pipelines, quality monitoring |

---

## Architecture

```
┌──────────────┐     ┌───────────────────────┐     ┌──────────────┐
│  AI Agent    │     │  Redmineflux MCP      │     │  Redmine     │
│  (Claude,    │────▶│  Server (Python)      │────▶│  REST API    │
│   ChatGPT,   │◀────│                       │◀────│              │
│   Copilot)   │     │  51 tools             │     │  + Plugins   │
└──────────────┘     │  Capability injection │     └──────────────┘
                     │  Observability layer  │
                     │  JSON audit logs      │
                     └───────────────────────┘
```

**Modular design:** Core tools (21) are always loaded. Plugin tools (30) are injected based on which Redmineflux plugins are installed on your Redmine instance — the server auto-detects capabilities at startup.

---

## Works With

| Plugin | Integration |
|--------|-------------|
| Redmineflux Timesheet | Query timesheets, check submission status, view approvals via AI |
| Redmineflux Workload | Check resource allocation, capacity, and utilization across teams |
| Redmineflux Agile Board | Manage sprints, move cards, check WIP limits |
| Redmineflux DevOps | Query builds, deployments, DORA metrics, releases |
| Redmineflux Knowledge Base | Search articles, browse categories, find documentation |
| Redmineflux CRM | *Coming soon* |
| Redmineflux Helpdesk | *Coming soon* |

---

## FAQ

**Q: Does the MCP server require direct database access?**
No. The server communicates exclusively through Redmine's REST API. No database credentials or direct connections needed.

**Q: Which AI agents are supported?**
Any agent that supports the Model Context Protocol (MCP) — Claude Code, ChatGPT (with MCP plugin), GitHub Copilot, and custom agents built with the Anthropic SDK.

**Q: Do I need all Redmineflux plugins installed?**
No. The server auto-detects which plugins are available and loads only the relevant tools. Core Redmine tools (21) always work, even without any Redmineflux plugins installed.

**Q: Is my data sent to third parties?**
The MCP server runs locally on your machine. It communicates with your Redmine instance via its REST API. Your project data stays between the server and your Redmine — the MCP server does not send data anywhere else.

**Q: Can I restrict which tools are available?**
Yes. The server respects Redmine's permission model — users only see data they have access to based on their API key's role and project memberships.

**Q: What about audit logging?**
Every tool call is logged as JSON Lines in the `logs/` directory with session ID, user identity, tool name, parameters, timing, and result status. Sensitive fields are redacted automatically.

**Q: Can I see MCP activity inside Redmine?**
A Redmine dashboard plugin is planned (Phase 6) that will show connection status, agent activity feed, and usage statistics directly in the Redmine UI. The MCP server itself remains external — the dashboard reads its audit logs.

---

## Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| **Phase 1** | Core Redmine tools (21) + observability | **Done** |
| **Phase 2** | Capability injection system | **Done** |
| **Phase 3** | DevOps + Timesheet + Workload + Agile + KB (30 tools) | **Done** |
| **Phase 4** | CRM + Testcase Management | Planned |
| **Phase 5** | Helpdesk + Dashboard plugin tools | Planned |
| **Phase 6** | MCP Dashboard — Redmine plugin for monitoring MCP activity | Planned |
| **Phase 7** | PyPI packaging | Planned |

### Phase 6 Preview: MCP Dashboard Plugin

A lightweight Redmine plugin (`redmineflux_mcp_dashboard`) that gives project managers and admins visibility into how AI agents are interacting with their Redmine data — without leaving the Redmine UI.

**Planned features:**
- **Connection status** — is the MCP server online? Last heartbeat, uptime, version
- **Live activity feed** — recent tool calls: who asked what, which tool, when, how long
- **Usage dashboard** — calls per day, most-used tools, busiest projects, response times
- **Agent sessions** — which AI agents connected, session duration, tools used per session
- **Audit log viewer** — searchable view of the MCP server's JSON Lines audit logs

This plugin reads the MCP server's audit logs — it does NOT embed MCP functionality into Redmine. The MCP server remains a standalone Python service; the dashboard is a read-only window into its activity.

---

## Release Notes

### v0.1.0 (2026-03-29)

- Initial release with 51 MCP tools (21 core + 30 plugin)
- Capability injection — auto-detects installed Redmineflux plugins
- Observability layer with JSON Lines audit logging
- 5 plugin modules: DevOps, Timesheet, Workload, Agile Board, Knowledge Base
- Docker development environment (Redmine 5.1 + PostgreSQL 16)
- 47 integration tests, Claude API e2e test, role-based scenario tests

---

## Support

- **Knowledge Base:** [redmineflux.com/knowledge-base](https://www.redmineflux.com/knowledge-base/)
- **Email:** support@redmineflux.com
- **Website:** [redmineflux.com](https://www.redmineflux.com)

---

<p align="center">
  <strong>Redmineflux MCP Server</strong> is developed by <a href="https://www.zehntech.com">Zehntech Technologies Inc.</a><br/>
  Part of the <a href="https://www.redmineflux.com">Redmineflux</a> plugin suite for Redmine.
</p>
