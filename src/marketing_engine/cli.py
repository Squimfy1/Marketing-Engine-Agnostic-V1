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


@app.command(name="new-brand")
def new_brand(
    tenant: str = typer.Option(..., "--tenant", "-t", help="Tenant (account) id."),
    brand: str = typer.Option(..., "--brand", "-b", help="Brand (client) id."),
    name: Optional[str] = typer.Option(None, "--name", help="Display name (defaults to brand id)."),
    vault_root: Optional[Path] = typer.Option(None, "--vault", help="Vault root."),
) -> None:
    """Scaffold a new client brand (folders + placeholder brand.yaml)."""

    from marketing_engine.tenant.scaffold import ScaffoldError, create_brand
    from marketing_engine.vault.layout import VaultLayout

    settings = Settings.from_env(vault_root=vault_root)
    layout = VaultLayout(settings.vault_root)
    try:
        brand_dir = create_brand(layout, tenant, brand, name=name)
    except ScaffoldError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    typer.secho(f"Created brand {tenant}/{brand} at {brand_dir}", fg=typer.colors.GREEN)
    typer.echo("Next: edit brand.yaml (identity + voice), then add source files to _kb/.")


@app.command()
def ingest(
    files: list[Path] = typer.Argument(..., help="Source files (.md / .txt / .pdf) to add."),
    tenant: str = typer.Option(..., "--tenant", "-t", help="Tenant id."),
    brand: str = typer.Option(..., "--brand", "-b", help="Brand id."),
    sources: bool = typer.Option(
        False, "--sources", "-s",
        help="Add to _sources/ (raw transcripts the engine distills but NEVER quotes) instead of _kb/.",
    ),
    vault_root: Optional[Path] = typer.Option(None, "--vault", help="Vault root."),
) -> None:
    """Copy source files into a brand's knowledge base (_kb/), or --sources for transcripts."""

    from marketing_engine.tenant.scaffold import ScaffoldError, ingest_files
    from marketing_engine.vault.layout import VaultLayout

    settings = Settings.from_env(vault_root=vault_root)
    layout = VaultLayout(settings.vault_root)
    dest = "_sources" if sources else "_kb"
    try:
        ingested, skipped = ingest_files(layout, tenant, brand, list(files), to=dest)
    except ScaffoldError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    typer.secho(f"Ingested {len(ingested)} file(s) into {tenant}/{brand}/{dest}/", fg=typer.colors.GREEN)
    for n in ingested:
        typer.echo(f"  + {n}")
    if skipped:
        typer.secho(f"Skipped {len(skipped)}:", fg=typer.colors.YELLOW)
        for n in skipped:
            typer.echo(f"  - {n}")


@app.command()
def distill(
    tenant: str = typer.Option(..., "--tenant", "-t", help="Tenant id."),
    brand: str = typer.Option(..., "--brand", "-b", help="Brand id."),
    vault_root: Optional[Path] = typer.Option(None, "--vault", help="Vault root."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Use the fake model (no network)."),
) -> None:
    """Distill a brand's _sources/ transcripts into a public-safe narrative profile."""

    from marketing_engine.content.distill import DistillError, distill as run_distill

    settings = Settings.from_env(vault_root=vault_root)
    llm = FakeLLMClient() if dry_run else ClaudeAgentClient()
    engine = MarketingEngine(settings, llm=llm)
    try:
        result = asyncio.run(run_distill(engine, tenant, brand))
    except (RegistryError, EngineError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    except DistillError as exc:
        typer.secho(str(exc), fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(code=1)
    typer.secho(f"Distilled {tenant}/{brand} ({result.model})", fg=typer.colors.GREEN)
    typer.echo(f"  Core narrative: {result.core_narrative}")
    typer.echo(f"  Key ideas: {len(result.key_ideas)} · proof points: {len(result.proof_points)}")
    for f in result.files_written:
        typer.echo(f"  wrote {f}")
    typer.echo("Review the written files, then generate.")


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
