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
   directly relevant to this request. Do NOT read the shared writing-rule files
   (your system prompt already constrains voice and style), do NOT run shell
   commands, and do NOT look outside this brand's folder.
2. If _kb/ doesn't have the facts you need, write the best on-brand piece you
   can from the request itself; only if that is impossible, state briefly in one
   line what source material is missing — do not keep searching.
3. Then write the finished piece and stop.
Return only the final copy in markdown — no preamble, no commentary, no notes
about what you read."""


def assemble_system_prompt(
    *,
    tenant_name: str,
    tenant_notes: str,
    brand_name: str,
    brand_identity: str,
    brand_voice: str,
    core_rules: str,
) -> str:
    """Compose the per-brand system prompt (the inlined constitution)."""

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
    if core_rules.strip():
        parts.append("")
        parts.append("## CORE RULES")
        parts.append(core_rules.strip())
    return "\n".join(parts).strip()


OPTIONS_INSTRUCTIONS = """\
Using the brand identity and voice above, write exactly {n} DISTINCT options for
the request below — different angles or hooks, each a complete, ready-to-post
post in the brand's voice.

Write them NOW from the brand identity and voice. Do NOT ask for more
information, do NOT refuse, and do NOT add any commentary. If a specific fact
would help but you don't have it, still write a strong angle and put a short
[bracketed note] where a real detail belongs.

No titles, no numbering, no preamble. Separate each option with a line
containing only @@@OPTION@@@ and nothing else."""


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
