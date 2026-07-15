"""TourMixin — an optional, skippable first-run guided tour for StarWindow.

star is accessibility-first, and a first launch can be daunting: there is a
toolbar of icon glyphs and a deep menu bar.  This mixin adds a short, skippable
*guided tour* that walks a new user through the handful of controls that matter
most — opening a file, play/pause, changing speed, highlights & notes, the Voice
Manager, the Library, and the reading aids (including the dyslexia-friendly
font) — with a small step-by-step popover anchored near the relevant control.

Design goals (mirroring star's accessibility philosophy):

* **Optional & non-blocking.**  The tour is a *floating, non-modal* popover, not
  a modal wizard: the underlying window stays live, so a user can ignore it.  It
  shows **once** on first run (gated by the ``tour_seen`` setting) and is
  re-runnable any time from *Help ▸ Guided Tour* (Shift+F1).
* **Keyboard-navigable & accessible.**  Every step is reachable with the
  keyboard: Right/Enter/N = Next, Left/Backspace/B = Back, Esc = Skip, and the
  Back/Next/Skip buttons are ordinary focusable ``QPushButton``s.  Each step is
  spoken to a screen reader via :func:`star.gui.a11y.announce` as it appears, so
  a blind user hears the guidance without the popover stealing document focus.
* **Anchored, but robust.**  A step names a toolbar control (by its stable
  English label in ``self._toolbar_actions``) and the popover is placed next to
  that button's on-screen rectangle.  When a control has no geometry yet (the
  offscreen QPA used in tests, or a hidden toolbar) the popover falls back to
  the centre of the window — it never crashes and never lands off-screen.

IMPORT SAFETY: references Qt at module scope — imported lazily by
main_window.py (itself imported after the _QT guard), like the other
mixin_*.py modules.
"""
from .._runtime import *  # noqa: F401,F403
from ..i18n import tr
from .a11y import announce

# ── Qt enum compatibility (PyQt6 nested scopes vs. PyQt5 flat) ───────────────
# Resolved once at import; the tour refers to the resolved constant everywhere.
try:  # window flags for a frameless, always-on-top popover child
    _POPOVER_FLAGS = (
        Qt.WindowType.Tool
        | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
    )
    _ALIGN_LEFT = Qt.AlignmentFlag.AlignLeft
    _KEY_RIGHT = Qt.Key.Key_Right
    _KEY_LEFT = Qt.Key.Key_Left
    _KEY_RETURN = Qt.Key.Key_Return
    _KEY_ENTER = Qt.Key.Key_Enter
    _KEY_BACKSPACE = Qt.Key.Key_Backspace
    _KEY_ESCAPE = Qt.Key.Key_Escape
    _KEY_N = Qt.Key.Key_N
    _KEY_B = Qt.Key.Key_B
except AttributeError:  # PyQt5 flat enums
    _POPOVER_FLAGS = (
        Qt.Tool  # type: ignore[attr-defined]
        | Qt.FramelessWindowHint  # type: ignore[attr-defined]
        | Qt.WindowStaysOnTopHint  # type: ignore[attr-defined]
    )
    _ALIGN_LEFT = Qt.AlignLeft  # type: ignore[attr-defined]
    _KEY_RIGHT = Qt.Key_Right  # type: ignore[attr-defined]
    _KEY_LEFT = Qt.Key_Left  # type: ignore[attr-defined]
    _KEY_RETURN = Qt.Key_Return  # type: ignore[attr-defined]
    _KEY_ENTER = Qt.Key_Enter  # type: ignore[attr-defined]
    _KEY_BACKSPACE = Qt.Key_Backspace  # type: ignore[attr-defined]
    _KEY_ESCAPE = Qt.Key_Escape  # type: ignore[attr-defined]
    _KEY_N = Qt.Key_N  # type: ignore[attr-defined]
    _KEY_B = Qt.Key_B  # type: ignore[attr-defined]


class _TourPopover(QWidget):
    """A small floating step card: title, body, progress, Back/Next/Skip.

    Non-modal and frameless.  Owns no tour state itself — the ``TourMixin`` on
    the host window drives it, wiring the three buttons to its navigation
    methods.  Keyboard handling lives here so the arrow/Enter/Esc shortcuts work
    whenever the popover (or one of its buttons) has focus.
    """

    def __init__(self, window: Any) -> None:
        super().__init__(window, _POPOVER_FLAGS)
        self._win = window
        self.setObjectName("tour_popover")
        self.setAccessibleName(tr("Guided tour"))
        # A subtle, theme-independent card look so it reads on any theme.
        self.setStyleSheet(
            "#tour_popover{background:#20232b;border:2px solid #7aa2f7;"
            "border-radius:10px;}"
            "#tour_popover QLabel{color:#e8e8e8;}"
            "#tour_title{font-size:15px;font-weight:bold;color:#7aa2f7;}"
            "#tour_body{font-size:13px;}"
            "#tour_progress{color:#a0a0a0;font-size:11px;}"
        )
        self.setMinimumWidth(320)
        self.setMaximumWidth(420)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(8)

        self._title = QLabel("", self)
        self._title.setObjectName("tour_title")
        self._title.setWordWrap(True)
        root.addWidget(self._title)

        self._body = QLabel("", self)
        self._body.setObjectName("tour_body")
        self._body.setWordWrap(True)
        self._body.setTextFormat(
            Qt.TextFormat.RichText if hasattr(Qt, "TextFormat")
            else Qt.RichText  # type: ignore[attr-defined]
        )
        root.addWidget(self._body)

        self._progress = QLabel("", self)
        self._progress.setObjectName("tour_progress")
        root.addWidget(self._progress)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._skip_btn = QPushButton(tr("Skip tour"), self)
        self._skip_btn.setAccessibleName(tr("Skip tour"))
        self._skip_btn.clicked.connect(window._tour_finish)
        self._back_btn = QPushButton(tr("Back"), self)
        self._back_btn.setAccessibleName(tr("Previous step"))
        self._back_btn.clicked.connect(window._tour_back)
        self._next_btn = QPushButton(tr("Next"), self)
        self._next_btn.setAccessibleName(tr("Next step"))
        self._next_btn.setDefault(True)
        self._next_btn.clicked.connect(window._tour_next)
        btn_row.addWidget(self._skip_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self._back_btn)
        btn_row.addWidget(self._next_btn)
        root.addLayout(btn_row)

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802 (Qt override)
        key = event.key()
        if key in (_KEY_RIGHT, _KEY_RETURN, _KEY_ENTER, _KEY_N):
            self._win._tour_next()
        elif key in (_KEY_LEFT, _KEY_BACKSPACE, _KEY_B):
            self._win._tour_back()
        elif key == _KEY_ESCAPE:
            self._win._tour_finish()
        else:
            super().keyPressEvent(event)


class TourMixin:
    """First-run guided tour: step data + navigation, mixed into StarWindow."""

    #: Live popover instance while the tour is running; None otherwise.
    _tour_popover: Optional[Any] = None
    #: Index of the current step within ``_tour_steps()``.
    _tour_index: int = 0

    def _tour_steps(self) -> "List[Dict[str, str]]":
        """Return the ordered tour steps.

        Each step is ``{"anchor", "title", "body"}`` where *anchor* is the
        stable English label of a toolbar control in ``self._toolbar_actions``
        (or ``""`` for a window-centred step).  Kept as a method (not a class
        constant) so every string is freshly localised through tr() on the
        active UI language each time the tour runs.
        """
        return [
            {
                "anchor": "Open",
                "title": tr("Open a document"),
                "body": tr(
                    "Click <b>Open</b> (or press <b>Ctrl+O</b>) to read a PDF, "
                    "Word, EPUB, web page, and many more formats. This welcome "
                    "page is itself a real document you can read right now."
                ),
            },
            {
                "anchor": "Play / Pause",
                "title": tr("Listen with built-in speech"),
                "body": tr(
                    "Press <b>Space</b> or click <b>Play / Pause</b> to start "
                    "reading aloud. Each word is highlighted as it is spoken. "
                    "Press <b>Escape</b> to stop."
                ),
            },
            {
                "anchor": "Faster",
                "title": tr("Set your reading speed"),
                "body": tr(
                    "Use <b>Slower</b> and <b>Faster</b> (or <b>Ctrl+−</b> / "
                    "<b>Ctrl+=</b>) to tune the speaking rate to a comfortable "
                    "pace while it reads."
                ),
            },
            {
                "anchor": "Highlight",
                "title": tr("Highlight and take notes"),
                "body": tr(
                    "Select text and click <b>Highlight</b> to mark it, or add a "
                    "note at the cursor with <b>Ctrl+Shift+A</b>. Your highlights "
                    "and notes are saved per document and can be exported."
                ),
            },
            {
                "anchor": "Voice",
                "title": tr("Choose and manage voices"),
                "body": tr(
                    "Click <b>Voice</b> to pick a speaking voice. The full "
                    "<b>Voice Manager</b> (<b>F4</b>, under the Speech menu) lets "
                    "you search, preview, and favourite voices across engines."
                ),
            },
            {
                "anchor": "",
                "title": tr("Build a library"),
                "body": tr(
                    "Point star at any folder — even a synced Dropbox or OneDrive "
                    "folder — with <b>Ctrl+Shift+L</b> and browse it as a library, "
                    "with reading progress remembered per document."
                ),
            },
            {
                "anchor": "Theme",
                "title": tr("Reading aids for every reader"),
                "body": tr(
                    "The <b>View ▸ Reading Aids</b> menu offers a "
                    "dyslexia-friendly font, adjustable text spacing, bionic "
                    "reading, and one-word-at-a-time RSVP. Press <b>F5</b> to "
                    "cycle themes, including a high-contrast theme."
                ),
            },
        ]

    # ── lifecycle ──────────────────────────────────────────────────────
    def _maybe_run_first_run_tour(self) -> None:
        """Show the tour once on first launch, unless already seen.

        Gated by the ``tour_seen`` setting so it never re-triggers on its own.
        Best-effort: a failure here must never block the app.

        Never starts while a modal dialog is up: on a true first run the
        optional-features chooser (and possibly the autosave-recovery prompt)
        opens right after the window shows, and this singleShot(0) would fire
        inside its exec() loop — popping the tour on top of a modal the user
        must deal with first, with the tour impossible to dismiss.  While any
        modal is active, re-check shortly; the tour begins once the user has
        dealt with first-run dialogs.
        """
        try:
            if bool(self.settings.get("tour_seen", False)):
                return
            app = QApplication.instance()
            if app is not None and app.activeModalWidget() is not None:
                QTimer.singleShot(500, self._maybe_run_first_run_tour)
                return
            self._start_tour()
        except Exception:  # noqa: BLE001 — onboarding must never crash a launch.
            pass

    def _start_tour(self) -> None:
        """Start (or restart) the guided tour from the first step.

        Wired to *Help ▸ Guided Tour* (Shift+F1) and to the first-run check.
        Idempotent: a running tour is torn down and restarted cleanly.
        """
        if self._tour_popover is not None:
            self._tour_popover.close()
            self._tour_popover = None
        self._tour_index = 0
        self._tour_popover = _TourPopover(self)
        self._tour_show_step()

    def _tour_finish(self) -> None:
        """End the tour, mark it seen, and clean up the popover.

        Called on Skip, Escape, or after the last step. Persisting
        ``tour_seen`` here (rather than only on completion) means a user who
        skips is not nagged again — the tour stays reachable from the Help menu.
        """
        if self._tour_popover is not None:
            self._tour_popover.close()
            self._tour_popover = None
        try:
            self.settings.set("tour_seen", True)
        except Exception:  # noqa: BLE001 — never fail on a settings write.
            pass
        try:
            self.statusBar().showMessage(tr("Guided tour closed"), 4000)
        except Exception:  # noqa: BLE001
            pass

    # ── navigation ─────────────────────────────────────────────────────
    def _tour_next(self) -> None:
        """Advance to the next step, or finish after the last one."""
        if self._tour_popover is None:
            return
        if self._tour_index >= len(self._tour_steps()) - 1:
            self._tour_finish()
            return
        self._tour_index += 1
        self._tour_show_step()

    def _tour_back(self) -> None:
        """Go back one step (no-op on the first step)."""
        if self._tour_popover is None or self._tour_index <= 0:
            return
        self._tour_index -= 1
        self._tour_show_step()

    def _tour_show_step(self) -> None:
        """Render the current step into the popover, place it, and announce it."""
        pop = self._tour_popover
        if pop is None:
            return
        steps = self._tour_steps()
        # Clamp defensively so a stale index can never index out of range.
        self._tour_index = max(0, min(self._tour_index, len(steps) - 1))
        step = steps[self._tour_index]

        pop._title.setText(step["title"])
        pop._body.setText(step["body"])
        n = len(steps)
        i = self._tour_index + 1
        pop._progress.setText(tr("Step {i} of {n}").format(i=i, n=n))

        # Back is disabled on the first step; the final step's Next reads "Done".
        pop._back_btn.setEnabled(self._tour_index > 0)
        last = self._tour_index == n - 1
        pop._next_btn.setText(tr("Done") if last else tr("Next"))

        pop.adjustSize()
        self._tour_position(step.get("anchor", ""))
        pop.show()
        pop.raise_()
        pop.setFocus()

        # Speak the step to assistive tech without stealing document focus.
        # Strip the light HTML in the body so the announcement is clean prose.
        spoken = f"{step['title']}. " + _strip_html(step["body"])
        announce(pop, spoken)

    def _tour_position(self, anchor: str) -> None:
        """Place the popover next to *anchor*'s on-screen rect (or window centre).

        *anchor* is a toolbar-action label in ``self._toolbar_actions``.  When
        the control has a real geometry the popover sits just below it; when it
        has none (offscreen QPA, hidden toolbar) or the anchor is empty, the
        popover is centred on the window.  Always clamped to stay on screen.
        """
        pop = self._tour_popover
        if pop is None:
            return
        pw, ph = pop.width(), pop.height()
        target_rect = self._tour_anchor_rect(anchor)
        if target_rect is not None:
            # Below the button, left-aligned to it.
            gx = target_rect.left()
            gy = target_rect.bottom() + 8
        else:
            # Centre on the window.
            geo = self.frameGeometry()
            gx = geo.center().x() - pw // 2
            gy = geo.center().y() - ph // 2

        # Clamp to the available screen so the card is never off-screen.
        screen_rect = self._tour_screen_rect()
        if screen_rect is not None:
            margin = 8
            gx = max(screen_rect.left() + margin,
                     min(gx, screen_rect.right() - pw - margin))
            gy = max(screen_rect.top() + margin,
                     min(gy, screen_rect.bottom() - ph - margin))
        pop.move(int(gx), int(gy))

    def _tour_anchor_rect(self, anchor: str) -> Optional[Any]:
        """Return the global QRect of *anchor*'s toolbar button, or None.

        None when the anchor is empty/unknown, its widget is missing, or the
        widget has no real geometry yet (width/height 0 — the offscreen case).
        """
        if not anchor:
            return None
        actions = getattr(self, "_toolbar_actions", None)
        toolbar = getattr(self, "_toolbar", None)
        if not actions or toolbar is None:
            return None
        act = actions.get(anchor)
        if act is None:
            return None
        widget = toolbar.widgetForAction(act)
        if widget is None or widget.width() <= 0 or widget.height() <= 0:
            return None
        top_left = widget.mapToGlobal(widget.rect().topLeft())
        rect = widget.rect()
        rect.moveTopLeft(top_left)
        return rect

    def _tour_screen_rect(self) -> Optional[Any]:
        """Available geometry of the window's screen, or None if unavailable."""
        try:
            handle = self.screen() if hasattr(self, "screen") else None
            if handle is not None:
                return handle.availableGeometry()
            app = QApplication.instance()
            if app is not None and app.primaryScreen() is not None:
                return app.primaryScreen().availableGeometry()
        except Exception:  # noqa: BLE001
            return None
        return None


def _strip_html(text: str) -> str:
    """Return *text* with simple HTML tags removed, for a clean spoken string."""
    import re

    return re.sub(r"<[^>]+>", "", text).replace("&amp;", "&").strip()
