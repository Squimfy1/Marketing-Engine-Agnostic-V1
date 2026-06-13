"""The news scraper: relevance filtering, digest write, fail-soft."""

from __future__ import annotations

import json

import pytest

from marketing_engine.harness.engine import MarketingEngine
from marketing_engine.inputs.scraper import NewsItem, _coerce_items, _render_digest, scrape_news
from marketing_engine.sdk.client import FakeLLMClient, RunResult


def test_coerce_drops_low_relevance_and_caps():
    raw = [
        {"title": "A", "relevance": "high"},
        {"title": "B", "relevance": "low"},      # dropped (below medium floor)
        {"title": "", "relevance": "high"},       # dropped (no title)
        {"title": "C", "relevance": "medium"},
        {"title": "D", "relevance": "high"},
    ]
    items = _coerce_items(raw, max_items=2)
    assert [i.title for i in items] == ["A", "D"]  # high sorted first, capped at 2


def test_render_digest_includes_tags():
    items = [NewsItem(title="Prices rise", source="Wire", date="2026-06-10",
                      summary="Costs up.", principle="purchasing power",
                      narrative="savings erode", angle="tie to holding something real",
                      relevance="high")]
    md = _render_digest(items, "2026-06-12")
    assert "## Prices rise" in md and "Ties to:" in md and "Possible angle:" in md


@pytest.mark.asyncio
async def test_scrape_writes_digest(settings, layout):
    eng = MarketingEngine(settings, llm=FakeLLMClient())
    result = await scrape_news(eng, "acme-co", "acme")
    assert result.file_written and result.file_written.startswith("_kb/news/")
    assert result.file_written.endswith(".md")
    # The fake returns one high + one low; only the high survives.
    assert len(result.items) == 1 and result.items[0].relevance == "high"
    news_files = list(layout.news_dir("acme-co", "acme").glob("*.md"))
    assert news_files, "a digest file should be written"
    body = news_files[0].read_text(encoding="utf-8")
    assert "News digest" in body and "Inflation" in body


class _NoNewsFake(FakeLLMClient):
    async def run(self, prompt, options):
        if "Find recent news" in prompt:
            return RunResult(text="[]", model="fake")  # nothing relevant
        return await super().run(prompt, options)


@pytest.mark.asyncio
async def test_scrape_fails_soft_when_empty(settings, layout):
    eng = MarketingEngine(settings, llm=_NoNewsFake())
    result = await scrape_news(eng, "acme-co", "acme")
    assert result.items == [] and result.file_written is None
    assert not list(layout.news_dir("acme-co", "acme").glob("*.md"))
