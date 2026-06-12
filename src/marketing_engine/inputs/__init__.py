"""Integration connectors seam (Milestone 5).

Notion, Slack/Telegram, LinkedIn, Email, Call Transcripts, and the Scraper each
become a ``Connector`` that ingests into a brand's _kb/ or _memory/. In
Milestone 5 they are wired in as external ``mcp_servers``. Defined here as a
protocol so the harness can depend on the shape today.
"""

from __future__ import annotations

from typing import Protocol


class Connector(Protocol):
    name: str

    def ingest(self, tenant_id: str, brand_id: str) -> int:
        """Pull source data into the brand's vault; return items ingested."""
        ...
