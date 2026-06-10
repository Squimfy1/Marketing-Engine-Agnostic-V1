"""Obsidian Memory — append-only notes the engine accumulates per brand.

Append-only by design: memory is a log of facts/decisions/feedback, never
rewritten, so history is preserved and writes can't race-clobber.
"""

from __future__ import annotations

from marketing_engine.vault.adapter import VaultAdapter
from marketing_engine.vault.layout import MEMORY_DIR

MEMORY_LOG = f"{MEMORY_DIR}/log.md"


def append_memory(vault: VaultAdapter, *, note: str, date_str: str) -> str:
    """Append a timestamped entry to the brand's memory log. Returns the relpath."""

    entry = f"- **{date_str}** — {note.strip()}\n"
    if not vault.exists(MEMORY_LOG):
        vault.write(MEMORY_LOG, "# Memory\n\n")
    vault.append(MEMORY_LOG, entry)
    return MEMORY_LOG
