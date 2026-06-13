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
        description="Seed search queries. Empty = let the engine derive them from the brand.",
    )
    lookback_days: int = Field(default=30, description="Only keep news newer than this.")
    max_items: int = Field(default=8, description="Max news items to keep per scrape.")


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
