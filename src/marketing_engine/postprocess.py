"""Deterministic copy cleanup applied to every generated output.

The model is told to follow the writing rules, but mechanical AI-tells (em
dashes especially) slip through, particularly on cheaper models. This pass
guarantees them gone regardless of which model ran — a formatting backstop, not
a substitute for the rules in the system prompt.
"""

from __future__ import annotations

import re

EM_DASH = "—"  # —
EN_DASH = "–"  # –


def clean_copy(text: str) -> str:
    """Remove em/en-dash AI-tells and tidy the spacing they leave behind."""

    if not text:
        return text
    t = text
    # En dash: a range/compound joiner -> hyphen (e.g. "250–500" -> "250-500").
    t = t.replace(f" {EN_DASH} ", ", ").replace(EN_DASH, "-")
    # Em dash: a clause break -> comma (handles spaced and unspaced forms).
    t = t.replace(f" {EM_DASH} ", ", ").replace(EM_DASH, ", ")
    # Tidy the punctuation the swaps can leave.
    t = re.sub(r"\s+([,.;:!?])", r"\1", t)   # no space before punctuation
    t = re.sub(r",\s*,", ", ", t)              # collapse double commas
    t = re.sub(r",\s*\.", ".", t)              # ", ." -> "."
    t = re.sub(r"[ \t]{2,}", " ", t)           # collapse runs of spaces
    return t
