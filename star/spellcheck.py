"""Spell checking for edit mode via pyspellchecker.

Optional feature: requires ``pyspellchecker`` (``pip install pyspellchecker``;
the import name is ``spellchecker``).  Gated behind ``_SPELL``.

Also provides ``SpellHighlighter``, a ``QSyntaxHighlighter`` subclass that
underlines misspelled words in red while editing.  ``QSyntaxHighlighter`` is
not re-exported by ``_runtime``, so it is imported directly here from whichever
Qt binding is present; when neither Qt nor pyspellchecker is available the
class is set to ``None`` and the GUI degrades gracefully.
"""

from ._runtime import *  # noqa: F401,F403

try:
    from spellchecker import SpellChecker

    _SPELL = True
except ImportError:
    _SPELL = False

# QSyntaxHighlighter lives in QtGui and is not part of the _runtime re-export.
try:
    from PyQt6.QtGui import QSyntaxHighlighter
except ImportError:
    try:
        from PyQt5.QtGui import QSyntaxHighlighter
    except ImportError:
        QSyntaxHighlighter = None  # type: ignore[assignment,misc]


# Word tokenizer shared by the checker and the highlighter.
_WORD_RE = re.compile(r"\b\w+\b")

# A single SpellChecker loads a sizeable word-frequency list, so build it once
# and share it across the highlighter and the menu command.
_CHECKER = None


def _checker() -> "Optional[SpellChecker]":
    """Return the shared SpellChecker, built lazily, or None if unavailable."""
    global _CHECKER
    if _CHECKER is None and _SPELL:
        _CHECKER = SpellChecker()
    return _CHECKER


def misspelled_words(text: str) -> set:
    """Return the set of unrecognized words in *text*.

    Pure-digit tokens are ignored.  When pyspellchecker is not installed this
    returns an empty set so callers can treat "no spell checker" and "no
    misspellings" the same way.
    """
    if not _SPELL:
        return set()
    chk = _checker()
    candidates = {w for w in _WORD_RE.findall(text or "") if not w.isdigit()}
    if not candidates:
        return set()
    return set(chk.unknown(candidates))


if QSyntaxHighlighter is not None:

    class SpellHighlighter(QSyntaxHighlighter):  # type: ignore[misc,valid-type]
        """Underline misspelled words in red, word by word.

        Qt calls ``highlightBlock`` for each text block that changes, so the
        highlighter re-checks automatically as the user types.  Each ``\\b\\w+\\b``
        token is looked up in pyspellchecker and underlined with a red spell-check
        squiggle when unrecognized.  With pyspellchecker absent it highlights
        nothing, leaving edit mode fully usable.
        """

        def __init__(self, document):
            super().__init__(document)
            self._fmt = QTextCharFormat()
            self._fmt.setUnderlineColor(QColor("red"))
            try:
                self._fmt.setUnderlineStyle(
                    QTextCharFormat.UnderlineStyle.SpellCheckUnderline  # PyQt6
                )
            except AttributeError:
                self._fmt.setUnderlineStyle(
                    QTextCharFormat.SpellCheckUnderline  # type: ignore[attr-defined]
                )

        def highlightBlock(self, text: str) -> None:
            if not _SPELL:
                return
            chk = _checker()
            for m in _WORD_RE.finditer(text or ""):
                word = m.group()
                if word.isdigit():
                    continue
                if word.lower() in chk.unknown([word]):
                    self.setFormat(m.start(), len(word), self._fmt)

else:
    SpellHighlighter = None  # type: ignore[assignment,misc]
