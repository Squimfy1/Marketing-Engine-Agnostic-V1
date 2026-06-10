"""Commit a finished/edited draft: write it + append an edit-learning.

Backs the dashboard's "Save edits" (commit-edits). Two effects, both inside the
brand's subtree:
  1. write the draft as a dated note in ``_outputs/`` (reuses ``write_output_note``)
  2. if the user edited the model's text, append what changed to
     ``_memory/LAB_LEARNINGS.md`` so the next generation can honour it.

Learnings are append-only — a growing log the assembler feeds back into context.
"""

from __future__ import annotations

from marketing_engine.tools.output_tools import write_output_note
from marketing_engine.vault.adapter import VaultAdapter
from marketing_engine.vault.layout import MEMORY_DIR

LAB_LEARNINGS = f"{MEMORY_DIR}/LAB_LEARNINGS.md"
_HEADER = "# Lab edit learnings\n\nAppended on each saved edit. Newest at bottom.\n"


def _title(content: str, topic: str | None) -> str:
    if topic and topic.strip():
        return topic.strip()[:80]
    first = next((ln.strip() for ln in content.splitlines() if ln.strip()), "untitled")
    return first.lstrip("# ").strip()[:80] or "untitled"


def _learning_entry(
    *,
    date_str: str,
    platform: str,
    summary: str,
    tips: list[str],
    original: str | None,
    edited: str | None,
    char_delta: int | None,
) -> str:
    lines = [f"\n---\n\n## {date_str} — {platform}"]
    if summary.strip():
        lines.append(f"**Summary:** {summary.strip()}")
    if char_delta is not None:
        lines.append(f"**Length delta:** {char_delta:+d} chars")
    if tips:
        lines.append("\n**Apply next time:**")
        lines.extend(f"- {t.strip()}" for t in tips if t.strip())
    if original and edited:
        lines.append("\n### Model output\n```\n" + original.strip() + "\n```")
        lines.append("\n### Your edit\n```\n" + edited.strip() + "\n```")
    return "\n".join(lines) + "\n"


def commit(
    vault: VaultAdapter,
    *,
    content: str,
    platform: str,
    date_str: str,
    topic: str | None = None,
    summary: str = "",
    tips: list[str] | None = None,
    original: str | None = None,
    edited: str | None = None,
    char_delta: int | None = None,
) -> dict:
    """Write the draft and (if there was an edit) append a learning. Returns
    ``{path, learningEntries}``."""

    tips = tips or []
    title = _title(content, topic)
    relpath = write_output_note(
        vault, title=title, body=content, date_str=date_str, kind=platform
    )

    learning_written = 0
    has_edit = bool((original and edited) or tips or summary.strip())
    if has_edit:
        if not vault.exists(LAB_LEARNINGS):
            vault.write(LAB_LEARNINGS, _HEADER)
        vault.append(
            LAB_LEARNINGS,
            _learning_entry(
                date_str=date_str,
                platform=platform,
                summary=summary,
                tips=tips,
                original=original,
                edited=edited,
                char_delta=char_delta,
            ),
        )
        learning_written = 1

    return {"path": relpath, "learningEntries": learning_written}


def recent_learnings(vault: VaultAdapter, *, max_chars: int = 4000) -> str:
    """Return the tail of LAB_LEARNINGS.md for display / context injection."""

    if not vault.exists(LAB_LEARNINGS):
        return ""
    text = vault.read(LAB_LEARNINGS)
    return text[-max_chars:] if len(text) > max_chars else text
