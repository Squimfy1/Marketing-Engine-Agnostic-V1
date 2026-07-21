"""Image recommendations — the first half of the Image Generation step.

A finished post goes in; out comes a one-line recommendation plus a few concrete
image OPTIONS to choose from, each tagged with its SOURCE kind:

  * ``library``    — pick an existing image from the brand's library
  * ``real_photo`` — a real photo to source online and bring into Claude Design
  * ``generated``  — generate it from scratch in Claude Design

All are ultimately produced via Claude Code; the kind only says where the raw
image comes from. Once the operator picks one, ``engine.generate_image_brief``
writes the full Claude Design instructions for that specific choice.

Cheap and single-shot (the brand's 'ideas' tier, no file tools). Fails soft: if
the model returns nothing parseable, ``options`` is empty and the caller can fall
back to a plain brief.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from marketing_engine.content.postprocess import extract_json_obj
from marketing_engine.harness.prompts import (
    IMAGE_KINDS,
    IMAGE_RECOMMEND_SYSTEM,
    build_image_recommend_prompt,
)
from marketing_engine.sdk.client import AgentRunOptions
from marketing_engine.sdk.models import resolve_model

VALID_KINDS = set(IMAGE_KINDS)


@dataclass
class ImageOption:
    kind: str  # library | real_photo | generated
    direction: str
    rationale: str = ""

    def as_dict(self) -> dict:
        return {"kind": self.kind, "direction": self.direction, "rationale": self.rationale}


@dataclass
class ImageRecommendation:
    recommendation: str = ""
    options: list[ImageOption] = field(default_factory=list)
    model: str | None = None
    usage: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "recommendation": self.recommendation,
            "options": [o.as_dict() for o in self.options],
        }


def _coerce_kind(raw: str) -> str:
    k = (raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    if k in VALID_KINDS:
        return k
    if "photo" in k or "real" in k or "stock" in k:
        return "real_photo"
    if "librar" in k or "existing" in k:
        return "library"
    return "generated"


async def recommend_images(
    engine,
    tenant_id: str,
    brand_id: str,
    *,
    post_text: str,
    platform: str | None = None,
) -> ImageRecommendation:
    """Recommend image approaches + concrete options for a finished post."""

    if not post_text.strip():
        return ImageRecommendation()

    tenant = engine.registry.get_tenant(tenant_id)
    brand = engine.registry.get_brand(tenant_id, brand_id)
    model = resolve_model(
        "image_brief",
        brand_models=brand.models.model_dump(),
        tenant_default=tenant.default_model,
        settings_default=engine.settings.default_model,
    )
    options = AgentRunOptions(
        system_prompt=IMAGE_RECOMMEND_SYSTEM,
        cwd=engine.layout.brand_dir(tenant_id, brand_id),
        allowed_tools=[],
        model=model,
    )
    design_dir = engine.layout.design_dir(tenant_id, brand_id)
    tokens_path = design_dir / "tokens.yaml"
    tokens = tokens_path.read_text(encoding="utf-8") if tokens_path.is_file() else ""
    # The brand's reusable image templates (the "library" kind picks from these).
    lib_path = design_dir / "library.md"
    library = lib_path.read_text(encoding="utf-8") if lib_path.is_file() else ""
    prompt = build_image_recommend_prompt(post_text, design_tokens=tokens, library=library)
    try:
        result = await engine.llm.run(prompt, options)
    except Exception:
        return ImageRecommendation()

    data = extract_json_obj(result.text)
    opts: list[ImageOption] = []
    for item in data.get("options") or []:
        if not isinstance(item, dict):
            continue
        direction = str(item.get("direction", "")).strip()
        if not direction:
            continue
        opts.append(
            ImageOption(
                kind=_coerce_kind(str(item.get("kind", ""))),
                direction=direction,
                rationale=str(item.get("rationale", "")).strip(),
            )
        )
    # Backstop: a logo/wordmark-only direction is never a valid post image. Drop
    # those when post-connected options remain; if ALL are logo-ish (model ignored
    # the rule), keep them rather than return nothing.
    non_logo = [o for o in opts if not _is_logo_only(o.direction)]
    opts = non_logo or opts
    return ImageRecommendation(
        recommendation=str(data.get("recommendation", "")).strip(),
        options=opts,
        model=result.model,
        usage=result.usage,
    )


_LOGO_TERMS = ("logo", "wordmark", "brand mark", "brandmark", "lockup", "logotype")


def _is_logo_only(direction: str) -> bool:
    """True when the direction's subject is essentially the logo/brand mark rather
    than a scene depicting the post (a small corner watermark mention is fine)."""

    d = direction.lower()
    if not any(t in d for t in _LOGO_TERMS):
        return False
    # If it also describes a real scene, it's not logo-ONLY (allow watermark use).
    scene_cues = ("photo", "scene", "diagram", "chart", "illustration", "person",
                  "people", "hand", "table", "vault", "macro", "landscape", "graph")
    return not any(c in d for c in scene_cues)
