"""ReviewMixin — the in-app spaced-repetition review dashboard for StarWindow.

Notes and highlights become review cards (front = the highlighted passage, back
= the note).  This mixin adds **Study ▸ Review Due Cards…** — a keyboard-first,
accessible dialog that walks the reader through the cards due today, reveals the
answer on Enter, and grades recall with four buttons (or keys 1–4).  Each grade
updates the card's ``sr_state`` immediately via the pure scheduler in
``star/sr.py`` (through the persistence helpers in ``star/annotations.py``), so
progress is saved as the session runs — closing mid-session loses nothing.

Accessibility: every control carries an accessible name/description; the reveal
and grade actions are reachable by keyboard alone (Enter reveals; 1/2/3/4 grade;
the buttons are also focusable and clickable).  The header announces the due
count and the running retention estimate so a screen-reader user always knows
where they are in the deck.

IMPORT SAFETY: references Qt at module scope — imported lazily by
main_window.py (itself imported by runner.py after the ``_QT`` guard), like the
other ``mixin_*.py`` modules.
"""
from .._runtime import *  # noqa: F401,F403
from ..annotations import (
    due_cards,
    get_sr_state,
    review_annotation,
    review_summary,
)
from ..i18n import tr
from .. import sr

# The four grades, in dashboard order, with the key that triggers each.
_GRADE_BUTTONS = (
    ("again", "1", "Again"),
    ("hard", "2", "Hard"),
    ("good", "3", "Good"),
    ("easy", "4", "Easy"),
)


class ReviewMixin:
    # ── entry point ─────────────────────────────────────────────────────────
    def _qt_review_due(self) -> None:
        """Open the spaced-repetition review dashboard (Study ▸ Review Due Cards…)."""
        cards = due_cards(self.settings)
        if not cards:
            summary = review_summary(self.settings)
            if summary["total"] == 0:
                QMessageBox.information(
                    self,
                    tr("Review"),
                    tr("No review cards yet. Add notes or highlights, then come "
                       "back here to study them."),
                )
            else:
                QMessageBox.information(
                    self,
                    tr("Review"),
                    tr("Nothing due right now — all caught up!"),
                )
            return
        dlg = _ReviewDialog(self, cards)
        dlg.exec()
        # A session may have moved the reading position around; leave the
        # document as-is, but refresh the Notes panel so any new scheduling is
        # reflected if the user reopens it.
        if hasattr(self, "_qt_build_annotations"):
            try:
                self._qt_build_annotations()
            except Exception:
                pass

    # ── AnkiConnect two-way sync ─────────────────────────────────────────────
    def _qt_anki_sync(self) -> None:
        """Push cards to a running Anki and pull back review state (best-effort).

        Uses the AnkiConnect add-on over localhost.  Fully offline-safe: if Anki
        is not running the user gets a friendly hint instead of an error.
        """
        from .. import anki_sync

        if not anki_sync.is_available():
            QMessageBox.information(
                self,
                tr("Anki sync"),
                tr("Could not reach Anki. Start Anki with the AnkiConnect add-on "
                   "installed, then try again."),
            )
            return
        try:
            result = anki_sync.sync_annotations(self.settings)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, tr("Anki sync failed"), str(exc))
            return
        pushed = result.get("pushed", {})
        self.statusBar().showMessage(
            tr("Anki sync: {added} pushed, {pulled} updated.").format(
                added=pushed.get("added", 0), pulled=result.get("pulled", 0)
            )
        )


class _ReviewDialog(QDialog):
    """The modal review session dialog.

    Holds the queue of due cards and drives one card at a time: show the front,
    reveal the back on Enter, grade with 1–4, then advance.  Grading writes the
    new ``sr_state`` straight to settings via ``review_annotation`` so the
    session is crash-safe.
    """

    def __init__(self, window: Any, cards: "List[Any]") -> None:
        super().__init__(window)
        self._window = window
        self._settings = window.settings
        # Each queue entry is (doc_path, annotation-dict).
        self._queue: "List[Any]" = list(cards)
        self._pos = 0
        self._revealed = False
        self._graded = 0
        self._today = None  # real today; injected only in tests via _set_today

        self.setWindowTitle(tr("Review Due Cards"))
        self.setMinimumWidth(520)
        self.setMinimumHeight(360)
        self.setAccessibleName(tr("Spaced-repetition review"))
        self._build_ui()
        self._show_card()

    # ── construction ────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Header: progress + due count + retention.
        self._header = QLabel("")
        self._header.setWordWrap(True)
        self._header.setAccessibleName(tr("Review progress"))
        layout.addWidget(self._header)

        # Front (the prompt): the highlighted passage.
        self._front = QLabel("")
        self._front.setWordWrap(True)
        self._front.setTextInteractionFlags(
            _text_selectable_flag()
        )
        self._front.setAccessibleName(tr("Card front"))
        self._front.setStyleSheet("font-size: 16px; padding: 8px;")
        self._front.setMinimumHeight(80)
        layout.addWidget(self._front, 1)

        # Back (the answer): the note.  Hidden until revealed.
        self._back = QLabel("")
        self._back.setWordWrap(True)
        self._back.setTextInteractionFlags(_text_selectable_flag())
        self._back.setAccessibleName(tr("Card back"))
        self._back.setStyleSheet(
            "font-size: 15px; padding: 8px; border-top: 1px solid palette(mid);"
        )
        self._back.setMinimumHeight(80)
        self._back.setVisible(False)
        layout.addWidget(self._back, 1)

        # Reveal button (Enter also reveals; see keyPressEvent).
        self._reveal_btn = QPushButton(tr("Show Answer  (Enter)"))
        self._reveal_btn.setAccessibleName(tr("Show answer"))
        self._reveal_btn.setAccessibleDescription(
            tr("Reveal the note on the back of this card. Shortcut: Enter.")
        )
        self._reveal_btn.clicked.connect(self._reveal)
        layout.addWidget(self._reveal_btn)

        # Four grade buttons (keys 1–4).  Disabled until the answer is shown.
        grade_row = QHBoxLayout()
        self._grade_btns: "Dict[str, QPushButton]" = {}
        for name, key, label in _GRADE_BUTTONS:
            btn = QPushButton(f"{label}  ({key})")
            btn.setAccessibleName(tr(label))
            btn.setAccessibleDescription(
                tr("Grade recall as {label}. Shortcut: key {key}.").format(
                    label=tr(label), key=key
                )
            )
            btn.setEnabled(False)
            btn.clicked.connect(lambda _c=False, g=name: self._grade(g))
            grade_row.addWidget(btn)
            self._grade_btns[name] = btn
        layout.addLayout(grade_row)

        # Footer status + Close.
        self._status = QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        close_box = QDialogButtonBox()
        try:
            _close = QDialogButtonBox.StandardButton.Close
        except AttributeError:  # PyQt5
            _close = QDialogButtonBox.Close  # type: ignore[attr-defined]
        close_box.setStandardButtons(_close)
        close_box.rejected.connect(self.accept)
        layout.addWidget(close_box)

    # ── deterministic-today hook (tests) ────────────────────────────────────
    def _set_today(self, day: Any) -> None:
        """Inject a fixed 'today' so tests schedule deterministically."""
        self._today = day

    # ── card flow ────────────────────────────────────────────────────────────
    def _current(self) -> "Optional[Any]":
        if 0 <= self._pos < len(self._queue):
            return self._queue[self._pos]
        return None

    def _show_card(self) -> None:
        """Render the card at the current position (front only, back hidden)."""
        self._revealed = False
        self._back.setVisible(False)
        self._reveal_btn.setEnabled(True)
        for btn in self._grade_btns.values():
            btn.setEnabled(False)

        pair = self._current()
        if pair is None:
            self._finish()
            return
        _doc, ann = pair
        front = str(ann.get("anchor", "") or "").strip()
        back = str(ann.get("note", "") or "").strip()
        # A note with no highlight is a free-recall prompt; a highlight with no
        # note asks the reader to recall its significance.
        if not front:
            front = tr("(Recall the note for this card)")
        if not back:
            back = tr("(no note — this is a highlight-only card)")
        self._front.setText(front)
        self._back.setText(back)
        self._reveal_btn.setFocus()
        self._update_header()

    def _update_header(self) -> None:
        summary = review_summary(self._settings, self._today)
        total = len(self._queue)
        idx = min(self._pos + 1, total)
        pct = int(round(summary["retention"] * 100))
        self._header.setText(
            tr("Card {i} of {n}  ·  {due} due  ·  retention {pct}%").format(
                i=idx, n=total, due=summary["due"], pct=pct
            )
        )

    def _reveal(self) -> None:
        """Show the answer and enable grading."""
        if self._revealed:
            return
        self._revealed = True
        self._back.setVisible(True)
        self._reveal_btn.setEnabled(False)
        for btn in self._grade_btns.values():
            btn.setEnabled(True)
        # Move focus to Good — the most common grade — for one-key grading.
        self._grade_btns["good"].setFocus()

    def _grade(self, grade: str) -> None:
        """Apply *grade* to the current card, persist, and advance."""
        if not self._revealed:
            # Enforce reveal-before-grade so the reader tests recall honestly.
            self._reveal()
            return
        pair = self._current()
        if pair is None:
            return
        doc, ann = pair
        ann_id = ann.get("id")
        new_state = None
        if ann_id:
            new_state = review_annotation(
                self._settings, doc, ann_id, grade, self._today
            )
        if new_state is None:
            # Fall back to an in-memory update so the session still progresses
            # even if the annotation lost its id somehow.
            new_state = sr.review(get_sr_state(ann), grade, self._today)
            ann["sr_state"] = new_state
        self._graded += 1
        ivl = new_state.get("interval", 0)
        self._status.setText(
            tr("Graded {grade} — next review in {ivl} day(s).").format(
                grade=tr(grade.capitalize()), ivl=ivl
            )
        )
        self._pos += 1
        self._show_card()

    def _finish(self) -> None:
        """Session complete — summarise and let the user close."""
        self._front.setText(tr("Session complete."))
        self._back.setVisible(False)
        self._reveal_btn.setEnabled(False)
        for btn in self._grade_btns.values():
            btn.setEnabled(False)
        summary = review_summary(self._settings, self._today)
        pct = int(round(summary["retention"] * 100))
        self._status.setText(
            tr("Reviewed {n} card(s).  {due} still due.  Retention {pct}%.").format(
                n=self._graded, due=summary["due"], pct=pct
            )
        )
        self._header.setText(tr("All done"))

    # ── keyboard-first grading ───────────────────────────────────────────────
    def keyPressEvent(self, event: Any) -> None:
        """Enter reveals; 1–4 grade; everything else defers to Qt."""
        key = event.key()
        text = event.text()
        try:
            _enter_keys = (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        except AttributeError:  # PyQt5
            _enter_keys = (Qt.Key_Return, Qt.Key_Enter)  # type: ignore[attr-defined]
        if key in _enter_keys and not self._revealed and self._current() is not None:
            self._reveal()
            return
        if text in ("1", "2", "3", "4") and self._revealed:
            grade = {"1": "again", "2": "hard", "3": "good", "4": "easy"}[text]
            self._grade(grade)
            return
        super().keyPressEvent(event)


def _text_selectable_flag() -> Any:
    """Return the TextSelectableByMouse|ByKeyboard interaction flags (PyQt5/6)."""
    try:
        flags = (Qt.TextInteractionFlag.TextSelectableByMouse
                 | Qt.TextInteractionFlag.TextSelectableByKeyboard)  # PyQt6
    except AttributeError:  # PyQt5
        flags = (Qt.TextSelectableByMouse  # type: ignore[attr-defined]
                 | Qt.TextSelectableByKeyboard)
    return flags
