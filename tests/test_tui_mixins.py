"""Unit tests for high-value TUI mixins (navigation · search · document · render).

The TUI (``star.tui``) is a curses app: instantiating the real ``StarApp`` needs a
terminal, so these tests follow the pattern established by
``tests/test_tui_clipboard.py`` — compose the *real* mixin classes onto a tiny
fake app that supplies only the state the methods touch (``rendered``, ``scroll``,
``doc``, a fake ``tts``, a fake ``scr``), then exercise the pure navigation /
search / mapping logic with no curses, no threads, and no real TTS engine.

Covered here:
  * ``NavigationMixin`` — paragraph/heading/table finders, scroll clamping, and
    the ``_navigate_to`` "restart speech if it was playing" contract;
  * ``DocumentMixin`` — the sentence map, ``_find_sentence_idx`` binary search,
    ``_current_word_for_nav`` priority order, and the Flesch-Kincaid readout;
  * ``SearchEngine`` (``star.search``) — forward/backward wrap, from-line anchor,
    regex, and the graceful fall-back on a bad pattern;
  * ``render_markdown`` — heading/table role tagging the navigation relies on.

curses is stdlib on Linux/macOS and ships via windows-curses on Windows, so the
module normally runs everywhere; it is skipped only if curses is truly absent
(mirrors ``tests/test_tui_clipboard.py``'s environment).
"""
import importlib.util

import pytest

from star.documents import Document, _build_word_map
from star.render import render_markdown
from star.search import SearchEngine
from star.tui.mixin_caret import CaretMixin
from star.tui.mixin_document import DocumentMixin
from star.tui.mixin_navigation import NavigationMixin

# The mixin modules import cleanly without a terminal (curses is pulled in via
# the runtime hub but no live screen is needed to import the classes), so the
# imports sit at module top like tests/test_tui_clipboard.py.  The skip guard
# still protects any environment where the _curses C extension is truly absent.
pytestmark = pytest.mark.skipif(
    not (importlib.util.find_spec("curses") or importlib.util.find_spec("_curses")),
    reason="curses not available",
)


# ── Fakes ────────────────────────────────────────────────────────────────────


class _FakeScreen:
    """Just enough of a curses window for the scroll/goto helpers."""

    def __init__(self, height=24, width=80):
        self._h, self._w = height, width

    def getmaxyx(self):
        return (self._h, self._w)


class _FakeTTS:
    """Records play/stop calls without touching a real engine."""

    def __init__(self, speaking=False, cb=-1, cur=-1):
        self.speaking = speaking
        self.last_cb_word_idx = cb
        self.current_word_idx = cur
        self.stopped = 0
        self.played_from = []
        self.plain_played = 0

    def stop(self):
        self.stopped += 1
        self.speaking = False

    def set_word_map(self, wm):
        self.word_map = wm


class _FakeApp(DocumentMixin, NavigationMixin):
    """A StarApp stand-in composed from the real navigation/document mixins."""

    def __init__(self, rendered=None, doc=None, scroll=0, speaking=False):
        self.scr = _FakeScreen()
        self.rendered = rendered or []
        self.doc = doc
        self.scroll = scroll
        self.tts = _FakeTTS(speaking=speaking)
        self.settings = {}
        self._sentence_starts = [0]
        self._tts_paused_at_word = -1
        self._highlight_line = -1
        self._highlight_col_start = -1
        self._highlight_col_end = -1
        # Caret-browsing state (read by _current_word_for_nav / CaretMixin).
        self._caret_word = -1
        self._caret_goal_col = -1
        self._caret_manual_ts = 0.0
        self.messages = []
        # Track the play calls the navigation methods make.
        self.play_calls = []
        self.play_from_calls = []
        self.history = []

    # Collaborators the mixins call on `self` — stubbed to record intent.
    def notify(self, msg, dur=4.0, error=False):
        self.messages.append((msg, error))

    def _tts_play(self):
        self.play_calls.append(True)

    def _tts_play_from_word(self, idx):
        self.play_from_calls.append(idx)

    def _tts_stop(self):
        self.tts.stop()

    def _history_push(self):
        self.history.append(self.scroll)


# Reusable rendered document: H1 / para / H2 / table.
_MD = (
    "# Introduction\n\n"
    "This is the first paragraph with several words in it.\n\n"
    "## Details\n\n"
    "Second paragraph here now.\n\n"
    "| Name | Age |\n| --- | --- |\n| Ann | 30 |\n"
)


def _doc_from_md(md=_MD):
    """Build a Document with a real word map + rendered lines for it."""
    plain = md
    # Strip the markdown-ish syntax the same way the TTS text would roughly be;
    # for navigation tests we only need word_map disp_line values that index the
    # rendered buffer, and _build_word_map derives those from the render itself.
    rendered = render_markdown(md, 60)
    flat = ["".join(t for t, _ in line) for line in rendered]
    doc = Document(path="/tmp/x.md", title="x", markdown=md, plain_text=plain)
    doc.word_map = _build_word_map(plain, flat)
    return doc, rendered


# ── NavigationMixin: paragraph / heading / table finders ─────────────────────


def test_find_next_and_prev_paragraph():
    _, rendered = _doc_from_md()
    app = _FakeApp(rendered=rendered, scroll=0)
    # From the top, the next paragraph start is a later content line.
    nxt = app._find_next_paragraph(0)
    assert 0 < nxt < len(rendered)
    assert rendered[nxt], "next-paragraph target must be a content line"
    # Going back from there returns to an earlier content line.
    prev = app._find_prev_paragraph(nxt)
    assert prev < nxt
    assert rendered[prev]


def test_find_next_heading_locates_h2():
    _, rendered = _doc_from_md()
    app = _FakeApp(rendered=rendered)
    first_h = app._find_next_heading(0)
    assert first_h is not None
    # The second heading (## Details) is found after the first.
    second_h = app._find_next_heading(first_h)
    assert second_h is not None and second_h > first_h
    text = "".join(t for t, _ in rendered[second_h]).strip()
    assert "Details" in text


def test_find_prev_heading_and_none_at_top():
    _, rendered = _doc_from_md()
    app = _FakeApp(rendered=rendered)
    last = len(rendered) - 1
    assert app._find_prev_heading(last) is not None
    assert app._find_prev_heading(0) is None  # nothing above line 0


def test_is_heading_and_table_line_roles():
    _, rendered = _doc_from_md()
    app = _FakeApp(rendered=rendered)
    heading_lines = [i for i in range(len(rendered)) if app._is_heading_line(i)]
    table_lines = [i for i in range(len(rendered)) if app._is_table_line(i)]
    assert heading_lines, "at least one heading line expected"
    assert table_lines, "at least one table line expected"
    # A heading line is not simultaneously classified as a table line.
    assert not (set(heading_lines) & set(table_lines))


def test_find_next_table_and_prev_table():
    # A trailing paragraph after the table gives _find_prev_table a starting
    # point that is *outside* the table (so it doesn't just skip the table it
    # is standing in).
    md = _MD + "\nA closing paragraph after the table.\n"
    rendered = render_markdown(md, 60)
    app = _FakeApp(rendered=rendered)
    nxt = app._find_next_table(0)
    assert nxt is not None and app._is_table_line(nxt)
    # From the trailing paragraph, the previous-table finder walks back to the
    # first row of the table above it.
    prev = app._find_prev_table(len(rendered) - 1)
    assert prev is not None and app._is_table_line(prev)
    # It returns the *first* row of that table (the row above it is not a table).
    assert not app._is_table_line(prev - 1)


# ── NavigationMixin: scroll + navigate contract ──────────────────────────────


def test_scroll_by_clamps_to_bounds():
    _, rendered = _doc_from_md()
    app = _FakeApp(rendered=rendered, scroll=0)
    app._scroll_by(-5)
    assert app.scroll == 0  # can't go above the top
    app._scroll_by(10_000)
    assert app.scroll == len(rendered) - 1  # can't go past the end


def test_goto_top_and_bottom():
    _, rendered = _doc_from_md()
    app = _FakeApp(rendered=rendered, scroll=3)
    app._goto_bottom()
    assert app.scroll == len(rendered) - 1
    app._goto_top()
    assert app.scroll == 0


def test_navigate_to_restarts_speech_only_when_it_was_playing():
    _, rendered = _doc_from_md()
    # Was speaking → navigate stops then replays.
    app = _FakeApp(rendered=rendered, speaking=True)
    app._navigate_to(3)
    assert app.scroll == 3
    assert app.tts.stopped == 1
    assert app.play_calls == [True]

    # Was idle → navigate just scrolls, no replay.
    app2 = _FakeApp(rendered=rendered, speaking=False)
    app2._navigate_to(4)
    assert app2.scroll == 4
    assert app2.play_calls == []


def test_skip_next_heading_notifies_and_scrolls():
    _, rendered = _doc_from_md()
    app = _FakeApp(rendered=rendered, scroll=0)
    app._skip_next_heading()
    # Scrolled to a heading line and produced a "↓ Heading" notice.
    assert app._is_heading_line(app.scroll)
    assert app.messages and "Heading" in app.messages[-1][0]


def test_skip_next_table_no_table_notifies():
    # A document with no table → the skip reports "No table…".
    md = "# Only a heading\n\nJust prose, no tables at all here.\n"
    rendered = render_markdown(md, 60)
    app = _FakeApp(rendered=rendered, scroll=0)
    app._skip_next_table()
    assert app.messages and "No table" in app.messages[-1][0]


# ── DocumentMixin: sentence map + current-word priority ──────────────────────


def test_build_sentence_map_and_find_idx():
    doc, rendered = _doc_from_md()
    app = _FakeApp(rendered=rendered, doc=doc)
    app._build_sentence_map()
    ss = app._sentence_starts
    # Monotonic non-decreasing, in-bounds indices into the word map.
    assert ss == sorted(ss)
    assert all(0 <= w < len(doc.word_map) for w in ss)
    assert len(ss) >= 2, "the sample text has multiple sentences"
    # Binary search returns the sentence bucket containing a given word.
    for wi in (0, len(doc.word_map) // 2, len(doc.word_map) - 1):
        si = app._find_sentence_idx(wi)
        assert 0 <= si < len(ss)
        assert ss[si] <= wi
        if si + 1 < len(ss):
            assert ss[si + 1] > wi


def test_build_sentence_map_empty_doc_is_safe():
    app = _FakeApp(doc=None)
    app._build_sentence_map()
    assert app._sentence_starts == [0]


def test_current_word_for_nav_priority_order():
    doc, rendered = _doc_from_md()

    # 1. Speaking with a callback-confirmed word wins.
    app = _FakeApp(rendered=rendered, doc=doc, speaking=True)
    app.tts.last_cb_word_idx = 7
    app.tts.current_word_idx = 9
    assert app._current_word_for_nav() == 7

    # 2. Speaking, no callback yet → the timer estimate.
    app.tts.last_cb_word_idx = -1
    assert app._current_word_for_nav() == 9

    # 3. Idle but paused → the saved pause word.
    app.tts.speaking = False
    app._tts_paused_at_word = 4
    assert app._current_word_for_nav() == 4

    # 4. Idle, never paused → first word at/after the scroll line.
    app._tts_paused_at_word = -1
    app.scroll = doc.word_map[0].disp_line
    assert app._current_word_for_nav() == 0


def test_reading_level_readout():
    doc, rendered = _doc_from_md()
    app = _FakeApp(rendered=rendered, doc=doc)
    out = app._compute_reading_level_tui()
    assert "Reading level" in out and "Grade" in out and "Ease" in out

    empty = _FakeApp(doc=None)
    assert "No document" in empty._compute_reading_level_tui()


# ── SearchEngine (star.search) ───────────────────────────────────────────────


def _rendered(md):
    return render_markdown(md, 60)


def test_search_finds_all_and_wraps():
    rendered = _rendered("alpha beta\n\nbeta gamma\n\nbeta delta\n")
    eng = SearchEngine()
    assert eng.search("beta", rendered) is True
    assert eng.match_count == 3
    first = eng.current_match
    # next_match advances; after the last it wraps back to the first.
    seen = [eng.current_match]
    for _ in range(eng.match_count):
        seen.append(eng.next_match())
    assert seen[-1] == first  # wrapped a full cycle


def test_search_from_line_anchors_to_first_match_at_or_below():
    rendered = _rendered("target up top\n\n\n\n\ntarget down low\n")
    eng = SearchEngine()
    # Anchor below the first occurrence → current match is the lower one.
    eng.search("target", rendered, from_line=3)
    assert eng.current_match is not None
    assert eng.current_match[0] >= 3


def test_search_no_match_returns_false():
    rendered = _rendered("nothing to see here\n")
    eng = SearchEngine()
    assert eng.search("absent", rendered) is False
    assert eng.current_match is None
    assert eng.next_match() is None  # nothing to advance to


def test_search_regex_and_bad_pattern_falls_back():
    rendered = _rendered("cat cot cut\n")
    eng = SearchEngine()
    assert eng.search_regex(r"c.t", rendered) is True
    assert eng.match_count == 3
    # An invalid regex degrades to a literal plain search, never raising.
    eng2 = SearchEngine()
    assert eng2.search_regex("c[t", rendered) is False  # no literal "c[t"


# ── Welcome-as-document (0.1.22): _is_welcome gates + startup load ───────────


class _Settings(dict):
    """Dict with the .set() method the persistence helpers call."""

    def set(self, key, value):
        self[key] = value


class _WelcomeAwareApp(_FakeApp):
    """_FakeApp that treats the sentinel path "WELCOME" as the welcome doc and
    stubs the load-side collaborators _poll_load_queue touches."""

    def __init__(self, **kw):
        super().__init__(**kw)
        import queue as _q

        self._load_queue = _q.Queue()
        self.loading = True
        self.render_calls = 0
        self.settings = _Settings(recent_files=[], tts_auto_play=True)

    def _render_doc(self):  # rendering exercised by its own tests
        self.render_calls += 1

    def _save_reading_position(self):  # exercised separately below
        pass

    def _is_welcome(self, doc):
        return getattr(doc, "path", "") == "WELCOME"


def test_welcome_path_resolves_and_is_welcome_truth_table():
    """StarApp's welcome trio works without curses init (no instance state)."""
    from types import SimpleNamespace

    from star.tui.app import StarApp

    app = StarApp.__new__(StarApp)  # methods below use no __init__ state
    wp = app._welcome_path
    assert wp is not None and wp.name == "welcome.md", "bundled welcome.md missing"
    assert app._is_welcome(SimpleNamespace(path=str(wp))) is True
    assert app._is_welcome(SimpleNamespace(path="C:/elsewhere/other.md")) is False
    assert app._is_welcome(SimpleNamespace(path="")) is False


def test_poll_load_queue_gates_welcome_side_effects():
    """The welcome doc loads fully but writes no recents/last_path/library and
    never auto-plays; a normal doc still records everything."""
    welcome = Document(path="WELCOME", title="Welcome", markdown="hi", plain_text="hi")
    app = _WelcomeAwareApp()
    app._load_queue.put(welcome)
    app._poll_load_queue()
    assert app.doc is welcome and app.render_calls == 1  # real pipeline ran
    assert app.settings["recent_files"] == []
    assert "last_path" not in app.settings
    assert "library" not in app.settings
    assert app.play_calls == []  # tts_auto_play suppressed for welcome
    assert app.messages == []  # no "Opened:" toast

    normal = Document(path="/tmp/y.md", title="y", markdown="hi", plain_text="hi")
    app._load_queue.put(normal)
    app._poll_load_queue()
    assert app.settings["recent_files"] == ["/tmp/y.md"]
    assert app.settings["last_path"] == "/tmp/y.md"
    assert "/tmp/y.md" in app.settings["library"]
    assert app.play_calls == [True]  # auto-play honored for a real doc
    assert any("Opened" in m for m, _ in app.messages)


class _PosApp(_FakeApp):
    """_FakeApp whose welcome-ness is a switch, for the position gates."""

    welcome = False

    def _is_welcome(self, doc):
        return self.welcome


def test_reading_position_save_restore_gated_for_welcome():
    doc, rendered = _doc_from_md()
    app = _PosApp(rendered=rendered, doc=doc, scroll=0)
    app.settings = _Settings(tts_auto_resume=True)

    app.welcome = True
    app._save_reading_position()
    assert "reading_positions" not in app.settings  # welcome never saves

    app.welcome = False
    app._save_reading_position()
    assert doc.path in app.settings["reading_positions"]  # real doc saves

    # Restore: blocked for welcome, works for a real doc.
    app.welcome = True
    assert app._restore_reading_position() is False
    app.welcome = False
    assert app._restore_reading_position() is True
    assert any("Resumed" in m for m, _ in app.messages)


# ── Theming (0.1.22): platform-safe constants + orange accent ────────────────


def test_resolve_color_orange_and_passthrough():
    import curses

    from star.tui.theming import ORANGE, _ORANGE_256, _resolve_color

    assert _resolve_color(ORANGE, 256) == _ORANGE_256
    assert _resolve_color(ORANGE, 768) == _ORANGE_256  # windows-curses reports 768
    assert _resolve_color(ORANGE, 8) == curses.COLOR_YELLOW  # base-8 fallback
    assert _resolve_color(curses.COLOR_BLUE, 8) == curses.COLOR_BLUE  # passthrough
    assert _resolve_color(-1, 8) == -1  # terminal default untouched


def test_no_theme_uses_red():
    """Colorblind guard: no fg/bg in any TUI theme may be COLOR_RED.

    This is platform-sensitive on purpose — the old tables hardcoded
    ncurses-order ints, and on windows-curses (BGR) every intended blue (4)
    was actually COLOR_RED, painting the whole chrome red.  Named constants +
    this invariant keep that from regressing on either platform."""
    import curses

    from star.tui.theming import THEMES

    offenders = [
        (theme, role)
        for theme, table in THEMES.items()
        for role, (fg, bg, *_flags) in table.items()
        if curses.COLOR_RED in (fg, bg)
    ]
    assert not offenders, f"red found in themes: {offenders}"


def test_dark_theme_chrome_is_orange():
    """The default (dark) theme's chrome + spoken-word highlight carry the
    ORANGE sentinel; other themes keep their designed look (no orange)."""
    from star.tui.theming import ORANGE, THEMES

    dark = THEMES["dark"]
    for role in ("status", "title_bar", "progress", "current_word", "status_hi"):
        assert dark[role][1] is ORANGE, f"dark[{role}] lost the orange accent"
    for other in ("light", "contrast", "phosphor"):
        assert all(
            ORANGE not in (fg, bg)
            for fg, bg, *_f in THEMES[other].values()
        ), f"{other} theme unexpectedly gained orange"


# ── Caret browsing (0.1.22): CaretMixin + nav-priority integration ───────────


class _CaretApp(CaretMixin, _FakeApp):
    """_FakeApp with the real CaretMixin on top."""


def _caret_app():
    doc, rendered = _doc_from_md()
    return _CaretApp(rendered=rendered, doc=doc, scroll=0), doc


def test_caret_sync_places_at_reading_word():
    app, doc = _caret_app()
    assert app._caret_word == -1
    assert app._caret_sync() is True
    assert 0 <= app._caret_word < len(doc.word_map)


def test_caret_word_movement_clamps_at_both_ends():
    app, doc = _caret_app()
    app._caret_sync()
    app._caret_word = 0
    app._caret_move_word(1)
    assert app._caret_word == 1
    app._caret_move_word(-5)
    assert app._caret_word == 0  # clamped low
    app._caret_end()
    assert app._caret_word == len(doc.word_map) - 1
    app._caret_move_word(3)
    assert app._caret_word == len(doc.word_map) - 1  # clamped high
    app._caret_home()
    assert app._caret_word == 0


def test_caret_line_movement_walks_display_lines():
    app, doc = _caret_app()
    app._caret_home()
    l0 = doc.word_map[app._caret_word].disp_line
    app._caret_move_line(1)
    l1 = doc.word_map[app._caret_word].disp_line
    assert l1 > l0  # moved to a later display line
    app._caret_move_line(-1)
    assert doc.word_map[app._caret_word].disp_line < l1  # and back up


def test_caret_play_stops_then_reads_from_caret():
    app, doc = _caret_app()
    app._caret_sync()
    app._caret_word = 3
    app._caret_play()
    assert app.tts.stopped >= 1  # prior speech stopped first
    assert app.play_from_calls == [3]  # reads from the caret word
    assert any("caret" in m.lower() for m, _ in app.messages)


def test_current_word_for_nav_caret_priority():
    """speaking > paused > caret > viewport fallback."""
    app, doc = _caret_app()
    assert app._current_word_for_nav() == 0  # viewport fallback (caret unplaced)
    app._caret_word = 5
    assert app._current_word_for_nav() == 5  # caret wins while idle
    app._tts_paused_at_word = 2
    assert app._current_word_for_nav() == 2  # explicit pause beats caret
    app.tts.speaking = True
    app.tts.last_cb_word_idx = 7
    assert app._current_word_for_nav() == 7  # live speech beats everything


def test_caret_movers_fall_back_without_word_map():
    """Before a word map exists the arrows keep the classic scroll feel."""
    _, rendered = _doc_from_md()
    app = _CaretApp(rendered=rendered, doc=None, scroll=5)
    app._caret_move_line(1)
    assert app.scroll == 6  # plain scroll
    app._caret_home()
    assert app.scroll == 0  # classic goto-top
    assert app._caret_word == -1  # caret stays unplaced


# ── Polish-2 (0.1.22): caret reset on doc switch + error-doc handling ────────


def test_caret_resets_on_document_switch():
    """A caret placed in doc A must not survive into doc B — a stale index
    would make Enter/define/annotate act at an arbitrary word."""
    doc_a = Document(path="/tmp/a.md", title="a", markdown="hi", plain_text="hi")
    app = _WelcomeAwareApp()
    app._caret_word = 7
    app._caret_goal_col = 3
    app._load_queue.put(doc_a)
    app._poll_load_queue()
    assert app._caret_word == -1
    assert app._caret_goal_col == -1


def test_error_doc_never_reported_as_success():
    """A failed load must not toast 'Opened:', enter recents/last_path, or
    auto-play (which would read the exception text aloud)."""
    err = Document(
        path="/tmp/broken.pdf", title="Error — broken.pdf",
        markdown="# Could not open", plain_text="boom", format="error",
    )
    app = _WelcomeAwareApp()  # settings has tts_auto_play=True
    app._load_queue.put(err)
    app._poll_load_queue()
    assert app.settings["recent_files"] == []
    assert "last_path" not in app.settings
    assert app.play_calls == []  # auto-play suppressed
    msgs = [m for m, _err in app.messages]
    assert not any(m.startswith("Opened") for m in msgs)
    assert any("Could not open" in m for m in msgs)
    assert any(is_err for _m, is_err in app.messages)  # toast flagged as error
