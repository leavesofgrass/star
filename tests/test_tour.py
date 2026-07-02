"""Offscreen tests for the first-run guided tour (star/gui/mixin_tour.py).

These exercise the TourMixin on a live, headless ``StarWindow``:

* the tour *builds* — every step has a title/body and (where anchored) a known
  toolbar control;
* Next/Back navigation advances and rewinds the step index, with the popover
  card updating (and Back disabled on the first step);
* the ``tour_seen`` setting gates the first-run auto-show and is set when the
  tour is skipped/finished, so it never re-triggers on its own;
* the tour is re-runnable (Help ▸ Guided Tour) even after ``tour_seen`` is set,
  and re-running restarts it from step one.

Environment mirrors the other GUI tests: offscreen QPA, no auto-install, a
couple of Windows TTFs for glyph rendering.  Skipped when Qt is unavailable.
"""
import importlib.util
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))

pytestmark = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")


@pytest.fixture(scope="module")
def qapp():
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
    # Tear down any live tour popover, then the window.
    try:
        win._tour_finish()
    except Exception:
        pass
    win.close()


# ── step data ────────────────────────────────────────────────────────────


def test_tour_has_reasonable_step_set(window):
    """The tour walks 5–7 core features, each with a title and body."""
    steps = window._tour_steps()
    assert 5 <= len(steps) <= 7, f"expected 5–7 steps, got {len(steps)}"
    for step in steps:
        assert step["title"].strip(), "a step has no title"
        assert step["body"].strip(), "a step has no body"
        assert "anchor" in step


def test_tour_anchors_point_at_real_toolbar_controls(window):
    """Every non-empty anchor names an actual toolbar action.

    The tour anchors popovers by the stable English label registered in
    ``_toolbar_actions`` (see mixin_chrome); a typo would silently fall back to
    a centred popover, so guard the mapping here.
    """
    actions = window._toolbar_actions
    for step in window._tour_steps():
        anchor = step.get("anchor", "")
        if anchor:
            assert anchor in actions, f"tour anchor {anchor!r} is not a toolbar action"


# ── build + navigation ───────────────────────────────────────────────────


def test_start_tour_builds_popover_on_first_step(window):
    window._start_tour()
    assert window._tour_popover is not None
    assert window._tour_index == 0
    # First step shows its title; Back is disabled at the start.
    pop = window._tour_popover
    assert pop._title.text() == window._tour_steps()[0]["title"]
    assert pop._back_btn.isEnabled() is False


def test_tour_next_and_back_move_the_step(window):
    window._start_tour()
    steps = window._tour_steps()

    window._tour_next()
    assert window._tour_index == 1
    assert window._tour_popover._title.text() == steps[1]["title"]
    assert window._tour_popover._back_btn.isEnabled() is True

    window._tour_back()
    assert window._tour_index == 0
    assert window._tour_popover._title.text() == steps[0]["title"]

    # Back on the first step is a no-op (never goes negative).
    window._tour_back()
    assert window._tour_index == 0


def test_tour_next_past_last_step_finishes(window):
    window._start_tour()
    n = len(window._tour_steps())
    for _ in range(n - 1):
        window._tour_next()
    assert window._tour_index == n - 1
    # The final step's Next button reads "Done"; pressing it ends the tour.
    from star.i18n import tr

    assert window._tour_popover._next_btn.text() == tr("Done")
    window._tour_next()
    assert window._tour_popover is None
    assert window.settings.get("tour_seen") is True


# ── first-run gating ─────────────────────────────────────────────────────


def test_first_run_shows_tour_when_unseen(window):
    """With tour_seen False, the first-run hook opens the tour."""
    window.settings["tour_seen"] = False
    window._maybe_run_first_run_tour()
    assert window._tour_popover is not None
    assert window._tour_index == 0


def test_first_run_skips_tour_when_seen(window):
    """With tour_seen True, the first-run hook does nothing."""
    window.settings["tour_seen"] = True
    # Ensure no stale popover.
    window._tour_finish()
    window._maybe_run_first_run_tour()
    assert window._tour_popover is None


def test_skip_marks_tour_seen(window):
    """Skipping (via _tour_finish) persists tour_seen so it won't re-trigger."""
    window.settings["tour_seen"] = False
    window._start_tour()
    assert window._tour_popover is not None
    window._tour_finish()
    assert window._tour_popover is None
    assert window.settings.get("tour_seen") is True


def test_tour_rerunnable_after_seen(window):
    """Help ▸ Guided Tour re-runs even after tour_seen is set, from step one."""
    window.settings["tour_seen"] = True
    window._start_tour()
    assert window._tour_popover is not None
    assert window._tour_index == 0
    # Advance, then restart — index resets to 0.
    window._tour_next()
    assert window._tour_index == 1
    window._start_tour()
    assert window._tour_index == 0


def test_start_tour_is_idempotent(window):
    """Starting a tour while one is running restarts cleanly (no leak/crash)."""
    window._start_tour()
    first = window._tour_popover
    window._start_tour()
    assert window._tour_popover is not None
    assert window._tour_popover is not first
    assert window._tour_index == 0
