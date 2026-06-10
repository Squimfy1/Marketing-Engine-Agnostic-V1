"""Per-tenant configuration (``tenant.yaml``).

A tenant is an account: an agency (many client brands) or a single company
(one brand). Auth/billing live here eventually; Milestone 1 keeps it minimal —
just enough to carry account-wide defaults that brands inherit.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TenantConfig(BaseModel):
    """Parsed ``tenant.yaml``. ``id`` is derived from the folder name."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    plan: str = Field(default="self-hosted", description="Billing plan (informational for now).")
    default_model: str | None = Field(
        default=None,
        description="Account-wide model default; a brand's own model policy overrides this.",
    )
    notes: str = Field(default="", description="Free-text account notes injected as context.")
