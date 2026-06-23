"""Unit tests for the v0.1.7 feature modules: translation, feeds, and the
difficult-word overlay.

The pure logic of each module is tested directly.  Where the optional package
is installed the real behavior is checked; where it is absent the
graceful-degradation contract is checked instead — the function must raise a
clear ``RuntimeError`` with an install hint (translation) or return an empty
result (vocabulary), never an ``ImportError`` or ``NameError``.
"""

import pytest

from star import feeds, translate, vocab


# ── Vocabulary (wordfreq) ──────────────────────────────────────────────────


def test_find_difficult_words_absent_returns_empty(monkeypatch):
    """Without wordfreq the overlay must degrade to "nothing flagged"."""
    monkeypatch.setattr(vocab, "_WORDFREQ", False)
    assert vocab.find_difficult_words("idiopathic thrombocytopenia") == set()


def test_find_difficult_words_empty_text():
    assert vocab.find_difficult_words("") == set()


@pytest.mark.skipif(not vocab._WORDFREQ, reason="wordfreq not installed")
def test_find_difficult_words_flags_rare_not_common():
    text = (
        "The patient presented with idiopathic thrombocytopenia and the nurse "
        "documented the etiology."
    )
    hard = vocab.find_difficult_words(text)
    assert {"idiopathic", "thrombocytopenia", "etiology"} <= hard
    # Common and short words are never flagged.
    assert "the" not in hard and "with" not in hard and "and" not in hard


@pytest.mark.skipif(not vocab._WORDFREQ, reason="wordfreq not installed")
def test_find_difficult_words_threshold_monotonic():
    text = "The patient presented with idiopathic thrombocytopenia etiology."
    lenient = vocab.find_difficult_words(text, threshold=3.0)
    strict = vocab.find_difficult_words(text, threshold=6.0)
    # A higher threshold flags at least as many words as a lower one.
    assert lenient <= strict


def test_find_difficult_words_skips_short_words(monkeypatch):
    if not vocab._WORDFREQ:
        pytest.skip("wordfreq not installed")
    # "qi" is rare but below the minimum length, so it must be ignored.
    assert "qi" not in vocab.find_difficult_words("qi qi qi")


# ── Translation (deep-translator) ──────────────────────────────────────────


def test_translate_absent_raises_with_hint(monkeypatch):
    monkeypatch.setattr(translate, "_DEEP_TRANSLATOR", False)
    with pytest.raises(RuntimeError) as exc:
        translate.translate_text("hello", target_lang="es")
    assert "deep-translator" in str(exc.value)


def test_translate_empty_short_circuits():
    # Empty input returns "" without needing the package or a network call.
    assert translate.translate_text("") == ""
    assert translate.translate_text("   ") == ""


def test_common_languages_well_formed():
    assert len(translate.COMMON_LANGUAGES) >= 12
    codes = [code for _name, code in translate.COMMON_LANGUAGES]
    assert len(codes) == len(set(codes)), "duplicate language codes"
    assert ("English", "en") in translate.COMMON_LANGUAGES


# ── Feeds (feedparser) ─────────────────────────────────────────────────────


def test_fetch_feed_absent_raises_with_hint(monkeypatch):
    monkeypatch.setattr(feeds, "_FEEDPARSER", False)
    with pytest.raises(RuntimeError) as exc:
        feeds.fetch_feed("http://example.com/rss")
    assert "feedparser" in str(exc.value)


@pytest.mark.skipif(not feeds._FEEDPARSER, reason="feedparser not installed")
def test_fetch_feed_maps_entries(monkeypatch):
    import feedparser

    rss = """<?xml version="1.0"?>
    <rss version="2.0"><channel><title>T</title>
      <item>
        <title>Article One</title>
        <link>https://example.com/1</link>
        <description>Summary one</description>
        <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
      </item>
      <item>
        <title>Article Two</title>
        <link>https://example.com/2</link>
      </item>
      <item>
        <title>No Link — skipped</title>
      </item>
    </channel></rss>"""

    # fetch_feed passes a URL to feedparser.parse; intercept and parse our text
    # via the *original* parser (capture it before patching to avoid recursion).
    real_parse = feedparser.parse
    monkeypatch.setattr(feedparser, "parse", lambda _url: real_parse(rss))
    entries = feeds.fetch_feed("ignored")

    # The link-less entry is dropped; the rest map field-for-field.
    assert len(entries) == 2
    assert entries[0] == {
        "title": "Article One",
        "url": "https://example.com/1",
        "summary": "Summary one",
        "published": "Mon, 01 Jan 2024 00:00:00 GMT",
    }
    assert entries[1]["title"] == "Article Two"
    assert entries[1]["url"] == "https://example.com/2"
    assert entries[1]["summary"] == ""
    assert entries[1]["published"] == ""


@pytest.mark.skipif(not feeds._FEEDPARSER, reason="feedparser not installed")
def test_fetch_feed_caps_entries(monkeypatch):
    import feedparser

    items = "".join(
        f"<item><title>A{i}</title><link>https://e/{i}</link></item>"
        for i in range(120)
    )
    rss = f'<?xml version="1.0"?><rss version="2.0"><channel>{items}</channel></rss>'
    real_parse = feedparser.parse
    monkeypatch.setattr(feedparser, "parse", lambda _url: real_parse(rss))
    entries = feeds.fetch_feed("ignored")
    assert len(entries) == feeds._MAX_ENTRIES == 50
