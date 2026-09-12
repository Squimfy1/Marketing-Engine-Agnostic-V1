from __future__ import annotations

import pytest

from marketing_engine.inputs.convert import ConvertError, convert, pdf_to_text


def test_text_passthrough():
    c = convert("notes.md", text="# Hello")
    assert c.name == "notes.md" and c.content == "# Hello" and c.note == ""


def test_pdf_extracted_to_markdown(pdf_factory):
    data = pdf_factory("Acme builds AI research tools")
    assert "Acme builds AI research tools" in pdf_to_text(data)
    c = convert("paper.pdf", data=data)
    assert c.name == "paper.md"
    assert "Acme builds AI research tools" in c.content
    assert c.note == ""


def test_scanned_pdf_notes_no_text(pdf_factory):
    c = convert("scan.pdf", data=pdf_factory(""))
    assert c.name == "scan.md"
    assert "no extractable text" in c.note


def test_unsupported_type_raises():
    with pytest.raises(ConvertError):
        convert("deck.pptx", data=b"x")
