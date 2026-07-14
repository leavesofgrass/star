"""The GUI word→editor-offset map must survive spoken/rendered divergence.

The karaoke highlight paints ``_qt_word_map[word_idx]``.  The map used to be
built with a rolling forward substring search, which derailed the moment the
spoken stream diverged from the rendered text — structured table narration
("Table with 3 columns", "Row 1", "… is …") matched *later* rendered
occurrences of common words, dragged the search cursor past real content,
and pinned every following word to a stale fallback offset: from the first
table to the end of the document the highlight no longer tracked speech.
These tests pin the sequence-alignment replacement.
"""
import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))

pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")

from star.gui.mixin_document import (  # noqa: E402
    _QT_TOKEN_RE,
    _align_word_offsets,
)


def _tokens(text):
    return [m.group().lower() for m in _QT_TOKEN_RE.finditer(text)]


def _rendered(text):
    return [(m.group().lower(), m.start()) for m in _QT_TOKEN_RE.finditer(text)]


def _assert_exact(spoken, qt_text, offsets, indices):
    qt_lower = qt_text.lower()
    for i in indices:
        assert offsets[i] >= 0, f"word {i} ({spoken[i]!r}) unaligned"
        assert qt_lower.startswith(spoken[i], offsets[i]), (
            f"word {i} ({spoken[i]!r}) points at "
            f"{qt_text[offsets[i]:offsets[i] + 12]!r}"
        )


def test_identical_streams_align_exactly():
    text = "the quick brown fox jumps over the lazy dog"
    spoken = _tokens(text)
    offsets = _align_word_offsets(spoken, _rendered(text))
    _assert_exact(spoken, text, offsets, range(len(spoken)))


def test_table_narration_does_not_derail_following_text():
    """The regression: spoken-only narration words used to drag the rolling
    cursor forward, breaking every word from the table to document end."""
    plain = (
        "Before the table sits ordinary prose. "
        "Table with 3 columns: Group, N, Change. "
        "Row 1: Group is Treated, N is 6,423, Change is -15.3. "
        "Row 2: Group is Control, N is 6,424, Change is -2.1. "
        "After the table the prose continues with completely normal "
        "sentences that every reader expects to see highlighted."
    )
    qt = (
        "Before the table sits ordinary prose.\n"
        "Group N Change\n"
        "Treated 6,423 -15.3\n"
        "Control 6,424 -2.1\n"
        "After the table the prose continues with completely normal "
        "sentences that every reader expects to see highlighted."
    )
    spoken = _tokens(plain)
    offsets = _align_word_offsets(spoken, _rendered(qt))
    after = spoken.index("continues")
    _assert_exact(spoken, qt, offsets, range(after, len(spoken)))
    # Cell words inside the narration align to the actual cells too.
    treated = spoken.index("treated")
    _assert_exact(spoken, qt, offsets, [treated])


def test_rendered_only_content_is_skipped_not_derailing():
    """A code block shown in the editor but absent from speech (tts_skip_code)
    must not break the alignment of the prose after it."""
    plain = "Look at this example. And the story continues after the code."
    qt = (
        "Look at this example.\n"
        "def compute(items):\n"
        "    return sum(items)\n"
        "And the story continues after the code."
    )
    spoken = _tokens(plain)
    offsets = _align_word_offsets(spoken, _rendered(qt))
    _assert_exact(spoken, qt, offsets, range(len(spoken)))


def test_repeated_words_match_in_document_order():
    text = "the cat saw the cat chase the cat"
    spoken = _tokens(text)
    offsets = _align_word_offsets(spoken, _rendered(text))
    assert offsets == sorted(offsets)
    _assert_exact(spoken, text, offsets, range(len(spoken)))


def test_narration_words_report_unaligned():
    plain = "alpha Table with 3 columns beta"
    qt = "alpha beta"
    spoken = _tokens(plain)
    offsets = _align_word_offsets(spoken, _rendered(qt))
    _assert_exact(spoken, qt, offsets, [0, len(spoken) - 1])
    assert all(o == -1 for o in offsets[1:-1])


# ── the bound builders (gap-fill + windowed sentinel semantics) ──────────────


class _Host:
    """Minimal stand-in for StarWindow: just the attributes the builders use."""

    def __init__(self, doc=None):
        self.doc = doc
        self._qt_word_map = []


def test_build_qt_word_map_gap_fills_forward():
    from star.gui.mixin_document import DocumentMixin

    plain = "alpha Table with 3 columns beta gamma"
    qt = "alpha beta gamma"
    host = _Host()
    DocumentMixin._build_qt_word_map(host, plain, qt)
    offsets = host._qt_word_map
    spoken = _tokens(plain)
    assert len(offsets) == len(spoken)
    assert all(o >= 0 for o in offsets)  # consumers require real offsets
    beta = qt.index("beta")
    # Narration words park on the next aligned word's offset.
    assert offsets[1:5] == [beta] * 4
    _assert_exact(spoken, qt, offsets, [0, 5, 6])


def test_build_qt_word_map_windowed_keeps_sentinels():
    from star.documents import _build_word_map
    from star.gui.mixin_document import DocumentMixin

    plain = "one two three four five six seven eight"
    doc = type("D", (), {})()
    doc.word_map = _build_word_map(plain, [plain])
    host = _Host(doc)
    qt_window = "three four five"  # only words 2..4 are rendered
    DocumentMixin._build_qt_word_map_windowed(host, 2, 5, qt_window)
    offsets = host._qt_word_map
    assert len(offsets) == len(doc.word_map)
    assert offsets[0] == offsets[1] == -1          # before the window
    assert offsets[5] == offsets[6] == offsets[7] == -1  # after the window
    spoken = _tokens(plain)
    _assert_exact(spoken, qt_window, offsets, [2, 3, 4])
