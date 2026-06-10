"""API handlers — the V2 re-implementation of the V1 dashboard contract.

Handlers are plain methods returning ``(status, payload)`` so they can be unit
tested without sockets. ``app.py`` is the thin HTTP adapter over this class.

Every brand-touching call resolves ``(tenant, brand)`` from a ``"tenant/brand"``
reference and runs through the M1 ``Registry`` + ``FilesystemVaultAdapter``, so
generation and saves stay inside the selected brand's subtree.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from marketing_engine.harness.engine import EngineError, MarketingEngine
from marketing_engine.harness.platforms import PLATFORMS
from marketing_engine.server.bundle import assemble_bundle
from marketing_engine.tenant.registry import RegistryError
from marketing_engine.tools import learnings
from marketing_engine.vault.fs_adapter import FilesystemVaultAdapter

SESSIONS_DIRNAME = "_sessions"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def split_ref(ref: str | None) -> tuple[str, str]:
    """Split a ``"tenant/brand"`` reference. Raises ``ValueError`` if malformed."""

    if not ref or "/" not in ref:
        raise ValueError(f"Expected 'tenant/brand', got {ref!r}")
    tenant, brand = ref.split("/", 1)
    if not tenant or not brand:
        raise ValueError(f"Expected 'tenant/brand', got {ref!r}")
    return tenant, brand


def _ref_of(data: dict) -> str | None:
    """The brand reference, from `brand` or the repurposed `voice` field.

    The reused V1 dashboard carries the selected tenant/brand in `voice` (its
    `resolveVoice()` was repurposed), so we accept either key.
    """

    return data.get("brand") or data.get("voice")


@dataclass
class Api:
    engine: MarketingEngine

    # -- discovery -------------------------------------------------------
    def list_brands(self) -> tuple[int, dict]:
        reg = self.engine.registry
        items = []
        for t in reg.list_tenants():
            for b in reg.list_brands(t):
                cfg = reg.get_brand(t, b)
                items.append({"tenant": t, "brand": b, "name": cfg.name, "ref": f"{t}/{b}"})
        return 200, {"brands": items}

    def platforms(self) -> tuple[int, dict]:
        return 200, {"platforms": [{"id": p.id, "label": p.label} for p in PLATFORMS]}

    # -- context bundle --------------------------------------------------
    def bundle_pack(self, params: dict) -> tuple[int, dict]:
        try:
            tenant, brand = split_ref(_ref_of(params))
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc)}
        try:
            bundle = assemble_bundle(
                self.engine.layout,
                self.engine.registry,
                tenant_id=tenant,
                brand_id=brand,
                platform=params.get("platform"),
                intent=params.get("intent", "draft"),
                generated_at=_now(),
            )
        except RegistryError as exc:
            return 404, {"ok": False, "error": str(exc)}
        return 200, {"ok": True, **bundle}

    # -- generate --------------------------------------------------------
    def generate(self, body: dict) -> tuple[int, dict]:
        try:
            tenant, brand = split_ref(_ref_of(body))
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc)}
        braindump = body.get("braindump") or body.get("pickedTopic") or ""
        try:
            result = asyncio.run(
                self.engine.generate(
                    tenant,
                    brand,
                    braindump=braindump,
                    platform=body.get("platform"),
                    intent=body.get("labIntent", "draft"),
                )
            )
        except RegistryError as exc:
            return 404, {"ok": False, "error": str(exc)}
        except EngineError as exc:
            return 400, {"ok": False, "error": str(exc)}
        except Exception as exc:  # never leave the HTTP client with an empty body
            return 500, {"ok": False, "error": f"generate failed: {exc}"}
        return 200, {
            "ok": not result.is_error,
            "text": result.text,
            "model": result.model,
            "usage": {"num_turns": result.num_turns, **result.usage},
            "denied": result.denied_paths,
        }

    # -- commit edits ----------------------------------------------------
    def commit_edits(self, body: dict) -> tuple[int, dict]:
        try:
            tenant, brand = split_ref(_ref_of(body))
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc)}
        content = (body.get("content") or body.get("edited") or "").strip()
        if not content:
            return 400, {"ok": False, "error": "No content to save."}
        try:
            self.engine.registry.get_brand(tenant, brand)  # validate
        except RegistryError as exc:
            return 404, {"ok": False, "error": str(exc)}

        vault = FilesystemVaultAdapter(self.engine.layout, tenant, brand)
        result = learnings.commit(
            vault,
            content=content,
            platform=body.get("platform", "Short posts"),
            date_str=_today(),
            topic=body.get("topic"),
            summary=body.get("notes", ""),
            tips=body.get("tips") or [],
            original=body.get("original"),
            edited=body.get("edited"),
            char_delta=body.get("charDelta"),
        )
        return 200, {"ok": True, **result}

    # -- knowledge base (source uploads) ---------------------------------
    def kb_list(self, params: dict) -> tuple[int, dict]:
        try:
            tenant, brand = split_ref(_ref_of(params))
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc)}
        try:
            self.engine.registry.get_brand(tenant, brand)
        except RegistryError as exc:
            return 404, {"ok": False, "error": str(exc)}
        vault = FilesystemVaultAdapter(self.engine.layout, tenant, brand)
        files = [
            rel.split("/", 1)[1]
            for rel in vault.glob("_kb/*")
            if rel != "_kb/README.md"
        ]
        return 200, {"ok": True, "files": files}

    def kb_upload(self, body: dict) -> tuple[int, dict]:
        try:
            tenant, brand = split_ref(_ref_of(body))
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc)}
        try:
            self.engine.registry.get_brand(tenant, brand)
        except RegistryError as exc:
            return 404, {"ok": False, "error": str(exc)}
        files = body.get("files") or []
        vault = FilesystemVaultAdapter(self.engine.layout, tenant, brand)
        ingested, skipped = [], []
        for f in files:
            name = os.path.basename((f.get("name") or "").strip())
            content = f.get("content")
            if not name or content is None:
                continue
            if os.path.splitext(name)[1].lower() not in (".md", ".txt", ".markdown"):
                skipped.append(name)
                continue
            try:
                vault.write(f"_kb/{name}", content)
                ingested.append(name)
            except PermissionError:
                skipped.append(name)
        return 200, {"ok": True, "ingested": ingested, "skipped": skipped}

    # -- sessions (server-managed UI state) ------------------------------
    def _sessions_dir(self) -> Path:
        d = self.engine.layout.root / SESSIONS_DIRNAME
        d.mkdir(parents=True, exist_ok=True)
        return d

    def session_post(self, body: dict) -> tuple[int, dict]:
        sid = body.get("id") or uuid.uuid4().hex
        path = self._sessions_dir() / f"{sid}.json"
        existing = {}
        if path.is_file():
            existing = json.loads(path.read_text(encoding="utf-8"))
        existing.update(body)
        existing["id"] = sid
        existing["updatedAt"] = _now()
        path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        return 200, {"ok": True, "id": sid, "updatedAt": existing["updatedAt"]}

    def session_get(self, params: dict) -> tuple[int, dict]:
        sid = params.get("id", "")
        path = self._sessions_dir() / f"{sid}.json"
        if not sid or not path.is_file():
            return 404, {"ok": False, "error": "session not found"}
        return 200, json.loads(path.read_text(encoding="utf-8"))

    # -- status badges (so the UI renders; generation is always available) --
    def anthropic_status(self) -> tuple[int, dict]:
        return 200, {"configured": True, "model": self.engine.settings.default_model}

    def bridge_status(self) -> tuple[int, dict]:
        return 200, {"available": True, "watcher": "claude-code"}

    def engine_status(self) -> tuple[int, dict]:
        return 200, {"demo_ready": True, "auth": "claude-code"}

    def not_implemented(self, name: str) -> tuple[int, dict]:
        return 501, {"ok": False, "error": f"{name} is deferred to a later milestone"}
