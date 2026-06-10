from __future__ import annotations

import pytest

from marketing_engine.tenant.registry import (
    BrandNotFoundError,
    ConfigInvalidError,
    Registry,
    TenantNotFoundError,
)
from marketing_engine.vault.layout import VaultLayout


def test_lists_tenants_and_brands(layout: VaultLayout):
    reg = Registry(layout)
    assert reg.list_tenants() == ["acme-co"]
    assert reg.list_brands("acme-co") == ["acme", "globex"]


def test_resolves_valid_brand(layout: VaultLayout):
    reg = Registry(layout)
    brand = reg.get_brand("acme-co", "acme")
    assert brand.id == "acme"
    assert brand.name == "Acme Rockets"


def test_unknown_tenant_fails_fast(layout: VaultLayout):
    reg = Registry(layout)
    with pytest.raises(TenantNotFoundError):
        reg.get_tenant("nope")


def test_unknown_brand_fails_fast(layout: VaultLayout):
    reg = Registry(layout)
    with pytest.raises(BrandNotFoundError):
        reg.get_brand("acme-co", "nope")


def test_id_folder_mismatch_is_invalid(layout: VaultLayout):
    layout.brand_config("acme-co", "acme").write_text(
        "id: wrong\nname: X\n", encoding="utf-8"
    )
    reg = Registry(layout)
    with pytest.raises(ConfigInvalidError):
        reg.get_brand("acme-co", "acme")
