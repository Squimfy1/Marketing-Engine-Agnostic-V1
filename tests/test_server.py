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
    assert {p["label"] for p in payload["platforms"]} == {"Short posts"}


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


# -- options -------------------------------------------------------------
def test_options_returns_four(api: Api):
    status, payload = api.options(
        {"voice": "acme-co/acme", "platform": "Short posts", "braindump": "Launch the Sky Pup", "n": 4}
    )
    assert status == 200 and payload["ok"]
    assert len(payload["options"]) == 4
    assert all(o["text"].strip() for o in payload["options"])  # rich idea objects
    assert payload["optionsText"] and all(t.strip() for t in payload["optionsText"])


def test_options_bad_ref(api: Api):
    status, _ = api.options({"braindump": "x"})
    assert status == 400


def test_version_reports_build(api: Api):
    status, payload = api.version()
    assert status == 200 and payload["ok"]
    assert "commit" in payload and "started" in payload  # staleness stamp


def test_image_options(api: Api):
    status, payload = api.image_options(
        {"voice": "acme-co/acme", "platform": "Short posts", "text": "Launch the Sky Pup kit."}
    )
    assert status == 200 and payload["ok"]
    assert payload["recommendation"].strip()
    assert len(payload["options"]) == 3
    kinds = {o["kind"] for o in payload["options"]}
    assert kinds <= {"library", "real_photo", "generated"}  # only valid source kinds
    assert all(o["direction"].strip() for o in payload["options"])


def test_image_brief(api: Api):
    status, payload = api.image_brief(
        {"voice": "acme-co/acme", "platform": "Short posts", "text": "Launch the Sky Pup kit."}
    )
    assert status == 200 and payload["ok"]
    assert payload["brief"].strip()


def test_image_brief_for_chosen_option(api: Api):
    # Passing a chosen kind/direction still returns a brief (built for that choice).
    status, payload = api.image_brief(
        {
            "voice": "acme-co/acme",
            "text": "Launch the Sky Pup kit.",
            "kind": "real_photo",
            "direction": "A family at a kitchen table",
        }
    )
    assert status == 200 and payload["ok"]
    assert payload["brief"].strip()


def test_image_brief_empty_text(api: Api):
    status, _ = api.image_brief({"voice": "acme-co/acme", "text": "  "})
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


# -- knowledge base upload ----------------------------------------------
def test_kb_upload_and_list(api: Api):
    status, payload = api.kb_upload({
        "brand": "acme-co/acme",
        "files": [
            {"name": "whitepaper.md", "content": "# WP\n\nFacts."},
            {"name": "notes.txt", "content": "more"},
            {"name": "deck.pdf", "content": "binary"},
            {"name": "../escape.md", "content": "nope"},
        ],
    })
    assert status == 200 and payload["ok"]
    assert set(payload["ingested"]) == {"whitepaper.md", "notes.txt", "escape.md"}  # basename'd
    assert "deck.pdf" in payload["skipped"]

    status, listing = api.kb_list({"brand": "acme-co/acme"})
    assert status == 200
    assert "whitepaper.md" in listing["files"] and "notes.txt" in listing["files"]


def test_kb_upload_unknown_brand(api: Api):
    status, _ = api.kb_upload({"brand": "acme-co/ghost", "files": []})
    assert status == 404


def test_kb_upload_pdf_converted(api: Api, pdf_factory):
    import base64
    b64 = base64.b64encode(pdf_factory("Denario whitepaper body")).decode()
    status, payload = api.kb_upload({
        "brand": "acme-co/acme",
        "files": [{"name": "whitepaper.pdf", "content_b64": b64}],
    })
    assert status == 200 and payload["ok"]
    assert "whitepaper.md" in payload["ingested"]  # pdf -> md
    from marketing_engine.vault.fs_adapter import FilesystemVaultAdapter
    vault = FilesystemVaultAdapter(api.engine.layout, "acme-co", "acme")
    assert "Denario whitepaper body" in vault.read("_kb/whitepaper.md")


# -- status --------------------------------------------------------------
def test_status_endpoints_enable_generation(api: Api):
    assert api.anthropic_status()[1]["configured"] is True
    assert api.bridge_status()[1]["available"] is True
    assert api.engine_status()[1]["demo_ready"] is True
