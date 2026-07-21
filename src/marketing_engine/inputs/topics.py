"""Per-category topic scan — the Scraper map's refresh.

For ONE category, runs a Claude web-research agent (WebSearch + WebFetch) over the
user's Claude Code login, groups findings into a few concrete SUBTOPICS, and attaches
the real sources behind each so a human can fact-check before drafting. Brand-isolated
and strategy/focus/exclude-aware — the same lens as the news scraper, just organised by
topic instead of a flat digest. The model RETURNS structured JSON; the caller persists.
"""

from __future__ import annotations

from datetime import datetime, timezone

from marketing_engine.content.strategy import format_strategy_for_filter, load_strategy
from marketing_engine.harness.prompts import (
    TOPIC_MAP_SYSTEM,
    TOPIC_SCAN_SYSTEM,
    build_topic_map_prompt,
    build_topic_scan_prompt,
)
from marketing_engine.inputs.scraper import _RELEVANCE_RANK, _raw_objects
from marketing_engine.sdk.client import AgentRunOptions
from marketing_engine.sdk.models import SONNET


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _slugify(label: str) -> str:
    import re

    s = label.strip().lower().replace("&", "and")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "topic"


def _raw_object(text: str) -> dict:
    """Parse the first balanced JSON object from a model reply (tolerates preamble)."""
    import json

    if not text:
        return {}
    start = text.find("{")
    if start < 0:
        return {}
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(text[start : i + 1])
                except Exception:
                    return {}
                return data if isinstance(data, dict) else {}
    return {}


def _coerce_map(text: str, *, fallback_center: str, max_n: int = 9) -> dict:
    obj = _raw_object(text)
    center = str(obj.get("center", "")).strip() or fallback_center
    cats: list[dict] = []
    seen: set[str] = set()
    for c in obj.get("categories", []) or []:
        if isinstance(c, str):
            label = c.strip()
            cid = _slugify(label)
        elif isinstance(c, dict):
            label = str(c.get("label", "")).strip()
            cid = str(c.get("id", "")).strip() or _slugify(label)
        else:
            continue
        if not label or cid in seen:
            continue
        seen.add(cid)
        cats.append({"id": cid, "label": label})
    return {"center": center, "categories": cats[:max_n]}


def _coerce_sources(raw) -> list[dict]:
    out: list[dict] = []
    if not isinstance(raw, list):
        return out
    for s in raw:
        if not isinstance(s, dict):
            continue
        url = str(s.get("url", "")).strip()
        title = str(s.get("title", "")).strip()
        if not (url or title):
            continue
        out.append(
            {
                "title": title,
                "url": url,
                "source": str(s.get("source", "")).strip(),
                "date": str(s.get("date", "")).strip(),
            }
        )
    return out[:4]


def _coerce_subtopics(text: str, max_subtopics: int) -> list[dict]:
    out: list[dict] = []
    for it in _raw_objects(text) or []:
        if not isinstance(it, dict):
            continue
        title = str(it.get("title", "")).strip()
        if not title:
            continue
        out.append(
            {
                "title": title,
                "summary": str(it.get("summary", "")).strip(),
                "angle": str(it.get("angle", "")).strip(),
                "relevance": str(it.get("relevance", "")).strip().lower(),
                "sources": _coerce_sources(it.get("sources")),
            }
        )
    out.sort(key=lambda s: _RELEVANCE_RANK.get(s.get("relevance", ""), 0), reverse=True)
    return out[:max_subtopics]


async def scan_category(
    engine,
    tenant_id: str,
    brand_id: str,
    *,
    category: str,
    max_subtopics: int = 6,
) -> dict:
    """Web-research ONE category for the Scraper map; return subtopics + sources."""

    brand = engine.registry.get_brand(tenant_id, brand_id)
    layout = engine.layout

    news_cfg = getattr(brand, "news", None)
    focus = getattr(news_cfg, "focus", "") or ""
    exclude = list(getattr(news_cfg, "exclude", []) or [])
    preferred_sources = list(getattr(news_cfg, "preferred_sources", []) or [])
    lookback = getattr(news_cfg, "lookback_days", None) or 30

    strategy = load_strategy(layout, tenant_id, brand_id)
    strategy_block = format_strategy_for_filter(strategy)

    model = getattr(brand.models, "news", None) or brand.models.default or SONNET
    options = AgentRunOptions(
        system_prompt=TOPIC_SCAN_SYSTEM
        + ("\n\n## BRAND IDENTITY\n" + brand.identity if brand.identity else ""),
        cwd=layout.brand_dir(tenant_id, brand_id),
        add_dirs=[layout.shared_dir],
        allowed_roots=list(layout.allowed_roots(tenant_id, brand_id)),
        denied_roots=[layout.sources_dir(tenant_id, brand_id)],  # firewall stays on
        allowed_tools=["WebSearch", "WebFetch"],
        model=model,
    )
    prompt = build_topic_scan_prompt(
        brand_identity=brand.identity,
        strategy_block=strategy_block,
        category=category,
        focus=focus,
        exclude=exclude,
        preferred_sources=preferred_sources,
        lookback_days=lookback,
        max_subtopics=max_subtopics,
        today=_today(),
    )
    result = await engine.llm.run(prompt, options)
    return {
        "category": category,
        "subtopics": _coerce_subtopics(result.text, max_subtopics),
        "scanned": _now_iso(),
        "model": result.model,
        "usage": result.usage,
        "is_error": getattr(result, "is_error", False),
    }


async def derive_topic_map(
    engine,
    tenant_id: str,
    brand_id: str,
    *,
    min_n: int = 6,
    max_n: int = 9,
) -> dict:
    """Agnostic: infer the Scraper map (audience + topic categories) from the brand's
    OWN material — identity, strategy/objectives, and uploaded ``_kb/`` docs.

    Runs a read-only agent (Read/Grep/Glob over the brand subtree) so the map updates
    itself as the knowledge base changes. Returns ``{center, categories:[{id,label}]}``.
    """

    brand = engine.registry.get_brand(tenant_id, brand_id)
    layout = engine.layout

    news_cfg = getattr(brand, "news", None)
    focus = getattr(news_cfg, "focus", "") or ""
    exclude = list(getattr(news_cfg, "exclude", []) or [])

    strategy = load_strategy(layout, tenant_id, brand_id)
    strategy_block = format_strategy_for_filter(strategy)

    model = getattr(brand.models, "ideas", None) or brand.models.default or SONNET
    options = AgentRunOptions(
        system_prompt=TOPIC_MAP_SYSTEM
        + ("\n\n## BRAND IDENTITY\n" + brand.identity if brand.identity else ""),
        cwd=layout.brand_dir(tenant_id, brand_id),
        add_dirs=[layout.shared_dir],
        allowed_roots=list(layout.allowed_roots(tenant_id, brand_id)),
        denied_roots=[layout.sources_dir(tenant_id, brand_id)],  # firewall stays on
        allowed_tools=["Read", "Grep", "Glob"],  # read the brand's own KB + rules
        model=model,
    )
    prompt = build_topic_map_prompt(
        brand_identity=brand.identity,
        strategy_block=strategy_block,
        focus=focus,
        exclude=exclude,
        min_n=min_n,
        max_n=max_n,
    )
    result = await engine.llm.run(prompt, options)
    fallback_center = f"{brand.name} Users"
    coerced = _coerce_map(result.text, fallback_center=fallback_center, max_n=max_n)
    return {
        "center": coerced["center"],
        "categories": coerced["categories"],
        "derived": _now_iso(),
        "model": result.model,
        "usage": result.usage,
        "is_error": getattr(result, "is_error", False),
    }
