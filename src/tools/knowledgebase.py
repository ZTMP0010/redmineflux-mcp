"""Redmineflux MCP Server — Knowledge Base Plugin Tools.

Tools for reading, creating, searching, and updating KB articles.
Only registered if the redmineflux_knowledgebase plugin is detected.

Note: KB stores content as editor.js JSON. These tools convert content
to readable text for agents and accept plain text for creation/updates.

Security: KB content may contain stored XSS (found in security audit).
All content is stripped of HTML tags before returning to agents.

Spec: RMCP-009
"""

import re
from typing import Any

from mcp.server.fastmcp import Context

from ..redmine_client import RedmineClient

TOOL_COUNT = 6


def _strip_html(text: str) -> str:
    """Remove HTML tags from text. Safety measure against stored XSS."""
    return re.sub(r"<[^>]+>", "", text) if text else ""


def _extract_text_from_editorjs(content: Any) -> str:
    """Convert editor.js JSON content to readable plain text.

    Handles common block types. Unknown types are skipped gracefully —
    agent gets partial content rather than an error.
    """
    if isinstance(content, str):
        return _strip_html(content)

    if not isinstance(content, dict):
        return str(content) if content else ""

    blocks = content.get("blocks", [])
    if not blocks:
        # Might be raw text stored as JSON
        text = content.get("text", content.get("content", ""))
        return _strip_html(str(text)) if text else str(content)

    lines: list[str] = []
    for block in blocks:
        block_type = block.get("type", "")
        data = block.get("data", {})

        if block_type == "paragraph":
            lines.append(_strip_html(data.get("text", "")))
        elif block_type == "header":
            level = data.get("level", 2)
            text = _strip_html(data.get("text", ""))
            lines.append(f"{'#' * level} {text}")
        elif block_type == "list":
            style = data.get("style", "unordered")
            items = data.get("items", [])
            for i, item in enumerate(items, 1):
                prefix = f"{i}." if style == "ordered" else "-"
                lines.append(f"  {prefix} {_strip_html(str(item))}")
        elif block_type == "code":
            code = data.get("code", "")
            lines.append(f"```\n{code}\n```")
        elif block_type == "quote":
            text = _strip_html(data.get("text", ""))
            lines.append(f"> {text}")
        elif block_type == "table":
            rows = data.get("content", [])
            for row in rows:
                cells = " | ".join(_strip_html(str(c)) for c in row)
                lines.append(f"| {cells} |")
        elif block_type == "image":
            url = data.get("file", {}).get("url", data.get("url", ""))
            caption = _strip_html(data.get("caption", ""))
            lines.append(f"[Image: {caption or url}]")
        # Unknown block types are silently skipped

    return "\n".join(lines)


def register_knowledgebase_tools(mcp: Any, client: RedmineClient) -> int:
    """Register Knowledge Base plugin tools. Returns count of tools registered."""

    @mcp.tool()
    async def redmineflux_kb_list_pages(
        ctx: Context,
        project_id: str = "",
    ) -> str:
        """List Knowledge Base pages/articles for a project.

        Returns page titles, paths, and space organization.
        Use this to discover what documentation exists.

        Args:
            project_id: Optional project filter.
        """
        params: dict[str, Any] = {}
        if project_id:
            params["project_id"] = project_id

        data = await client.get("/knowledgebase/space.json", params=params)
        pages = data.get("pages", data.get("knowledgebases", []))

        if not pages:
            return "No Knowledge Base pages found." + (
                f" (project: {project_id})" if project_id else ""
            )

        lines = [f"Knowledge Base Pages ({len(pages)} total):\n"]
        for p in pages:
            title = _strip_html(p.get("title", "Untitled"))
            path = p.get("path", "")
            space = p.get("space", {}).get("name", "") if isinstance(p.get("space"), dict) else ""
            updated = p.get("updated_at", p.get("created_at", ""))[:10]

            lines.append(f"  ID:{p.get('id')} {title}")
            if space:
                lines.append(f"    Space: {space}")
            if path:
                lines.append(f"    Path: {path}")
            if updated:
                lines.append(f"    Updated: {updated}")

        return "\n".join(lines)

    @mcp.tool()
    async def redmineflux_kb_get_page(
        ctx: Context,
        page_id: int,
    ) -> str:
        """Get the content of a Knowledge Base page.

        Returns the page title, content as readable text, and metadata.
        Content is converted from editor.js format to plain text.

        Args:
            page_id: The KB page ID.
        """
        try:
            # Note: route has typo in actual code — /knowlegebase_pages/ (missing 'd')
            data = await client.get(f"/knowlegebase_pages/{page_id}.json")
        except Exception:
            return f"Knowledge Base page #{page_id} not found."

        page = data.get("page", data.get("knowledgebase", data))
        title = _strip_html(page.get("title", "Untitled"))
        content_raw = page.get("content", "")

        # Convert editor.js JSON to readable text
        if isinstance(content_raw, str):
            try:
                import json
                content_json = json.loads(content_raw)
                content_text = _extract_text_from_editorjs(content_json)
            except (json.JSONDecodeError, TypeError):
                content_text = _strip_html(content_raw)
        elif isinstance(content_raw, dict):
            content_text = _extract_text_from_editorjs(content_raw)
        else:
            content_text = str(content_raw)

        author = page.get("created_by", page.get("author", {}).get("name", "?"))
        version = page.get("version", "?")
        updated = page.get("updated_at", "")[:16]

        lines = [
            f"# {title}",
            f"Author: {author} | Version: {version} | Updated: {updated}",
            "",
            content_text,
        ]

        return "\n".join(lines)

    @mcp.tool()
    async def redmineflux_kb_search(
        ctx: Context,
        query: str,
        project_id: str = "",
    ) -> str:
        """Search across all Knowledge Base pages.

        Returns matching pages with excerpts. Useful for finding
        relevant documentation, specs, or process guides.

        Args:
            query: Search terms.
            project_id: Optional project filter.
        """
        params: dict[str, Any] = {"q": query}
        if project_id:
            params["project_id"] = project_id

        data = await client.get(
            "/content_search_knowledgebase.json", params=params
        )
        results = data.get("results", data.get("pages", []))

        if not results:
            return f"No Knowledge Base pages match '{query}'."

        lines = [f"KB search results for '{query}' ({len(results)} matches):\n"]
        for r in results:
            title = _strip_html(r.get("title", "Untitled"))
            excerpt = _strip_html(r.get("excerpt", r.get("snippet", "")))[:200]
            lines.append(f"  ID:{r.get('id')} {title}")
            if excerpt:
                lines.append(f"    ...{excerpt}...")

        return "\n".join(lines)

    @mcp.tool()
    async def redmineflux_kb_create_page(
        ctx: Context,
        project_id: str,
        title: str,
        content: str,
        space_id: int = 0,
    ) -> str:
        """Create a new Knowledge Base page.

        Use this to document specs, process guides, API references,
        or any knowledge that the team needs to share.

        Args:
            project_id: Project where the page will be created.
            title: Page title.
            content: Page content as plain text or markdown.
            space_id: Optional space/category ID to organize the page.
        """
        # Convert plain text to editor.js format
        blocks = []
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("# "):
                blocks.append({
                    "type": "header",
                    "data": {"text": line[2:], "level": 1},
                })
            elif line.startswith("## "):
                blocks.append({
                    "type": "header",
                    "data": {"text": line[3:], "level": 2},
                })
            elif line.startswith("### "):
                blocks.append({
                    "type": "header",
                    "data": {"text": line[4:], "level": 3},
                })
            elif line.startswith("- ") or line.startswith("* "):
                # Collect list items
                blocks.append({
                    "type": "list",
                    "data": {"style": "unordered", "items": [line[2:]]},
                })
            else:
                blocks.append({
                    "type": "paragraph",
                    "data": {"text": line},
                })

        import json
        payload: dict[str, Any] = {
            "title": title,
            "content": json.dumps({"blocks": blocks}),
            "project_id": project_id,
        }
        if space_id:
            payload["space_id"] = space_id

        try:
            data = await client.post(
                "/create_knowlegebase_pages.json", json=payload
            )
            page_id = data.get("id", data.get("page", {}).get("id", "?"))
            return f"Knowledge Base page created: '{title}' (ID: {page_id}) in project '{project_id}'."
        except Exception as exc:
            error_msg = str(exc)
            if "403" in error_msg:
                return f"Access denied. Check KB permissions for project '{project_id}'."
            return f"Failed to create KB page: {error_msg}"

    @mcp.tool()
    async def redmineflux_kb_update_page(
        ctx: Context,
        page_id: int,
        content: str,
    ) -> str:
        """Update the content of an existing Knowledge Base page.

        Version history is preserved — the previous version can be restored.

        Args:
            page_id: The KB page ID to update.
            content: New content as plain text or markdown.
        """
        # Convert plain text to editor.js format (same as create)
        blocks = []
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("# "):
                blocks.append({"type": "header", "data": {"text": line[2:], "level": 1}})
            elif line.startswith("## "):
                blocks.append({"type": "header", "data": {"text": line[3:], "level": 2}})
            elif line.startswith("### "):
                blocks.append({"type": "header", "data": {"text": line[4:], "level": 3}})
            elif line.startswith("- ") or line.startswith("* "):
                blocks.append({"type": "list", "data": {"style": "unordered", "items": [line[2:]]}})
            else:
                blocks.append({"type": "paragraph", "data": {"text": line}})

        import json
        payload: dict[str, Any] = {
            "content": json.dumps({"blocks": blocks}),
        }

        try:
            # Note: actual route from routes.rb
            await client.put(
                f"/new_pages/{page_id}/update_content.json", json=payload
            )
            return f"Knowledge Base page #{page_id} updated successfully."
        except Exception as exc:
            error_msg = str(exc)
            if "404" in error_msg:
                return f"Knowledge Base page #{page_id} not found."
            if "403" in error_msg:
                return "Access denied. Check your KB edit permissions."
            return f"Failed to update KB page #{page_id}: {error_msg}"

    @mcp.tool()
    async def redmineflux_kb_list_spaces(
        ctx: Context,
        project_id: str = "",
    ) -> str:
        """List Knowledge Base spaces/categories.

        Spaces organize KB pages into logical groups (e.g., "API Docs",
        "Process Guides", "Architecture"). Use this to find the right
        space before creating a page.

        Args:
            project_id: Optional project filter.
        """
        params: dict[str, Any] = {}
        if project_id:
            params["project_id"] = project_id

        data = await client.get(
            "/spaces_data_knowledgebase.json", params=params
        )
        spaces = data.get("spaces", [])

        if not spaces:
            return "No Knowledge Base spaces found." + (
                f" (project: {project_id})" if project_id else ""
            )

        lines = [f"KB Spaces ({len(spaces)}):\n"]
        for s in spaces:
            name = s.get("name", "Unnamed")
            if isinstance(name, dict):
                # name stored as JSON in some versions
                name = name.get("en", name.get("name", str(name)))
            page_count = s.get("page_count", s.get("pages_count", "?"))
            lines.append(f"  ID:{s.get('id')} {name} ({page_count} pages)")

        return "\n".join(lines)

    return TOOL_COUNT
