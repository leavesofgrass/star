"""Vocabulary-difficulty detection via wordfreq.

Optional feature: requires the ``wordfreq`` package (``pip install wordfreq``).
When it is absent the module still imports cleanly with ``_WORDFREQ = False``,
so the rest of star runs unchanged and the GUI shows an install hint instead of
the command — the same graceful-degradation pattern every other optional
feature follows.

``wordfreq`` reports a word's Zipf frequency: a log-scale score where common
words score high (the, and ~7) and rare words score low.  Flagging words below
a threshold gives a reader a visual pre-scan of the dense academic vocabulary
in a document before speech begins.
"""

from ._runtime import *  # noqa: F401,F403

try:
    from wordfreq import zipf_frequency

    _WORDFREQ = True
except ImportError:
    _WORDFREQ = False


# Zipf ~4 is roughly the boundary of "rare"; 4.5 also catches the moderately
# uncommon academic vocabulary (anatomy, statistics, pharmacology) that trips
# up readers without flagging everyday words.
DEFAULT_THRESHOLD = 4.5

# Words shorter than this are almost always common function words and add only
# noise to the overlay, so they are skipped regardless of frequency.
_MIN_LENGTH = 4

_WORD_RE = re.compile(r"[A-Za-z]+")


def find_difficult_words(text: str, threshold: float = DEFAULT_THRESHOLD) -> "set[str]":
    """Return the set of lowercased "difficult" words found in *text*.

    A word is difficult when its English Zipf frequency is below *threshold*.
    Words shorter than ``_MIN_LENGTH`` characters are ignored.  Returns an
    empty set when wordfreq is unavailable, so callers can degrade gracefully
    without a separate availability check.
    """
    if not _WORDFREQ or not text:
        return set()
    difficult: "set[str]" = set()
    seen: "set[str]" = set()
    for match in _WORD_RE.finditer(text):
        word = match.group(0).lower()
        if len(word) < _MIN_LENGTH or word in seen:
            continue
        seen.add(word)
        if zipf_frequency(word, "en") < threshold:
            difficult.add(word)
    return difficult
