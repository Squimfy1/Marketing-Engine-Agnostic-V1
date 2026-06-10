"""Shared fixtures: a throwaway vault built on disk for each test."""

from __future__ import annotations

from pathlib import Path

import pytest

from marketing_engine.config.settings import Settings
from marketing_engine.vault.layout import BRAND_SUBDIRS, VaultLayout


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_brand(
    layout: VaultLayout,
    tenant_id: str,
    brand_id: str,
    *,
    name: str,
    voice: str,
    core_rule: str,
    dashboard_input: str = "Write a tagline.",
) -> None:
    for sub in BRAND_SUBDIRS:
        (layout.brand_dir(tenant_id, brand_id) / sub).mkdir(parents=True, exist_ok=True)
    _write(
        layout.brand_config(tenant_id, brand_id),
        f"id: {brand_id}\nname: {name}\nidentity: Test identity.\nvoice: {voice}\n",
    )
    _write(layout.core_rules(tenant_id, brand_id), f"# Core\n\n- {core_rule}\n")
    _write(
        layout.dashboard(tenant_id, brand_id),
        f"# Dashboard\n\n## Input\n\n{dashboard_input}\n\n## Text Output\n\n## Status\n",
    )


@pytest.fixture()
def vault_root(tmp_path: Path) -> Path:
    layout = VaultLayout(tmp_path)
    layout.shared_dir.mkdir(parents=True, exist_ok=True)
    (layout.shared_dir / "house-style.md").write_text("# House style\n", encoding="utf-8")
    _write(
        layout.tenant_config("acme-co"),
        "id: acme-co\nname: Acme Co\nnotes: Test agency.\n",
    )
    make_brand(
        layout,
        "acme-co",
        "acme",
        name="Acme Rockets",
        voice="Playful and warm.",
        core_rule="Always sound fun.",
        dashboard_input="Write an Instagram caption for the Sky Pup kit.",
    )
    make_brand(
        layout,
        "acme-co",
        "globex",
        name="Globex Capital",
        voice="Formal and authoritative.",
        core_rule="Maintain a formal register.",
        dashboard_input="Write a LinkedIn post for CFOs.",
    )
    return tmp_path


@pytest.fixture()
def layout(vault_root: Path) -> VaultLayout:
    return VaultLayout(vault_root)


@pytest.fixture()
def settings(vault_root: Path) -> Settings:
    return Settings.from_env(vault_root=vault_root)
