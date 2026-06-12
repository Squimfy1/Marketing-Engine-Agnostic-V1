"""The Agent Harness — orchestrates one content run for one brand.

Flow (Milestone 1):
  resolve (tenant, brand) -> read Dashboard ## Input -> assemble brand-scoped
  run -> agent reads KB/Rules and drafts copy -> write copy back to
  ## Text Output + a dated _outputs/ note -> record a memory entry.

The agent run is brand-isolated (cwd + allowlist hook). The authoritative write
is done here deterministically from the agent's final text, so it never depends
on the model choosing to call a write tool.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from marketing_engine.brand.assembler import assemble_run
from marketing_engine.config.settings import Settings
from marketing_engine.content.platforms import load_guidance, resolve_platform
from marketing_engine.harness.prompts import build_image_brief_prompt, build_options_prompt
from marketing_engine.content.validate import validate_post
from marketing_engine.content.postprocess import clean_copy
from marketing_engine.sdk.client import ClaudeAgentClient, LLMClient, RunResult
from marketing_engine.tenant.registry import Registry
from marketing_engine.tools.memory_tools import append_memory
from marketing_engine.tools.output_tools import write_output_note
from marketing_engine.vault.dashboard import Dashboard
from marketing_engine.vault.fs_adapter import FilesystemVaultAdapter
from marketing_engine.vault.layout import VaultLayout


class EngineError(Exception):
    pass


@dataclass
class EngineResult:
    tenant_id: str
    brand_id: str
    text: str
    output_relpath: str
    model: str | None
    denied_paths: list[str] = field(default_factory=list)
    is_error: bool = False


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class MarketingEngine:
    def __init__(
        self,
        settings: Settings,
        *,
        llm: LLMClient | None = None,
    ) -> None:
        self.settings = settings
        self.layout = VaultLayout(settings.vault_root)
        self.registry = Registry(self.layout)
        self.llm: LLMClient = llm or ClaudeAgentClient()

    async def generate(
        self,
        tenant_id: str,
        brand_id: str,
        *,
        braindump: str,
        platform: str | None = None,
        intent: str = "draft",
        task: str = "default",
    ) -> RunResult:
        """Generate copy for a brand + platform from a braindump.

        Returns the agent's draft text WITHOUT writing to the vault — the web
        dashboard is the surface, and the save happens later via commit-edits.
        Brand-isolated via the assembled, scoped options.
        """

        if not braindump.strip():
            raise EngineError("Empty braindump — nothing to generate from.")

        tenant = self.registry.get_tenant(tenant_id)
        brand = self.registry.get_brand(tenant_id, brand_id)
        plat = resolve_platform(platform)

        assembled = assemble_run(
            layout=self.layout,
            settings=self.settings,
            tenant=tenant,
            brand=brand,
            input_text=braindump,
            platform_label=plat.label,
            platform_guidance=load_guidance(self.layout, plat),
            task=task,
        )
        result = await self.llm.run(assembled.run_prompt, assembled.options)
        result.text = clean_copy(result.text)

        # Cheap Haiku reliability gate + ONE bounded retry on failure.
        ok, reason = await validate_post(self, brand, result.text, cwd=assembled.options.cwd)
        if not ok and reason:
            retry_prompt = (
                assembled.run_prompt
                + "\n\n## REVISION NEEDED\nA reviewer flagged this draft: "
                + reason
                + "\nRewrite the post to fix it — develop ONE idea, connect it to the core "
                "narrative, and end on a single call to action. Return only the post."
            )
            retried = await self.llm.run(retry_prompt, assembled.options)
            retried.text = clean_copy(retried.text)
            if retried.text.strip():
                result = retried
        return result

    async def generate_options(
        self,
        tenant_id: str,
        brand_id: str,
        *,
        braindump: str,
        platform: str | None = None,
        n: int = 4,
    ) -> RunResult:
        """Generate N distinct post options in a single fast, cheap call.

        Uses the brand's 'ideas' model tier (Haiku by default) and NO file tools,
        so it is a one-shot generation from the inlined brand voice + rules —
        fast and token-light. The full draft (with KB reading) comes later when
        the operator picks an option.
        """

        if not braindump.strip():
            raise EngineError("Empty braindump — nothing to generate from.")

        tenant = self.registry.get_tenant(tenant_id)
        brand = self.registry.get_brand(tenant_id, brand_id)
        plat = resolve_platform(platform)
        guidance = load_guidance(self.layout, plat)

        assembled = assemble_run(
            layout=self.layout,
            settings=self.settings,
            tenant=tenant,
            brand=brand,
            input_text=braindump,
            platform_label=plat.label,
            platform_guidance=guidance,
            task="ideas",
        )
        # Single-shot, no tools: ideas come from the inlined brand narrative + rules
        # (the 'ideas' Haiku tier). Cheap, fast, and reliably structured.
        assembled.options.allowed_tools = []
        prompt = build_options_prompt(
            braindump, n=n, platform_label=plat.label, platform_guidance=guidance
        )
        result = await self.llm.run(prompt, assembled.options)
        result.text = clean_copy(result.text)
        return result

    async def generate_image_brief(
        self,
        tenant_id: str,
        brand_id: str,
        *,
        post_text: str,
        platform: str | None = None,
    ) -> RunResult:
        """Generate image-generation instructions (a visual brief) for a post.

        Single-shot from the post + the brand's design tokens + voice. Fast/cheap
        ('ideas' tier). This is the Design System -> Image Output step.
        """

        if not post_text.strip():
            raise EngineError("No post text to brief an image from.")

        tenant = self.registry.get_tenant(tenant_id)
        brand = self.registry.get_brand(tenant_id, brand_id)
        plat = resolve_platform(platform)

        assembled = assemble_run(
            layout=self.layout,
            settings=self.settings,
            tenant=tenant,
            brand=brand,
            input_text=post_text,
            platform_label=plat.label,
            task="ideas",
        )
        assembled.options.allowed_tools = []  # single-shot, no file reading

        tokens_path = self.layout.design_dir(tenant_id, brand_id) / "tokens.yaml"
        tokens = tokens_path.read_text(encoding="utf-8") if tokens_path.is_file() else ""
        prompt = build_image_brief_prompt(post_text, design_tokens=tokens)
        result = await self.llm.run(prompt, assembled.options)
        result.text = clean_copy(result.text)
        return result

    async def run(
        self,
        tenant_id: str,
        brand_id: str,
        *,
        input_text: str | None = None,
        date_str: str | None = None,
    ) -> EngineResult:
        # Fail fast on unknown/invalid tenant or brand (raises RegistryError).
        tenant = self.registry.get_tenant(tenant_id)
        brand = self.registry.get_brand(tenant_id, brand_id)
        date_str = date_str or _today()

        vault = FilesystemVaultAdapter(self.layout, tenant_id, brand_id)
        dashboard = Dashboard(vault)

        if input_text is None:
            input_text = dashboard.read_input()
        if not input_text.strip():
            raise EngineError(
                f"No input found. Add a request under '## Input' in "
                f"{self.layout.dashboard(tenant_id, brand_id)}"
            )

        assembled = assemble_run(
            layout=self.layout,
            settings=self.settings,
            tenant=tenant,
            brand=brand,
            input_text=input_text,
        )

        result = await self.llm.run(assembled.run_prompt, assembled.options)
        result.text = clean_copy(result.text)

        # Authoritative, deterministic writes back into the vault.
        title = _title_from_input(input_text)
        output_relpath = write_output_note(
            vault, title=title, body=result.text, date_str=date_str
        )
        dashboard.write_text_output(result.text)
        status = "ok" if not result.is_error else "error"
        dashboard.set_status(f"{date_str}: {status} ({result.model}) -> {output_relpath}")
        append_memory(
            vault,
            note=f"Generated '{title}' ({result.model}); saved {output_relpath}.",
            date_str=date_str,
        )

        return EngineResult(
            tenant_id=tenant_id,
            brand_id=brand_id,
            text=result.text,
            output_relpath=output_relpath,
            model=result.model,
            denied_paths=result.denied_paths,
            is_error=result.is_error,
        )


def _title_from_input(input_text: str) -> str:
    first = next((ln.strip() for ln in input_text.splitlines() if ln.strip()), "untitled")
    return first[:80]
