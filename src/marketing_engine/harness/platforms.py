"""Content platforms (formats) — client-agnostic, shared across all brands.

A platform is a content format the dashboard can target (Short posts, Articles).
Its guidance lives in ``_shared/platforms/<id>.md`` and is injected into the run
prompt at generate time. Platforms are intentionally a small fixed set in M2;
per-brand platform sets are a later milestone.
"""

from __future__ import annotations

from dataclasses import dataclass

from marketing_engine.vault.layout import VaultLayout

PLATFORMS_DIR = "platforms"


@dataclass(frozen=True)
class Platform:
    id: str  # filename stem under _shared/platforms/
    label: str  # what the dashboard shows / sends


# Focused on short posts for now (Articles deferred — re-add when needed).
PLATFORMS: tuple[Platform, ...] = (
    Platform(id="short-posts", label="Short posts"),
)

_BY_LABEL = {p.label: p for p in PLATFORMS}
_BY_ID = {p.id: p for p in PLATFORMS}

DEFAULT_PLATFORM = PLATFORMS[0]


def resolve_platform(value: str | None) -> Platform:
    """Resolve a platform from its label or id; falls back to the default."""

    if not value:
        return DEFAULT_PLATFORM
    return _BY_LABEL.get(value) or _BY_ID.get(value) or DEFAULT_PLATFORM


def load_guidance(layout: VaultLayout, platform: Platform) -> str:
    """Read the platform's format guidance from _shared/platforms/<id>.md."""

    path = layout.shared_dir / PLATFORMS_DIR / f"{platform.id}.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""
