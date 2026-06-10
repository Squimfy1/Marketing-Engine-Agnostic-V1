"""Path-safety helpers shared by the vault adapter and the SDK isolation hook.

The single rule the whole isolation model rests on: a resolved path must live
inside one of the allowed roots. Symlinks and ``..`` are collapsed via
``resolve()`` before the check, so traversal attempts cannot escape.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


def is_within(path: Path | str, allowed_roots: Iterable[Path]) -> bool:
    """True if ``path`` resolves to a location inside any allowed root."""

    resolved = Path(path).expanduser().resolve()
    for root in allowed_roots:
        root_resolved = Path(root).expanduser().resolve()
        if resolved == root_resolved or root_resolved in resolved.parents:
            return True
    return False


def resolve_within(path: Path | str, allowed_roots: Iterable[Path]) -> Path:
    """Resolve ``path`` and assert it is inside an allowed root.

    Raises ``PermissionError`` on escape — used by the vault adapter so a
    programming bug can never write outside a brand's subtree.
    """

    resolved = Path(path).expanduser().resolve()
    roots = list(allowed_roots)
    if not is_within(resolved, roots):
        roots_str = ", ".join(str(r) for r in roots)
        raise PermissionError(f"Path {resolved} is outside allowed roots: {roots_str}")
    return resolved
