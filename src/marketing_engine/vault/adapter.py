"""The vault backend seam.

Milestone 1 ships only ``FilesystemVaultAdapter`` (markdown files on disk — the
filesystem-direct Obsidian integration). This ABC keeps a Local REST API / MCP
backend a drop-in addition later: the harness depends only on this interface.

Every operation is scoped to a single brand's subtree. The adapter resolves all
paths through ``resolve_within`` so a bug can never escape the brand's
``allowed_roots`` — a second line of defence behind the SDK isolation hook.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class VaultAdapter(ABC):
    """Brand-scoped read/write over a vault."""

    @abstractmethod
    def read(self, relpath: str) -> str:
        """Read a file relative to the brand folder."""

    @abstractmethod
    def write(self, relpath: str, content: str) -> None:
        """Write/overwrite a file relative to the brand folder (parents created)."""

    @abstractmethod
    def append(self, relpath: str, content: str) -> None:
        """Append to a file relative to the brand folder (created if absent)."""

    @abstractmethod
    def exists(self, relpath: str) -> bool: ...

    @abstractmethod
    def glob(self, pattern: str) -> list[str]:
        """Return relpaths (relative to the brand folder) matching ``pattern``."""
