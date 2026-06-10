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
    _write(layout.shared_dir / "rules" / "WRITING_RULES.md", "# Writing rules\n\n- Be concrete.\n")
    _write(layout.shared_dir / "rules" / "BANNED_PATTERNS.md", "# Banned\n\n- delve\n")
    _write(layout.shared_dir / "platforms" / "short-posts.md", "# Short posts\n\n- 50-280 words.\n")
    _write(layout.shared_dir / "platforms" / "articles.md", "# Articles\n\n- 900-1200 words.\n")
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


@pytest.fixture()
def pdf_factory():
    """Return a function that builds a minimal, valid single-page PDF with text."""

    def make_pdf(text: str) -> bytes:
        objs = [
            b"<</Type/Catalog/Pages 2 0 R>>",
            b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
            b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 200]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
            None,
            b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
        ]
        stream = b"BT /F1 18 Tf 20 100 Td (" + text.encode() + b") Tj ET"
        objs[3] = b"<</Length " + str(len(stream)).encode() + b">>\nstream\n" + stream + b"\nendstream"
        pdf = b"%PDF-1.4\n"
        offsets = []
        for i, o in enumerate(objs, start=1):
            offsets.append(len(pdf))
            pdf += ("%d 0 obj\n" % i).encode() + o + b"\nendobj\n"
        xref = len(pdf)
        pdf += b"xref\n0 " + str(len(objs) + 1).encode() + b"\n0000000000 65535 f \n"
        for off in offsets:
            pdf += ("%010d 00000 n \n" % off).encode()
        pdf += (
            b"trailer<</Size " + str(len(objs) + 1).encode() + b"/Root 1 0 R>>\nstartxref\n"
            + str(xref).encode() + b"\n%%EOF"
        )
        return pdf

    return make_pdf
