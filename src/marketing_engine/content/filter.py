"""The strategy filter — a cheap, tight gate between ideas and the post.

It replaces a heavy multi-agent prosecutor chain with ONE Haiku call that scores
every candidate idea against the brand's distilled strategy: does it tie a real
BUSINESS PRINCIPLE to a real CUSTOMER NARRATIVE for a known PERSONA? Ideas that
do not link strategy to a felt customer story are dropped; the survivors carry
their principle/narrative tags so the dashboard can show *why* each made it.

Agnostic by construction: this module references only the section *names* from
``content.strategy`` (business_principles, customer_personas, customer_narratives)
— never any brand. A client works because its strategy.md is filled in; any
other company works the same way once theirs is.

Fails OPEN: if there is no distilled strategy yet, or the verdict can't be parsed,
every idea is kept (untagged) so the filter never silently empties the slate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from marketing_engine.content.postprocess import extract_json_list
from marketing_engine.content.strategy import (
    format_strategy_for_filter,
    has_filter_dimensions,
)
from marketing_engine.harness.prompts import FILTER_SYSTEM, build_filter_prompt
from marketing_engine.sdk.client import AgentRunOptions
from marketing_engine.sdk.models import HAIKU


@dataclass
class FilteredIdea:
    text: str
    keep: bool = True
    principle: str = ""
    persona: str = ""
    narrative: str = ""
    reason: str = ""
    filtered: bool = False  # True only if the strategy filter actually ran on it

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "keep": self.keep,
            "principle": self.principle,
            "persona": self.persona,
            "narrative": self.narrative,
            "reason": self.reason,
            "filtered": self.filtered,
        }


@dataclass
class FilterOutcome:
    ideas: list[FilteredIdea] = field(default_factory=list)
    ran: bool = False  # did the filter call actually happen?
    model: str | None = None
    usage: dict = field(default_factory=dict)


def _passthrough(ideas: list[str]) -> list[FilteredIdea]:
    return [FilteredIdea(text=i, keep=True, filtered=False) for i in ideas]


async def filter_ideas(
    engine,
    *,
    tenant_id: str,
    brand_id: str,
    ideas: list[str],
    cwd=None,
) -> FilterOutcome:
    """Score ``ideas`` against the brand's strategy. One Haiku call, no tools.

    Returns a :class:`FilterOutcome` whose ``ideas`` align 1:1 with the input
    order. If there is no usable strategy, returns all ideas as kept passthroughs.
    """

    ideas = [i for i in (ideas or []) if i and i.strip()]
    if not ideas:
        return FilterOutcome(ideas=[], ran=False)

    from marketing_engine.content.strategy import load_strategy

    strategy = load_strategy(engine.layout, tenant_id, brand_id)
    if not has_filter_dimensions(strategy):
        # No distilled principles/narratives yet — keep everything, unfiltered.
        return FilterOutcome(ideas=_passthrough(ideas), ran=False)

    options = AgentRunOptions(
        system_prompt=FILTER_SYSTEM,
        cwd=cwd or engine.layout.brand_dir(tenant_id, brand_id),
        allowed_tools=[],  # everything it needs is inlined
        model=HAIKU,
    )
    prompt = build_filter_prompt(ideas, format_strategy_for_filter(strategy))
    try:
        result = await engine.llm.run(prompt, options)
    except Exception:
        return FilterOutcome(ideas=_passthrough(ideas), ran=False)

    verdicts = _parse_verdicts(result.text)
    if not verdicts:
        return FilterOutcome(ideas=_passthrough(ideas), ran=False, model=result.model)

    out: list[FilteredIdea] = []
    for i, idea in enumerate(ideas):
        v = verdicts.get(i, {})
        out.append(
            FilteredIdea(
                text=idea,
                keep=bool(v.get("keep", True)),
                principle=str(v.get("principle", "")).strip(),
                persona=str(v.get("persona", "")).strip(),
                narrative=str(v.get("narrative", "")).strip(),
                reason=str(v.get("reason", "")).strip(),
                filtered=True,
            )
        )
    return FilterOutcome(ideas=out, ran=True, model=result.model, usage=result.usage)


def select(outcome: FilterOutcome, n: int) -> list[FilteredIdea]:
    """Pick the ideas to surface: kept ones first (in order), then backfill with
    the rest so we always return up to ``n`` cards even if the filter was harsh."""

    kept = [i for i in outcome.ideas if i.keep]
    dropped = [i for i in outcome.ideas if not i.keep]
    return (kept + dropped)[:n]


def _parse_verdicts(text: str) -> dict[int, dict]:
    """Parse the filter's JSON array into ``{idx0: verdict}`` keyed by 0-based
    idea index. Tolerates objects keyed by 1-based ``i`` or plain array order."""

    import json

    if not text:
        return {}
    start = text.find("[")
    if start < 0:
        return {}
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
                    return {}
                if not isinstance(data, list):
                    return {}
                out: dict[int, dict] = {}
                for pos, item in enumerate(data):
                    if not isinstance(item, dict):
                        continue
                    idx = item.get("i")
                    key = (int(idx) - 1) if isinstance(idx, (int, float)) else pos
                    out[key] = item
                return out
    return {}
