"""Offscreen tests for the Controls toolbar (ChromeMixin._build_toolbar).

The toolbar is icon-only: every button is a hand-drawn vector glyph whose
QAction *label* doubles as the accessible name (screen readers) and as the
stable English key in the ``_toolbar_actions`` registry (the guided tour and
Voice Typing anchor on those keys, regardless of UI language).  These tests
pin that contract — icon + tooltip + text on every button, registry keys that
match the built actions, triggers wired to their handlers — plus the shortcut
invariant: toolbar buttons carry NO keyboard shortcut, because every binding
is owned by exactly one menu QAction (an ambiguous shortcut fires neither).
"""
import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Never let a toolbar test trigger a background pip install of optional deps.
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))

pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp):
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    win = StarWindow(Settings())
    yield win
    win.close()


def _buttons(toolbar):
    """The toolbar's real command actions (separators filtered out)."""
    return [a for a in toolbar.actions() if not a.isSeparator()]


def test_every_action_has_icon_tooltip_and_text(window):
    """Icon-only toolbar contract: each button needs a glyph to show, a
    tooltip to hover, and a text label for screen readers to announce."""
    missing = []
    for act in _buttons(window._toolbar):
        if act.icon().isNull():
            missing.append(f"{act.text()!r}: null icon")
        if not act.toolTip():
            missing.append(f"{act.text()!r}: empty tooltip")
        if not act.text():
            missing.append("<unnamed action>: empty text (no accessible name)")
    assert not missing, "toolbar actions violating the icon/tip/text contract:\n  " + "\n  ".join(missing)


def test_registry_keys_are_stable_english_labels(window):
    """_toolbar_actions maps the untranslated English label → its QAction, in
    build order — the lookup contract the tour and Voice Typing depend on."""
    registry = window._toolbar_actions
    built = _buttons(window._toolbar)

    # Every built button is registered, same objects, same order — no strays.
    assert list(registry.values()) == built
    # With English active tr() is the identity, so key == displayed text.
    for label, act in registry.items():
        assert act.text() == label, f"registry key {label!r} != action text {act.text()!r}"

    # The labels other code anchors on by name must stay present verbatim:
    # the guided-tour steps (star/gui/mixin_tour.py) and the Voice Typing
    # check-state sync (star/gui/mixin_transcription.py).
    anchored = {"Open", "Play / Pause", "Faster", "Highlight", "Voice", "Theme",
                "Voice Typing"}
    assert anchored <= set(registry), f"missing anchored labels: {anchored - set(registry)}"


def test_triggering_actions_calls_their_handlers(window, monkeypatch):
    """act.trigger() reaches the command handler.  _act connects the bound
    method at build time, so patch first and rebuild the toolbar — the same
    rebind path a UI-language change exercises."""
    calls = []
    monkeypatch.setattr(window, "_tts_toggle", lambda *a: calls.append("play"))
    monkeypatch.setattr(window, "_open_dialog", lambda *a: calls.append("open"))
    monkeypatch.setattr(
        window, "_qt_skip_next_sentence", lambda *a: calls.append("next-sent")
    )
    # Faster/Slower go through a lambda: verify the delta argument too.
    monkeypatch.setattr(window, "_rate_change", lambda d: calls.append(("rate", d)))
    window._build_toolbar()

    for label in ("Play / Pause", "Open", "Next Sentence", "Faster"):
        window._toolbar_actions[label].trigger()
    assert calls == ["play", "open", "next-sent", ("rate", +20)]

    # Triggering also feeds the command-history log (the second connection).
    assert [e[2] for e in window._command_history[-4:]] == [
        "Play / Pause", "Open", "Next Sentence", "Faster",
    ]


def test_toolbar_actions_carry_no_shortcut(window):
    """No toolbar button owns a key binding — shortcuts live on menu actions
    only, so each sequence has exactly one owner (Qt fires *neither* action
    when two claim the same shortcut).  The edit-mode formatting toolbar
    follows the same rule."""
    offenders = [
        f"{act.text()!r} -> {act.shortcut().toString()!r}"
        for tb in (window._toolbar, window._edit_toolbar)
        for act in _buttons(tb)
        if not act.shortcut().isEmpty()
    ]
    assert not offenders, "toolbar actions carrying a shortcut:\n  " + "\n  ".join(offenders)


def test_menu_actions_own_the_shortcuts(window):
    """The other half of the invariant: the bindings the toolbar tooltips
    advertise are really owned by *menu* actions (the remappable registry
    self._shortcut_actions), not by the toolbar buttons."""
    owned = {label: (act, seq) for label, act, seq in window._shortcut_actions}
    for label, expected in (
        ("Play / Pause", "Space"),
        ("Stop", "Escape"),
        ("New", "Ctrl+N"),
    ):
        assert label in owned, f"no menu action registered for {label!r}"
        act, seq = owned[label]
        assert seq == expected
        assert not act.shortcut().isEmpty()
        # The owner is the menu QAction, never the toolbar button.
        assert act is not window._toolbar_actions[label]
