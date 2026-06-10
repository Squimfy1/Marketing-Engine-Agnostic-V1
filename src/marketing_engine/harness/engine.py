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
from marketing_engine.sdk.client import ClaudeAgentClient, LLMClient
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
