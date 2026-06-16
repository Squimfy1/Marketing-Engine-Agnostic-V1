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
    base_dir: str | Path | None = None,
    denied_roots: Iterable[Path] = (),
) -> tuple[bool, list[str]]:
    """Pure isolation decision.

    Returns ``(allowed, offending_paths)``. Relative paths are resolved against
    ``base_dir`` (the agent's working directory) — NOT the server process cwd.
    A path is denied if it falls outside ``allowed_roots`` OR inside any
    ``denied_roots`` (e.g. ``_sources/`` raw transcripts, which generation must
    never read). A tool with no path arguments is allowed. ``Bash`` is denied.
    """

    if tool_name == "Bash":
        return False, ["<bash command>"]

    roots = list(allowed_roots)
    denied = list(denied_roots)
    offending = []
    for p in extract_paths(tool_name, tool_input):
        candidate = Path(p)
        if not candidate.is_absolute() and base_dir is not None:
            candidate = Path(base_dir) / candidate
        if not is_within(candidate, roots) or (denied and is_within(candidate, denied)):
            offending.append(p)
    return (len(offending) == 0, offending)


def make_path_guard_hook(
    allowed_roots: Iterable[Path],
    denied_log: list[str] | None = None,
    denied_roots: Iterable[Path] = (),
    base_dir: str | Path | None = None,
):
    """Build a ``PreToolUse`` hook callback enforcing the brand allowlist.

    ``denied_roots`` are subtrees that are blocked even though they sit inside an
    allowed root (e.g. the brand's ``_sources/`` raw transcripts). ``denied_log``
    (if provided) collects human-readable strings for every denied attempt.
    ``base_dir`` is the brand folder the agent runs in; relative tool paths resolve
    against it. We prefer this known value over the SDK-reported ``cwd`` (which can
    be the launch directory, not the agent's folder) so a relative ``_kb/x.md`` read
    resolves inside the brand, not the repo root.
    """

    roots = [Path(r) for r in allowed_roots]
    denied = [Path(r) for r in denied_roots]
    fixed_base = Path(base_dir) if base_dir is not None else None

    async def hook(input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict:
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {}) or {}
        resolve_base = fixed_base or input_data.get("cwd")
        allowed, offending = guard_decision(
            tool_name, tool_input, roots, base_dir=resolve_base, denied_roots=denied
        )
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
