"""Marketing Engine — agnostic, multi-tenant AI marketing-content engine.

One engine serves many tenants (accounts/agencies), each owning many brands.
Obsidian (a folder of markdown files) is the knowledge base, memory, and UI.

Seam rules:
  * only ``marketing_engine.sdk`` imports ``claude_agent_sdk``
  * only ``marketing_engine.vault`` touches files on disk
  * everything else depends on internal interfaces, so the system is testable
    without a live model.
"""

__version__ = "0.1.0"
