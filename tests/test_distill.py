from __future__ import annotations

import pytest

from marketing_engine.content.distill import DistillError, distill
from marketing_engine.harness.engine import MarketingEngine
from marketing_engine.sdk.client import FakeLLMClient


@pytest.mark.asyncio
async def test_distill_writes_profile(settings, layout):
    sdir = layout.sources_dir("acme-co", "acme")
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "call.txt").write_text("Founder: our whole thesis is X. We keep coming back to it.", encoding="utf-8")

    engine = MarketingEngine(settings, llm=FakeLLMClient())
    result = await distill(engine, "acme-co", "acme")

    assert result.core_narrative
    assert "_rules/strategy.md" in result.files_written
    km = (layout.rules_dir("acme-co", "acme") / "strategy.md").read_text(encoding="utf-8")
    assert "KEY IDEAS" in km
    # The three universal filter dimensions are present and filled.
    assert "BUSINESS PRINCIPLES" in km and "CUSTOMER NARRATIVES" in km
    assert result.strategy["business_principles"]
    assert (layout.kb_dir("acme-co", "acme") / "proof-points.md").is_file()


@pytest.mark.asyncio
async def test_distill_no_sources_errors(settings):
    engine = MarketingEngine(settings, llm=FakeLLMClient())
    with pytest.raises(DistillError):
        await distill(engine, "acme-co", "globex")  # no _sources content


@pytest.mark.asyncio
async def test_distilled_narrative_reaches_system_prompt(settings, layout):
    sdir = layout.sources_dir("acme-co", "acme")
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "call.txt").write_text("strategy talk", encoding="utf-8")
    engine = MarketingEngine(settings, llm=FakeLLMClient())
    await distill(engine, "acme-co", "acme")
    from marketing_engine.brand.assembler import assemble_run
    run = assemble_run(
        layout=layout, settings=settings,
        tenant=engine.registry.get_tenant("acme-co"),
        brand=engine.registry.get_brand("acme-co", "acme"),
        input_text="x", platform_label="Short posts",
    )
    assert "KEY IDEAS" in run.system_prompt  # key-ideas.md is inlined as a brand rule
