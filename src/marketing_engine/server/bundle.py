"""Assemble the "context bundle" the dashboard shows before generating.

Mirrors V1's ``/api/lab/bundle-pack``: returns the sections of context that will
shape the draft — brand identity/voice, the brand's core rules, the shared
writing rules, the platform format guidance, and recent edit-learnings — so the
operator can see (and trust) what the model is working from.

This is server-side display assembly, not the agent's own context, so it reads
files directly via the layout. Read-only.
"""

from __future__ import annotations

from pathlib import Path

from marketing_engine.brand.schema import BrandConfig
from marketing_engine.harness.platforms import PLATFORMS_DIR, resolve_platform
from marketing_engine.tenant.registry import Registry
from marketing_engine.tools.learnings import LAB_LEARNINGS
from marketing_engine.vault.layout import VaultLayout

# Shared rules surfaced in the bundle (client-agnostic writing constitution).
_SHARED_RULES = ("WRITING_RULES.md", "BANNED_PATTERNS.md", "CONTENT_STRUCTURES.md")
_MAX_SECTION_CHARS = 20000


def _section(title: str, path: str, content: str) -> dict:
    if len(content) > _MAX_SECTION_CHARS:
        content = content[:_MAX_SECTION_CHARS] + "\n…(truncated)"
    return {"title": title, "path": path, "content": content.strip()}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def assemble_bundle(
    layout: VaultLayout,
    registry: Registry,
    *,
    tenant_id: str,
    brand_id: str,
    platform: str | None = None,
    intent: str = "draft",
    generated_at: str = "",
) -> dict:
    """Return ``{sections, intent, snapshot}`` for the dashboard. Raises
    ``RegistryError`` if the tenant/brand is unknown."""

    brand: BrandConfig = registry.get_brand(tenant_id, brand_id)
    plat = resolve_platform(platform)
    sections: list[dict] = []

    # 1. Brand identity + voice.
    identity = f"**Identity:** {brand.identity}\n\n**Voice:** {brand.voice}".strip()
    sections.append(_section(f"BRAND: {brand.name}", f"brands/{brand_id}/brand.yaml", identity))

    # 2. Brand core rules.
    core = _read(layout.core_rules(tenant_id, brand_id))
    if core:
        sections.append(_section("BRAND RULES", "_rules/_core.md", core))

    # 3. Shared writing rules.
    for fname in _SHARED_RULES:
        content = _read(layout.shared_dir / "rules" / fname)
        if content:
            sections.append(_section(f"RULES: {fname[:-3]}", f"_shared/rules/{fname}", content))

    # 4. Platform guidance.
    plat_content = _read(layout.shared_dir / PLATFORMS_DIR / f"{plat.id}.md")
    if plat_content:
        sections.append(
            _section(f"PLATFORM: {plat.label}", f"_shared/platforms/{plat.id}.md", plat_content)
        )

    # 5. Recent edit-learnings for this brand.
    learnings = _read(layout.brand_dir(tenant_id, brand_id) / LAB_LEARNINGS)
    if learnings:
        sections.append(_section("LEARNINGS", LAB_LEARNINGS, learnings[-6000:]))

    return {
        "sections": sections,
        "intent": intent,
        "snapshot": {
            "tenant": tenant_id,
            "brand": brand_id,
            "platform": plat.label,
            "bundleIntent": intent,
            "generatedAt": generated_at,
        },
    }
