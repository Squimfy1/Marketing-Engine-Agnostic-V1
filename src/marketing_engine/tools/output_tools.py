"""Writing generated content back into the vault.

The core work lives in plain functions (``write_output_note``) so it is
deterministic and unit-testable without the SDK. ``build_brand_mcp_server``
exposes them to the agent as in-process MCP tools for later milestones; in
Milestone 1 the harness calls the plain functions directly so the authoritative
write does not depend on the model choosing to call a tool.
"""

from __future__ import annotations

import re

from marketing_engine.vault.adapter import VaultAdapter
from marketing_engine.vault.layout import OUTPUTS_DIR

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, *, max_len: int = 48) -> str:
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    return (slug[:max_len].rstrip("-")) or "untitled"


def write_output_note(
    vault: VaultAdapter,
    *,
    title: str,
    body: str,
    date_str: str,
    kind: str = "text",
) -> str:
    """Write a dated output note into ``_outputs/`` and return its relpath."""

    relpath = f"{OUTPUTS_DIR}/{date_str}-{slugify(title)}.md"
    frontmatter = (
        "---\n"
        f"title: {title}\n"
        f"date: {date_str}\n"
        f"kind: {kind}\n"
        "generated_by: marketing-engine\n"
        "---\n\n"
    )
    vault.write(relpath, frontmatter + body.rstrip() + "\n")
    return relpath


def build_brand_mcp_server(vault: VaultAdapter, date_str: str):
    """Build an in-process MCP server exposing vault-write tools to the agent.

    Used in later milestones; returns an ``McpSdkServerConfig``.
    """

    from claude_agent_sdk import create_sdk_mcp_server, tool

    @tool(
        "write_output_note",
        "Save a finished piece of marketing copy as a dated note in the brand's _outputs folder.",
        {"title": str, "body": str},
    )
    async def _write_output_note(args: dict) -> dict:
        relpath = write_output_note(
            vault, title=args["title"], body=args["body"], date_str=date_str
        )
        return {"content": [{"type": "text", "text": f"Saved to {relpath}"}]}

    return create_sdk_mcp_server(name="brand_output", version="0.1.0", tools=[_write_output_note])
