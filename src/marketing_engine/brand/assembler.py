"""Assemble per-brand run inputs from tenant + brand config and the vault.

This is the agnostic seam: identical code, different data per brand → different,
on-brand behaviour. Produces a fully-formed ``AgentRunOptions`` plus the run
prompt, ready to hand to any ``LLMClient``.
"""

from __future__ import annotations

from dataclasses import dataclass

from marketing_engine.brand.schema import BrandConfig
from marketing_engine.config.settings import Settings
from marketing_engine.harness.prompts import assemble_system_prompt, build_run_prompt
from marketing_engine.sdk.client import AgentRunOptions
from marketing_engine.sdk.models import resolve_model
from marketing_engine.tenant.schema import TenantConfig
from marketing_engine.vault.layout import CORE_RULES_FILE, VaultLayout


@dataclass
class AssembledRun:
    system_prompt: str
    run_prompt: str
    options: AgentRunOptions


def _read_core_rules(layout: VaultLayout, tenant_id: str, brand_id: str) -> str:
    path = layout.core_rules(tenant_id, brand_id)
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def _read_shared_rules(layout: VaultLayout) -> str:
    """Concatenate every shared rule file (anti-AI writing rules) for inlining."""

    rules_dir = layout.shared_dir / "rules"
    if not rules_dir.is_dir():
        return ""
    blocks = []
    for path in sorted(rules_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if text:
            blocks.append(text)
    return "\n\n---\n\n".join(blocks)


def assemble_run(
    *,
    layout: VaultLayout,
    settings: Settings,
    tenant: TenantConfig,
    brand: BrandConfig,
    input_text: str,
    platform_label: str | None = None,
    platform_guidance: str = "",
    task: str = "default",
) -> AssembledRun:
    core_rules = _read_core_rules(layout, tenant.id, brand.id)
    writing_rules = _read_shared_rules(layout)

    system_prompt = assemble_system_prompt(
        tenant_name=tenant.name,
        tenant_notes=tenant.notes,
        brand_name=brand.name,
        brand_identity=brand.identity,
        brand_voice=brand.voice,
        core_rules=core_rules,
        writing_rules=writing_rules,
    )

    model = resolve_model(
        task,
        brand_models=brand.models.model_dump(),
        tenant_default=tenant.default_model,
        settings_default=settings.default_model,
    )

    options = AgentRunOptions(
        system_prompt=system_prompt,
        cwd=layout.brand_dir(tenant.id, brand.id),
        add_dirs=[layout.shared_dir],
        allowed_roots=list(layout.allowed_roots(tenant.id, brand.id)),
        allowed_tools=["Read", "Grep", "Glob"],
        model=model,
    )

    return AssembledRun(
        system_prompt=system_prompt,
        run_prompt=build_run_prompt(
            input_text,
            platform_label=platform_label,
            platform_guidance=platform_guidance,
        ),
        options=options,
    )
