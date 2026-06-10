from __future__ import annotations

from marketing_engine.vault.layout import VaultLayout


def test_paths_are_nested_tenant_then_brand(layout: VaultLayout):
    brand = layout.brand_dir("acme-co", "acme")
    assert brand == layout.root / "tenants" / "acme-co" / "brands" / "acme"
    assert layout.brand_config("acme-co", "acme") == brand / "brand.yaml"
    assert layout.core_rules("acme-co", "acme") == brand / "_rules" / "_core.md"
    assert layout.dashboard("acme-co", "acme") == brand / "Dashboard.md"


def test_allowed_roots_are_brand_subtree_plus_shared(layout: VaultLayout):
    roots = layout.allowed_roots("acme-co", "acme")
    assert layout.brand_dir("acme-co", "acme") in roots
    assert layout.shared_dir in roots
    # A sibling brand is NOT in the allowed roots.
    assert layout.brand_dir("acme-co", "globex") not in roots
