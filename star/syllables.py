"""Offline syllable splitting — a decoding aid built on Pyphen.

Pyphen is a pure-Python hyphenation library (bundled Hunspell/LibreOffice
dictionaries, OFL/GPL/LGPL tri-licensed).  star uses it to break long words into
their syllables so struggling readers can decode them piece by piece — the
familiar ``read·a·bil·i·ty`` presentation.

Optional feature: requires the ``pyphen`` package (``pip install pyphen``).  When
it is absent the module still imports cleanly with ``_PYPHEN = False`` and the
transforms degrade to no-ops, so the rest of star runs unchanged and the GUI
offers a one-click download instead of the pip command — the same graceful-
degradation pattern every other optional feature follows.

Everything here is pure and unit-testable: the functions take text in and return
text out, with the hyphenation object lazily created (and cached) on first use.
The public :func:`split_word` / :func:`syllabify_text` are **display-only** — the
plain text handed to TTS and the word map are built from the untransformed
document, so speech and highlighting are never affected.
"""
from __future__ import annotations

import re

from ._runtime import _module_available

# Detected cheaply at import; the Pyphen object itself is created lazily by
# _hyphenator() the first time a word is split, so importing this module never
# pulls Pyphen's dictionary loading into startup.
_PYPHEN = _module_available("pyphen")

# The visible separator inserted between syllables.  A middot (U+00B7) reads as a
# soft, non-intrusive break; callers may pass their own (the GUI stores it as a
# setting) so power users can prefer a hyphen or thin space.
MIDDOT = "·"

# star's documents are English; Pyphen keys dictionaries by locale.
_DEFAULT_LANG = "en_US"

# Cache one hyphenator per language so repeated calls don't rebuild the (small
# but non-trivial) pattern object.  Keyed by lang; value is the Pyphen instance
# or None when the language dictionary could not be loaded.
_HYPHENATORS: dict[str, object] = {}

# A "word" for syllabification: a run of letters (Unicode), optionally carrying
# internal apostrophes/hyphens.  Splitting on this keeps punctuation, digits,
# and whitespace untouched so only real words are transformed.
_WORD_RE = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*", re.UNICODE)


def available() -> bool:
    """True when Pyphen is importable (the feature can run)."""
    return _PYPHEN


def _hyphenator(lang: str = _DEFAULT_LANG):
    """Return a cached ``pyphen.Pyphen`` for *lang*, or ``None``.

    Lazily imports Pyphen and constructs the hyphenator on first use.  Any
    failure (Pyphen absent, unknown language) is swallowed and cached as
    ``None`` so callers get a clean no-op rather than an exception.
    """
    if not _PYPHEN:
        return None
    if lang in _HYPHENATORS:
        return _HYPHENATORS[lang]
    obj = None
    try:
        import pyphen  # deferred: avoid dictionary load at startup

        obj = pyphen.Pyphen(lang=lang)
    except Exception:  # noqa: BLE001 — unknown lang / import race → no-op
        obj = None
    _HYPHENATORS[lang] = obj
    return obj


def split_word(word: str, sep: str = MIDDOT, *, lang: str = _DEFAULT_LANG) -> str:
    """Return *word* with *sep* inserted between its syllables.

    A word Pyphen cannot (or need not) break — a monosyllable, a word shorter
    than Pyphen's minimum, or anything when Pyphen is unavailable — is returned
    unchanged.  Pure and side-effect-free; safe to call on any token.
    """
    if not word:
        return word
    hy = _hyphenator(lang)
    if hy is None:
        return word
    try:
        # Pyphen inserts the separator itself; passing our sep keeps the middot.
        return hy.inserted(word, hyphen=sep)
    except Exception:  # noqa: BLE001 — never let a decoding aid raise.
        return word


def syllabify_text(text: str, sep: str = MIDDOT, *, lang: str = _DEFAULT_LANG) -> str:
    """Insert *sep* between syllables of every word in *text*.

    Only alphabetic word runs are transformed; whitespace, digits, and
    punctuation are preserved exactly.  Returns *text* unchanged when Pyphen is
    unavailable, so this is always safe to call.  Pure — for display only.
    """
    if not text or _hyphenator(lang) is None:
        return text

    def _repl(m: "re.Match") -> str:
        return split_word(m.group(0), sep, lang=lang)

    return _WORD_RE.sub(_repl, text)


def syllabify_html(html: str, sep: str = MIDDOT, *, lang: str = _DEFAULT_LANG) -> str:
    """Insert syllable separators into the text runs of an HTML *body*.

    Mirrors the bionic-reading transform: the string is split on tags and HTML
    entities so markup and entities are left intact, and text inside ``<code>`` /
    ``<pre>`` spans is skipped (code and formulae stay verbatim).  A no-op when
    Pyphen is unavailable.  Display-only — it never touches the TTS plain text or
    the word map.
    """
    if not html or _hyphenator(lang) is None:
        return html
    parts = re.split(r"(<[^>]+>|&[a-zA-Z]+;|&#\d+;)", html)
    in_verbatim = False
    out: list[str] = []
    for p in parts:
        if not p:
            continue
        if p.startswith("<"):
            low = p.lower()
            if low.startswith(("<code", "<pre")):
                in_verbatim = True
            elif low.startswith(("</code", "</pre")):
                in_verbatim = False
            out.append(p)
        elif p.startswith("&"):
            out.append(p)  # HTML entity — leave untouched
        elif in_verbatim:
            out.append(p)
        else:
            out.append(syllabify_text(p, sep, lang=lang))
    return "".join(out)
