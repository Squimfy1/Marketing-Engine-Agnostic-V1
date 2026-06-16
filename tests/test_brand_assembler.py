from __future__ import annotations

from marketing_engine.brand.assembler import assemble_run
from marketing_engine.config.settings import Settings
from marketing_engine.tenant.registry import Registry
from marketing_engine.vault.layout import VaultLayout


def _assemble(layout: VaultLayout, settings: Settings, brand_id: str):
    reg = Registry(layout)
    return assemble_run(
        layout=layout,
        settings=settings,
        tenant=reg.get_tenant("acme-co"),
        brand=reg.get_brand("acme-co", brand_id),
        input_text="Write a tagline.",
    )


def test_system_prompt_inlines_voice_and_core_rules(layout, settings):
    run = _assemble(layout, settings, "acme")
    assert "Brand: Acme Rockets" in run.system_prompt
    assert "Playful and warm." in run.system_prompt
    assert "## CORE RULES" in run.system_prompt
    assert "Always sound fun." in run.system_prompt


def test_run_prompt_carries_input(layout, settings):
    run = _assemble(layout, settings, "acme")
    assert "## INPUT" in run.run_prompt
    assert "Write a tagline." in run.run_prompt


def test_options_scope_to_brand_subtree(layout, settings):
    run = _assemble(layout, settings, "acme")
    assert run.options.cwd == layout.brand_dir("acme-co", "acme")
    assert layout.shared_dir in run.options.add_dirs
    # File tools (brand subtree) + web research for briefs that need current facts.
    assert run.options.allowed_tools == ["Read", "Grep", "Glob", "WebSearch", "WebFetch"]
    assert run.options.model == "claude-opus-4-8"


def test_different_brands_produce_different_prompts(layout, settings):
    acme = _assemble(layout, settings, "acme").system_prompt
    globex = _assemble(layout, settings, "globex").system_prompt
    assert acme != globex
    assert "Playful" in acme and "Formal" in globex
