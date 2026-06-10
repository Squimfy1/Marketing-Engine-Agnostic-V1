from __future__ import annotations

import pytest

from marketing_engine.sdk.isolation import extract_paths, guard_decision, make_path_guard_hook
from marketing_engine.vault.fs_adapter import FilesystemVaultAdapter
from marketing_engine.vault.layout import VaultLayout


def test_in_brand_read_is_allowed(layout: VaultLayout):
    roots = layout.allowed_roots("acme-co", "acme")
    path = str(layout.kb_dir("acme-co", "acme") / "product.md")
    allowed, offending = guard_decision("Read", {"file_path": path}, roots)
    assert allowed and offending == []


def test_shared_read_is_allowed(layout: VaultLayout):
    roots = layout.allowed_roots("acme-co", "acme")
    path = str(layout.shared_dir / "house-style.md")
    allowed, _ = guard_decision("Read", {"file_path": path}, roots)
    assert allowed


def test_cross_brand_write_is_denied(layout: VaultLayout):
    roots = layout.allowed_roots("acme-co", "acme")
    other = str(layout.brand_dir("acme-co", "globex") / "_outputs" / "leak.md")
    allowed, offending = guard_decision("Write", {"file_path": other}, roots)
    assert not allowed and offending == [other]


def test_path_traversal_is_denied(layout: VaultLayout):
    roots = layout.allowed_roots("acme-co", "acme")
    escape = str(layout.brand_dir("acme-co", "acme") / ".." / "globex" / "brand.yaml")
    allowed, offending = guard_decision("Read", {"file_path": escape}, roots)
    assert not allowed


def test_bash_is_always_denied(layout: VaultLayout):
    roots = layout.allowed_roots("acme-co", "acme")
    allowed, _ = guard_decision("Bash", {"command": "ls"}, roots)
    assert not allowed


def test_extract_paths_handles_glob_and_grep():
    assert extract_paths("Glob", {"path": "/x", "pattern": "*.md"}) == ["/x"]
    assert extract_paths("Grep", {"path": "/y"}) == ["/y"]
    assert extract_paths("Read", {}) == []


@pytest.mark.asyncio
async def test_hook_denies_and_logs(layout: VaultLayout):
    roots = layout.allowed_roots("acme-co", "acme")
    log: list[str] = []
    hook = make_path_guard_hook(roots, log)
    other = str(layout.brand_dir("acme-co", "globex") / "brand.yaml")
    out = await hook({"tool_name": "Read", "tool_input": {"file_path": other}}, "id", None)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert len(log) == 1


@pytest.mark.asyncio
async def test_hook_allows_in_brand(layout: VaultLayout):
    roots = layout.allowed_roots("acme-co", "acme")
    hook = make_path_guard_hook(roots, [])
    inside = str(layout.kb_dir("acme-co", "acme") / "product.md")
    out = await hook({"tool_name": "Read", "tool_input": {"file_path": inside}}, "id", None)
    assert out == {}


def test_fs_adapter_blocks_escape(layout: VaultLayout):
    vault = FilesystemVaultAdapter(layout, "acme-co", "acme")
    with pytest.raises(PermissionError):
        vault.write("../globex/_outputs/leak.md", "nope")
