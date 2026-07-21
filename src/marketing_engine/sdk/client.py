"""The LLM seam — the ONLY module that imports ``claude_agent_sdk``.

The harness talks to an ``LLMClient`` (a small protocol), never to the SDK
directly. Two implementations:

  * ``ClaudeAgentClient`` — drives the real Claude Agent SDK via ``query()``,
    with the brand isolation hook installed.
  * ``FakeLLMClient`` — deterministic, no network. Powers ``--dry-run`` and the
    offline test suite. It derives output from the system prompt + input so
    different brands produce different (but reproducible) copy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from marketing_engine.sdk.isolation import make_path_guard_hook


@dataclass
class AgentRunOptions:
    """Everything the harness needs to launch one agent run for one brand."""

    system_prompt: str
    cwd: Path
    add_dirs: list[Path] = field(default_factory=list)
    allowed_roots: list[Path] = field(default_factory=list)
    denied_roots: list[Path] = field(default_factory=list)  # blocked even inside allowed (e.g. _sources)
    allowed_tools: list[str] = field(default_factory=lambda: ["Read", "Grep", "Glob"])
    model: str | None = None
    mcp_servers: dict[str, Any] = field(default_factory=dict)
    max_turns: int = 30


@dataclass
class RunResult:
    """Outcome of a run. ``text`` is the agent's final copy."""

    text: str
    is_error: bool = False
    denied_paths: list[str] = field(default_factory=list)
    num_turns: int = 0
    model: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)  # token counts from the SDK


class LLMClient(Protocol):
    async def run(self, prompt: str, options: AgentRunOptions) -> RunResult: ...


class ClaudeAgentClient:
    """Real client: builds ``ClaudeAgentOptions`` and runs ``query()``."""

    async def run(self, prompt: str, options: AgentRunOptions) -> RunResult:
        # Imported lazily so importing the harness never requires the SDK
        # (keeps the rest of the package importable in minimal environments).
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            HookMatcher,
            ResultMessage,
            TextBlock,
            query,
        )

        denied: list[str] = []
        guard = make_path_guard_hook(
            options.allowed_roots or [options.cwd],
            denied,
            options.denied_roots,
            base_dir=options.cwd,  # resolve relative tool paths inside the brand folder
        )

        sdk_options = ClaudeAgentOptions(
            system_prompt=options.system_prompt,
            allowed_tools=options.allowed_tools,
            mcp_servers=options.mcp_servers,
            model=options.model,
            cwd=str(options.cwd),
            add_dirs=[str(p) for p in options.add_dirs],
            permission_mode="default",
            # Brand config is the source of truth; ignore ambient ~/.claude settings.
            setting_sources=[],
            max_turns=options.max_turns,
            hooks={"PreToolUse": [HookMatcher(hooks=[guard])]},
        )

        texts: list[str] = []
        num_turns = 0
        is_error = False
        usage: dict[str, Any] = {}
        try:
            async for message in query(prompt=prompt, options=sdk_options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            texts.append(block.text)
                elif isinstance(message, ResultMessage):
                    num_turns = message.num_turns
                    is_error = bool(message.is_error)
                    usage = _normalize_usage(message.usage)
                    if message.result and not texts:
                        texts.append(message.result)
        except Exception as exc:
            # e.g. "Reached maximum number of turns" — salvage any draft the
            # agent already produced rather than crashing the caller.
            is_error = not texts
            if not texts:
                texts.append(f"[generation error: {exc}]")

        return RunResult(
            text="\n\n".join(t for t in texts if t).strip(),
            is_error=is_error,
            denied_paths=denied,
            num_turns=num_turns,
            model=options.model,
            usage=usage,
        )


class FakeLLMClient:
    """Deterministic stand-in. No network, no SDK, no filesystem reads.

    Produces brand-differentiated copy by echoing salient lines from the
    assembled system prompt (which already carries the brand's identity, voice,
    and core-rules digest). Good enough to prove the end-to-end path and that
    different brands yield different output.
    """

    async def run(self, prompt: str, options: AgentRunOptions) -> RunResult:
        brand_line = _first_matching(options.system_prompt, "Brand:") or "Brand"
        if '"pass": true or false' in prompt:  # validator verdict
            import json

            return RunResult(text=json.dumps({"pass": True, "rule": "", "reason": ""}), model="fake")
        if "with this exact shape" in prompt:  # distillation mode
            import json

            return RunResult(
                text=json.dumps(
                    {
                        "core_narrative": "Distilled core narrative.",
                        "business_principles": ["Tangible backing", "Buy in small amounts"],
                        "customer_personas": ["Everyday family protecting savings"],
                        "customer_narratives": ["Prices keep rising and my savings erode"],
                        "trajectory": "Where the company is heading.",
                        "key_ideas": ["Idea A", "Idea B", "Idea C", "Idea D"],
                        "proof_points": ["Proof one", "Proof two"],
                        "avoid": ["Avoid this"],
                    }
                ),
                model=options.model or "fake",
            )
        if "## CANDIDATE POOL" in prompt:  # news scraper relevance/reliability filter
            import json

            return RunResult(
                text=json.dumps(
                    [
                        {
                            "title": "Inflation ticks up again, squeezing household budgets",
                            "url": "https://example.com/news/inflation",
                            "source": "Example Wire",
                            "date": "2026-06-10",
                            "summary": "Consumer prices rose again last month, with everyday essentials leading the increase.",
                            "principle": "purchasing-power protection",
                            "narrative": "prices keep rising and savings erode",
                            "angle": "Tie rising prices to the case for holding something real.",
                            "relevance": "high",
                        },
                        {
                            "title": "Unrelated celebrity gossip",
                            "url": "https://example.com/news/gossip",
                            "source": "Tabloid",
                            "date": "2026-06-09",
                            "summary": "Not relevant to the brand.",
                            "relevance": "low",
                        },
                    ]
                ),
                model=options.model or "fake",
            )
        if '"pivots_from_default"' in prompt:  # assignment extraction
            import json

            req = (_section(prompt, "OPERATOR REQUEST") or prompt.strip()).split("\n\n", 1)[0].strip()
            return RunResult(
                text=json.dumps(
                    {
                        "specific": bool(req),
                        "subject": req[:80],
                        "angle": "",
                        "audience": "",
                        "must_cover": [],
                        "pivots_from_default": False,
                    }
                ),
                model=options.model or "fake",
            )
        if "image SOURCE per option" in prompt:  # image recommendation
            import json

            return RunResult(
                text=json.dumps(
                    {
                        "recommendation": "Lead with a calm, tangible visual that feels trustworthy.",
                        "options": [
                            {"kind": "generated", "direction": "A clean chart showing steady monthly growth", "rationale": "makes the value tangible"},
                            {"kind": "real_photo", "direction": "A family at a kitchen table reviewing finances", "rationale": "grounds it in real life"},
                            {"kind": "library", "direction": "Brand shot of vaulted silver granules", "rationale": "reinforces physical backing"},
                        ],
                    }
                ),
                model=options.model or "fake",
            )
        if "## CANDIDATE IDEAS" in prompt:  # strategy filter → verdict per idea
            import json
            import re

            section = _section(prompt, "CANDIDATE IDEAS")
            n_ideas = len([ln for ln in section.splitlines() if re.match(r"\s*\d+\.", ln)])
            arr = [
                {
                    "i": k + 1,
                    "keep": True,
                    "principle": "tangible physical backing",
                    "persona": "everyday family",
                    "narrative": "prices keep rising and savings erode",
                    "reason": "ties a business principle to a felt customer story",
                }
                for k in range(n_ideas)
            ]
            return RunResult(text=json.dumps(arr), model=options.model or "fake")
        if "JSON array" in prompt:  # options mode → return a JSON array of ideas
            import json
            import re

            req = (_section(prompt, "REQUEST") or prompt.strip()).split("\n\n", 1)[0].strip()
            m = re.search(r"exactly (\d+)", prompt)
            count = int(m.group(1)) if m else 4
            opts = [f"Idea {i + 1} for: {req} ({brand_line})" for i in range(count)]
            return RunResult(text=json.dumps(opts), model=options.model or "fake")

        section = _section(prompt, "INPUT") or prompt.strip()
        # The INPUT section is followed by run instructions; the operator's
        # actual request is its first paragraph.
        request = section.split("\n\n", 1)[0].strip()
        brand_line = _first_matching(options.system_prompt, "Brand:")
        voice_line = _first_matching(options.system_prompt, "Voice:")
        rules = _section(options.system_prompt, "BRAND RULES")

        lines = [f"# {request}", ""]
        if brand_line:
            lines.append(f"_{brand_line}_")
        lines.append("")
        lines.append(f"Here is on-brand copy for: {request}.")
        if voice_line:
            lines.append(f"Written in the brand's voice — {voice_line.removeprefix('Voice:').strip()}.")
        if rules:
            first_rule = next((ln.strip("-* ").strip() for ln in rules.splitlines() if ln.strip()), "")
            if first_rule:
                lines.append(f"Honouring the rule: {first_rule}")
        return RunResult(text="\n".join(lines).strip(), model=options.model or "fake")


def _normalize_usage(usage: Any) -> dict[str, Any]:
    """Pull token counts out of the SDK usage object (dict or attrs)."""

    if not usage:
        return {}
    keys = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
    out: dict[str, Any] = {}
    for k in keys:
        v = usage.get(k) if isinstance(usage, dict) else getattr(usage, k, None)
        if v is not None:
            out[k] = v
    inp = out.get("input_tokens", 0) or 0
    cached = out.get("cache_read_input_tokens", 0) or 0
    out["total_tokens"] = inp + cached + (out.get("output_tokens", 0) or 0)
    return out


def _first_matching(text: str, prefix: str) -> str | None:
    for line in text.splitlines():
        if line.strip().startswith(prefix):
            return line.strip()
    return None


def _section(text: str, header: str) -> str:
    """Extract the body under a ``## HEADER`` or ``HEADER`` marker line."""

    lines = text.splitlines()
    body: list[str] = []
    capturing = False
    for line in lines:
        stripped = line.strip().lstrip("#").strip()
        if not capturing and stripped.upper() == header.upper():
            capturing = True
            continue
        if capturing:
            if line.strip().startswith("#") and line.strip().lstrip("#").strip():
                break
            body.append(line)
    return "\n".join(body).strip()
