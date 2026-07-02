"""Screen-reader live-region announcements for the Qt GUI.

star is an accessibility-first reader, so a sighted-only status-bar message is
not enough: a blind user driving the app with NVDA / JAWS / Orca must *hear*
state changes (playback started, a document loaded, the theme changed, a search
result) without the focus moving to the status bar.  Qt exposes exactly this via
``QAccessible.updateAccessibility`` with an ``Announcement`` event — the Qt
equivalent of an ARIA live region.

This module wraps that call in a single, defensive :func:`announce` helper:

* It is a **no-op** when ``QAccessible`` is unavailable (PyQt built without the
  accessibility bridge, or Qt too old for the ``Announcement`` event), and it
  **never raises** — an announcement failing must never break playback or a
  document load.  In particular, under the ``offscreen`` QPA used by the test
  suite there is no active accessibility bridge, so the call degrades silently.
* It guards for the PyQt6 (scoped-enum) and PyQt5 (unscoped-enum) spellings of
  every enum it touches.

Callers pair each :func:`announce` with the existing ``statusBar().showMessage``
so the message is both seen and heard; neither replaces the other.

IMPORT SAFETY: unlike the mixin modules this file imports Qt lazily *inside* the
helper, so ``import star.gui.a11y`` is safe even when PyQt is absent — the module
can be imported unconditionally and the helper simply becomes a no-op.
"""
from __future__ import annotations

from typing import Any, Optional

# Resolved once and cached: (QAccessible, QAccessibleEvent, Announcement-enum).
# ``False`` means "already tried and unavailable"; ``None`` means "not yet
# probed".  Kept module-level so the (small) import cost is paid at most once.
_A11Y: Any = None


def _resolve() -> Optional[tuple]:
    """Return ``(QAccessible, QAccessibleEvent, announcement_event)`` or None.

    The third element is the ``QAccessible.Event.Announcement`` enum value
    resolved for whichever PyQt binding is active; None if this build has no
    Announcement event (older Qt) or no accessibility module at all.  Cached.
    """
    global _A11Y
    if _A11Y is not None:
        return _A11Y or None
    try:
        try:  # PyQt6
            from PyQt6.QtGui import QAccessible, QAccessibleEvent
        except ImportError:  # PyQt5
            from PyQt5.QtGui import QAccessible, QAccessibleEvent  # type: ignore

        # The Announcement event arrived in Qt 6.8 on some builds and later on
        # others; probe both the scoped (PyQt6) and flat (PyQt5) spellings and
        # bail gracefully when neither exists.
        ann = None
        ev_enum = getattr(QAccessible, "Event", None)
        if ev_enum is not None and hasattr(ev_enum, "Announcement"):
            ann = ev_enum.Announcement  # PyQt6 scoped enum
        elif hasattr(QAccessible, "Announcement"):
            ann = QAccessible.Announcement  # PyQt5 / flat enum
        if ann is None:
            _A11Y = False
            return None
        _A11Y = (QAccessible, QAccessibleEvent, ann)
        return _A11Y
    except Exception:  # noqa: BLE001 — any failure → permanently disable, no-op
        _A11Y = False
        return None


def announce(widget: Any, text: str) -> bool:
    """Announce *text* to assistive technology as a live-region update.

    Sends a ``QAccessible.Event.Announcement`` for *widget* so a screen reader
    speaks *text* immediately **without moving focus**.  Returns True if the
    announcement was dispatched, False if it was a no-op (accessibility
    unavailable, empty text, or any failure).  Never raises.

    Pair this with ``self.statusBar().showMessage(text)`` so the same message is
    both visible and audible.
    """
    if not text or widget is None:
        return False
    resolved = _resolve()
    if resolved is None:
        return False
    QAccessible, QAccessibleEvent, ann = resolved
    try:
        # QAccessible must be active for the event to reach the bridge; when it
        # is not (e.g. offscreen QPA in tests), isActive() is False and we skip
        # the call so nothing is attempted against a dormant bridge.
        is_active = getattr(QAccessible, "isActive", None)
        if callable(is_active) and not QAccessible.isActive():
            return False
        event = QAccessibleEvent(widget, ann)
        # Some Qt builds expose the spoken string via setValue on the event; set
        # it when available so readers that read the value (not just the object
        # name) speak the intended text.
        setter = getattr(event, "setValue", None)
        if callable(setter):
            setter(text)
        QAccessible.updateAccessibility(event)
        return True
    except Exception:  # noqa: BLE001 — announcements are best-effort only
        return False
