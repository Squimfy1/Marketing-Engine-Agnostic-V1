"""The news scraper: Google News scan -> relevance/reliability filter -> cross-exam."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

import marketing_engine.inputs.scraper as scraper
from marketing_engine.harness.engine import MarketingEngine
from marketing_engine.inputs.scraper import (
    NewsItem,
    _coerce_items,
    _render_digest,
    google_news_scan,
    scrape_news,
)
from marketing_engine.sdk.client import FakeLLMClient, RunResult

# A candidate pool the deterministic Google News scan would return — patched in so tests
# never touch the network.
_POOL = [
    {"title": "Fresh Swiss savings story", "url": "https://nzz.ch/a", "source": "NZZ", "date": "2026-07-20"},
    {"title": "Second fresh story", "url": "https://finews.ch/b", "source": "finews", "date": "2026-07-19"},
]


def _patch_scan(monkeypatch, pool):
    async def fake_scan(entries, **kw):
        return list(pool), {}  # (candidates, coverage)
    monkeypatch.setattr(scraper, "scan_news_matrix", fake_scan)


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


def test_render_digest_includes_tags_and_corroboration():
    items = [NewsItem(title="Prices rise", source="Wire", date="2026-06-10",
                      summary="Costs up.", principle="purchasing power",
                      narrative="savings erode", angle="tie to holding something real",
                      relevance="high", corroboration="Reuters (url), WGC (url)")]
    md = _render_digest(items, "2026-06-12")
    assert "## Prices rise" in md and "Ties to:" in md and "Possible angle:" in md
    assert "Confirmed by:" in md and "Reuters" in md


@pytest.mark.asyncio
async def test_scrape_writes_digest(settings, layout, monkeypatch):
    _patch_scan(monkeypatch, _POOL)
    eng = MarketingEngine(settings, llm=FakeLLMClient())
    result = await scrape_news(eng, "acme-co", "acme")
    assert result.file_written and result.file_written.startswith("_kb/news/")
    assert result.file_written.endswith(".md")
    # The fake filter returns one high + one low; only the high survives.
    assert len(result.items) == 1 and result.items[0].relevance == "high"
    news_files = list(layout.news_dir("acme-co", "acme").glob("*.md"))
    assert news_files, "a digest file should be written"
    body = news_files[0].read_text(encoding="utf-8")
    assert "News digest" in body and "Inflation" in body


@pytest.mark.asyncio
async def test_scrape_fails_soft_when_pool_empty(settings, layout, monkeypatch):
    # Nothing fresh on the wire -> early return, no agent call, no file.
    _patch_scan(monkeypatch, [])
    eng = MarketingEngine(settings, llm=FakeLLMClient())
    result = await scrape_news(eng, "acme-co", "acme")
    assert result.items == [] and result.file_written is None
    assert not list(layout.news_dir("acme-co", "acme").glob("*.md"))


class _EmptyFilterFake(FakeLLMClient):
    """Pool is non-empty but the relevance filter keeps nothing."""

    async def run(self, prompt, options):
        if "## CANDIDATE POOL" in prompt:
            return RunResult(text="[]", model="fake")
        return await super().run(prompt, options)


@pytest.mark.asyncio
async def test_scrape_fails_soft_when_filter_empty(settings, layout, monkeypatch):
    _patch_scan(monkeypatch, _POOL)
    eng = MarketingEngine(settings, llm=_EmptyFilterFake())
    result = await scrape_news(eng, "acme-co", "acme")
    assert result.items == [] and result.file_written is None


class _CrossExamFake(FakeLLMClient):
    """Filter keeps two 'high' items; cross-examination corroborates one and refutes the
    other. Each cross-exam subagent sees exactly ONE item, so branch on its title."""

    async def run(self, prompt, options):
        if "## ITEM TO CROSS-EXAMINE" in prompt:  # per-item cross-examination subagent
            if "Real, corroborated story" in prompt:
                verdict = {"corroborated": True, "legitimate": True,
                           "sources": ["Reuters (https://reuters.com/x)", "WGC (https://gold.org/y)"],
                           "summary": "Corrected, cross-checked summary.", "date": "2026-07-18",
                           "reason": "confirmed by two independent reputable sources"}
            else:  # the uncorroborated candidate
                verdict = {"corroborated": False, "legitimate": False,
                           "sources": [], "summary": "", "date": "",
                           "reason": "only the one originating outlet reports it"}
            return RunResult(text=json.dumps(verdict), model="fake")
        if "## CANDIDATE POOL" in prompt:  # relevance/reliability filter
            return RunResult(
                text=json.dumps(
                    [
                        {"title": "Real, corroborated story", "url": "https://nzz.ch/a",
                         "source": "NZZ", "date": "2026-07-20", "summary": "Draft summary.",
                         "relevance": "high"},
                        {"title": "Uncorroborated story", "url": "https://blog.example/b",
                         "source": "Some blog", "date": "2026-07-19", "summary": "Made up.",
                         "relevance": "high"},
                    ]
                ),
                model="fake",
            )
        return await super().run(prompt, options)


@pytest.mark.asyncio
async def test_cross_exam_drops_uncorroborated_and_records_sources(settings, layout, monkeypatch):
    _patch_scan(monkeypatch, _POOL)
    eng = MarketingEngine(settings, llm=_CrossExamFake())
    result = await scrape_news(eng, "acme-co", "acme")
    assert result.verified is True
    # Only the corroborated story survives.
    assert [i.title for i in result.items] == ["Real, corroborated story"]
    # Corrections + independent corroborating sources are recorded on the kept item.
    assert result.items[0].summary == "Corrected, cross-checked summary."
    assert "Reuters" in result.items[0].corroboration and "WGC" in result.items[0].corroboration
    # The refuted item is recorded (not silently dropped).
    assert any("Uncorroborated" in d["title"] for d in result.dropped)
    body = list(layout.news_dir("acme-co", "acme").glob("*.md"))[0].read_text(encoding="utf-8")
    assert "Uncorroborated story" not in body and "Real, corroborated story" in body
    assert "Confirmed by:" in body


# -- Step 1: the deterministic multi-surface / multi-locale scan -------------------

def _item(title, days_ago, source="Reuters"):
    ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {"title": title, "url": f"https://x/{title}", "source": source,
            "date": ts.strftime("%Y-%m-%d"), "ts": ts}


@pytest.mark.asyncio
async def test_scan_windows_dedupes_and_keeps_query_order(monkeypatch):
    # q0 returns an in-window + a stale item; q1 returns a dup + a fresh unique item.
    feeds = {
        "q0": [_item("Swiss fresh", 3), _item("Swiss stale", 90)],
        "q1": [_item("Swiss fresh", 1), _item("Global fresh", 2)],  # "Swiss fresh" is a dup
    }

    def fake_fetch(url, default_source="", timeout=20):
        # Deterministic by URL content (concurrency-safe), not call order.
        return feeds["q0"] if "q0" in url else feeds["q1"] if "q1" in url else []

    monkeypatch.setattr(scraper, "_fetch_rss_items", fake_fetch)
    out = await google_news_scan(
        ["q0", "q1"], lookback_days=30, per_query=5,
        locales=[scraper._Locale("de-CH", "CH", "CH:de", "de")],  # single locale for determinism
    )
    titles = [o["title"] for o in out]
    assert "Swiss stale" not in titles           # dropped: outside 30-day window
    assert titles.count("Swiss fresh") == 1      # deduped across queries
    assert titles.index("Swiss fresh") < titles.index("Global fresh")  # entry order preserved
    assert set(out[0].keys()) == {"title", "url", "source", "date"}     # ts stripped


@pytest.mark.asyncio
async def test_scan_matrix_reports_coverage_by_category_and_lang(monkeypatch):
    def fake_fetch(url, default_source="", timeout=20):
        # French locale (hl=fr-CH) returns an item; others return nothing.
        return [_item("FR home story", 2)] if "fr-CH" in url else []

    monkeypatch.setattr(scraper, "_fetch_rss_items", fake_fetch)
    entries = scraper.build_query_matrix({"home-lockout": {"de": ["q_de"], "fr": ["q_fr"]}})
    cands, coverage = await scraper.scan_news_matrix(
        entries, lookback_days=30,
        locales=[scraper._Locale("de-CH", "CH", "CH:de", "de"),
                 scraper._Locale("fr-CH", "CH", "CH:fr", "fr")],
    )
    assert [c["title"] for c in cands] == ["FR home story"]
    # Coverage is auditable: fr found 1, de found 0 (a visible gap, not silent).
    assert coverage["home-lockout"]["fr"] == 1
    assert coverage["home-lockout"]["de"] == 0


def test_build_query_matrix_shapes():
    m = scraper.build_query_matrix({
        "problems": {"de": ["a", "b"], "fr": ["c"]},
        "entities": ["UBS"],  # flat list -> language-agnostic
    })
    assert {"category": "problems", "lang": "de", "query": "a"} in m
    assert {"category": "problems", "lang": "fr", "query": "c"} in m
    assert {"category": "entities", "lang": "any", "query": "UBS"} in m


@pytest.mark.asyncio
async def test_google_news_scan_empty_queries():
    assert await google_news_scan([], lookback_days=30) == []
