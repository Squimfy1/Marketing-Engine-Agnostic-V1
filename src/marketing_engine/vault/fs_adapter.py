"""Filesystem-direct vault backend — the Milestone 1 Obsidian integration.

A brand's data is just a folder of markdown. This adapter is scoped to one
brand subtree; relative paths are resolved against the brand folder and asserted
to stay within the brand's allowed roots.
"""

from __future__ import annotations

from pathlib import Path

from marketing_engine.vault.adapter import VaultAdapter
from marketing_engine.vault.layout import VaultLayout
from marketing_engine.vault.paths import resolve_within


class FilesystemVaultAdapter(VaultAdapter):
    def __init__(self, layout: VaultLayout, tenant_id: str, brand_id: str) -> None:
        self.layout = layout
        self.tenant_id = tenant_id
        self.brand_id = brand_id
        self.brand_dir = layout.brand_dir(tenant_id, brand_id)
        self.allowed_roots = layout.allowed_roots(tenant_id, brand_id)

    def _abs(self, relpath: str) -> Path:
        return resolve_within(self.brand_dir / relpath, self.allowed_roots)

    def read(self, relpath: str) -> str:
        return self._abs(relpath).read_text(encoding="utf-8")

    def write(self, relpath: str, content: str) -> None:
        target = self._abs(relpath)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def append(self, relpath: str, content: str) -> None:
        target = self._abs(relpath)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(content)

    def exists(self, relpath: str) -> bool:
        try:
            return self._abs(relpath).exists()
        except PermissionError:
            return False

    def glob(self, pattern: str) -> list[str]:
        return sorted(
            str(p.relative_to(self.brand_dir))
            for p in self.brand_dir.glob(pattern)
            if p.is_file()
        )
