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


def extract_json_list(text: str) -> list[str]:
    """Robustly pull a JSON array of strings out of a model reply.

    Tolerates surrounding prose/markdown fences (so a preamble can't break it).
    Returns [] if no parseable array is found. Dicts in the array are flattened to
    their idea/brief/angle text.
    """

    import json

    if not text:
        return []
    start = text.find("[")
    if start < 0:
        return []
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(text[start : i + 1])
                except Exception:
                    return []
                if not isinstance(data, list):
                    return []
                out: list[str] = []
                for item in data:
                    if isinstance(item, str):
                        out.append(item.strip())
                    elif isinstance(item, dict):
                        out.append(
                            str(
                                item.get("idea")
                                or item.get("brief")
                                or item.get("angle")
                                or json.dumps(item)
                            ).strip()
                        )
                    else:
                        out.append(str(item).strip())
                return [o for o in out if o]
    return []


def extract_json_obj(text: str) -> dict:
    """Robustly pull the first JSON object out of a model reply (tolerates
    surrounding prose / markdown fences). Returns {} if none parses."""

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
                    return data if isinstance(data, dict) else {}
                except Exception:
                    return {}
    return {}


def clean_copy(text: str) -> str:
    """Strip AI-tell punctuation and tidy the spacing the swaps leave behind.

    Removes em/en dashes, semicolons, and spaced-hyphen clause breaks ("word - word"
    and "word -- word") — the marks cheaper models reach for once told to avoid em
    dashes. Real hyphens inside compounds (``well-made``, ``999.9-purity``) are kept:
    they have no surrounding spaces, so only a hyphen used as a clause break is hit.
    """

    if not text:
        return text
    t = text
    # Double hyphen used as an em-dash substitute -> comma.
    t = t.replace(" -- ", ", ").replace("--", ", ")
    # En dash: a range/compound joiner -> hyphen (e.g. "250–500" -> "250-500").
    t = t.replace(f" {EN_DASH} ", ", ").replace(EN_DASH, "-")
    # Em dash: a clause break -> comma (handles spaced and unspaced forms).
    t = t.replace(f" {EM_DASH} ", ", ").replace(EM_DASH, ", ")
    # Single hyphen flanked by spaces = a clause break, not a compound -> comma.
    t = re.sub(r" +- +", ", ", t)
    # Semicolon -> comma (an AI-tell in short marketing copy).
    t = t.replace(";", ",")
    # Tidy the punctuation the swaps can leave.
    t = re.sub(r"\s+([,.:!?])", r"\1", t)    # no space before punctuation
    t = re.sub(r",\s*,", ", ", t)              # collapse double commas
    t = re.sub(r",\s*\.", ".", t)              # ", ." -> "."
    t = re.sub(r"[ \t]{2,}", " ", t)           # collapse runs of spaces
    return t
