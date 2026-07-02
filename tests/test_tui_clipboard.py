"""Tests for the TUI clipboard copy logic (``star.tui.mixin_docops``).

The copy path must:
  * copy the active *selection* (the current search match span) when present,
  * else copy the *paragraph* (logical block) around the reading cursor —
    not just one wrapped visual row,
  * fall back to the top-visible line when there is no cursor content,
  * use ``pyperclip`` when importable, an OSC-52 terminal escape next, and a
    status-line message last, and
  * never raise, even when ``pyperclip`` is absent.

These exercise the pure copy logic against a tiny fake rendered buffer and a
monkeypatched clipboard, with no curses or real terminal involved.
"""

import sys
import types

from star.tui.mixin_docops import DocOpsMixin


# ── A minimal stand-in for StarApp exposing only what the copy code touches ──

class _FakeSearch:
    def __init__(self, current_match=None):
        self.current_match = current_match


class _FakeApp(DocOpsMixin):
    def __init__(self, rendered, scroll=0, sc_line=-1, current_match=None):
        self.rendered = rendered
        self.scroll = scroll
        self._sc_line = sc_line
        self.search = _FakeSearch(current_match)
        self.messages = []  # (msg, error)

    def notify(self, msg, dur=4.0, error=False):
        self.messages.append((msg, error))


def _line(text, role="body"):
    """One rendered display line as the TUI stores it: a list of (text, role)."""
    return [(text, role)]


# A paragraph that spans three wrapped display lines, then a blank, then a
# second paragraph — the classic "copy should grab the whole block" case.
BUFFER = [
    _line("The quick brown fox"),
    _line("jumps over the lazy"),
    _line("dog near the river."),
    [],  # blank line separates paragraphs
    _line("Second paragraph here."),
]


# ── Selection copy ───────────────────────────────────────────────────────────

def test_selection_wins_over_paragraph():
    # Selection = search match (line 0, cols 4..9) -> "quick".
    app = _FakeApp(BUFFER, scroll=0, sc_line=0, current_match=(0, 4, 9))
    assert app._selection_text() == "quick"
    assert app._clipboard_text() == "quick"


def test_no_selection_returns_empty():
    app = _FakeApp(BUFFER, scroll=0, sc_line=0, current_match=None)
    assert app._selection_text() == ""


# ── Paragraph fallback ───────────────────────────────────────────────────────

def test_paragraph_joins_wrapped_lines():
    # Cursor in the middle of the first paragraph: copy the whole block.
    app = _FakeApp(BUFFER, scroll=0, sc_line=1, current_match=None)
    assert app._current_paragraph_text() == (
        "The quick brown fox jumps over the lazy dog near the river."
    )
    # With no selection, the clipboard text is the paragraph.
    assert app._clipboard_text() == (
        "The quick brown fox jumps over the lazy dog near the river."
    )


def test_paragraph_from_second_block():
    app = _FakeApp(BUFFER, scroll=4, sc_line=4, current_match=None)
    assert app._current_paragraph_text() == "Second paragraph here."


def test_blank_cursor_line_steps_to_next_content():
    # Cursor sits on the blank separator (line 3) -> step forward to content.
    app = _FakeApp(BUFFER, scroll=3, sc_line=3, current_match=None)
    assert app._current_paragraph_text() == "Second paragraph here."


def test_current_line_helper_still_works():
    app = _FakeApp(BUFFER, scroll=2, sc_line=-1, current_match=None)
    assert app._copy_current_line() == "dog near the river."


def test_empty_buffer_is_safe():
    app = _FakeApp([], scroll=0, sc_line=0, current_match=None)
    assert app._selection_text() == ""
    assert app._current_paragraph_text() == ""
    assert app._clipboard_text() == ""
    app._copy_to_clipboard()  # must not raise
    assert app.messages and app.messages[-1][1] is True  # error notice


# ── pyperclip present ────────────────────────────────────────────────────────

def test_copy_uses_pyperclip_when_present(monkeypatch):
    copied = {}
    fake = types.ModuleType("pyperclip")
    fake.copy = lambda text: copied.__setitem__("text", text)
    monkeypatch.setitem(sys.modules, "pyperclip", fake)

    app = _FakeApp(BUFFER, scroll=0, sc_line=1, current_match=None)
    app._copy_to_clipboard()

    assert copied["text"] == (
        "The quick brown fox jumps over the lazy dog near the river."
    )
    assert app.messages[-1][1] is False  # success, not an error
    assert "Copied to clipboard" in app.messages[-1][0]


def test_selection_copied_via_pyperclip(monkeypatch):
    copied = {}
    fake = types.ModuleType("pyperclip")
    fake.copy = lambda text: copied.__setitem__("text", text)
    monkeypatch.setitem(sys.modules, "pyperclip", fake)

    app = _FakeApp(BUFFER, scroll=0, sc_line=0, current_match=(0, 4, 9))
    app._copy_to_clipboard()
    assert copied["text"] == "quick"


# ── pyperclip absent ─────────────────────────────────────────────────────────

def test_never_raises_without_pyperclip(monkeypatch, capfd):
    # Force `import pyperclip` to fail even if it happens to be installed.
    monkeypatch.setitem(sys.modules, "pyperclip", None)

    app = _FakeApp(BUFFER, scroll=0, sc_line=1, current_match=None)
    app._copy_to_clipboard()  # must not raise

    # It must have reported success (OSC-52 fallback) or surfaced the text.
    assert app.messages, "copy should always notify"
    last_msg, is_error = app.messages[-1]
    assert is_error is False
    # OSC-52 escape should have been emitted to the real stdout as the fallback
    # (capfd captures the underlying fd, which sys.__stdout__ writes to).
    out = capfd.readouterr().out
    assert "\033]52;c;" in out or "Copied to clipboard" in last_msg


def test_pyperclip_exception_falls_back(monkeypatch):
    # pyperclip present but its copy() blows up (e.g. no display) -> fall back,
    # never raise.
    boom = types.ModuleType("pyperclip")

    def _raise(_text):
        raise RuntimeError("no clipboard mechanism available")

    boom.copy = _raise
    monkeypatch.setitem(sys.modules, "pyperclip", boom)

    app = _FakeApp(BUFFER, scroll=0, sc_line=1, current_match=None)
    app._copy_to_clipboard()  # must not raise
    assert app.messages  # some notice was produced


# ── OSC-52 helper ────────────────────────────────────────────────────────────

def test_osc52_emits_escape(capfd):
    ok = DocOpsMixin._osc52_copy("hello")
    assert ok is True
    out = capfd.readouterr().out
    assert out.startswith("\033]52;c;")
    assert out.endswith("\a")


def test_osc52_never_raises_on_bad_stream(monkeypatch):
    # A broken stdout must be swallowed, not raised.
    class _Broken:
        def write(self, *_a, **_k):
            raise OSError("pipe closed")

        def flush(self):
            raise OSError("pipe closed")

    monkeypatch.setattr(sys, "stdout", _Broken())
    monkeypatch.setattr(sys, "__stdout__", _Broken(), raising=False)
    assert DocOpsMixin._osc52_copy("x") is False
