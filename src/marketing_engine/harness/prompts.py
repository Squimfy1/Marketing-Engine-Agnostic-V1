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
            "and every option. Do not produce AI-tell phrasing. "
            "PUNCTUATION: never use em dashes, en dashes, or semicolons, and never "
            "use a hyphen as a clause break (' - '). Use commas or separate sentences "
            "instead. Hyphens are allowed only inside compound words (e.g. well-made)."
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


# The single hard rule shared by every image step: depict the post, never the logo.
IMAGE_HARD_RULE = (
    "HARD RULE: the image's MAIN SUBJECT must be the specific idea/scene of THIS post. "
    "A logo, wordmark, brand mark, or generic brand/abstract motif is NEVER the main "
    "image (it may appear only as a small optional corner watermark). If you cannot "
    "picture a concrete scene for the post, describe the closest literal depiction of "
    "what the post talks about — never substitute a brand mark."
)

IMAGE_BRIEF_INSTRUCTIONS = (
    """\
First, in one line, state the post's CORE IDEA (the single message a reader takes
away) and the concrete SUBJECT/SCENE that depicts it. Then write concise
image-generation instructions for an image that ILLUSTRATES THAT SUBJECT — the post
and the image must read as one piece. """
    + IMAGE_HARD_RULE
    + """ Cover: subject/scene (grounded in the post), composition, art style, mood,
colour palette, and any short text overlay (pull wording from the post if used).
If a ## POST IMAGE LAYOUT is given, the brief MUST follow that composition exactly:
say what fills the photo area (for a 'library' pick, name the uploaded template image
to drop in), give the EXACT short headline text for the panel (pulled from the post),
and list the company details, using the brand colours/fonts from the tokens.
Keep it on-brand and ready to paste into an image tool. Output ONLY the one-line
core idea + subject followed by the brief — no other preamble or commentary."""
)


# Image SOURCE kinds the recommender chooses between. All are produced via Claude
# Code; they differ in where the raw image comes from. Each must depict THIS post —
# and per IMAGE_HARD_RULE none may be the logo/brand mark.
IMAGE_KINDS = {
    "library": "an existing on-brand IMAGE (photo or graphic, NOT the logo/wordmark) that depicts THIS post's idea",
    "real_photo": "a real photograph (sourced online) that depicts THIS post's idea",
    "generated": "an image generated from scratch that illustrates THIS post's idea",
}

IMAGE_RECOMMEND_SYSTEM = (
    "You are an art director for a brand. Given a finished post, you recommend how "
    "to illustrate ITS SPECIFIC IDEA and offer concrete options to choose from. "
    + IMAGE_HARD_RULE
    + " You return ONLY JSON."
)

IMAGE_RECOMMEND_INSTRUCTIONS = """\
Identify the post's CORE IDEA, then recommend how to illustrate THAT idea. Every
option's `direction` must describe a concrete subject/scene a reader of THIS post
would recognise as illustrating it. """ + IMAGE_HARD_RULE + """

Choose the image SOURCE per option:
- "library": an existing on-brand image (photo/graphic, NOT the logo) that fits this post's idea
- "real_photo": a real photograph (sourced online) that depicts this post's idea
- "generated": an image generated from scratch that illustrates this post's idea
Let the content decide (e.g. a product explainer often suits a generated diagram;
a news reaction often suits a real photo).

If an ## IMAGE LIBRARY is provided below and one of its templates genuinely fits this
post, PREFER a "library" option and name that template by its exact filename at the
start of the `direction` (e.g. "kitchen-table-bills.jpg — bills on a kitchen table,
warm light, …"). Do not invent library filenames that are not listed; if nothing in
the library fits, use real_photo or generated instead.

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


def build_image_recommend_prompt(
    post_text: str, *, design_tokens: str = "", library: str = ""
) -> str:
    """Prompt to recommend image approaches + concrete options for a post."""

    parts = ["## POST", post_text.strip()]
    if design_tokens.strip():
        parts += ["", "## BRAND DESIGN TOKENS", design_tokens.strip()]
    if library.strip():
        parts += [
            "",
            "## IMAGE LIBRARY (reusable on-brand templates — prefer one if it fits)",
            library.strip(),
        ]
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


ASSIGNMENT_SYSTEM = (
    "You turn a marketing operator's rough request into a precise assignment for a "
    "copywriter. You identify exactly what THIS post must be about, even when that "
    "differs from the brand's usual message. You return ONLY JSON."
)

ASSIGNMENT_INSTRUCTIONS = """\
Convert the operator request into an assignment. Return ONLY a JSON object:
{
  "specific": true or false,
  "subject": "the exact subject this post must be about, in a few words",
  "angle": "the framing/perspective requested, or empty",
  "audience": "intended audience if named, else empty",
  "must_cover": ["concrete points the request explicitly asks for"],
  "pivots_from_default": true or false
}
"specific" is true when the request names a particular subject, angle, audience, or
topic (not merely "write something on brand"). "pivots_from_default" is true when
the requested subject is NOT the brand's default message shown above — i.e. the
writer must resist drifting back to that default. No prose outside the JSON."""


def build_assignment_prompt(braindump: str, core_narrative: str = "") -> str:
    """Prompt to extract a binding assignment from the operator's request."""

    parts = ["## OPERATOR REQUEST", braindump.strip()]
    if core_narrative.strip():
        parts += ["", "## BRAND DEFAULT MESSAGE (for pivot detection only)", core_narrative.strip()]
    parts += ["", ASSIGNMENT_INSTRUCTIONS]
    return "\n".join(parts)


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
    "You are a relevance-and-reliability FILTER for a brand's news. You are GIVEN a pool "
    "of fresh candidate stories already scanned from Google News (each real and recently "
    "dated). You do NOT search the open web for new stories and you NEVER invent items or "
    "URLs — you SELECT, from the pool, only the ones genuinely relevant to the brand's "
    "audience, drop the rest, and reject unreliable sources. You judge relevance through "
    "the brand's strategy and guardrails."
)

SCRAPE_INSTRUCTIONS = """\
Work ONLY from the CANDIDATE POOL below — a set of fresh Google News results, already
dated within the last {lookback_days} days. Do not search for other stories and do not
invent any; every item you return must be one from the pool (same URL). You may WebFetch a
candidate's page to confirm what it actually says before keeping it.

Apply TWO filters to each candidate, and keep it only if it passes BOTH:

FILTER 1 — RELEVANCE to THIS brand's audience. The test is not "is this about the brand?"
but "would the brand's actual customer find this relevant to their world, and could a post
plausibly connect it back?" Judge through the brand STRATEGY, FOCUS, and HARD EXCLUSIONS
above. Obey the exclusions strictly — never keep an item whose main subject falls under
one. Drop generic trade-press / market-desk noise (e.g. junior-mining-stock results,
broker price chatter, analyst targets) that the audience would never read. A story does
NOT have to be about the brand; an adjacent item a good post can link back is fine.

FILTER 2 — SOURCE RELIABILITY. Keep only items from an established, identifiable outlet a
careful analyst would cite (recognised news organisations, primary institutions, research
houses, and the audience's own reputable local press). Drop blogs, forums, content farms,
SEO/affiliate pages, promotional or product pages, and unattributed press-release wires.

TONE GUARD: honour the brand's guardrails. Do not select items that only work as a
doom/panic or fear pitch — the brand is calm and factual; prefer items whose lead is a
concrete, on-strategy fact.

Then make each kept item POST-READY, not just a headline: name the THEME/cluster it maps
to (or "open" if it's an adjacent find); extract a featurable STAT (a single number + unit
a card could headline, e.g. "49%", "CHF 20bn") and a short QUOTE (<=20 words) if the story
offers one; suggest how a post could CONNECT IT BACK to the brand (an adjacent or indirect
link is fine); and set TEMPLATE to the card format that fits best — "stat" if there is a
strong number, "quote" if there is a strong line, else "headline".

Return ONLY a JSON array, best first, at most {max_items} items (fewer is fine — keep only
what genuinely passes both filters; an empty array is a valid answer):
[{{"title": "headline", "url": "the candidate's url (unchanged)", "source": "publication",
   "date": "YYYY-MM-DD from the candidate", "summary": "2-3 factual sentences",
   "principle": "the business principle it advances, or empty",
   "narrative": "the customer narrative it taps, or empty",
   "angle": "one line: how a post could use this, tied to the brand",
   "cluster": "the theme this maps to, or 'open' for an adjacent find, or empty",
   "stat": "one featurable number + unit from the story, or empty",
   "quote": "one short quotable line (<=20 words) from the story, or empty",
   "product_tie": "one line: how a post could connect this back to the brand (adjacent/indirect is fine)",
   "template": "stat | quote | headline",
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
    focus: str = "",
    exclude: list[str] | None = None,
    preferred_sources: list[str] | None = None,
    candidates: list[dict] | None = None,
) -> str:
    parts = ["## BRAND", brand_identity.strip()]
    if strategy_block.strip():
        parts += ["", "## BRAND STRATEGY", strategy_block.strip()]
    if focus.strip():
        parts += ["", "## FOCUS (weight your selection toward this)", focus.strip()]
    if exclude:
        parts += [
            "",
            "## HARD EXCLUSIONS (never keep a story PRIMARILY about any of these)",
            "\n".join(f"- {x}" for x in exclude),
        ]
    if preferred_sources:
        parts += [
            "",
            "## PREFERRED SOURCES (weight these outlets first when judging reliability)",
            "\n".join(f"- {s}" for s in preferred_sources),
        ]
    parts += ["", f"## TODAY\n{today} — the pool is already within the last {lookback_days} days."]
    pool = []
    for i, h in enumerate(candidates or [], start=1):
        title = str(h.get("title", "")).strip()
        if not title:
            continue
        meta = " · ".join(
            p for p in [str(h.get("source", "")).strip(), str(h.get("date", "")).strip()] if p
        )
        url = str(h.get("url", "")).strip()
        pool.append(f"{i}. {title}" + (f" ({meta})" if meta else "") + (f"\n   {url}" if url else ""))
    parts += [
        "",
        "## CANDIDATE POOL (fresh Google News results — SELECT from these, do not invent)",
        "\n".join(pool) if pool else "(empty)",
    ]
    parts += ["", SCRAPE_INSTRUCTIONS.format(max_items=max_items, lookback_days=lookback_days)]
    return "\n".join(parts)


# -- Step 4: cross-examination (corroborate each claim across independent sources) --
CROSS_EXAM_SYSTEM = (
    "You are a fact CROSS-EXAMINER auditing one news item BEFORE it is published. You do "
    "not take the cited page at face value and you do not stop at re-opening it: your job "
    "is to CORROBORATE the item's core stat/claim in OTHER, INDEPENDENT reputable sources. "
    "A single outlet's number is not confirmed until at least two independent reputable "
    "sources agree. You are skeptical by default, you never invent sources, and you return "
    "ONLY a JSON verdict."
)

CROSS_EXAM_INSTRUCTIONS = """\
CROSS-EXAMINE the single item below. First open its own cited page (WebFetch) to fix the
exact claim/number. Then use WebSearch/WebFetch to find the SAME core stat/claim reported
INDEPENDENTLY by at least TWO other reputable sources (different owners — not the same wire
re-posted, not the brand itself, not the originating outlet again). Prefer primary sources
(central banks, statistics offices, regulators, industry bodies, tax authorities) and
established news organisations.

Decide two things:

CORROBORATION — set "corroborated" = TRUE only if the core stat/claim is confirmed by at
least TWO independent reputable sources you actually opened, the figures agree (allowing
minor rounding), and the development is datable to within the last {lookback_days} days.
Set it FALSE if you can only find it in the one original outlet, if independent sources
disagree on the number, if it traces back to a single press release, or if you cannot pin
a date within the window. When sources genuinely disagree on the magnitude, say so in the
reason and set corroborated=false rather than silently picking one.

LEGITIMACY — set "legitimate" = TRUE only if the ORIGINAL outlet is itself an established,
identifiable, citable organisation (not a blog, forum, content farm, SEO/affiliate page,
promotional/product page, or unattributed wire).

Return ONLY a single JSON object (no array, no wrapper):
{{"corroborated": true or false,
  "legitimate": true or false,
  "sources": ["Outlet A (url)", "Outlet B (url)"],
  "summary": "the corrected 2-3 sentence factual summary agreed across sources; keep it if already correct",
  "date": "corrected YYYY-MM-DD, or empty if unknowable",
  "reason": "one short sentence: what corroborated it, or why it failed"}}

Default BOTH flags to false whenever you are unsure. It is far better to drop a real story
than to publish an uncorroborated or misattributed one. No prose outside the JSON, no
markdown fences."""


def build_cross_exam_prompt(
    item,
    *,
    today: str,
    lookback_days: int,
    reputable_only: bool = True,
) -> str:
    """Prompt for the per-item cross-examination subagent (step 4).

    ``item`` is one candidate with ``.title``/``.url``/``.source``/``.date``/``.summary``
    (the scraper's :class:`NewsItem`). The subagent corroborates the core claim across
    independent sources and returns a single verdict object; the engine drops anything not
    ``corroborated`` (and, when ``reputable_only``, whose original outlet isn't ``legitimate``)."""

    candidate = (
        f"title: {getattr(item, 'title', '')}\n"
        f"url: {getattr(item, 'url', '') or '(none given — treat as unverifiable)'}\n"
        f"source: {getattr(item, 'source', '') or '(unstated)'} · "
        f"claimed date: {getattr(item, 'date', '') or '(unstated)'}\n"
        f"claim to corroborate: {getattr(item, 'summary', '')}"
    )
    parts = [f"## TODAY\n{today} — a story is stale if older than {lookback_days} days."]
    if reputable_only:
        parts += [
            "",
            "## REPUTABLE SOURCES ONLY",
            "The legitimacy gate is enforced: the engine drops this item unless "
            "legitimate=true as well as corroborated=true.",
        ]
    parts += [
        "",
        "## ITEM TO CROSS-EXAMINE",
        candidate,
        "",
        CROSS_EXAM_INSTRUCTIONS.format(lookback_days=lookback_days),
    ]
    return "\n".join(parts)


# -- Topic scan (the Scraper map's per-category refresh) ----------------------
TOPIC_SCAN_SYSTEM = (
    "You are a research scout mapping what a brand's AUDIENCE is dealing with right "
    "now, organised by topic. For ONE category you search the web for RECENT, "
    "genuinely relevant developments, group them into a few concrete SUBTOPICS, and "
    "for each subtopic attach the real SOURCES (with working URLs) that back it. You "
    "judge relevance through the brand's strategy and audience. You never invent "
    "stories or URLs — every source must be a real page you actually found."
)

TOPIC_SCAN_INSTRUCTIONS = """\
Scan recent developments (within the lookback window) in the category "{category}"
as it affects THIS brand's audience. Use WebSearch to find stories and WebFetch to
confirm details. Prioritise the brand's TARGET MARKET and GEOGRAPHY — local sources
and local context a real customer there would actually see.

Group what you find into at most {max_subtopics} concrete SUBTOPICS. A subtopic is a
specific, checkable development (not a vague theme). For each subtopic attach 1-3
real SOURCES with working URLs so a human can fact-check it. Keep a subtopic ONLY if
it advances a BUSINESS PRINCIPLE or speaks to a CUSTOMER NARRATIVE. If a FOCUS or
HARD EXCLUSIONS section is given above, obey it strictly: never return a subtopic
whose main subject falls under an exclusion.

Return ONLY a JSON array, best first, at most {max_subtopics} items:
[{{"title": "the subtopic, one specific line",
   "summary": "2-3 factual sentences a household would care about",
   "angle": "one line: how a post for this brand could use it",
   "relevance": "high|medium|low",
   "sources": [{{"title": "headline", "url": "https://…", "source": "publication", "date": "YYYY-MM-DD"}}]}}]

Public-safe and factual only. Every URL must be real and fetchable. No prose outside
the JSON, no markdown fences."""


def build_topic_scan_prompt(
    *,
    brand_identity: str,
    strategy_block: str,
    category: str,
    focus: str = "",
    exclude: list[str] | None = None,
    preferred_sources: list[str] | None = None,
    lookback_days: int = 30,
    max_subtopics: int = 6,
    today: str = "",
) -> str:
    parts = ["## BRAND", brand_identity.strip()]
    if strategy_block.strip():
        parts += ["", "## BRAND STRATEGY", strategy_block.strip()]
    parts += ["", "## CATEGORY TO SCAN", category.strip()]
    if focus.strip():
        parts += ["", "## FOCUS (weight your searches and selection toward this)", focus.strip()]
    if exclude:
        parts += [
            "",
            "## HARD EXCLUSIONS (never return a subtopic PRIMARILY about any of these)",
            "\n".join(f"- {x}" for x in exclude),
        ]
    if preferred_sources:
        parts += [
            "",
            "## PREFERRED SOURCES (search the open web, but weight these outlets first)",
            "\n".join(f"- {s}" for s in preferred_sources),
        ]
    if today:
        parts += ["", f"## TODAY\n{today} — only keep developments from the last {lookback_days} days."]
    parts += ["", TOPIC_SCAN_INSTRUCTIONS.format(category=category, max_subtopics=max_subtopics)]
    return "\n".join(parts)


# -- Topic MAP derivation (agnostic: infer the categories from the brand's KB) ----
TOPIC_MAP_SYSTEM = (
    "You design a brand's NEWS-MONITORING MAP. From the brand's identity, strategy / "
    "business objectives, and its knowledge-base documents, you infer WHO the audience "
    "is and the handful of real-world TOPIC AREAS whose news most affects the brand's "
    "objectives and that audience. You READ the brand's own files before deciding — the "
    "map must follow from the brand's actual material, not generic guesses. You return a "
    "compact JSON map and nothing else."
)

TOPIC_MAP_INSTRUCTIONS = """\
Read this brand's own material before deciding: use Glob/Grep/Read over the brand's
`_kb/` (knowledge base the user uploaded) and `_rules/` (objectives, strategy, audience).
Infer the business objective and who the audience really is.

Then design the news-monitoring map: the topic areas whose ongoing developments a
content team should watch because they advance a BUSINESS OBJECTIVE or speak to the
audience's lived reality. Prefer concrete, monitorable areas over abstract themes.
Honor any FOCUS and HARD EXCLUSIONS given above. Aim for {min_n}-{max_n} categories.

Return ONLY this JSON object (no prose, no markdown fences):
{{"center": "2-4 words naming the audience (e.g. 'Swiss Households')",
  "categories": [{{"id": "kebab-case-id", "label": "Short Title"}}]}}"""


def build_topic_map_prompt(
    *,
    brand_identity: str,
    strategy_block: str,
    focus: str = "",
    exclude: list[str] | None = None,
    min_n: int = 6,
    max_n: int = 9,
) -> str:
    parts = ["## BRAND", brand_identity.strip()]
    if strategy_block.strip():
        parts += ["", "## BRAND STRATEGY", strategy_block.strip()]
    if focus.strip():
        parts += ["", "## FOCUS (weight the map toward this audience reality)", focus.strip()]
    if exclude:
        parts += [
            "",
            "## HARD EXCLUSIONS (do not create a category centred on any of these)",
            "\n".join(f"- {x}" for x in exclude),
        ]
    parts += ["", TOPIC_MAP_INSTRUCTIONS.format(min_n=min_n, max_n=max_n)]
    return "\n".join(parts)


def build_image_brief_prompt(
    post_text: str, *, design_tokens: str = "", kind: str = "", direction: str = "", layout: str = ""
) -> str:
    """Prompt for an image/visual brief for a finished post.

    When the operator has already picked an option (``kind`` + ``direction``), the
    brief is written FOR that choice (e.g. instructions to source a real photo vs.
    generate one); otherwise it's a generic brief. When a brand ``layout`` spec is
    given, the finished image must follow that fixed composition.
    """

    parts = ["## POST (the image must illustrate THIS post's idea)", post_text.strip()]
    if design_tokens.strip():
        parts += ["", "## BRAND DESIGN TOKENS", design_tokens.strip()]
    if layout.strip():
        parts += ["", "## POST IMAGE LAYOUT (the finished image MUST follow this composition)", layout.strip()]
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
                else " — instruct the designer to USE THE UPLOADED LIBRARY IMAGE named "
                "in the direction (the template the user dropped in) as the photo, and "
                "say how to place/crop it; if the library lacks a fitting image, specify "
                "the image to create instead"
                if kind == "library"
                else " — describe the image to generate, depicting the post's idea"
            )
            + "."
        )
        chosen.append(IMAGE_HARD_RULE)
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
    concepts: list[str] | None = None,
) -> str:
    """Prompt for generating N distinct post options in one call.

    When recent ``news_headlines`` are supplied, the model is nudged to make some
    ideas news-reactive (the Product/News axis) while staying on-brand. ``concepts``
    are always-on, evergreen post seeds (tax facts, product truths) that don't expire
    like news does — the model may draw ideas from them directly.
    """

    parts = ["## REQUEST", input_text.strip()]
    if platform_label:
        parts += ["", f"## PLATFORM\n{platform_label}"]
    if platform_guidance.strip():
        parts += ["", "## PLATFORM GUIDANCE", platform_guidance.strip()]
    if concepts:
        parts += [
            "",
            "## EVERGREEN POST CONCEPTS (always-on seeds — draw ideas from these freely)",
            "\n".join(f"- {c}" for c in concepts),
        ]
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
