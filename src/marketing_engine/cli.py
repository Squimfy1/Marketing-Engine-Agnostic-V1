"""Command-line entry point: ``engine run --tenant <t> --brand <b>``."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer

from marketing_engine.config.settings import Settings
from marketing_engine.harness.engine import EngineError, MarketingEngine
from marketing_engine.sdk.client import ClaudeAgentClient, FakeLLMClient
from marketing_engine.tenant.registry import RegistryError

app = typer.Typer(help="Marketing Engine — multi-tenant, brand-agnostic content engine.")


@app.command()
def run(
    tenant: str = typer.Option(..., "--tenant", "-t", help="Tenant (account) id."),
    brand: str = typer.Option(..., "--brand", "-b", help="Brand id within the tenant."),
    input_text: Optional[str] = typer.Option(
        None, "--input", "-i", help="Inline request (overrides Dashboard ## Input)."
    ),
    vault_root: Optional[Path] = typer.Option(
        None, "--vault", help="Vault root (defaults to $VAULT_ROOT)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Use the deterministic fake model — no network, no API key."
    ),
) -> None:
    settings = Settings.from_env(vault_root=vault_root)
    llm = FakeLLMClient() if dry_run else ClaudeAgentClient()
    engine = MarketingEngine(settings, llm=llm)

    try:
        result = asyncio.run(
            engine.run(tenant, brand, input_text=input_text)
        )
    except RegistryError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    except EngineError as exc:
        typer.secho(str(exc), fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(code=1)

    typer.secho(
        f"[{result.tenant_id}/{result.brand_id}] {'(dry-run) ' if dry_run else ''}"
        f"model={result.model}",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"Output note: {result.output_relpath}")
    if result.denied_paths:
        typer.secho(
            f"Isolation denials: {len(result.denied_paths)}", fg=typer.colors.YELLOW, err=True
        )
    typer.echo("\n--- Text Output ---\n")
    typer.echo(result.text)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host."),
    port: int = typer.Option(8765, "--port", "-p", help="Bind port."),
    vault_root: Optional[Path] = typer.Option(None, "--vault", help="Vault root."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Use the deterministic fake model — no network, no auth."
    ),
) -> None:
    """Serve the dashboard web UI and the lab API."""

    from marketing_engine.server.app import serve as serve_app

    settings = Settings.from_env(vault_root=vault_root)
    llm = FakeLLMClient() if dry_run else ClaudeAgentClient()
    if dry_run:
        typer.secho("Running with the fake model (--dry-run).", fg=typer.colors.YELLOW)
    serve_app(settings, host=host, port=port, llm=llm)


@app.command(name="list")
def list_brands(
    vault_root: Optional[Path] = typer.Option(None, "--vault", help="Vault root."),
) -> None:
    """List tenants and their brands discovered in the vault."""

    settings = Settings.from_env(vault_root=vault_root)
    engine = MarketingEngine(settings, llm=FakeLLMClient())
    tenants = engine.registry.list_tenants()
    if not tenants:
        typer.echo(f"No tenants found under {engine.layout.tenants_dir}")
        return
    for t in tenants:
        brands = ", ".join(engine.registry.list_brands(t)) or "(no brands)"
        typer.echo(f"{t}: {brands}")


if __name__ == "__main__":
    app()
