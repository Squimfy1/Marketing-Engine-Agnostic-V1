"""The Dashboard.md control surface — the Milestone 1 frontend.

The dashboard is a markdown note with ``## Section`` headings. The operator
writes under ``## Input``; the engine writes under ``## Text Output`` and
``## Status``. Parsing/writing preserves every other section verbatim so the
operator's note is never clobbered.
"""

from __future__ import annotations

import re

from marketing_engine.vault.adapter import VaultAdapter
from marketing_engine.vault.layout import DASHBOARD_FILE

INPUT = "Input"
TEXT_OUTPUT = "Text Output"
STATUS = "Status"

_H2 = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)

DEFAULT_DASHBOARD = """\
# Dashboard

## Input

<!-- Describe the marketing content you want. -->

## Text Output

## Status
"""


def parse_sections(text: str) -> dict[str, str]:
    """Map ``## Heading`` -> body (text until the next ``##`` or EOF)."""

    sections: dict[str, str] = {}
    matches = list(_H2.finditer(text))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[title] = text[start:end].strip("\n")
    return sections


def get_section(text: str, title: str) -> str | None:
    body = parse_sections(text).get(title)
    return body.strip() if body is not None else None


def set_section(text: str, title: str, body: str) -> str:
    """Replace the body under ``## title``; append the section if it's missing."""

    body = body.rstrip("\n")
    matches = list(_H2.finditer(text))
    for i, m in enumerate(matches):
        if m.group(1).strip() == title:
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            replacement = f"\n\n{body}\n\n" if body else "\n\n"
            return text[:start] + replacement + text[end:]
    sep = "" if text.endswith("\n") else "\n"
    return f"{text}{sep}\n## {title}\n\n{body}\n"


class Dashboard:
    """Read/write helper bound to a brand's Dashboard.md via a vault adapter."""

    def __init__(self, vault: VaultAdapter, relpath: str = DASHBOARD_FILE) -> None:
        self.vault = vault
        self.relpath = relpath

    def _text(self) -> str:
        if self.vault.exists(self.relpath):
            return self.vault.read(self.relpath)
        return DEFAULT_DASHBOARD

    def read_input(self) -> str:
        body = get_section(self._text(), INPUT) or ""
        # Drop HTML comment placeholders so an untouched template reads as empty.
        cleaned = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip()
        return cleaned

    def write_text_output(self, content: str) -> None:
        self.vault.write(self.relpath, set_section(self._text(), TEXT_OUTPUT, content))

    def set_status(self, status: str) -> None:
        self.vault.write(self.relpath, set_section(self._text(), STATUS, status))
