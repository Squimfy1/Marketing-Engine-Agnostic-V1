"""Design System seam (Milestone 4). Image output renders from brand tokens.

Stubbed in Milestone 1: the protocol documents the contract; the stub turns a
brief into a markdown image-brief instead of a rendered image.
"""

from __future__ import annotations

from typing import Protocol


class DesignSystem(Protocol):
    def render(self, brief: str, tokens: dict) -> str:
        """Return a reference to the produced image (a path/URL). Stubbed for now."""
        ...


class StubDesignSystem:
    """Placeholder: echoes the brief as a 'brief' reference, no real rendering."""

    def render(self, brief: str, tokens: dict) -> str:  # pragma: no cover - M4
        return f"image-brief: {brief[:80]}"
