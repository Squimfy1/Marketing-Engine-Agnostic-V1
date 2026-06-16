"""Cheap reliability gate: a Haiku verdict on a finished short post.

One small, fast check per post (one idea? connects to the narrative? no crypto /
returns promises? single CTA?). The engine uses it for ONE bounded retry — far
cheaper than a multi-model prosecutor loop, and it never blocks: if the validator
itself errors or returns nothing parseable, the post passes.
"""

from __future__ import annotations

from marketing_engine.harness.prompts import VALIDATE_SYSTEM, build_validate_prompt
from marketing_engine.content.postprocess import extract_json_obj
from marketing_engine.sdk.client import AgentRunOptions
from marketing_engine.sdk.models import HAIKU


async def validate_post(engine, brand, post_text: str, *, request: str = "", cwd=None) -> tuple[bool, str]:
    """Return ``(ok, reason)``. Always Haiku, no tools. Fails open (ok=True) if the
    verdict can't be parsed, so the gate never silently drops a good post.

    ``request`` is the operator's brief — when present, the gate checks the post
    answers IT (not the brand's default narrative)."""

    if not post_text.strip():
        return True, ""
    narrative = (getattr(brand, "narrative", "") or getattr(brand, "identity", "") or "").strip()
    options = AgentRunOptions(
        system_prompt=VALIDATE_SYSTEM,
        cwd=cwd or engine.layout.root,
        allowed_tools=[],
        model=HAIKU,
    )
    result = await engine.llm.run(build_validate_prompt(post_text, narrative, request), options)
    data = extract_json_obj(result.text)
    if not data:
        return True, ""
    return bool(data.get("pass", True)), str(data.get("reason", "")).strip()
