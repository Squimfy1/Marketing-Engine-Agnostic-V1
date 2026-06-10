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
Read the brand's _rules/ and _kb/ as needed, then write the requested content.
Return only the finished copy in markdown."""


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


def build_run_prompt(input_text: str) -> str:
    """The user-turn prompt carrying the operator's request."""

    return f"## INPUT\n{input_text.strip()}\n\n{RUN_INSTRUCTIONS}"
