from __future__ import annotations

from marketing_engine.vault.dashboard import (
    Dashboard,
    get_section,
    parse_sections,
    set_section,
)
from marketing_engine.vault.fs_adapter import FilesystemVaultAdapter
from marketing_engine.vault.layout import VaultLayout

SAMPLE = "# Dashboard\n\n## Input\n\nHello\n\n## Text Output\n\n## Status\n"


def test_parse_and_get_sections():
    sections = parse_sections(SAMPLE)
    assert set(sections) == {"Input", "Text Output", "Status"}
    assert get_section(SAMPLE, "Input") == "Hello"
    assert get_section(SAMPLE, "Text Output") == ""


def test_set_section_replaces_only_target():
    updated = set_section(SAMPLE, "Text Output", "Generated copy.")
    assert get_section(updated, "Text Output") == "Generated copy."
    assert get_section(updated, "Input") == "Hello"  # untouched
    assert "## Status" in updated


def test_set_section_appends_when_missing():
    updated = set_section("# D\n\n## Input\n\nx\n", "Notes", "added")
    assert get_section(updated, "Notes") == "added"


def test_read_input_strips_comment_placeholder(layout: VaultLayout):
    vault = FilesystemVaultAdapter(layout, "acme-co", "acme")
    vault.write(
        "Dashboard.md",
        "# D\n\n## Input\n\n<!-- placeholder -->\n\n## Text Output\n\n## Status\n",
    )
    dash = Dashboard(vault)
    assert dash.read_input() == ""


def test_write_text_output_persists_and_preserves_input(layout: VaultLayout):
    vault = FilesystemVaultAdapter(layout, "acme-co", "acme")
    dash = Dashboard(vault)
    original_input = dash.read_input()
    dash.write_text_output("Fresh copy")
    assert get_section(vault.read("Dashboard.md"), "Text Output") == "Fresh copy"
    assert Dashboard(vault).read_input() == original_input
