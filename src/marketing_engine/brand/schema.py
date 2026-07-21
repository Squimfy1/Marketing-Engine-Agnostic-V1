"""Per-brand configuration (``brand.yaml``).

A brand is fully self-describing: identity, voice, the model it should use, and
where its design tokens live. The engine code never hard-codes any of this — add
a brand by adding a folder with a valid ``brand.yaml``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModelPolicy(BaseModel):
    """Which model to use, per task. Milestone 1 only uses ``default``."""

    model_config = ConfigDict(extra="forbid")

    default: str | None = None
    ideas: str | None = None
    editor: str | None = None
    image_brief: str | None = None
    news: str | None = None  # the news scraper (web research + summarise)


class NewsPolicy(BaseModel):
    """Optional news-scraper config. All fields optional — if ``queries`` is empty
    the scraper derives its own searches from the brand identity + strategy, so a
    brand needs no news config to work (fully agnostic)."""

    model_config = ConfigDict(extra="forbid")

    queries: list[str] = Field(
        default_factory=list,
        description="Legacy flat seed queries. Prefer ``topics`` (the categorised matrix). "
        "Empty = let the engine derive searches from the brand.",
    )
    topics: dict[str, dict[str, list[str]]] = Field(
        default_factory=dict,
        description="The query MATRIX: category -> language ('de'|'fr'|'it'|'en'|'any') -> "
        "list of queries. Coverage becomes a property of this taxonomy, scanned across every "
        "configured locale, so gaps (a topic with no queries in a language) are auditable.",
    )
    locales: list[str] = Field(
        default_factory=list,
        description="Google News locales to scan, e.g. ['de-CH','fr-CH','it-CH','en']. Empty "
        "= the default trilingual Swiss + English set. Switzerland is multilingual, so scan all.",
    )
    feeds: list[dict] = Field(
        default_factory=list,
        description="Optional direct RSS feeds (primary sources / outlet sections) pulled every "
        "run regardless of query, e.g. [{'url': '...', 'source': 'SNB', 'category': '...'}].",
    )
    focus: str = Field(
        default="",
        description="One line: what kind of news to prioritise (the audience reality to "
        "weight). Steers both the scout's own searches and what it keeps.",
    )
    exclude: list[str] = Field(
        default_factory=list,
        description="Hard exclusions — topic classes to drop even if otherwise on-brand "
        "(e.g. 'global macro / central-bank reserves', 'price forecasts'). The scout must "
        "not return a story that is primarily about any of these.",
    )
    preferred_sources: list[str] = Field(
        default_factory=list,
        description="Trusted outlets to weight first (e.g. national + local papers, "
        "official statistics). The scout still searches the open web, but prefers these "
        "and the kind of local/national coverage they represent.",
    )
    lookback_days: int = Field(default=30, description="Only keep news newer than this.")
    max_items: int = Field(default=8, description="Max news items to keep per scrape.")
    verify: bool = Field(
        default=True,
        description="Run the adversarial fact-check pass after the scout selects items: "
        "re-open each cited source, confirm it exists and actually supports the claim, "
        "and drop anything hallucinated, misquoted, stale, or unverifiable.",
    )
    reputable_only: bool = Field(
        default=True,
        description="During verification, keep only items from a reputable, identifiable "
        "outlet (established news orgs, primary institutions, recognised research houses) "
        "— drops blogs, forums, content farms, PR wires, and anonymous sources. Requires "
        "``verify`` to be on.",
    )


class BrandConfig(BaseModel):
    """Parsed ``brand.yaml``. ``id`` is derived from the folder name."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    identity: str = Field(
        default="",
        description="Who the brand is — one paragraph of positioning/personality.",
    )
    voice: str = Field(
        default="",
        description="Tone-of-voice guidance applied to every piece of copy.",
    )
    narrative: str = Field(
        default="",
        description="The brand's core narrative / central thesis. Each short post is "
        "one angle or proof point on it. Falls back to identity if unset; usually "
        "populated by the narrative-distillation step from the client's call sources.",
    )
    models: ModelPolicy = Field(default_factory=ModelPolicy)
    news: NewsPolicy = Field(default_factory=NewsPolicy)
    design_tokens: str = Field(
        default="_design/tokens.yaml",
        description="Path (relative to the brand folder) to design tokens.",
    )
