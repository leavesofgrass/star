"""Tests for star.syllables — offline syllable splitting (Pyphen decoding aid).

Pure functions, no Qt.  When Pyphen is installed the transforms split words;
when it is absent every function degrades to an identity no-op.  The tests cover
both regimes: the availability-gated behavior is checked with a patched
hyphenator so they pass whether or not pyphen is on the machine.
"""
import pytest

from star import syllables


def _has_pyphen() -> bool:
    try:
        import pyphen  # noqa: F401
        return True
    except ImportError:
        return False


def test_constants_and_available_flag():
    assert syllables.MIDDOT == "·"
    # available() reflects the import-time detection.
    assert syllables.available() == _has_pyphen()


def test_empty_and_none_are_noops():
    assert syllables.syllabify_text("") == ""
    assert syllables.split_word("") == ""
    assert syllables.syllabify_html("") == ""


def test_missing_pyphen_is_identity(monkeypatch):
    """With no hyphenator, every transform returns its input unchanged."""
    monkeypatch.setattr(syllables, "_hyphenator", lambda lang=syllables._DEFAULT_LANG: None)
    text = "readability of syllables"
    assert syllables.syllabify_text(text) == text
    assert syllables.split_word("readability") == "readability"
    html = "<p>readability</p>"
    assert syllables.syllabify_html(html) == html


class _FakeHy:
    """A stand-in Pyphen that hyphenates on fixed internal boundaries."""

    _POINTS = {
        "readability": ["read", "abil", "i", "ty"],
        "hello": ["hel", "lo"],
        "syllables": ["syl", "la", "bles"],
    }

    def inserted(self, word, hyphen="·"):
        parts = self._POINTS.get(word.lower())
        if not parts:
            return word
        joined = hyphen.join(parts)
        # Real Pyphen preserves the original casing of each character.
        if word[:1].isupper():
            joined = joined[:1].upper() + joined[1:]
        return joined


@pytest.fixture
def fake_hy(monkeypatch):
    monkeypatch.setattr(syllables, "_hyphenator", lambda lang=syllables._DEFAULT_LANG: _FakeHy())


def test_split_word_inserts_middot(fake_hy):
    assert syllables.split_word("readability") == "read·abil·i·ty"
    # A word the dictionary doesn't split is returned unchanged.
    assert syllables.split_word("xyzzy") == "xyzzy"


def test_split_word_custom_separator(fake_hy):
    assert syllables.split_word("hello", sep="-") == "hel-lo"


def test_syllabify_text_preserves_non_words(fake_hy):
    out = syllables.syllabify_text("Hello, syllables!")
    assert out == "Hel·lo, syl·la·bles!"
    # Punctuation, spacing, and case boundaries are preserved.
    assert out.startswith("Hel·lo,")
    assert out.endswith("!")


def test_syllabify_text_leaves_digits_untouched(fake_hy):
    # Digits and standalone punctuation are never treated as words.
    assert syllables.syllabify_text("v2 3.14 --") == "v2 3.14 --"


def test_syllabify_html_skips_tags_entities_and_code(fake_hy):
    html = "<p>hello <code>hello()</code> &amp; <b>syllables</b></p>"
    out = syllables.syllabify_html(html)
    # Text inside <code> stays verbatim.
    assert "<code>hello()</code>" in out
    # Tags and the &amp; entity are untouched.
    assert out.startswith("<p>")
    assert "&amp;" in out
    # Body text runs are split.
    assert "hel·lo" in out
    assert "syl·la·bles" in out


def test_syllabify_html_skips_pre_blocks(fake_hy):
    html = "<pre>hello syllables</pre><p>hello</p>"
    out = syllables.syllabify_html(html)
    assert "<pre>hello syllables</pre>" in out  # verbatim
    assert "hel·lo</p>" in out             # split outside pre


@pytest.mark.skipif(not _has_pyphen(), reason="pyphen not installed")
def test_real_pyphen_splits_a_long_word():
    """Smoke-test the real library end-to-end when it's installed."""
    out = syllables.split_word("readability")
    assert syllables.MIDDOT in out
    # Stripping the separators recovers the original word.
    assert out.replace(syllables.MIDDOT, "") == "readability"


def test_syllables_wired_into_autodeps():
    from star import autodeps

    assert "syllables" in autodeps.FEATURES
    assert autodeps.FEATURES["syllables"] == [("pyphen", "pyphen")]
    assert "syllables" in autodeps.FEATURE_INFO
    # The stale-flag map flips star.syllables._PYPHEN after a runtime install.
    assert autodeps._FEATURE_FLAGS.get("syllables") == [("star.syllables", "_PYPHEN")]
