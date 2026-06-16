"""Turn a rough operator request into a precise, BINDING assignment.

A brand's distilled strategy deliberately pulls every post toward its core
message. When the operator asks for something specific that ISN'T that (a legal
angle, a news reaction, an investor cut), the writer can still drift back to the
default story. This cheap Haiku step pins down what THIS post must be about and
hands the writer a hard constraint, so the request wins over the default angle.

Agnostic: it reads only the operator's words plus the brand's core narrative (to
detect when the request pivots away from the default). No brand is hard-coded.
Fails soft — if it can't parse an assignment, generation proceeds unconstrained.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from marketing_engine.content.postprocess import extract_json_obj
from marketing_engine.harness.prompts import ASSIGNMENT_SYSTEM, build_assignment_prompt
from marketing_engine.sdk.client import AgentRunOptions
from marketing_engine.sdk.models import HAIKU


@dataclass
class Assignment:
    specific: bool = False
    subject: str = ""
    angle: str = ""
    audience: str = ""
    must_cover: list[str] = field(default_factory=list)
    pivots_from_default: bool = False

    def block(self) -> str:
        """The binding constraint to inject into the run prompt, or '' if the
        request named nothing specific (then the brand default angle applies)."""

        if not self.specific or not self.subject:
            return ""
        lines = [
            "## ASSIGNMENT (binding — overrides the brand's default-angle guidance)",
            f"This post MUST be about: {self.subject}.",
        ]
        if self.angle:
            lines.append(f"Angle / framing: {self.angle}")
        if self.audience:
            lines.append(f"Audience: {self.audience}")
        if self.must_cover:
            lines.append("Cover: " + "; ".join(self.must_cover))
        if self.pivots_from_default:
            lines.append(
                "This subject is NOT the brand's usual message. Do NOT drift back to "
                "the brand's default value proposition or any \"lead with X\" guidance — "
                "stay on this subject. Relate to the brand only where it genuinely fits."
            )
        lines.append(
            "Develop this as ONE idea and end on a single call to action."
        )
        return "\n".join(lines)


async def extract_assignment(engine, brand, braindump: str, *, cwd=None) -> Assignment:
    """Extract the binding assignment from the operator's request (Haiku, no tools)."""

    if not braindump.strip():
        return Assignment()
    narrative = (getattr(brand, "narrative", "") or getattr(brand, "identity", "") or "").strip()
    options = AgentRunOptions(
        system_prompt=ASSIGNMENT_SYSTEM,
        cwd=cwd or engine.layout.root,
        allowed_tools=[],
        model=HAIKU,
    )
    try:
        result = await engine.llm.run(build_assignment_prompt(braindump, narrative), options)
    except Exception:
        return Assignment()
    data = extract_json_obj(result.text)
    if not data:
        return Assignment()
    cover = data.get("must_cover") or []
    return Assignment(
        specific=bool(data.get("specific", False)),
        subject=str(data.get("subject", "")).strip(),
        angle=str(data.get("angle", "")).strip(),
        audience=str(data.get("audience", "")).strip(),
        must_cover=[str(c).strip() for c in cover if str(c).strip()],
        pivots_from_default=bool(data.get("pivots_from_default", False)),
    )
