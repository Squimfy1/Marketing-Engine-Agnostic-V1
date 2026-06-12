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
First, Glob/Grep the brand's _kb/ and read the 1–2 files most relevant to the
request, so every idea is grounded in the brand's REAL product and material.

Then propose exactly {n} DISTINCT short-post IDEAS — NOT full posts. Each idea is
a brief: a short angle/headline, then 1–2 sentences on what the post would say and
why it fits the brand. Take DIFFERENT angles (e.g. a product explainer, an
analytical insight, a reaction to relevant news, a concrete use-case).

Rules:
- Keep each idea to **1–2 sentences. Do NOT write the full post.**
- Make each idea SPECIFIC to this brand using facts from _kb/. Do NOT invent facts
  and do NOT write generic filler; if a detail isn't in _kb/, stay high-level.
- Obey the WRITING RULES and Guardrails. No numbering, no commentary.
Format strictly: start EVERY idea (including the first) with a line containing
only @@@OPTION@@@, immediately followed by the idea. Write nothing before the
first @@@OPTION@@@."""


IMAGE_BRIEF_INSTRUCTIONS = """\
Write concise image-generation instructions (a visual brief) for an image to
accompany the post below. Cover: subject/scene, composition, art style, mood,
colour palette, and any short text overlay. Keep it on-brand and ready to paste
into an image tool. Output ONLY the brief — no preamble, no commentary."""


def build_image_brief_prompt(post_text: str, *, design_tokens: str = "") -> str:
    """Prompt for an image/visual brief for a finished post."""

    parts = ["## POST", post_text.strip()]
    if design_tokens.strip():
        parts += ["", "## BRAND DESIGN TOKENS", design_tokens.strip()]
    parts += ["", IMAGE_BRIEF_INSTRUCTIONS]
    return "\n".join(parts)


def build_options_prompt(
    input_text: str,
    *,
    n: int = 4,
    platform_label: str | None = None,
    platform_guidance: str = "",
) -> str:
    """Prompt for generating N distinct post options in one call."""

    parts = ["## REQUEST", input_text.strip()]
    if platform_label:
        parts += ["", f"## PLATFORM\n{platform_label}"]
    if platform_guidance.strip():
        parts += ["", "## PLATFORM GUIDANCE", platform_guidance.strip()]
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
