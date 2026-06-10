"""Brand isolation: the load-bearing security/correctness control.

In a single shared vault, the only thing stopping an agent working on brand A
from reading or clobbering brand B is this guard. It is enforced as a
``PreToolUse`` hook on the Claude Agent SDK: before any file-touching tool runs,
every path argument is resolved and checked against the brand's allowlist
(its own subtree + ``_shared``). Anything outside is denied.

The decision logic (``guard_decision``) is a pure function so it can be unit
tested exhaustively without a live agent; ``make_path_guard_hook`` is the thin
SDK adapter around it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from marketing_engine.vault.paths import is_within

# Which keys in a tool's input carry filesystem paths, per built-in tool.
_PATH_KEYS: dict[str, tuple[str, ...]] = {
    "Read": ("file_path",),
    "Write": ("file_path",),
    "Edit": ("file_path",),
    "NotebookEdit": ("notebook_path",),
    "Glob": ("path",),
    "Grep": ("path",),
}


def extract_paths(tool_name: str, tool_input: dict[str, Any]) -> list[str]:
    """Return the filesystem path arguments for a tool call (may be empty)."""

    paths: list[str] = []
    for key in _PATH_KEYS.get(tool_name, ()):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            paths.append(value)
    return paths


def guard_decision(
    tool_name: str,
    tool_input: dict[str, Any],
    allowed_roots: Iterable[Path],
) -> tuple[bool, list[str]]:
    """Pure isolation decision.

    Returns ``(allowed, offending_paths)``. A tool with no path arguments (e.g.
    a brand-scoped MCP tool) is allowed — it cannot reach the filesystem
    directly. ``Bash`` is intentionally *not* in ``_PATH_KEYS``; if it is ever
    enabled it should be gated separately, so for safety we deny it here.
    """

    if tool_name == "Bash":
        return False, ["<bash command>"]

    roots = list(allowed_roots)
    offending = [p for p in extract_paths(tool_name, tool_input) if not is_within(p, roots)]
    return (len(offending) == 0, offending)


def make_path_guard_hook(allowed_roots: Iterable[Path], denied_log: list[str] | None = None):
    """Build a ``PreToolUse`` hook callback enforcing the brand allowlist.

    ``denied_log`` (if provided) collects human-readable strings for every
    denied attempt, so the engine can report isolation violations after a run.
    """

    roots = [Path(r) for r in allowed_roots]

    async def hook(input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict:
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {}) or {}
        allowed, offending = guard_decision(tool_name, tool_input, roots)
        if allowed:
            return {}
        reason = (
            f"Isolation: {tool_name} blocked — path(s) outside this brand's "
            f"allowed area: {', '.join(offending)}"
        )
        if denied_log is not None:
            denied_log.append(reason)
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }

    return hook
