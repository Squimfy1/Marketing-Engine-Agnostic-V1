"""Path conventions for the Tenant -> Brand vault layout.

This is the single source of truth for *where things live* in the vault. Every
other module asks ``VaultLayout`` for paths rather than hard-coding strings, so
the on-disk structure can change in exactly one place.

    VAULT_ROOT/
    ├── _shared/
    └── tenants/<tenant_id>/
        ├── tenant.yaml
        └── brands/<brand_id>/
            ├── brand.yaml
            ├── _kb/  _rules/  _memory/  _outputs/  _design/
            └── Dashboard.md
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SHARED_DIR = "_shared"
TENANTS_DIR = "tenants"
BRANDS_DIR = "brands"

TENANT_CONFIG = "tenant.yaml"
BRAND_CONFIG = "brand.yaml"

KB_DIR = "_kb"
RULES_DIR = "_rules"
MEMORY_DIR = "_memory"
OUTPUTS_DIR = "_outputs"
DESIGN_DIR = "_design"
SOURCES_DIR = "_sources"  # raw call transcripts; read ONLY by distillation, never by generation

CORE_RULES_FILE = "_rules/_core.md"
DASHBOARD_FILE = "Dashboard.md"

# Folders created when a brand is scaffolded.
BRAND_SUBDIRS = (KB_DIR, RULES_DIR, MEMORY_DIR, OUTPUTS_DIR, DESIGN_DIR, SOURCES_DIR)


@dataclass(frozen=True)
class VaultLayout:
    """Resolves paths within a single vault root. Always returns absolute paths."""

    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root).expanduser().resolve())

    # -- top level -------------------------------------------------------
    @property
    def shared_dir(self) -> Path:
        return self.root / SHARED_DIR

    @property
    def tenants_dir(self) -> Path:
        return self.root / TENANTS_DIR

    # -- tenant ----------------------------------------------------------
    def tenant_dir(self, tenant_id: str) -> Path:
        return self.tenants_dir / tenant_id

    def tenant_config(self, tenant_id: str) -> Path:
        return self.tenant_dir(tenant_id) / TENANT_CONFIG

    def brands_dir(self, tenant_id: str) -> Path:
        return self.tenant_dir(tenant_id) / BRANDS_DIR

    # -- brand -----------------------------------------------------------
    def brand_dir(self, tenant_id: str, brand_id: str) -> Path:
        return self.brands_dir(tenant_id) / brand_id

    def brand_config(self, tenant_id: str, brand_id: str) -> Path:
        return self.brand_dir(tenant_id, brand_id) / BRAND_CONFIG

    def kb_dir(self, tenant_id: str, brand_id: str) -> Path:
        return self.brand_dir(tenant_id, brand_id) / KB_DIR

    def rules_dir(self, tenant_id: str, brand_id: str) -> Path:
        return self.brand_dir(tenant_id, brand_id) / RULES_DIR

    def core_rules(self, tenant_id: str, brand_id: str) -> Path:
        return self.brand_dir(tenant_id, brand_id) / CORE_RULES_FILE

    def memory_dir(self, tenant_id: str, brand_id: str) -> Path:
        return self.brand_dir(tenant_id, brand_id) / MEMORY_DIR

    def outputs_dir(self, tenant_id: str, brand_id: str) -> Path:
        return self.brand_dir(tenant_id, brand_id) / OUTPUTS_DIR

    def design_dir(self, tenant_id: str, brand_id: str) -> Path:
        return self.brand_dir(tenant_id, brand_id) / DESIGN_DIR

    def sources_dir(self, tenant_id: str, brand_id: str) -> Path:
        return self.brand_dir(tenant_id, brand_id) / SOURCES_DIR

    def dashboard(self, tenant_id: str, brand_id: str) -> Path:
        return self.brand_dir(tenant_id, brand_id) / DASHBOARD_FILE

    # -- isolation -------------------------------------------------------
    def allowed_roots(self, tenant_id: str, brand_id: str) -> tuple[Path, ...]:
        """Directories the agent may touch for this brand: its own subtree + _shared.

        This is the allowlist enforced by the SDK path hook.
        """

        return (self.brand_dir(tenant_id, brand_id), self.shared_dir)
