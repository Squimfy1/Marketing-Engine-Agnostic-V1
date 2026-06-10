# Marketing Engine (Agnostic V2)

A multi-tenant, brand-agnostic AI marketing-content engine built on the
[Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/python), with
**Obsidian as the knowledge base, memory, and control surface**.

One engine serves many **tenants** (accounts / agencies), each owning many
**brands**. A brand carries its own Knowledge Base, Rules, and design tokens —
nothing is hard-coded. A single company is just a one-brand tenant.

## How it works (Milestone 1)

The vault *is* the interface. Obsidian stores everything as markdown:

```
$VAULT_ROOT/
├── _shared/                          # cross-tenant templates / house style
└── tenants/<tenant_id>/
    ├── tenant.yaml
    └── brands/<brand_id>/
        ├── brand.yaml                # identity, voice, model policy
        ├── _kb/        _rules/        # Knowledge Base + Rules (agent reads these)
        ├── _memory/    _outputs/      # agent writes here
        ├── _design/tokens.yaml
        └── Dashboard.md              # your control surface
```

You write an `## Input` in `Dashboard.md`, run the engine, and it reads the
brand's KB + Rules, drafts on-brand copy, and writes the result back into
`## Text Output` plus a dated note in `_outputs/`.

The agent is **physically scoped** to one brand's subtree (`cwd`/`add_dirs` +
a `PreToolUse` path-allowlist hook), so it can never read or write another
brand's or tenant's data.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Auth:** no API key needed. The engine drives the Claude Code CLI, which uses
your existing Claude Code login. Make sure `claude` is installed and you're
logged in (`claude --version` should work).

## Usage

```bash
engine run --tenant acme-co --brand acme            # live run (uses your Claude Code login)
engine run --tenant acme-co --brand acme --dry-run  # fake model, no network, no auth
pytest                                              # full offline test suite
```

## Architecture

Hard seam rules keep the system testable without a live model:

- **only `sdk/`** imports `claude_agent_sdk`
- **only `vault/`** touches files on disk
- everything else depends on internal interfaces

See `~/.claude/plans/refactored-gliding-frost.md` for the full design and roadmap.
