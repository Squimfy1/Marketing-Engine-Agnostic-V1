from __future__ import annotations

import pytest

from marketing_engine.harness.distill import DistillError, distill
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
    assert "_rules/narrative.md" in result.files_written
    nm = (layout.rules_dir("acme-co", "acme") / "narrative.md").read_text(encoding="utf-8")
    assert "CORE NARRATIVE" in nm and "KEY IDEAS" in nm
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
    assert "CORE NARRATIVE" in run.system_prompt  # narrative.md is inlined as a brand rule
