"""Offscreen (headless) smoke tests for the Qt GUI.

The GUI is imported only inside ``star.gui.runner._run_qt_gui()`` and never
instantiated by the rest of the suite — a blind spot that let a stale import
crash launch through the whole 0.1.14 cycle (see tests/test_import_smoke.py).
These tests go one step further and actually *construct* ``StarWindow`` under
the offscreen QPA, exercising the toolbar, the hand-drawn vector icons, and the
welcome-as-document startup path.

Runs on every CI leg: PyQt6 is a base dependency.  The offscreen platform ships
zero fonts, so Windows TTFs are loaded up front for any text-rendering glyphs.
The module is fully skipped when Qt is unavailable.
"""
import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Never let a smoke run trigger a background pip install of optional deps.
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))

pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")


@pytest.fixture(scope="module")
def qapp():
    """A single QApplication for the module, with Windows fonts loaded.

    The offscreen QPA has no fonts of its own; loading a couple of Windows TTFs
    keeps any QPainter text glyphs (the ``font``/``help`` icons) from rendering
    blank.  Loading is best-effort — absent fonts (non-Windows CI) are fine.
    """
    from PyQt6.QtGui import QFontDatabase
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    for ttf in ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(ttf):
            QFontDatabase.addApplicationFont(ttf)
    return app


@pytest.fixture
def window(qapp):
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    win = StarWindow(Settings())
    yield win
    win.close()


def test_starwindow_constructs_with_toolbar(window):
    """StarWindow builds offscreen and its toolbar has actions."""
    tb = window._toolbar
    assert tb is not None
    assert len(tb.actions()) > 0


def test_make_icon_every_glyph(qapp):
    """make_icon() returns a non-null QIcon with a non-empty pixmap for every
    known glyph key, plus the unknown-name fallback."""
    from PyQt6.QtCore import QSize

    from star.gui import icons

    size = QSize(icons._SIZE, icons._SIZE)
    for name in icons._GLYPHS:
        icon = icons.make_icon(name)
        assert not icon.isNull(), f"icon {name!r} is null"
        pm = icon.pixmap(size)
        assert not pm.isNull() and pm.width() > 0, f"icon {name!r} has empty pixmap"

    # Unknown names must still yield a usable fallback icon (the neutral dot).
    fallback = icons.make_icon("this_glyph_does_not_exist")
    assert not fallback.isNull()
    assert not fallback.pixmap(size).isNull()


def test_welcome_loads_as_document(qapp, window):
    """With no initial path, StarWindow loads welcome.md as a real Document via
    a background thread; pump the event loop until it lands."""
    import time

    for _ in range(50):
        if window.doc is not None and getattr(window.doc, "word_map", None):
            break
        qapp.processEvents()
        time.sleep(0.1)

    assert window.doc is not None, "welcome document never loaded"
    assert window.doc.word_map, "welcome document has an empty word_map"
    assert window._is_welcome(window.doc) is True

    readme = window._bundled_path("README.md")
    assert readme is not None and readme.is_file()


def test_dyslexia_font_reaches_the_document_even_for_css_themes(window):
    """The dyslexia font must override a CSS/palette theme's own font-family.

    Regression: the Obsidian (default) theme injects its CSS verbatim with a
    hard-coded ``font-family: Georgia`` — which used to win in the reading pane,
    so OpenDyslexic changed only the chrome and 'nothing happened' in the
    document.  The renderer now appends an override the cascade resolves last.
    """
    # Avoid any network: pretend the family is available.
    window._find_dyslexia_font = lambda prefer="": "OpenDyslexic"
    window.settings["qt_dyslexia_font"] = True

    # The default theme is CSS-based (has a `_css`), which is the failing case.
    assert window._effective_palette(window.settings.get("theme")).get("_css")

    html = window._md_to_html("# Heading\n\nHello world.")
    # An OpenDyslexic font-family override is present…
    assert "OpenDyslexic" in html
    # …and it comes *after* the theme's own font-family so it wins the cascade.
    assert html.rfind("OpenDyslexic") > html.find("font-family")
    # Code stays monospace.
    assert "monospace" in html


def test_dyslexia_font_toggles_off_and_reverts_chrome(window, qapp):
    """Toggling the dyslexia font off must restore the original app font.

    Regression: app.setFont(QFont()) (a default-constructed font, no resolve
    mask) failed to revert already-styled widgets (menus, ToC), so they stayed
    OpenDyslexic. The real default font is now captured and restored.
    """
    original = qapp.font().family()
    window._find_dyslexia_font = lambda prefer="": "OpenDyslexic"
    window._apply_dyslexia_font(True, fetch=False)
    assert qapp.font().family() == "OpenDyslexic"
    window._apply_dyslexia_font(False)
    assert qapp.font().family() == original


def test_footnote_anchor_click_jumps(window):
    """Clicking a footnote marker (or its backlink) scrolls to the anchor;
    an ordinary click is not consumed so it still places the caret."""
    from PyQt6.QtCore import QEvent, QPoint

    md = "Body text.[^1]\n\n[^1]: The footnote."
    html = window._md_to_html(md)
    assert 'name="fn-1"' in html and 'href="#fn-1"' in html
    window.editor.setHtml(html)

    called = {}
    window.editor.anchorAt = lambda _p: "#fn-1"
    window.editor.scrollToAnchor = lambda n: called.__setitem__("n", n)

    class _Evt:
        def type(self):
            return QEvent.Type.MouseButtonRelease

        def pos(self):
            return QPoint(1, 1)

    assert window._editor_anchor_click(_Evt()) is True
    assert called["n"] == "fn-1"

    window.editor.anchorAt = lambda _p: ""   # not over an anchor
    assert window._editor_anchor_click(_Evt()) is False


def test_rsvp_overlay_toggles_and_feeds(window):
    """RSVP mode creates + shows the floating one-word overlay and accepts word
    updates. Regression: mixin_aiddialogs referenced _RSVPOverlay without
    importing it, so toggling RSVP on raised NameError."""
    window.settings["qt_rsvp_mode"] = True   # a stale setting must not block turning it on
    window._qt_toggle_rsvp()
    ov = window._rsvp_overlay
    # isHidden() is ancestor-independent (the test window is never shown), so it
    # reflects the explicit show/hide the toggle performs.
    assert ov is not None and not ov.isHidden()
    ov.update_word("a", "b", "c")            # the playback feed path
    assert ov._word_lbl.text() == "b"
    window._qt_toggle_rsvp()
    assert ov.isHidden()


def test_reading_font_chooser_selects_and_reverts(window):
    """The Reading Font chooser applies a family app-wide and back to default.

    Pretend every family is available so no network fetch happens; verify the
    chooser key is persisted, the legacy boolean stays coherent, and Default
    reverts the app font.
    """
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    original = app.font().family()
    window._find_dyslexia_font = lambda prefer="": (prefer or "OpenDyslexic")

    window._qt_set_reading_font("atkinson")
    assert window.settings.get("qt_reading_font") == "atkinson"
    assert window.settings.get("qt_dyslexia_font") is True  # legacy alias coherent
    assert window._reading_font_key() == "atkinson"
    assert app.font().family() == "Atkinson Hyperlegible"

    window._qt_set_reading_font("default")
    assert window.settings.get("qt_reading_font") == "default"
    assert window.settings.get("qt_dyslexia_font") is False
    assert app.font().family() == original


def test_first_run_tour_defers_while_a_modal_is_up(qapp, monkeypatch):
    """The guided tour must not pop over a modal (the first-run
    optional-features chooser): while a modal is active it reschedules
    itself instead of starting."""
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    settings = Settings()
    settings._data["tour_seen"] = False
    win = StarWindow(settings)
    try:
        try:  # PyQt6
            from PyQt6.QtWidgets import QApplication
        except ImportError:
            from PyQt5.QtWidgets import QApplication  # type: ignore[no-redef]
        # Simulate an active modal (the deps chooser's exec loop).
        monkeypatch.setattr(
            QApplication, "activeModalWidget", lambda *a: object()
        )
        win._maybe_run_first_run_tour()
        assert win._tour_popover is None  # deferred, not shown
        # Modal gone → the tour starts on the next attempt.
        monkeypatch.setattr(
            QApplication, "activeModalWidget", lambda *a: None
        )
        win._maybe_run_first_run_tour()
        assert win._tour_popover is not None
        win._tour_finish()
    finally:
        win.close()
        qapp.processEvents()


def test_stale_rsvp_mode_never_survives_startup(qapp):
    """A qt_rsvp_mode persisted True (app closed with RSVP on, or a
    Preferences apply) must not leave a phantom checkmark: the overlay is
    never restored at startup, so the setting is normalized to off and the
    Reading Aids menu item starts unchecked."""
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    settings = Settings()
    settings._data["qt_rsvp_mode"] = True  # simulate the stale persisted state
    win = StarWindow(settings)
    try:
        assert win.settings.get("qt_rsvp_mode") is False
        assert win._rsvp_act.isChecked() is False
        # And no overlay was conjured up by startup.
        assert win._rsvp_overlay is None or win._rsvp_overlay.isHidden()
    finally:
        win.close()
        qapp.processEvents()


def test_word_highlight_paints_user_color_with_collapsed_caret(window, qapp):
    """The spoken-word highlight must show the user's highlight_color.

    Regression: _apply_word_highlight used to hand the editor a text cursor
    with the word still SELECTED, so the native selection painted the theme's
    `sel` color over the ExtraSelection — a custom word color (Preferences ▸
    Reading ▸ Word color) never showed.  The real caret must be collapsed and
    the painted ExtraSelection must carry the user's color."""
    from types import SimpleNamespace

    qapp.processEvents()  # let the async welcome render land first
    window.settings["highlight_color"] = "#0f766e"  # a dark teal
    window.settings["highlight_style"] = "background"
    window.settings["highlight_lead_words"] = 0
    window._rebuild_hl_fmt()
    window.editor.setPlainText("alpha beta gamma delta epsilon")
    window._qt_word_map = [0, 6, 11, 17, 23]
    old_doc = window.doc
    window.doc = SimpleNamespace(
        path="", title="t", format="markdown", markdown="",
        word_map=[SimpleNamespace(tts_len=5, word="w")] * 5,
    )
    try:
        # setExtraSelections/setTextCursor are synchronous — assert without
        # pumping the loop (a queued render would replace the editor text).
        window._apply_word_highlight(2, window._hl_session)
        # No native selection — that is what painted over the user's color.
        assert not window.editor.textCursor().hasSelection()
        # And the caret parked on the spoken word (ruler / resume tracking).
        assert window.editor.textCursor().position() == 11
        # The word's ExtraSelection carries the user's color, verbatim.
        word_sels = [
            s for s in window.editor.extraSelections() if s.cursor.hasSelection()
        ]
        assert word_sels, "no word ExtraSelection painted"
        assert word_sels[-1].format.background().color().name() == "#0f766e"
    finally:
        window.doc = old_doc


def test_reading_font_lives_in_preferences_not_a_submenu(window):
    """0.1.28: the Reading Font radios left the View menu for Preferences ▸
    Display — the menu keeps only the one-tap dyslexia toggle.  The empty
    registry must stay a dict so _qt_set_reading_font's checkmark sync is a
    clean no-op, and every family must still be settable without menu radios."""
    assert window._reading_font_acts == {}
    assert window._dyslexia_font_act is not None  # quick toggle survives
    window._find_dyslexia_font = lambda prefer="": (prefer or "OpenDyslexic")
    for key in ("default", "opendyslexic", "atkinson", "lexend"):
        window._qt_set_reading_font(key)
        assert window.settings.get("qt_reading_font") == key
    window._qt_set_reading_font("default")


def test_syllable_split_is_display_only(window, monkeypatch):
    """Syllable splitting inserts middots into the rendered HTML only; the Qt
    word-map text (which drives speech highlighting) is unchanged."""
    import star.syllables as _syl

    # Force pyphen "available" with a deterministic splitter so the test does not
    # depend on the package being installed.
    monkeypatch.setattr(
        _syl, "_hyphenator",
        lambda lang=_syl._DEFAULT_LANG: type(
            "H", (), {"inserted": staticmethod(lambda w, hyphen="·": hyphen.join(w))}
        )(),
    )
    md = "# Title\n\nHello there reader."
    window.settings["qt_syllable_split"] = False
    off_html = window._md_to_html(md)
    plain_ref = window._plain_text_without_syllables(md)

    window.settings["qt_syllable_split"] = True
    on_html = window._md_to_html(md)
    # The rendered HTML now carries the visible separator…
    assert _syl.MIDDOT in on_html and _syl.MIDDOT not in off_html
    # …but the word-map source text is byte-identical (no middots leak into it).
    assert window._plain_text_without_syllables(md) == plain_ref
    assert _syl.MIDDOT not in plain_ref


def test_reading_ruler_toggles_and_tears_down_cleanly(window):
    """The reading ruler overlay is created on first toggle, persists its
    setting, and disconnects its caret-tracking slot when turned off."""
    assert window.settings.get("qt_reading_ruler", False) is False
    window._qt_toggle_reading_ruler()
    assert window.settings.get("qt_reading_ruler") is True
    ruler = window._reading_ruler
    assert ruler is not None
    # Moving the caret must not raise while the ruler tracks it.
    from PyQt6.QtGui import QTextCursor

    cur = window.editor.textCursor()
    cur.movePosition(QTextCursor.MoveOperation.NextWord)
    window.editor.setTextCursor(cur)
    window._qt_toggle_reading_ruler()
    assert window.settings.get("qt_reading_ruler") is False
    assert ruler.isHidden()


def test_missing_feature_offers_autoinstall_not_pip(window, monkeypatch):
    """A gated feature offers a one-click background install — never a pip
    instruction. Students don't know Python."""
    from PyQt6.QtWidgets import QMessageBox

    from star import autodeps

    # Already installed -> True, no prompt.
    monkeypatch.setattr(autodeps, "missing", lambda pkgs: [])
    assert window._qt_require_optional_feature("transcribe", "Speech recognition") is True

    # Missing + user accepts -> kicks off the (forced) install, returns False.
    monkeypatch.setattr(autodeps, "missing", lambda pkgs: [("openai-whisper", "whisper")])
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    started = {}
    monkeypatch.setattr(
        window, "_qt_start_feature_install",
        lambda key, name: started.update(key=key, name=name),
    )
    assert window._qt_require_optional_feature("transcribe", "Speech recognition") is False
    assert started["key"] == "transcribe"

    # Missing + user declines -> nothing installed.
    started.clear()
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )
    assert window._qt_require_optional_feature("transcribe", "Speech recognition") is False
    assert "key" not in started


def test_install_feature_now_ignores_markers(monkeypatch, tmp_path):
    """Explicit installs must ignore the once-per-machine markers (the bug that
    made Summarize/Dictate say 'check your internet' while online)."""
    from star import autodeps

    monkeypatch.setattr(autodeps, "_MARKER_DIR", str(tmp_path))
    monkeypatch.setattr(autodeps, "_attempted_session", set())
    calls = []
    monkeypatch.setattr(autodeps, "_INSTALL_FN", lambda pip, **k: calls.append(pip) or True)
    monkeypatch.setattr(autodeps, "installed", lambda mod: False)

    # Pre-mark the package as already attempted — ensure() would now skip it…
    autodeps._mark("sumy")
    assert autodeps.ensure([("sumy", "sumy")], background=False) == []   # blocked by marker
    # …but the explicit installer still runs it and reports success.
    assert autodeps.install_now([("sumy", "sumy")]) is True
    assert "sumy" in calls


def test_no_ambiguous_shortcuts(window):
    """No keyboard shortcut is claimed by two *different* QActions — Qt fires
    neither in that case. Regression: Ctrl+Shift+L was bound to both
    'Open Folder as Library' and 'Live HTML Preview'."""
    from PyQt6.QtGui import QAction

    owner = {}
    dupes = []
    for act in window.findChildren(QAction):
        sc = act.shortcut().toString()
        if not sc:
            continue  # toolbar actions and separators carry no shortcut
        if sc in owner and owner[sc] is not act:
            dupes.append((sc, owner[sc].text(), act.text()))
        else:
            owner[sc] = act
    assert not dupes, f"ambiguous shortcuts: {dupes}"


def test_bare_less_than_in_prose_survives_render(window):
    """A bare "<" in prose must not swallow the rest of the text.

    Regression: Qt's rich-text parser treated "< 0.001)…" as a malformed tag
    opening and dropped everything from "p <" onward, so the read view showed
    less text than TTS spoke (doc.plain_text keeps the tail) and the highlight
    aligner had to park around the hole.  Stray "<" is now escaped before
    setHtml while real HTML constructs still render.
    """
    from PyQt6.QtGui import QTextDocument

    md = (
        "Mean systolic pressure fell from 142.6 to 127.3 mmHg "
        "(95% CI, 124.1 to 130.5; p < 0.001).\n\n"
        "Thresholds: x<3 and y <= 4, plus <b>bold</b> and `<code>` literal.\n"
    )
    scratch = QTextDocument()
    scratch.setHtml(window._md_to_html(md))
    text = scratch.toPlainText()
    assert "p < 0.001" in text
    assert "x<3" in text
    assert "y <= 4" in text
    # Real inline HTML still renders (tag consumed, content kept)…
    assert "bold" in text and "<b>" not in text
    # …and inline code shows its angle brackets literally.
    assert "<code>" in text
