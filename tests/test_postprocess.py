from __future__ import annotations

from marketing_engine.postprocess import clean_copy


def test_em_dash_becomes_comma():
    assert clean_copy("metal—the same metals") == "metal, the same metals"
    assert clean_copy("backing — no depeg") == "backing, no depeg"
    assert "—" not in clean_copy("a—b — c—d")


def test_en_dash_range_becomes_hyphen():
    assert clean_copy("250–500 CHF") == "250-500 CHF"
    assert "–" not in clean_copy("3–5%")


def test_tidies_spacing_and_punctuation():
    assert clean_copy("word  ,  next") == "word, next"
    assert "  " not in clean_copy("a   b    c")


def test_empty_safe():
    assert clean_copy("") == ""
