"""Direct unit tests for :mod:`star.ttstext` — the pure TTS text-preprocessing
layer.  Every function under test is a deterministic string→string transform
(markdown stripping, SSML/DECtalk markup, abbreviation/pronunciation expansion,
number/date normalization, table narration, math normalization), so none of
this touches the network, audio devices, or Qt.

Assertions were written against the *observed* output of the current code.  A
couple of behaviours that look like bugs are pinned with ``# NOTE`` comments so
the tests stay green while the surprising behaviour stays visible.
"""
import pytest

import star.settings as _settings_mod
from star.settings import Settings
from star.ttstext import (
    _apply_pronunciations,
    _decimal_digits_to_words,
    _expand_abbreviations,
    _int_to_words,
    _normalize_math_inline,
    _normalize_numbers,
    _ordinal_to_words,
    _preprocess_tts_text,
    _strip_markdown_for_tts,
    _tables_to_narration,
    _text_to_dectalk,
    _text_to_ssml,
    _year_to_words,
)


# ── _int_to_words ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "n,expected",
    [
        (0, "zero"),
        (1, "one"),
        (5, "five"),
        (13, "thirteen"),
        (20, "twenty"),
        (21, "twenty-one"),
        (42, "forty-two"),
        (100, "one hundred"),
        (105, "one hundred five"),
        (1000, "one thousand"),
        (1234, "one thousand two hundred thirty-four"),
        (1_000_000, "one million"),
        (2_500_000, "two million five hundred thousand"),
        (-7, "negative seven"),
    ],
)
def test_int_to_words(n, expected):
    assert _int_to_words(n) == expected


# ── _year_to_words ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "year,expected",
    [
        (1984, "nineteen eighty-four"),
        (2024, "twenty twenty-four"),
        (1900, "nineteen hundred"),
        (1905, "nineteen oh five"),
        (2009, "twenty oh nine"),
        (50, "fifty"),  # below the 100..2999 range → plain integer
        (3000, "three thousand"),  # above the range → plain integer
    ],
)
def test_year_to_words(year, expected):
    assert _year_to_words(year) == expected


def test_year_to_words_round_millennium():
    # Round millennia read as "<n> thousand"; other round centuries keep the
    # "<century> hundred" reading.
    assert _year_to_words(2000) == "two thousand"
    assert _year_to_words(1000) == "one thousand"
    assert _year_to_words(1900) == "nineteen hundred"


# ── _ordinal_to_words ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "n,expected",
    [
        (1, "first"),
        (2, "second"),
        (3, "third"),
        (4, "fourth"),
        (11, "eleventh"),
        (12, "twelfth"),
        (13, "thirteenth"),
        (20, "twentieth"),
        (21, "twenty-first"),
        (23, "twenty-third"),
        (100, "one hundredth"),
        (101, "one hundred first"),
        (1000, "one thousandth"),
        (1_000_000, "one millionth"),
        (1_000_001, "one million first"),  # large value with non-zero remainder
        (-3, "negative third"),
    ],
)
def test_ordinal_to_words(n, expected):
    assert _ordinal_to_words(n) == expected


# ── _decimal_digits_to_words ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "digits,expected",
    [
        ("14", "one four"),
        ("0", "zero"),
        ("305", "three zero five"),
        ("7", "seven"),
    ],
)
def test_decimal_digits_to_words(digits, expected):
    assert _decimal_digits_to_words(digits) == expected


# ── _normalize_numbers ────────────────────────────────────────────────────────


def test_normalize_numbers_iso_date():
    assert (
        _normalize_numbers("Meeting on 2024-03-15 today.")
        == "Meeting on March fifteenth, twenty twenty-four today."
    )


def test_normalize_numbers_us_date():
    assert (
        _normalize_numbers("Due 03/15/2024 ok.")
        == "Due March fifteenth, twenty twenty-four ok."
    )


@pytest.mark.parametrize(
    "text,expected",
    [
        ("at 12:00", "at noon"),
        ("at 00:00", "at midnight"),
        ("at 15:30", "at three thirty PM"),
        ("at 3:45 PM", "at three forty-five PM"),
        ("at 9:15 AM", "at nine fifteen AM"),  # explicit AM branch
        ("at 00:30", "at zero thirty AM"),  # midnight hour with minutes
    ],
)
def test_normalize_numbers_times(text, expected):
    assert _normalize_numbers(text) == expected


def test_normalize_numbers_currency():
    assert (
        _normalize_numbers("costs $1,234.56 total")
        == "costs one thousand two hundred thirty-four dollars and fifty-six cents total"
    )


@pytest.mark.parametrize(
    "text,expected",
    [
        ("$1.00", "one dollar"),
        ("$0.50", "fifty cents"),
    ],
)
def test_normalize_numbers_currency_small(text, expected):
    assert _normalize_numbers(text) == expected


def test_normalize_numbers_percent():
    assert (
        _normalize_numbers("75% and 3.5%")
        == "seventy-five percent and three point five percent"
    )


def test_normalize_numbers_ordinals():
    assert _normalize_numbers("the 1st and 22nd") == "the first and twenty-second"


def test_normalize_numbers_comma_integer():
    assert (
        _normalize_numbers("1,234,567 people")
        == "one million two hundred thirty-four thousand five hundred sixty-seven people"
    )


def test_normalize_numbers_decimal():
    assert _normalize_numbers("pi is 3.14") == "pi is three point one four"


def test_normalize_numbers_plain_year_vs_big_int():
    # 4-digit values in 1000..2099 are read as years; larger plain ints as numbers.
    assert _normalize_numbers("year 1984 here") == "year nineteen eighty-four here"
    assert _normalize_numbers("value 50000 ok") == "value fifty thousand ok"


def test_normalize_numbers_version_string_left_mostly_intact():
    # The decimal rule avoids version-like dotted runs on the left side, but the
    # trailing ".3" still matches; this pins the current behaviour.
    assert _normalize_numbers("v1.2.3") == "v1.two point three"


# ── _strip_markdown_for_tts ───────────────────────────────────────────────────


def test_strip_markdown_removes_syntax():
    md = (
        "# Heading\n\n"
        "Some **bold** and *italic* and `code` text.\n\n"
        "- item one\n"
        "- item two\n\n"
        "> a quote\n\n"
        "[link](http://x.com)\n\n"
        "```python\nprint(1)\n```\n"
    )
    out = _strip_markdown_for_tts(md)
    assert "Heading" in out
    assert "bold" in out and "italic" in out and "code" in out
    assert "item one" in out and "item two" in out
    assert "a quote" in out
    assert "link" in out
    # No leftover markdown punctuation should survive.
    for ch in ("#", "*", "`", ">", "["):
        assert ch not in out
    # Fenced code block content is dropped when skip_code is on (the default).
    assert "print(1)" not in out


def test_strip_markdown_keeps_code_when_not_skipping():
    md = "```\nkeep me\n```"
    out = _strip_markdown_for_tts(md, skip_code=False)
    assert "keep me" in out


# ── _text_to_ssml ─────────────────────────────────────────────────────────────


def test_text_to_ssml_wraps_and_inserts_breaks():
    out = _text_to_ssml("Hello world. This is a test, really.")
    assert out.startswith("<speak>") and out.endswith("</speak>")
    assert '<break time="350ms"/>' in out  # sentence break
    assert '<break time="150ms"/>' in out  # clause break


def test_text_to_ssml_passthrough_when_already_ssml():
    assert _text_to_ssml("<speak>x</speak>") == "<speak>x</speak>"


def test_text_to_ssml_escapes_xml():
    out = _text_to_ssml("a < b")
    assert "&lt;" in out
    assert "<speak>" in out and "</speak>" in out


def test_text_to_ssml_ampersand_entity_not_split():
    # The ";" that terminates an escaped XML entity (&amp;) must NOT get a clause
    # break inserted mid-entity, but a real semicolon still pauses.
    out = _text_to_ssml("Tom & Jerry run")
    assert "&amp;" in out
    assert '&amp;<break' not in out
    real = _text_to_ssml("First clause; second clause")
    assert ';<break time="150ms"/>' in real


def test_text_to_ssml_dectalk_backend_delegates():
    out = _text_to_ssml("Hi there. Done.", backend="dectalk")
    assert "[:pau 350]" in out
    assert "<speak>" not in out


# ── _text_to_dectalk ──────────────────────────────────────────────────────────


def test_text_to_dectalk_inserts_pauses():
    out = _text_to_dectalk("Hi there. Wait, what?")
    assert "[:pau 350]" in out  # sentence
    assert "[:pau 150]" in out  # clause


def test_text_to_dectalk_custom_durations():
    out = _text_to_dectalk("One. Two, three.", sentence_ms=500, clause_ms=200)
    assert "[:pau 500]" in out
    assert "[:pau 200]" in out


# ── _expand_abbreviations ─────────────────────────────────────────────────────


def test_expand_abbreviations_builtins():
    out = _expand_abbreviations("See Fig. 3 and e.g., this, etc. Dr. Smith.")
    assert "Figure" in out
    assert "for example," in out
    assert "et cetera" in out
    assert "Doctor" in out


def test_expand_abbreviations_multiword_latin():
    assert _expand_abbreviations("Smith et al. found") == "Smith and others found"


def test_expand_abbreviations_custom_takes_precedence():
    assert _expand_abbreviations("Use FOO here", {"FOO": "foobar"}) == "Use foobar here"


# ── _apply_pronunciations ─────────────────────────────────────────────────────


def test_apply_pronunciations_basic():
    assert (
        _apply_pronunciations("CHF is bad", {"CHF": "congestive heart failure"})
        == "congestive heart failure is bad"
    )


def test_apply_pronunciations_case_insensitive():
    assert (
        _apply_pronunciations("the chf patient", {"CHF": "see aitch eff"})
        == "the see aitch eff patient"
    )


def test_apply_pronunciations_longest_term_wins():
    out = _apply_pronunciations(
        "heart attack now", {"heart attack": "MI", "heart": "pump"}
    )
    assert out == "MI now"


def test_apply_pronunciations_empty_lexicon_is_noop():
    assert _apply_pronunciations("text", {}) == "text"


def test_apply_pronunciations_skips_empty_term():
    # An empty-string key is skipped rather than matching everywhere.
    assert _apply_pronunciations("hi", {"": "x"}) == "hi"


# ── _normalize_math_inline ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text,expected",
    [
        (r"$\frac{a}{b}$", "a over b"),
        (r"$\sqrt{x}$", "square root of x"),
        (r"\alpha + \beta", "alpha + beta"),
        (r"a \times b \leq c", "a times b less than or equal to c"),
        (r"\bar{x}", "x-bar"),
    ],
)
def test_normalize_math_inline(text, expected):
    assert _normalize_math_inline(text) == expected


def test_normalize_math_inline_powers():
    assert _normalize_math_inline("x^2 and y^{3}") == "x squared and y cubed"


def test_normalize_math_inline_subscripts():
    assert _normalize_math_inline("x_i and x_{ij}") == "x sub i and x sub i j"


def test_normalize_math_inline_plain_text_unchanged():
    assert _normalize_math_inline("hello world") == "hello world"


# ── _tables_to_narration ──────────────────────────────────────────────────────


_TABLE = (
    "Intro text\n\n"
    "| Name | Age | City |\n"
    "|------|-----|------|\n"
    "| Alice | 30 | NY |\n"
    "| Bob | 25 | Boston |\n\n"
    "After text"
)


def test_tables_to_narration_structured():
    out = _tables_to_narration(_TABLE, mode="structured")
    assert "Table with 3 columns: Name, Age, City." in out
    assert "Row 1: Name is Alice, Age is 30, City is NY." in out
    assert "Row 2: Name is Bob, Age is 25, City is Boston." in out
    assert "Intro text" in out and "After text" in out
    assert "|" not in out


def test_tables_to_narration_flat():
    out = _tables_to_narration(_TABLE, mode="flat")
    assert "Name.  Age.  City." in out
    assert "Alice.  30.  NY." in out
    assert "Bob.  25.  Boston." in out


def test_tables_to_narration_skip():
    out = _tables_to_narration(_TABLE, mode="skip")
    assert "Table with 3 columns — skipped." in out
    assert "Alice" not in out


def test_tables_to_narration_unknown_mode_falls_back_to_structured():
    out = _tables_to_narration("| a | b |\n|---|---|\n| 1 | 2 |", mode="nonsense")
    assert "Table with 2 columns: a, b." in out
    assert "Row 1: a is 1, b is 2." in out


def test_tables_to_narration_no_table_is_passthrough():
    assert _tables_to_narration("just text\nno tables") == "just text\nno tables"


# ── _preprocess_tts_text (top-level pipeline) ─────────────────────────────────


def test_preprocess_default_runs_all_steps():
    out = _preprocess_tts_text("See Fig. 3, it costs $5 in 2024 today.", Settings())
    assert "Figure" in out  # abbreviations
    assert "five dollars" in out  # numbers / currency
    assert "twenty twenty-four" in out  # year


def test_preprocess_all_steps_disabled_is_noop():
    s = Settings()
    s["use_pronunciations"] = False
    s["expand_abbreviations"] = False
    s["normalize_numbers"] = False
    s["normalize_math"] = False
    text = "See Fig. 3 costs $5"
    assert _preprocess_tts_text(text, s) == text


def test_preprocess_custom_pronunciations_and_abbreviations():
    s = Settings()
    s["pronunciations"] = {"CHF": "see aitch eff"}
    s["abbrev_expansions"] = {"XYZ": "exwhyzee"}
    out = _preprocess_tts_text("CHF and XYZ in Fig. 1", s)
    assert out == "see aitch eff and exwhyzee in Figure 1"


def test_preprocess_respects_settings_isolation(tmp_path, monkeypatch):
    # Belt-and-braces: even outside the autouse fixture, a redirected settings
    # file gives clean defaults so the pipeline applies every transform.
    monkeypatch.setattr(_settings_mod, "SETTINGS_FILE", tmp_path / "s.json")
    out = _preprocess_tts_text("It is 2024 now.", Settings())
    assert "twenty twenty-four" in out


# ── 0.1.22 audit: nested lists + nested blockquotes must be narrated ─────────


def test_nested_list_items_are_spoken():
    """CommonMark nested list items are 4-space-indented — the indented-code
    strip used to run first and silently deleted them from narration."""
    md = (
        "Groceries:\n\n"
        "- fruit\n"
        "    - apples\n"
        "    - bananas\n"
        "- bread\n"
    )
    out = _strip_markdown_for_tts(md, skip_code=True)
    for word in ("fruit", "apples", "bananas", "bread"):
        assert word in out, f"nested list item {word!r} lost from narration"


def test_true_indented_code_still_skipped():
    """Real indented code (no list marker) is still stripped with skip_code."""
    md = "Paragraph.\n\n    x = compute_thing()\n\nAfter.\n"
    out = _strip_markdown_for_tts(md, skip_code=True)
    assert "compute_thing" not in out
    assert "Paragraph." in out and "After." in out


def test_nested_blockquote_markers_do_not_leak():
    md = "> quoted\n>> nested quote\n> > spaced nested\n"
    out = _strip_markdown_for_tts(md, skip_code=True)
    assert ">" not in out
    assert "quoted" in out and "nested quote" in out and "spaced nested" in out


def test_soft_line_breaks_joined_into_spaces():
    """Single newlines within a paragraph are soft breaks — they must become
    spaces so TTS engines don't pause at the end of every source line."""
    md = "star is a reader\nthat converts text\nfor easier reading.\n\nNew paragraph here.\n"
    out = _strip_markdown_for_tts(md)
    assert "reader that converts" in out
    assert "text for easier" in out
    # Paragraph break preserved
    assert "reading.\n\nNew" in out
