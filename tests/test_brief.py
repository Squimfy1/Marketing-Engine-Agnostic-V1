"""The binding-assignment step: extraction + injected constraint."""

from __future__ import annotations

import json

import pytest

from marketing_engine.content.brief import Assignment, extract_assignment
from marketing_engine.harness.engine import MarketingEngine
from marketing_engine.sdk.client import FakeLLMClient, RunResult


def test_block_empty_when_not_specific():
    assert Assignment(specific=False, subject="x").block() == ""
    assert Assignment(specific=True, subject="").block() == ""


def test_block_renders_binding_constraint_with_pivot():
    a = Assignment(
        specific=True,
        subject="the legal wrapper the assets are held in",
        angle="investor perspective",
        must_cover=["security classification", "solvency"],
        pivots_from_default=True,
    )
    b = a.block()
    assert "MUST be about: the legal wrapper" in b
    assert "investor perspective" in b
    assert "security classification; solvency" in b
    assert "Do NOT drift back" in b  # pivot guard present


class _PivotFake(FakeLLMClient):
    """Returns a specific, pivoting assignment for any request."""

    async def run(self, prompt, options):
        if '"pivots_from_default"' in prompt:
            return RunResult(text=json.dumps({
                "specific": True, "subject": "the legal wrapper", "angle": "why holders care",
                "audience": "", "must_cover": ["custody", "security status"],
                "pivots_from_default": True,
            }), model="fake")
        return await super().run(prompt, options)


@pytest.mark.asyncio
async def test_extract_assignment_parses(settings):
    eng = MarketingEngine(settings, llm=_PivotFake())
    brand = eng.registry.get_brand("acme-co", "acme")
    a = await extract_assignment(eng, brand, "write about the legal wrapper")
    assert a.specific and a.pivots_from_default
    assert a.subject == "the legal wrapper"
    assert "custody" in a.must_cover


@pytest.mark.asyncio
async def test_generate_injects_assignment(settings, monkeypatch):
    # Capture the run prompt the writer receives to confirm the binding block leads it.
    eng = MarketingEngine(settings, llm=_PivotFake())
    seen = {}
    real_run = eng.llm.run

    async def spy(prompt, options):
        if "## INPUT" in prompt:  # the writer turn (not the assignment/validator calls)
            seen["writer_prompt"] = prompt
        return await real_run(prompt, options)

    monkeypatch.setattr(eng.llm, "run", spy)
    await eng.generate("acme-co", "acme", braindump="explain the legal wrapper", platform="Short posts")
    assert "## ASSIGNMENT (binding" in seen["writer_prompt"]
    assert seen["writer_prompt"].index("## ASSIGNMENT") < seen["writer_prompt"].index("## INPUT")
