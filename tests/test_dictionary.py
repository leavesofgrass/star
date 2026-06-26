"""Direct unit tests for :mod:`star.dictionary` — offline definition lookup.

The deterministic surface (normalization, the custom-JSON backend, Markdown
formatting, and graceful degradation when nltk is absent) is always tested.
The WordNet/CMUdict lookups are guarded with skipif so they run locally once the
corpora are downloaded but skip on a lean CI runner — mirroring
``tests/test_features.py``'s optional-dependency pattern.
"""
import json

import pytest

from star import dictionary
from star.dictionary import (
    DefinitionResult,
    POSGroup,
    Sense,
    availability,
    define,
    format_definition_markdown,
)

_CORPUS = dictionary._wordnet() is not None  # WordNet corpus present?


class _Settings:
    """Minimal settings stub exposing only ``settings.get('dictionary_file')``."""

    def __init__(self, path=""):
        self._path = path

    def get(self, key, default=None):
        return self._path if key == "dictionary_file" else default


def _write_custom(tmp_path, mapping):
    p = tmp_path / "dict.json"
    p.write_text(json.dumps(mapping), encoding="utf-8")
    return str(p)


# ── normalization ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,norm",
    [
        ("Idiopathic", "idiopathic"),
        ("  (idiopathic).", "idiopathic"),
        ('"Word,"', "word"),
        ("CamelCase", "camelcase"),
        ("", ""),
        ("   ", ""),
    ],
)
def test_normalize(raw, norm):
    assert dictionary._normalize(raw) == norm


# ── custom-file backend (no corpus needed) ───────────────────────────────────


def test_custom_string_entry(tmp_path):
    s = _Settings(_write_custom(tmp_path, {"foo": "a plain definition"}))
    r = define("foo", s)
    assert r is not None
    assert r.source == "custom"
    assert r.groups[0].senses[0].definition == "a plain definition"


def test_custom_structured_entry(tmp_path):
    s = _Settings(_write_custom(tmp_path, {
        "idiopathic": {
            "pos": "adjective",
            "definition": "of unknown cause",
            "examples": ["idiopathic pain"],
            "synonyms": ["cryptogenic"],
            "pronunciation": "ID-ee-oh-PATH-ic",
        }
    }))
    r = define("Idiopathic.", s)  # normalization still finds it
    assert r.source == "custom"
    g = r.groups[0]
    assert g.pos == "adjective"
    assert g.senses[0].definition == "of unknown cause"
    assert g.senses[0].examples == ["idiopathic pain"]
    assert g.senses[0].synonyms == ["cryptogenic"]
    assert r.pronunciation == "ID-ee-oh-PATH-ic"


def test_custom_lookup_is_case_insensitive(tmp_path):
    s = _Settings(_write_custom(tmp_path, {"Aorta": "the main artery"}))
    assert define("AORTA", s).groups[0].senses[0].definition == "the main artery"


def test_custom_missing_word_falls_through(tmp_path, monkeypatch):
    # Word not in the custom file and nltk unavailable → no result.
    monkeypatch.setattr(dictionary, "_NLTK", False)
    s = _Settings(_write_custom(tmp_path, {"foo": "x"}))
    assert define("notinfile", s) is None


def test_bad_custom_file_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(dictionary, "_NLTK", False)
    p = tmp_path / "bad.json"
    p.write_text("{not valid json", encoding="utf-8")
    assert dictionary._load_custom_dictionary(str(p)) == {}
    assert define("anything", _Settings(str(p))) is None


# ── availability / graceful degradation ──────────────────────────────────────


def test_availability_without_nltk(monkeypatch):
    monkeypatch.setattr(dictionary, "_NLTK", False)
    ok, hint = availability(None)
    assert ok is False
    assert "nltk" in hint.lower()


def test_availability_custom_only_without_nltk(tmp_path, monkeypatch):
    monkeypatch.setattr(dictionary, "_NLTK", False)
    s = _Settings(_write_custom(tmp_path, {"foo": "x"}))
    ok, _hint = availability(s)
    assert ok is True  # a usable custom file is enough


def test_define_returns_none_without_backends(monkeypatch):
    monkeypatch.setattr(dictionary, "_NLTK", False)
    assert define("idiopathic", None) is None


def test_define_empty_word():
    assert define("", None) is None
    assert define("   ", None) is None


# ── Markdown formatting ───────────────────────────────────────────────────────


def test_format_definition_markdown_full():
    result = DefinitionResult(
        word="idiopathic",
        pronunciation="IH2 D IY0 AH0 P AE1 TH IH0 K",
        groups=[POSGroup(pos="adjective", senses=[
            Sense(definition="of unknown cause", examples=["idiopathic epilepsy"],
                  synonyms=["cryptogenic"]),
        ])],
        source="wordnet",
    )
    md = format_definition_markdown(result)
    assert md.startswith("# idiopathic")
    assert "IH2 D IY0 AH0 P AE1 TH IH0 K" in md
    assert "## adjective" in md
    assert "1. of unknown cause" in md
    assert "idiopathic epilepsy" in md
    assert "cryptogenic" in md
    assert "_Source: WordNet_" in md


def test_format_definition_markdown_custom_source():
    result = DefinitionResult(
        word="foo", groups=[POSGroup(pos="", senses=[Sense(definition="bar")])],
        source="custom",
    )
    md = format_definition_markdown(result)
    assert "1. bar" in md
    assert "_Source: custom dictionary_" in md


def test_format_definition_markdown_none():
    assert format_definition_markdown(None) == ""


# ── WordNet / CMUdict (skip when corpora not downloaded) ─────────────────────


@pytest.mark.skipif(not _CORPUS, reason="WordNet corpus not downloaded")
def test_define_idiopathic_wordnet():
    """Acceptance: 'idiopathic' resolves to its adjective sense offline."""
    r = define("idiopathic")
    assert r is not None and r.source == "wordnet"
    assert any(g.pos == "adjective" for g in r.groups)
    text = format_definition_markdown(r).lower()
    assert "unknown cause" in text


@pytest.mark.skipif(not _CORPUS, reason="WordNet corpus not downloaded")
def test_define_groups_by_part_of_speech():
    # "set" is the classic many-POS word: noun + verb at least.
    r = define("set")
    poses = {g.pos for g in r.groups}
    assert "noun" in poses and "verb" in poses


@pytest.mark.skipif(not _CORPUS, reason="WordNet corpus not downloaded")
def test_define_unknown_word_returns_none():
    assert define("zzzqxnotaword") is None


@pytest.mark.skipif(not _CORPUS, reason="WordNet corpus not downloaded")
def test_custom_file_wins_over_wordnet(tmp_path):
    s = _Settings(_write_custom(tmp_path, {"idiopathic": "CUSTOM definition"}))
    r = define("idiopathic", s)
    assert r.source == "custom"
    assert r.groups[0].senses[0].definition == "CUSTOM definition"
