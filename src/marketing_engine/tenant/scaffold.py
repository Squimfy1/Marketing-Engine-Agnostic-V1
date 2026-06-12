"""Create a new client brand and ingest its source material.

Keeps brand-onboarding a one-liner: ``create_brand`` lays down the standard
folder structure + a placeholder ``brand.yaml`` the operator fills in;
``ingest_files`` drops a client's markdown/text source files into ``_kb/`` so
the agent can ground generations in real material.
"""

from __future__ import annotations

from pathlib import Path

from marketing_engine.inputs.convert import SUPPORTED_EXTS, ConvertError, convert
from marketing_engine.vault.layout import BRAND_SUBDIRS, VaultLayout

INGESTIBLE = SUPPORTED_EXTS

_BRAND_YAML = """\
id: {brand_id}
name: {name}
# Fill these in (or let the loaded _kb material inform them).
identity: "{name} — what the company does, who it serves, its positioning."
voice: "{name}'s tone of voice — register, personality, what to avoid."
models:
  default: claude-opus-4-8
  ideas: claude-haiku-4-5-20251001
"""

_CORE_RULES = """\
# Core rules — {name}

Always-on constraints. Shared writing rules in `_shared/rules/` apply on top.

- Stay on {name}'s voice and positioning.
- Ground claims in `_kb/`; do not invent facts.
- Lead with concrete value; end with a clear call to action.
"""

_KB_README = """\
# Knowledge Base — {name}

Drop {name}'s source material here as Markdown (`.md`) or text (`.txt`):
white papers, articles, research, product notes. The engine reads these when
generating. One topic per file; clear filenames help.
"""

_DASHBOARD = """\
# Dashboard — {name}

## Input

<!-- Describe the marketing content you want for {name}. -->

## Text Output

## Status
"""


class ScaffoldError(Exception):
    pass


def create_brand(
    layout: VaultLayout, tenant_id: str, brand_id: str, *, name: str | None = None
) -> Path:
    """Scaffold a brand (and its tenant if absent). Returns the brand dir.

    Raises ``ScaffoldError`` if the brand already exists.
    """

    name = name or brand_id
    brand_dir = layout.brand_dir(tenant_id, brand_id)
    if layout.brand_config(tenant_id, brand_id).is_file():
        raise ScaffoldError(f"Brand '{tenant_id}/{brand_id}' already exists at {brand_dir}")

    tenant_cfg = layout.tenant_config(tenant_id)
    if not tenant_cfg.is_file():
        tenant_cfg.parent.mkdir(parents=True, exist_ok=True)
        tenant_cfg.write_text(
            f"id: {tenant_id}\nname: {tenant_id}\nplan: self-hosted\nnotes: \"\"\n",
            encoding="utf-8",
        )

    for sub in BRAND_SUBDIRS:
        (brand_dir / sub).mkdir(parents=True, exist_ok=True)
    layout.brand_config(tenant_id, brand_id).write_text(
        _BRAND_YAML.format(brand_id=brand_id, name=name), encoding="utf-8"
    )
    layout.core_rules(tenant_id, brand_id).write_text(
        _CORE_RULES.format(name=name), encoding="utf-8"
    )
    (layout.kb_dir(tenant_id, brand_id) / "README.md").write_text(
        _KB_README.format(name=name), encoding="utf-8"
    )
    layout.dashboard(tenant_id, brand_id).write_text(
        _DASHBOARD.format(name=name), encoding="utf-8"
    )
    return brand_dir


def ingest_files(
    layout: VaultLayout, tenant_id: str, brand_id: str, paths: list[Path], to: str = "_kb"
) -> tuple[list[str], list[str]]:
    """Copy markdown/text/pdf source files into the brand's ``to`` folder.

    ``to`` is ``_kb`` (public material, default) or ``_sources`` (raw transcripts
    the engine distills but never quotes). Returns ``(ingested_names,
    skipped_names)``. Raises ``ScaffoldError`` if the brand doesn't exist.
    """

    if not layout.brand_config(tenant_id, brand_id).is_file():
        raise ScaffoldError(f"No brand '{tenant_id}/{brand_id}' — create it first.")
    kb = layout.brand_dir(tenant_id, brand_id) / to
    kb.mkdir(parents=True, exist_ok=True)
    ingested: list[str] = []
    skipped: list[str] = []
    for src in paths:
        src = Path(src)
        if not src.is_file():
            skipped.append(f"{src.name} (not found)")
            continue
        if src.suffix.lower() not in INGESTIBLE:
            skipped.append(f"{src.name} (unsupported — convert to .md/.txt/.pdf)")
            continue
        try:
            result = convert(src.name, data=src.read_bytes())
        except ConvertError:
            skipped.append(f"{src.name} (could not convert)")
            continue
        (kb / result.name).write_text(result.content, encoding="utf-8")
        ingested.append(result.name)
    return ingested, skipped
