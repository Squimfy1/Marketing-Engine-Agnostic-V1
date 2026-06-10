"""M2 server: API handlers exercised directly (no sockets) against a tmp vault."""

from __future__ import annotations

import pytest

from marketing_engine.harness.engine import MarketingEngine
from marketing_engine.sdk.client import FakeLLMClient
from marketing_engine.server.routes import Api, _ref_of, split_ref
from marketing_engine.tools.learnings import LAB_LEARNINGS
from marketing_engine.vault.fs_adapter import FilesystemVaultAdapter


@pytest.fixture()
def api(settings) -> Api:
    return Api(MarketingEngine(settings, llm=FakeLLMClient()))


# -- ref parsing ---------------------------------------------------------
def test_ref_of_accepts_voice_or_brand():
    assert _ref_of({"brand": "t/b"}) == "t/b"
    assert _ref_of({"voice": "t/b"}) == "t/b"  # repurposed dashboard field
    assert _ref_of({"brand": "x/y", "voice": "ignored"}) == "x/y"


def test_split_ref_rejects_malformed():
    with pytest.raises(ValueError):
        split_ref("nobrand")


# -- discovery -----------------------------------------------------------
def test_list_brands(api: Api):
    status, payload = api.list_brands()
    assert status == 200
    refs = {b["ref"] for b in payload["brands"]}
    assert refs == {"acme-co/acme", "acme-co/globex"}


def test_platforms(api: Api):
    status, payload = api.platforms()
    assert status == 200
    assert {p["label"] for p in payload["platforms"]} == {"Short posts", "Articles"}


# -- bundle pack ---------------------------------------------------------
def test_bundle_pack_sections(api: Api):
    status, payload = api.bundle_pack({"brand": "acme-co/acme", "platform": "Short posts"})
    assert status == 200 and payload["ok"]
    titles = [s["title"] for s in payload["sections"]]
    assert any(t.startswith("BRAND: Acme") for t in titles)
    assert any(t.startswith("RULES:") for t in titles)
    assert any(t.startswith("PLATFORM: Short posts") for t in titles)
    assert payload["snapshot"]["brand"] == "acme"


def test_bundle_pack_bad_ref(api: Api):
    status, payload = api.bundle_pack({"brand": "nope"})
    assert status == 400 and not payload["ok"]


def test_bundle_pack_unknown_brand(api: Api):
    status, payload = api.bundle_pack({"brand": "acme-co/ghost"})
    assert status == 404


# -- generate ------------------------------------------------------------
def test_generate_via_voice_field(api: Api):
    status, payload = api.generate(
        {"voice": "acme-co/acme", "platform": "Short posts", "braindump": "Launch the Sky Pup"}
    )
    assert status == 200 and payload["ok"]
    assert "Sky Pup" in payload["text"] or "Launch" in payload["text"]
    assert payload["denied"] == []


def test_generate_differs_by_brand(api: Api):
    _, acme = api.generate({"brand": "acme-co/acme", "platform": "Short posts", "braindump": "x"})
    _, globex = api.generate({"brand": "acme-co/globex", "platform": "Short posts", "braindump": "x"})
    assert acme["text"] != globex["text"]


def test_generate_bad_ref(api: Api):
    status, payload = api.generate({"braindump": "x"})
    assert status == 400


# -- commit edits --------------------------------------------------------
def test_commit_edits_writes_draft_and_learning(api: Api):
    body = {
        "brand": "acme-co/acme",
        "platform": "Short posts",
        "content": "# Final copy\n\nShip it.",
        "original": "draft a",
        "edited": "draft b",
        "tips": ["tighten the hook"],
        "charDelta": -12,
        "topic": "sky pup launch",
    }
    status, payload = api.commit_edits(body)
    assert status == 200 and payload["ok"]
    assert payload["learningEntries"] == 1

    vault = FilesystemVaultAdapter(api.engine.layout, "acme-co", "acme")
    assert vault.exists(payload["path"])
    assert payload["path"].startswith("_outputs/")
    learn = vault.read(LAB_LEARNINGS)
    assert "tighten the hook" in learn and "Short posts" in learn


def test_commit_edits_empty_content(api: Api):
    status, payload = api.commit_edits({"brand": "acme-co/acme", "content": "   "})
    assert status == 400


# -- sessions ------------------------------------------------------------
def test_session_round_trip(api: Api):
    status, payload = api.session_post({"braindump": "hello", "brand": "acme-co/acme"})
    assert status == 200
    sid = payload["id"]
    status, loaded = api.session_get({"id": sid})
    assert status == 200
    assert loaded["braindump"] == "hello" and loaded["id"] == sid


def test_session_missing(api: Api):
    status, _ = api.session_get({"id": "does-not-exist"})
    assert status == 404


# -- status --------------------------------------------------------------
def test_status_endpoints_enable_generation(api: Api):
    assert api.anthropic_status()[1]["configured"] is True
    assert api.bridge_status()[1]["available"] is True
    assert api.engine_status()[1]["demo_ready"] is True
