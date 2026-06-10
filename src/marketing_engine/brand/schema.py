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
    models: ModelPolicy = Field(default_factory=ModelPolicy)
    design_tokens: str = Field(
        default="_design/tokens.yaml",
        description="Path (relative to the brand folder) to design tokens.",
    )
