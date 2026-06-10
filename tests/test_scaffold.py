from __future__ import annotations

from pathlib import Path

import pytest

from marketing_engine.tenant.registry import Registry
from marketing_engine.tenant.scaffold import ScaffoldError, create_brand, ingest_files
from marketing_engine.vault.layout import VaultLayout


def test_create_brand_scaffolds_and_resolves(layout: VaultLayout):
    create_brand(layout, "studio", "newco", name="NewCo")
    reg = Registry(layout)
    assert "newco" in reg.list_brands("studio")
    brand = reg.get_brand("studio", "newco")  # parses the placeholder brand.yaml
    assert brand.name == "NewCo"
    assert layout.core_rules("studio", "newco").is_file()
    assert (layout.kb_dir("studio", "newco") / "README.md").is_file()
    assert layout.dashboard("studio", "newco").is_file()


def test_create_brand_refuses_overwrite(layout: VaultLayout):
    create_brand(layout, "studio", "newco")
    with pytest.raises(ScaffoldError):
        create_brand(layout, "studio", "newco")


def test_ingest_copies_text_skips_binary(layout: VaultLayout, tmp_path: Path):
    create_brand(layout, "studio", "newco")
    md = tmp_path / "whitepaper.md"; md.write_text("# WP\n", encoding="utf-8")
    txt = tmp_path / "notes.txt"; txt.write_text("notes", encoding="utf-8")
    pdf = tmp_path / "deck.pdf"; pdf.write_text("%PDF", encoding="utf-8")
    ingested, skipped = ingest_files(layout, "studio", "newco", [md, txt, pdf])
    assert set(ingested) == {"whitepaper.md", "notes.txt"}
    assert any("deck.pdf" in s for s in skipped)
    assert (layout.kb_dir("studio", "newco") / "whitepaper.md").is_file()


def test_ingest_requires_brand(layout: VaultLayout, tmp_path: Path):
    f = tmp_path / "x.md"; f.write_text("x", encoding="utf-8")
    with pytest.raises(ScaffoldError):
        ingest_files(layout, "studio", "ghost", [f])
