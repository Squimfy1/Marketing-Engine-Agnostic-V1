"""Claude model identifiers and per-task model selection.

Latest model IDs (verified against current docs):
  * Opus 4.8   -> claude-opus-4-8     (default; strongest)
  * Sonnet 4.6 -> claude-sonnet-4-6   (balanced)
  * Haiku 4.5  -> claude-haiku-4-5-20251001  (fast/cheap)
"""

from __future__ import annotations

OPUS = "claude-opus-4-8"
SONNET = "claude-sonnet-4-6"
HAIKU = "claude-haiku-4-5-20251001"

DEFAULT_MODEL = OPUS

# Tasks the harness will eventually route to different tiers (M3). Kept here so
# the policy lives in one place.
KNOWN_TASKS = ("default", "ideas", "editor", "image_brief")


def resolve_model(
    task: str,
    *,
    brand_models: dict[str, str | None] | None = None,
    tenant_default: str | None = None,
    settings_default: str | None = None,
) -> str:
    """Pick a model for ``task``, most specific wins.

    brand task policy > brand default > tenant default > settings default > OPUS.
    """

    brand_models = brand_models or {}
    candidates = [
        brand_models.get(task),
        brand_models.get("default"),
        tenant_default,
        settings_default,
        DEFAULT_MODEL,
    ]
    for c in candidates:
        if c:
            return c
    return DEFAULT_MODEL
