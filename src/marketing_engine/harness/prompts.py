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
THE OPERATOR'S REQUEST IS THE BRIEF — it takes priority. Write the specific post
they asked for: honour the angle, audience, topic, and focus they named, even when
that differs from the brand's default CORE NARRATIVE. Do NOT swap their idea for a
safer or more familiar brand message. The brand voice, rules, and guardrails still
apply; the core narrative is only the fallback angle when the request doesn't
specify one.

Work efficiently — you have a limited number of tool calls:
1. If the request points you to specific source material (e.g. "look at the
   litepaper"), READ it first. Otherwise, if you need facts, Glob/Grep the brand's
   _kb/ and read the 1–2 files directly relevant to this request. The WRITING
   RULES are already in your system prompt — follow them; don't re-read the rule
   files, don't run shell commands, and don't read outside this brand's folder.
2. RESEARCH: when the request asks you to research, or needs current/external facts
   (recent news, prices, events, third-party context), use WebSearch to find them
   and WebFetch to confirm details from the source. Check _kb/ first; go to the web
   for what isn't there. Use only facts you can verify, attribute claims fairly, and
   keep everything public-safe — never state confidential or unverifiable specifics.
   If a needed fact can't be found, say so in one line rather than inventing it.
3. Write the finished piece, then self-check it. For a short post, enforce ONE
   IDEA PER SHORT POST: it must develop exactly the ONE idea the operator asked
   for (not a mix, and not replaced by a different brand message), must NOT read
   as a feature/benefit dump, and must end on a single call to action. Obey the
   WRITING RULES and the banned-vocabulary/filler lists. If any of these fail,
   name the rule it broke and rewrite before returning.
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

    # The priority hierarchy frames everything below it. Without this, the brand's
    # own rules ("lead with X", the core-narrative emphasis) dominate and every post
    # collapses to the same default story even when the operator asked for a
    # different, specific angle.
    parts.append("## HOW TO PRIORITISE")
    parts.append(
        "1. The operator's REQUEST sets the TOPIC and ANGLE of the post. If it names "
        "a subject, the post is ABOUT that subject, even when that is not the brand's "
        "usual focus. Develop exactly what was asked; never substitute a more familiar "
        "brand message.\n"
        "2. ALWAYS apply, whatever the request: the brand VOICE and tone, the GUARDRAILS "
        "and compliance limits, the WRITING RULES, ONE idea per short post, and a single "
        "call to action.\n"
        "3. DEFAULT-ANGLE guidance ONLY — the CORE NARRATIVE, any \"lead with X\" "
        "positioning, and the key-ideas / angle menus in the brand rules — applies when "
        "the request does NOT specify an angle. A specific request OVERRIDES it. Relate "
        "the requested topic to the brand where it fits naturally; do not force the "
        "default story, and feel free to branch into adjacent territory the request "
        "calls for (legal structure, a news reaction, an investor angle, etc.)."
    )

    parts.append("")
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
        parts.append("## CORE NARRATIVE (default angle — overridden by a specific request; see HOW TO PRIORITISE)")
        parts.append(core_narrative.strip())
    if core_rules.strip():
        parts.append("")
        parts.append("## BRAND RULES")
        parts.append(
            "VOICE and GUARDRAILS below ALWAYS apply. Any angle/positioning guidance "
            "(e.g. \"lead with X\", the key-ideas menu) is DEFAULT-ONLY and yields to a "
            "specific operator request per HOW TO PRIORITISE."
        )
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
First, in one line, state the post's CORE IDEA (the single message a reader takes
away). Then write concise image-generation instructions for an image that
ILLUSTRATES THAT IDEA — the post and the image must read as one piece. Draw the
subject/scene from what the post actually talks about; do NOT default to a bare
logo, brand mark, or generic abstract motif unless the post is literally about the
brand's identity. Cover: subject/scene (grounded in the post), composition, art
style, mood, colour palette, and any short text overlay (pull wording from the
post if used). Keep it on-brand and ready to paste into an image tool. Output ONLY
the one-line core idea followed by the brief — no other preamble or commentary."""


# Image SOURCE kinds the recommender chooses between. All are produced via Claude
# Code; they differ in where the raw image comes from. Each must depict THIS post.
IMAGE_KINDS = {
    "library": "an existing image from the brand's library that depicts THIS post's idea",
    "real_photo": "a real photograph (sourced online) that depicts THIS post's idea",
    "generated": "an image generated from scratch that illustrates THIS post's idea",
}

IMAGE_RECOMMEND_SYSTEM = (
    "You are an art director for a brand. Given a finished post, you recommend how "
    "to illustrate ITS SPECIFIC IDEA and offer concrete options to choose from. "
    "Every option must visually express what the post is actually about — never a "
    "generic logo or brand mark unless the post is about the brand identity itself. "
    "You return ONLY JSON."
)

IMAGE_RECOMMEND_INSTRUCTIONS = """\
Identify the post's CORE IDEA, then recommend how to illustrate THAT idea. Every
option's `direction` must describe a subject/scene a reader of THIS post would
recognise as illustrating it — do NOT fall back to a bare logo, brand mark, or
generic brand motif unless the post is literally about the brand's identity.

Choose the image SOURCE per option:
- "library": an existing image from the brand's library that fits this post's idea
- "real_photo": a real photograph (sourced online) that depicts this post's idea
- "generated": an image generated from scratch that illustrates this post's idea
Let the content decide (e.g. a product explainer often suits a generated diagram;
a news reaction often suits a real photo).

Return ONLY a JSON object:
{
  "core_idea": "one line: the single message this post conveys",
  "recommendation": "one sentence on the best overall approach and why",
  "options": [
    {"kind": "library|real_photo|generated",
     "direction": "a concrete subject/scene that illustrates the post's idea + the feel",
     "rationale": "one short clause on how it connects to THIS post"}
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
- A REQUEST is given and the post ignores it — wrong angle/topic/audience, or it
  drifts to a different (e.g. the brand's default) message instead of the one asked for.
- It uses crypto framing, or promises returns / price gains / specific pricing.
- It does not end with a single clear call to action.
Do NOT fail a post merely for differing from the CORE NARRATIVE when the REQUEST
asked for a specific angle — answering the request is what matters. The core
narrative is only the expected angle when no REQUEST is given.
Otherwise pass it. No prose outside the JSON."""


def build_validate_prompt(post_text: str, core_narrative: str, request: str = "") -> str:
    """Prompt for the cheap reliability gate (Haiku verdict on a short post).

    The operator's ``request`` (when present) is the primary thing the post must
    satisfy; the core narrative is only the default-angle reference."""

    parts = []
    if request.strip():
        parts += ["## REQUEST (what the operator asked for — this is the brief)", request.strip(), ""]
    if core_narrative.strip():
        parts += ["## CORE NARRATIVE (brand default angle, only if no REQUEST)", core_narrative.strip(), ""]
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

PRIORITISE the brand's TARGET MARKET and GEOGRAPHY as stated in its identity and
personas (e.g. a brand for Swiss families should weight Swiss/Switzerland-specific
news, local sources, and the region's cost-of-living/regulatory context over
generic global coverage). Prefer local-market stories a real customer there would
actually see.

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

    parts = ["## POST (the image must illustrate THIS post's idea)", post_text.strip()]
    if design_tokens.strip():
        parts += ["", "## BRAND DESIGN TOKENS", design_tokens.strip()]
    if kind or direction:
        chosen = ["", "## CHOSEN OPTION"]
        if kind:
            chosen.append(f"Source: {kind} — {IMAGE_KINDS.get(kind, kind)}")
        if direction:
            chosen.append(f"Direction: {direction.strip()}")
        chosen.append(
            "Write the instructions FOR this chosen source and direction, and keep "
            "them anchored to the post's core idea above"
            + (
                " — describe the exact photo to find (its subject/scene tied to the post) "
                "and how to adapt it"
                if kind == "real_photo"
                else " — describe which library image to pick and why it fits the post; "
                "if only a logo/brand mark is available, still tie its use to the post's idea"
                if kind == "library"
                else " — describe the image to generate, depicting the post's idea"
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
