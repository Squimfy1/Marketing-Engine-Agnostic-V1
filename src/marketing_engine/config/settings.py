"""Process-level settings, driven by the environment.

Nothing brand-specific lives here — only where the vault is and what the
default model is. Per-tenant / per-brand configuration lives in the vault.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from marketing_engine.sdk.models import DEFAULT_MODEL

DEFAULT_VAULT_ROOT = "./vault"


@dataclass(frozen=True)
class Settings:
    vault_root: Path
    default_model: str
    anthropic_api_key: str | None

    @classmethod
    def from_env(cls, *, vault_root: str | os.PathLike[str] | None = None) -> "Settings":
        root = vault_root or os.environ.get("VAULT_ROOT", DEFAULT_VAULT_ROOT)
        return cls(
            vault_root=Path(root).expanduser().resolve(),
            default_model=os.environ.get("MARKETING_ENGINE_MODEL", DEFAULT_MODEL),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )
