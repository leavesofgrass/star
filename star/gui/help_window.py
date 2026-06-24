"""Extracted Help dialog (_HelpWindow) for the Qt GUI.

WHY THIS MODULE EXISTS: the Qt GUI was historically one ~5,600-line
star/gui.py whose entire contents were nested inside a single
_run_qt_gui() function.  _HelpWindow was a class defined inside that
closure, so it captured the StarWindow class and the Qt-binding
enum-compat constants (_QUEUED for QueuedConnection, _KEEP_ANCHOR for
QTextCursor.MoveMode.KeepAnchor) as closure variables.  Pulling it into its
own module makes the GUI package smaller and testable without changing
behavior: build_help_window_class() takes those captured values as explicit
parameters instead of relying on the enclosing function's scope.  See
docs/architecture.md for the wider split.
"""
from .._runtime import *  # noqa: F401,F403
from ..documents import _build_word_map
from ..ttstext import _strip_markdown_for_tts
from ..tui import _HELP_TEXT


def build_help_window_class(StarWindow, _QUEUED, _KEEP_ANCHOR):
    """Construct and return the _HelpWindow QDialog subclass.

    Parameters carry the values _HelpWindow used to close over when it was
    nested in gui._run_qt_gui(); passing them in keeps the runtime behavior
    identical.
    """
    class _HelpWindow(QDialog):
        """Help window that mirrors the main window\'s TTS controls.

        Opened by StarWindow._show_about().  Uses the parent StarWindow\'s
        TTSManager so rate / volume changes propagate immediately.  On open
        it saves and takes over the manager\'s word-map and highlight
        callback; on close it restores them so the main window can resume
        normal highlighting.
        """

        # Thread-safe word-highlight delivery (same pattern as StarWindow).
        _word_signal = pyqtSignal(int)

        def __init__(self, parent: StarWindow) -> None:  # type: ignore[name-defined]
            super().__init__(parent)
            self._sw = parent
            self._doc_plain: str = ""
            self._word_map: List = []
            self._qt_word_map: List[int] = []
            # Saved parent TTS state — restored when this window closes.
            self._saved_word_map: List = []
            self._saved_hl_cb = None

            self._hl_fmt = QTextCharFormat()
            self._hl_fmt.setBackground(QColor("#06b6d4"))
            self._hl_fmt.setForeground(QColor("#000000"))
            self._hl_fmt.setFontWeight(700)

            self._setup_ui()
            self._word_signal.connect(self._apply_highlight, _QUEUED)
            # Kick off async word-map build so TTS can highlight words.
            self._load_async()

        # ── UI ────────────────────────────────────────────────────────────

        def _setup_ui(self) -> None:
            self.setWindowTitle(f"Help — {APP_TITLE}")
            self.resize(780, 600)

            root = QVBoxLayout(self)
            root.setContentsMargins(0, 0, 0, 0)
            root.setSpacing(0)

            # ─ Toolbar ─ identical actions to the main window ──────────────
            tb = QToolBar("TTS Controls")
            tb.setMovable(False)

            def _act(label: str, shortcut: str, fn: Any) -> None:
                a = QAction(label, self)
                if shortcut:
                    a.setShortcut(shortcut)
                a.triggered.connect(fn)
                tb.addAction(a)

            _act("Play/Pause ▶⏸", "Space", self._tts_toggle)
            _act("Stop ■", "Escape", self._tts_stop)
            _act("+ Speed", "Ctrl+=", lambda: self._rate_change(+20))
            _act("− Speed", "Ctrl+-", lambda: self._rate_change(-20))
            tb.addSeparator()
            _act("Close", "Ctrl+W", self.close)
            root.addWidget(tb)

            # ─ Editor ────────────────────────────────────────────
            pal = self._sw._PALETTES.get(
                self._sw.settings.get("theme", "dark"),
                self._sw._PALETTES["dark"],
            )
            font_size = int(self._sw.settings.get("font_size", 0)) or 14
            self.editor = QTextEdit()
            self.editor.setReadOnly(True)
            self.editor.setFont(
                QFont(self._sw.settings.get("qt_font_family", "Georgia"), font_size)
            )
            self.editor.setCursorWidth(0)
            self.editor.setStyleSheet(
                "QTextEdit {"
                f" background-color:{pal['bg']}; color:{pal['fg']};"
                f" font-size:{font_size}pt;"
                f" selection-background-color:{pal['sel']};"
                "}"
            )
            root.addWidget(self.editor)

            # ─ Status label ──────────────────────────────────────────
            self._status = QLabel(" ")
            self._status.setContentsMargins(4, 0, 0, 2)
            root.addWidget(self._status)

            # Show HTML immediately; TTS word map loads asynchronously.
            self.editor.setHtml(self._sw._md_to_html(_HELP_TEXT))

        # ── Content / word map ──────────────────────────────────────────

        def _load_async(self) -> None:
            """Build the TTS plain text and word map in a background thread
            so the window appears instantly."""
            qt_text = self.editor.document().toPlainText()

            def _work() -> None:
                plain = _strip_markdown_for_tts(_HELP_TEXT, self._sw.settings)
                flat = qt_text.splitlines()
                wm = _build_word_map(plain, flat)

                # Build Qt character-offset map (same algorithm as StarWindow).
                qt_lower = qt_text.lower()
                tok = re.compile(r"\b\w[\w'-]*")
                result: List[int] = []
                sfrom = 0
                for m in tok.finditer(plain):
                    w = m.group().lower()
                    p = qt_lower.find(w, sfrom)
                    if p >= 0:
                        result.append(p)
                        sfrom = p + 1
                    else:
                        p = qt_lower.find(w, 0)
                        result.append(p if p >= 0 else 0)

                self._doc_plain = plain
                self._word_map = wm
                self._qt_word_map = result

            threading.Thread(target=_work, daemon=True).start()

        # ── TTS ───────────────────────────────────────────────────────────

        def _tts_play(self) -> None:
            if not self._doc_plain:
                self._status.setText("Help text still loading … try again in a moment")
                return
            tm = self._sw.tts_manager
            wm = self._word_map
            text_offset = wm[0].tts_offset if wm else 0
            # Take over the manager\'s word map and highlight callback.
            self._saved_word_map = tm._word_map
            self._saved_hl_cb = tm._on_highlight
            tm.set_word_map(wm)
            tm.set_on_highlight(lambda idx: self._word_signal.emit(idx))
            tm.speak(
                self._doc_plain[text_offset:],
                start_word_idx=0,
                text_offset=text_offset,
            )
            self._status.setText(
                f"Reading at {self._sw.settings['tts_rate']} wpm"
                f"  —  via {tm.backend_name}"
            )

        def _tts_stop(self) -> None:
            self._sw.tts_manager.stop()
            self.editor.setExtraSelections([])
            self._status.setText("Stopped.")

        def _tts_toggle(self) -> None:
            if self._sw.tts_manager.speaking:
                self._tts_stop()
            else:
                self._tts_play()

        def _rate_change(self, delta: int) -> None:
            new_rate = max(50, min(600, int(self._sw.settings["tts_rate"]) + delta))
            self._sw.tts_manager.set_rate(new_rate)
            if self._sw._qt_sc_reader is not None:
                self._sw._qt_sc_reader.update_rate(new_rate)
            self._status.setText(f"Rate: {new_rate} wpm")

        # ── Word highlight ─────────────────────────────────────────────────

        def _apply_highlight(self, word_idx: int) -> None:
            self.editor.setExtraSelections([])
            if word_idx < 0 or not self._qt_word_map:
                return
            if word_idx >= len(self._qt_word_map):
                return
            char_pos = self._qt_word_map[word_idx]
            word_len = 1
            if word_idx < len(self._word_map):
                word_len = max(1, self._word_map[word_idx].tts_len)
            doc_obj = self.editor.document()
            doc_len = doc_obj.characterCount()
            if char_pos >= doc_len:
                return
            word_len = min(word_len, doc_len - char_pos - 1)
            if word_len <= 0:
                return
            cursor = QTextCursor(doc_obj)
            cursor.setPosition(char_pos)
            cursor.setPosition(char_pos + word_len, _KEEP_ANCHOR)
            sel = QTextEdit.ExtraSelection()
            sel.format = self._hl_fmt
            sel.cursor = cursor
            self.editor.setExtraSelections([sel])
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()
            if word_idx < len(self._word_map):
                word_text = self._word_map[word_idx].word
                pct = int(100 * word_idx / max(1, len(self._word_map)))
                self._status.setText(
                    f"▶  “{word_text}”  —  {pct}%"
                    f"  —  {self._sw.settings['tts_rate']} wpm"
                )

        # ── Close ──────────────────────────────────────────────────────────────

        def closeEvent(self, event: Any) -> None:
            """Stop speech and restore the main window\'s TTS context."""
            tm = self._sw.tts_manager
            tm.stop()
            self.editor.setExtraSelections([])
            # Restore the main window\'s word map.
            restore_wm = self._saved_word_map
            if not restore_wm and self._sw.doc:
                restore_wm = getattr(self._sw.doc, "word_map", []) or []
            tm.set_word_map(restore_wm)
            # Restore highlight callback — rewire to the main window\'s signal.
            if self._saved_hl_cb is not None:
                tm.set_on_highlight(self._saved_hl_cb)
            else:
                tm.set_on_highlight(lambda idx: self._sw._word_signal.emit(idx))
            event.accept()
    return _HelpWindow
