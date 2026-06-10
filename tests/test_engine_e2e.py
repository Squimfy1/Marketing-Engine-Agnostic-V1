"""End-to-end Milestone 1 path against the deterministic fake model (no network)."""

from __future__ import annotations

import pytest

from marketing_engine.harness.engine import EngineError, MarketingEngine
from marketing_engine.sdk.client import FakeLLMClient
from marketing_engine.tenant.registry import BrandNotFoundError
from marketing_engine.tools.memory_tools import MEMORY_LOG
from marketing_engine.vault.dashboard import get_section
from marketing_engine.vault.fs_adapter import FilesystemVaultAdapter


def _engine(settings):
    return MarketingEngine(settings, llm=FakeLLMClient())


@pytest.mark.asyncio
async def test_full_round_trip_writes_back_to_vault(settings):
    engine = _engine(settings)
    result = await engine.run("acme-co", "acme", date_str="2026-06-08")

    assert not result.is_error
    assert result.denied_paths == []

    vault = FilesystemVaultAdapter(engine.layout, "acme-co", "acme")

    # 1. Dated output note exists with frontmatter.
    assert vault.exists(result.output_relpath)
    note = vault.read(result.output_relpath)
    assert note.startswith("---")
    assert "generated_by: marketing-engine" in note
    assert result.output_relpath.startswith("_outputs/2026-06-08-")

    # 2. Dashboard Text Output + Status updated; Input preserved.
    dash_text = vault.read("Dashboard.md")
    assert get_section(dash_text, "Text Output") == result.text
    assert "2026-06-08: ok" in get_section(dash_text, "Status")
    assert "Sky Pup" in get_section(dash_text, "Input")

    # 3. Memory recorded.
    assert vault.exists(MEMORY_LOG)
    assert "2026-06-08" in vault.read(MEMORY_LOG)


@pytest.mark.asyncio
async def test_same_code_different_brand_yields_different_output(settings):
    """The agnosticism proof: one engine, two brands, divergent on-brand copy."""

    engine = _engine(settings)
    acme = await engine.run("acme-co", "acme", date_str="2026-06-08")
    globex = await engine.run("acme-co", "globex", date_str="2026-06-08")

    assert acme.text != globex.text
    assert "Playful" in acme.text or "warm" in acme.text.lower()
    assert "Formal" in globex.text or "authoritative" in globex.text.lower()


@pytest.mark.asyncio
async def test_inline_input_overrides_dashboard(settings):
    engine = _engine(settings)
    result = await engine.run(
        "acme-co", "acme", input_text="Write a product launch headline.", date_str="2026-06-08"
    )
    assert "product launch headline" in result.text.lower()


@pytest.mark.asyncio
async def test_unknown_brand_fails_fast(settings):
    engine = _engine(settings)
    with pytest.raises(BrandNotFoundError):
        await engine.run("acme-co", "ghost")


@pytest.mark.asyncio
async def test_empty_input_raises(settings):
    engine = _engine(settings)
    with pytest.raises(EngineError):
        await engine.run("acme-co", "acme", input_text="   ", date_str="2026-06-08")
