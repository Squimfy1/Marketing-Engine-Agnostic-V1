"""Prompt assembly — brand-parameterized, never hard-coded.

Hybrid context strategy (see plan): the small, stable *constitution* — engine
persona, tenant context, brand identity/voice, and the core-rules digest — is
inlined into the system prompt so the cached prefix stays stable. The full KB
and rule corpus are left for the agent to Read/Grep on demand at run time.
"""

from __future__ import annotations

ENGINE_PERSONA = """\
You are the Marketing Engine: a senior marketing copywriter and strategist that
produces on-brand content. You always honour the brand's voice and rules. When
you need facts, examples, or prior work, read the brand's _kb/ and _rules/
folders (use Grep/Read) before writing. Produce polished, ready-to-use copy —
no preamble, no meta-commentary."""

RUN_INSTRUCTIONS = """\
Work efficiently — you have a limited number of tool calls:
1. If you need facts, Glob/Grep the brand's _kb/ and read at most the 1–2 files
   directly relevant to this request. The WRITING RULES are already in your
   system prompt — follow them; don't re-read the rule files, don't run shell
   commands, and don't look outside this brand's folder.
2. If _kb/ doesn't have the facts you need, write the best on-brand piece you
   can from the request itself; only if that is impossible, state briefly in one
   line what source material is missing — do not keep searching.
3. Write the finished piece, then self-check it against the WRITING RULES and the
   banned-vocabulary/filler lists. For a short post, also enforce ONE IDEA PER
   SHORT POST: it must develop exactly one idea (not a mix), must NOT read as a
   feature/benefit dump, must connect clearly to the brand's CORE NARRATIVE, and
   must end on a single call to action. If any of these fail, name the rule it
   broke and rewrite before returning.
Return only the final copy in markdown — no preamble, no commentary, no notes
about what you read."""


def assemble_system_prompt(
    *,
    tenant_name: str,
    tenant_notes: str,
    brand_name: str,
    brand_identity: str,
    brand_voice: str,
    core_narrative: str = "",
    core_rules: str,
    writing_rules: str = "",
) -> str:
    """Compose the per-brand system prompt (the inlined constitution).

    Includes the shared anti-AI WRITING RULES so every generation obeys them —
    these are byte-stable across brands/runs, so they stay prompt-cache friendly.
    """

    parts = [ENGINE_PERSONA, ""]
    parts.append(f"Account: {tenant_name}")
    if tenant_notes.strip():
        parts.append(f"Account notes: {tenant_notes.strip()}")
    parts.append("")
    parts.append(f"Brand: {brand_name}")
    if brand_identity.strip():
        parts.append(f"Identity: {brand_identity.strip()}")
    if brand_voice.strip():
        parts.append(f"Voice: {brand_voice.strip()}")
    if core_narrative.strip():
        parts.append("")
        parts.append("## CORE NARRATIVE")
        parts.append("Every short post is ONE angle or proof point on this. Connect back to it.")
        parts.append(core_narrative.strip())
    if core_rules.strip():
        parts.append("")
        parts.append("## CORE RULES (brand)")
        parts.append(core_rules.strip())
    if writing_rules.strip():
        parts.append("")
        parts.append("## WRITING RULES — apply to EVERYTHING you write")
        parts.append(
            "These are mandatory. Obey the banned-vocabulary and filler lists, "
            "the sentence rules, and the structure guidance below in every draft "
            "and every option. Do not produce AI-tell phrasing."
        )
        parts.append("")
        parts.append(writing_rules.strip())
    return "\n".join(parts).strip()


OPTIONS_INSTRUCTIONS = """\
Propose exactly {n} DISTINCT short-post IDEAS — NOT full posts. Each idea is one
short angle/headline plus 1–2 sentences on what the post would say and why it fits
the brand. Take DIFFERENT angles, each a proof point or angle on the brand's CORE
NARRATIVE (a product explainer, an analytical insight, a reaction to relevant news,
a concrete use-case, etc.).

Ground them in the brand identity, voice, narrative, and rules already in your
system prompt. Keep each idea to 1–2 sentences (do NOT write the full post). Obey
the WRITING RULES and Guardrails; do not invent facts.

Return ONLY a JSON array of exactly {n} strings — each string is one idea (its
angle and 1–2 sentence brief). No prose before or after, no markdown fences.
Example: ["The quiet-erosion angle: open with ... and tie it to ...", "..."]"""


IMAGE_BRIEF_INSTRUCTIONS = """\
Write concise image-generation instructions (a visual brief) for an image to
accompany the post below. Cover: subject/scene, composition, art style, mood,
colour palette, and any short text overlay. Keep it on-brand and ready to paste
into an image tool. Output ONLY the brief — no preamble, no commentary."""


# Image SOURCE kinds the recommender chooses between. All are produced via Claude
# Code; they differ in where the raw image comes from.
IMAGE_KINDS = {
    "library": "pick an existing image from the brand's image library",
    "real_photo": "a real photograph to source online and bring into Claude Design",
    "generated": "generate the image from scratch in Claude Design",
}

IMAGE_RECOMMEND_SYSTEM = (
    "You are an art director for a brand. Given a finished post, you recommend how "
    "to illustrate it and offer a few concrete options to choose from. You return "
    "ONLY JSON."
)

IMAGE_RECOMMEND_INSTRUCTIONS = """\
Recommend how to illustrate the post above. Choose the image SOURCE per option:
- "library": pick an existing image from the brand's image library
- "real_photo": a real photograph to source online and bring into Claude Design
- "generated": generate the image from scratch in Claude Design
Let the content decide (e.g. a product explainer often suits a generated diagram;
a news reaction often suits a real photo).

Return ONLY a JSON object:
{
  "recommendation": "one sentence on the best overall approach and why",
  "options": [
    {"kind": "library|real_photo|generated",
     "direction": "a short concrete visual direction (subject/scene + feel)",
     "rationale": "one short clause on why it fits this post"}
  ]
}
Give 3 DISTINCT options. Keep everything on-brand. No prose outside the JSON."""


def build_image_recommend_prompt(post_text: str, *, design_tokens: str = "") -> str:
    """Prompt to recommend image approaches + concrete options for a post."""

    parts = ["## POST", post_text.strip()]
    if design_tokens.strip():
        parts += ["", "## BRAND DESIGN TOKENS", design_tokens.strip()]
    parts += ["", IMAGE_RECOMMEND_INSTRUCTIONS]
    return "\n".join(parts)


VALIDATE_SYSTEM = (
    "You are a strict but fair brand editor. You check a short post against the rules "
    "and return a JSON verdict. You do not rewrite it."
)

VALIDATE_INSTRUCTIONS = """\
Check the short post below. Return ONLY a JSON object:
{"pass": true or false, "rule": "the rule it breaks, or empty", "reason": "one short sentence"}

FAIL it if ANY is true:
- It develops more than one competing idea, or reads as a feature/benefit list.
- It does not clearly connect to the CORE NARRATIVE.
- It uses crypto framing, or promises returns / price gains / specific pricing.
- It does not end with a single clear call to action.
Otherwise pass it. No prose outside the JSON."""


def build_validate_prompt(post_text: str, core_narrative: str) -> str:
    """Prompt for the cheap reliability gate (Haiku verdict on a short post)."""

    parts = []
    if core_narrative.strip():
        parts += ["## CORE NARRATIVE", core_narrative.strip(), ""]
    parts += ["## POST", post_text.strip(), "", VALIDATE_INSTRUCTIONS]
    return "\n".join(parts)


DISTILL_SYSTEM = (
    "You are a precise brand strategist. You distill a company's strategy from raw "
    "call transcripts into a reusable, PUBLIC-SAFE content profile. You separate the "
    "durable strategy from the chatter, and you never include confidential internal "
    "material."
)

# The distiller fills a FIXED set of sections for every brand. Three of them
# (business_principles / customer_personas / customer_narratives) come straight
# from the universal STRATEGY_SECTIONS schema so the distiller and the filter
# stay in lockstep; the prompt below is generated, never hand-listed.
from marketing_engine.content.strategy import STRATEGY_SECTIONS  # noqa: E402


def _strategy_schema_lines() -> str:
    return "\n".join(
        f'  "{sec.key}": ["{sec.instruction} — 3-6 items"],' for sec in STRATEGY_SECTIONS
    )


DISTILL_INSTRUCTIONS = f"""\
Read the transcripts above and extract the durable strategy. Fill EVERY section
below; if a section is not stated outright, infer the most reasonable version
from context and never leave one empty.
Return ONLY a JSON object with this exact shape:
{{
  "core_narrative": "1-2 sentence central thesis the brand keeps returning to",
{_strategy_schema_lines()}
  "key_ideas": ["the most important recurring narratives or angles, ranked, 6-10 items"],
  "trajectory": "1-2 sentences on where the company is heading / current priorities",
  "proof_points": ["public-safe, citable facts the content can use, 5-10 items"],
  "avoid": ["positioning guardrails / things to never say that surfaced in the calls"]
}}

CRITICAL — public-safe only. EXCLUDE all confidential internal material: people's
names, org/HR changes, ownership, financials, fundraising, pricing or fees, roadmap
or launch dates, partner/supplier names, internal metrics, customer counts or
targets. If publishing something would embarrass the company, leave it out. No
prose outside the JSON, no markdown fences."""


def build_distill_prompt(sources_text: str) -> str:
    """Prompt to distill a public-safe narrative profile from raw transcripts."""

    return "## TRANSCRIPTS\n" + sources_text.strip() + "\n\n" + DISTILL_INSTRUCTIONS


FILTER_SYSTEM = (
    "You are a sharp brand strategist running a tight relevance filter. For each "
    "candidate post idea you judge whether it advances the brand's strategy — tying a "
    "real BUSINESS PRINCIPLE to a real CUSTOMER NARRATIVE for a known PERSONA — and "
    "you return ONLY JSON. You never rewrite the ideas."
)

FILTER_INSTRUCTIONS = """\
For EACH numbered idea, return one JSON object. Return ONLY a JSON array, in order:
[{"i": 1, "keep": true, "principle": "the business principle it advances, or empty",
  "persona": "the persona it speaks to, or empty",
  "narrative": "the customer narrative it taps, or empty",
  "reason": "one short sentence"}]

KEEP an idea (keep=true) ONLY if it clearly connects at least one BUSINESS
PRINCIPLE to at least one CUSTOMER NARRATIVE. Drop (keep=false) anything generic,
off-strategy, a pure feature dump, or that no real customer would feel. Quote the
principle/persona/narrative using the wording from the strategy above. No prose
outside the JSON, no markdown fences."""


def build_filter_prompt(ideas: list[str], strategy_block: str) -> str:
    """Prompt for the cheap strategy filter: score N ideas against the strategy."""

    numbered = "\n".join(f"{i + 1}. {idea.strip()}" for i, idea in enumerate(ideas))
    parts = ["## BRAND STRATEGY", strategy_block.strip(), "", "## CANDIDATE IDEAS", numbered, "", FILTER_INSTRUCTIONS]
    return "\n".join(parts)


SCRAPE_SYSTEM = (
    "You are a news scout for a brand. You search the web for RECENT, genuinely "
    "relevant news in the brand's market and for its customers, then return a tight, "
    "relevance-filtered, PUBLIC-SAFE digest as JSON. You judge relevance through the "
    "brand's strategy: a story matters only if it advances a BUSINESS PRINCIPLE or "
    "speaks to a CUSTOMER NARRATIVE. You never invent stories or URLs."
)

SCRAPE_INSTRUCTIONS = """\
Find recent news (within the lookback window) relevant to THIS brand's market and
customers. Use WebSearch to find stories and WebFetch to confirm details. Derive
your own searches from the brand's identity + strategy above; the seed queries (if
any) are only a starting point — branch out to the topics the customers actually
care about.

For each story, judge relevance through the strategy: keep it ONLY if it advances a
BUSINESS PRINCIPLE or speaks to a CUSTOMER NARRATIVE. Drop promotional fluff,
pure competitor PR, anything off-topic, and anything you cannot verify.

Return ONLY a JSON array, best first, at most {max_items} items:
[{{"title": "headline", "url": "source url", "source": "publication",
   "date": "YYYY-MM-DD or best estimate", "summary": "2-3 factual sentences",
   "principle": "the business principle it advances, or empty",
   "narrative": "the customer narrative it taps, or empty",
   "angle": "one line: how a post could use this, tied to the brand",
   "relevance": "high|medium|low"}}]

Public-safe and factual only. No prose outside the JSON, no markdown fences."""


def build_scrape_prompt(
    *,
    brand_identity: str,
    strategy_block: str,
    queries: list[str],
    max_items: int,
    today: str,
    lookback_days: int,
) -> str:
    parts = ["## BRAND", brand_identity.strip()]
    if strategy_block.strip():
        parts += ["", "## BRAND STRATEGY", strategy_block.strip()]
    parts += ["", f"## TODAY\n{today} — only keep news from the last {lookback_days} days."]
    if queries:
        parts += ["", "## SEED QUERIES", "\n".join(f"- {q}" for q in queries)]
    parts += ["", SCRAPE_INSTRUCTIONS.format(max_items=max_items)]
    return "\n".join(parts)


def build_image_brief_prompt(
    post_text: str, *, design_tokens: str = "", kind: str = "", direction: str = ""
) -> str:
    """Prompt for an image/visual brief for a finished post.

    When the operator has already picked an option (``kind`` + ``direction``), the
    brief is written FOR that choice (e.g. instructions to source a real photo vs.
    generate one); otherwise it's a generic brief.
    """

    parts = ["## POST", post_text.strip()]
    if design_tokens.strip():
        parts += ["", "## BRAND DESIGN TOKENS", design_tokens.strip()]
    if kind or direction:
        chosen = ["", "## CHOSEN OPTION"]
        if kind:
            chosen.append(f"Source: {kind} — {IMAGE_KINDS.get(kind, kind)}")
        if direction:
            chosen.append(f"Direction: {direction.strip()}")
        chosen.append(
            "Write the instructions FOR this chosen source and direction"
            + (
                " — describe the exact photo to find and how to adapt it"
                if kind == "real_photo"
                else " — describe the image to pick from the library"
                if kind == "library"
                else " — describe the image to generate"
            )
            + "."
        )
        parts += chosen
    parts += ["", IMAGE_BRIEF_INSTRUCTIONS]
    return "\n".join(parts)


def build_options_prompt(
    input_text: str,
    *,
    n: int = 4,
    platform_label: str | None = None,
    platform_guidance: str = "",
    news_headlines: list[str] | None = None,
) -> str:
    """Prompt for generating N distinct post options in one call.

    When recent ``news_headlines`` are supplied, the model is nudged to make some
    ideas news-reactive (the Product/News axis) while staying on-brand.
    """

    parts = ["## REQUEST", input_text.strip()]
    if platform_label:
        parts += ["", f"## PLATFORM\n{platform_label}"]
    if platform_guidance.strip():
        parts += ["", "## PLATFORM GUIDANCE", platform_guidance.strip()]
    if news_headlines:
        parts += [
            "",
            "## RECENT RELEVANT NEWS (for news-reactive angles — optional, only if it fits)",
            "\n".join(f"- {h}" for h in news_headlines),
        ]
    parts += ["", OPTIONS_INSTRUCTIONS.format(n=n)]
    return "\n".join(parts)


def build_run_prompt(
    input_text: str,
    *,
    platform_label: str | None = None,
    platform_guidance: str = "",
) -> str:
    """The user-turn prompt carrying the operator's request.

    Optionally folds in the target platform's format guidance (Short posts /
    Articles) so the draft matches the format without bloating the cached system
    prompt.
    """

    parts = ["## INPUT", input_text.strip()]
    if platform_label:
        parts += ["", f"## PLATFORM\n{platform_label}"]
    if platform_guidance.strip():
        parts += ["", "## PLATFORM GUIDANCE", platform_guidance.strip()]
    parts += ["", RUN_INSTRUCTIONS]
    return "\n".join(parts)
