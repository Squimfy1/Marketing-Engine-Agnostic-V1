"""The agnostic strategy filter: schema round-trip, parsing, scoring, selection."""

from __future__ import annotations

import json

import pytest

from marketing_engine.content import strategy as S
from marketing_engine.content.filter import (
    FilterOutcome,
    FilteredIdea,
    _parse_verdicts,
    filter_ideas,
    select,
)
from marketing_engine.harness.engine import MarketingEngine
from marketing_engine.sdk.client import AgentRunOptions, FakeLLMClient, RunResult


def test_strategy_md_round_trips():
    data = {
        "business_principles": ["Tangible backing", "Buy small amounts"],
        "customer_personas": ["Everyday family"],
        "customer_narratives": ["Prices keep rising"],
        "key_ideas": ["Angle A"],
        "trajectory": "Heading here.",
        "avoid": ["No hype"],
    }
    md = S.render_strategy_md(data)
    assert "## BUSINESS PRINCIPLES" in md and "## CUSTOMER NARRATIVES" in md
    parsed = S.parse_strategy_md(md)
    assert parsed["business_principles"] == ["Tangible backing", "Buy small amounts"]
    assert parsed["customer_narratives"] == ["Prices keep rising"]
    assert S.has_filter_dimensions(parsed)


def test_has_filter_dimensions_needs_both():
    assert not S.has_filter_dimensions({"business_principles": ["x"]})  # no narratives
    assert not S.has_filter_dimensions({"customer_narratives": ["x"]})  # no principles
    assert S.has_filter_dimensions(
        {"business_principles": ["x"], "customer_narratives": ["y"]}
    )


def test_parse_verdicts_keys_by_one_based_i():
    text = 'noise [{"i": 2, "keep": false}, {"i": 1, "keep": true}] tail'
    v = _parse_verdicts(text)
    assert v[0]["keep"] is True and v[1]["keep"] is False  # 0-based


def test_select_keeps_first_then_backfills():
    ideas = [
        FilteredIdea("a", keep=False),
        FilteredIdea("b", keep=True),
        FilteredIdea("c", keep=True),
        FilteredIdea("d", keep=False),
    ]
    out = select(FilterOutcome(ideas=ideas), 3)
    assert [i.text for i in out] == ["b", "c", "a"]  # kept first, then a dropped one


class _DropOddFake(FakeLLMClient):
    """A fake that keeps even-indexed ideas and drops odd ones (1-based)."""

    async def run(self, prompt, options):
        if "## CANDIDATE IDEAS" in prompt:
            import re

            section = prompt.split("## CANDIDATE IDEAS", 1)[1]
            n = len([ln for ln in section.splitlines() if re.match(r"\s*\d+\.", ln)])
            arr = [{"i": k + 1, "keep": (k % 2 == 0), "reason": "x"} for k in range(n)]
            return RunResult(text=json.dumps(arr), model="fake")
        return await super().run(prompt, options)


@pytest.mark.asyncio
async def test_filter_fails_open_without_strategy(settings, layout):
    # No strategy.md for this brand → every idea kept, untagged, filter didn't run.
    engine = MarketingEngine(settings, llm=FakeLLMClient())
    out = await filter_ideas(
        engine, tenant_id="acme-co", brand_id="acme", ideas=["one", "two"]
    )
    assert out.ran is False
    assert [i.text for i in out.ideas] == ["one", "two"]
    assert all(i.keep and not i.filtered for i in out.ideas)


@pytest.mark.asyncio
async def test_filter_runs_and_tags_when_strategy_present(settings, layout):
    # Write a strategy.md with the two required dimensions.
    rules = layout.rules_dir("acme-co", "acme")
    rules.mkdir(parents=True, exist_ok=True)
    (rules / S.STRATEGY_FILE).write_text(
        S.render_strategy_md(
            {
                "business_principles": ["Tangible backing"],
                "customer_narratives": ["Prices keep rising"],
            }
        ),
        encoding="utf-8",
    )
    engine = MarketingEngine(settings, llm=_DropOddFake())
    out = await filter_ideas(
        engine,
        tenant_id="acme-co",
        brand_id="acme",
        ideas=["idea1", "idea2", "idea3", "idea4"],
    )
    assert out.ran is True
    assert [i.keep for i in out.ideas] == [True, False, True, False]
    assert all(i.filtered for i in out.ideas)
    kept = select(out, 2)
    assert [i.text for i in kept] == ["idea1", "idea3"]
