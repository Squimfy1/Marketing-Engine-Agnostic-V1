from __future__ import annotations

from marketing_engine.postprocess import clean_copy, extract_json_list


def test_extract_json_list_plain():
    assert extract_json_list('["a", "b", "c"]') == ["a", "b", "c"]


def test_extract_json_list_ignores_preamble_and_fences():
    txt = 'Here are the ideas:\n```json\n["one", "two"]\n```\nHope that helps!'
    assert extract_json_list(txt) == ["one", "two"]


def test_extract_json_list_flattens_dicts():
    assert extract_json_list('[{"angle":"A","brief":"the brief"}]') == ["the brief"]


def test_extract_json_list_bad_input():
    assert extract_json_list("no json here") == []
    assert extract_json_list("") == []


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
