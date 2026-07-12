"""SpeechCursorNavMixin — Qt Speech Cursor mode & editor event filter.

Split out of the former ``mixin_navigation.py`` monolith; methods moved
verbatim.  Mixed into StarWindow via ``NavigationMixin``; holds no state of
its own, operating on StarWindow instance state via ``self``.

IMPORT SAFETY: references Qt at module scope — imported lazily by
main_window.py (itself imported by runner.py after the _QT guard).
"""
from ..._runtime import *  # noqa: F401,F403
from ...tts import Pyttsx3Backend, _SCReader
from ...ttstext import _preprocess_tts_text


class SpeechCursorNavMixin:
    # ── Speech Cursor mode (Qt) ─────────────────────────────────────

    def _key_enums(self) -> Tuple[Any, ...]:
        """Resolve and cache the Qt event-type / Control-key enums once.

        Returns ``(KeyPress, KeyRelease, ShortcutOverride, Shortcut,
        Key_Control)`` for whichever PyQt binding is active.
        """
        if self._key_enum_cache is not None:
            return self._key_enum_cache
        try:
            from PyQt6.QtCore import QEvent

            ET = QEvent.Type
            vals = (
                ET.KeyPress,
                ET.KeyRelease,
                ET.ShortcutOverride,
                ET.Shortcut,
                Qt.Key.Key_Control,
            )
        except (ImportError, AttributeError):
            from PyQt5.QtCore import QEvent  # type: ignore

            vals = (
                QEvent.KeyPress,  # type: ignore[attr-defined]
                QEvent.KeyRelease,  # type: ignore[attr-defined]
                QEvent.ShortcutOverride,  # type: ignore[attr-defined]
                QEvent.Shortcut,  # type: ignore[attr-defined]
                Qt.Key_Control,  # type: ignore[attr-defined]
            )
        self._key_enum_cache = vals
        return vals

    def _ctrl_tap_track(self, event: Any) -> None:
        """JAWS-style bare-Ctrl tap → play/pause.

        Tracks Ctrl key presses/releases on the editor.  A clean tap
        (Ctrl pressed and released with no other key, shortcut-override,
        or fired shortcut in between) toggles speech.  Using Ctrl as a
        modifier in a chord never triggers it.  Opt out via the
        ``qt_ctrl_pause`` setting.
        """
        if not self.settings.get("qt_ctrl_pause", True):
            return
        kp, kr, so, sh, k_ctrl = self._key_enums()
        et = event.type()
        if et == sh:
            # A shortcut fired — Ctrl was part of a chord, not a tap.
            self._ctrl_solo = False
            return
        if et in (kp, so):
            try:
                k = event.key()
                repeat = event.isAutoRepeat()
            except Exception:
                return
            if et == kp and k == k_ctrl and not repeat:
                self._ctrl_solo = True
                self._ctrl_press_t = time.monotonic()
            elif k != k_ctrl:
                # Any other key (or shortcut-override) cancels the tap.
                self._ctrl_solo = False
        elif et == kr:
            try:
                k = event.key()
                repeat = event.isAutoRepeat()
            except Exception:
                return
            if k == k_ctrl and not repeat:
                tap = (
                    self._ctrl_solo
                    and (time.monotonic() - self._ctrl_press_t) < 0.6
                )
                self._ctrl_solo = False
                if tap and not self._qt_edit_mode:
                    self._tts_toggle()

    def eventFilter(self, obj: Any, event: Any) -> bool:
        """Intercept keyboard events on the editor.

        Ctrl (tapped alone) — play / pause speech (JAWS habit)
        Tab    — enter / exit Speech Cursor mode
        While in SC mode:
          ↑ / ↓  — previous / next block, read it
          Enter  — exit SC mode and start continuous reading
          Esc    — exit SC mode, stop speech
        """
        # Find bar input: Escape closes it; F3 / Shift+F3 and Shift+Enter walk
        # matches even while the line edit holds focus.  Handled before the
        # editor branch because the find input is a different widget.
        if obj is getattr(self, "_find_input", None) or obj is getattr(
            self, "_replace_input", None
        ):
            if self._find_input_key(event):
                return True
            return super().eventFilter(obj, event)

        # Clicking an in-document anchor (footnote marker or its ↩ backlink) jumps
        # to it.  Mouse events land on the editor's viewport, not the editor.
        if self.editor is not None and obj is self.editor.viewport():
            if self._editor_anchor_click(event):
                return True
            return super().eventFilter(obj, event)

        if obj is not self.editor:
            return super().eventFilter(obj, event)

        # JAWS-style bare-Ctrl tap toggles speech (never consumes the event).
        self._ctrl_tap_track(event)

        try:
            from PyQt6.QtCore import QEvent  # noqa: F401

            kp = QEvent.Type.KeyPress
            Key = Qt.Key
        except (ImportError, AttributeError):
            from PyQt5.QtCore import QEvent  # type: ignore

            kp = QEvent.KeyPress  # type: ignore
            Key = Qt  # type: ignore

        if event.type() != kp:
            return super().eventFilter(obj, event)

        key = event.key()

        try:
            k_tab = Key.Key_Tab
            k_up = Key.Key_Up
            k_dn = Key.Key_Down
            k_esc = Key.Key_Escape
            k_ret = Key.Key_Return
            k_ent = Key.Key_Enter
        except AttributeError:  # PyQt5 uses Qt.Key_Tab etc. directly
            k_tab = Qt.Key_Tab  # type: ignore
            k_up = Qt.Key_Up  # type: ignore
            k_dn = Qt.Key_Down  # type: ignore
            k_esc = Qt.Key_Escape  # type: ignore
            k_ret = Qt.Key_Return  # type: ignore
            k_ent = Qt.Key_Enter  # type: ignore

        if key == k_tab:
            if self._qt_sc_mode:
                self._qt_sc_exit()
            else:
                self._qt_sc_enter()
            return True  # consume; don't let Tab move focus

        if not self._qt_sc_mode:
            return super().eventFilter(obj, event)

        if key in (k_esc,):
            self._qt_sc_exit()
            return True
        if key in (k_ret, k_ent):
            self._qt_sc_exit(start_reading=True)
            return True
        if key == k_up:
            self._qt_sc_move(-1)
            return True
        if key == k_dn:
            self._qt_sc_move(+1)
            return True

        return super().eventFilter(obj, event)

    def _editor_anchor_click(self, event: Any) -> bool:
        """Jump to an in-document anchor when its link is clicked.

        Footnote markers link to ``#fn-<label>`` and their backlinks to
        ``#fnref-<label>``; ``scrollToAnchor`` matches the ``<a name=…>`` targets
        the renderer emits.  Returns True only when an anchor was actually clicked
        (so ordinary clicks still place the caret)."""
        try:
            from PyQt6.QtCore import QEvent

            rel = QEvent.Type.MouseButtonRelease
        except (ImportError, AttributeError):
            from PyQt5.QtCore import QEvent  # type: ignore

            rel = QEvent.MouseButtonRelease  # type: ignore
        if event.type() != rel:
            return False
        try:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            anchor = self.editor.anchorAt(pos)
        except Exception:
            return False
        if not anchor:
            return False
        name = anchor[1:] if anchor.startswith("#") else anchor
        try:
            self.editor.scrollToAnchor(name)
        except Exception:
            return False
        return True

    def _qt_sc_enter(self) -> None:
        """Enter Qt Speech Cursor mode.

        Stops any running TTS, positions the reading cursor at the
        visible text-cursor position, and builds the persistent
        _SCReader engine so the first line has no startup lag.
        """
        self.tts_manager.stop()
        self.editor.setExtraSelections([])
        # Position SC cursor at the block under the text cursor.
        tc = self.editor.textCursor()
        self._qt_sc_block = tc.blockNumber()
        # Build the persistent reader so the first keystroke has no
        # SAPI5 engine-creation delay and stop() is always effective.
        if _PYTTSX3 and isinstance(self.tts_manager._backend, Pyttsx3Backend):
            self._qt_sc_reader = _SCReader(
                rate=int(self.settings["tts_rate"]),
                volume=float(self.settings["tts_volume"]),
            )
            self._qt_sc_reader.start()
        else:
            self._qt_sc_reader = None
        self._qt_sc_mode = True
        self._qt_sc_highlight()
        self.setWindowTitle(f"● SC CURSOR — {APP_TITLE}")
        self.statusBar().showMessage(
            "Speech Cursor ON  ↑↓:line  Enter:read-on  Esc/Tab:exit"
        )

    def _qt_sc_exit(self, start_reading: bool = False) -> None:
        """Exit Qt Speech Cursor mode.  Speech is always stopped first."""
        self._qt_sc_mode = False
        # Stop the persistent reader before stopping the main manager
        # so the SAPI5 engine is always reachable.
        if self._qt_sc_reader is not None:
            self._qt_sc_reader.close()
            self._qt_sc_reader = None
        self.tts_manager.stop()
        self.editor.setExtraSelections([])
        self.setWindowTitle(APP_TITLE)
        if start_reading:
            # Start continuous reading from the SC cursor position.
            doc_obj = self.editor.document()
            block = doc_obj.findBlockByNumber(self._qt_sc_block)
            if block.isValid():
                char_pos = block.position()
                wm = getattr(self.doc, "word_map", [])
                if wm:
                    qwm = self._qt_word_map
                    wi = 0
                    for i, off in enumerate(qwm):
                        if off >= char_pos:
                            wi = i
                            break
                    self._tts_play_from_word(wi)
                    self.statusBar().showMessage(
                        f"Reading from line {self._qt_sc_block + 1}"
                    )
                    return
            self._tts_play()
        else:
            self.statusBar().showMessage("Speech Cursor OFF")

    def _qt_sc_move(self, delta: int) -> None:
        """Move the SC cursor by *delta* blocks and read the new block."""
        doc_obj = self.editor.document()
        n_blocks = doc_obj.blockCount()
        if n_blocks == 0:
            return
        self._qt_sc_block = max(0, min(self._qt_sc_block + delta, n_blocks - 1))
        self._qt_sc_highlight()
        self._qt_sc_read_block()

    def _qt_sc_highlight(self) -> None:
        """Highlight the current SC cursor block with a bar selection."""
        doc_obj = self.editor.document()
        block = doc_obj.findBlockByNumber(self._qt_sc_block)
        if not block.isValid():
            return
        tc = QTextCursor(block)
        self.editor.setTextCursor(tc)
        self.editor.ensureCursorVisible()
        tc2 = QTextCursor(block)
        tc2.select(
            QTextCursor.SelectionType.BlockUnderCursor
            if hasattr(QTextCursor, "SelectionType")
            else QTextCursor.BlockUnderCursor  # type: ignore
        )
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#313244"))
        sel = QTextEdit.ExtraSelection()
        sel.cursor = tc2
        sel.format = fmt
        self.editor.setExtraSelections([sel])

    def _qt_sc_read_block(self) -> None:
        """Speak the plain text of the current SC cursor block.

        Uses the persistent _SCReader when the pyttsx3 backend is
        active so that stop() is always effective and there is no
        200–500 ms SAPI5 engine-construction window between navigation
        keystrokes.  Falls back to direct backend.speak() for eSpeak
        and other subprocess-based backends where termination is
        trivially reliable.
        """
        doc_obj = self.editor.document()
        block = doc_obj.findBlockByNumber(self._qt_sc_block)
        text = block.text().strip() if block.isValid() else ""
        # Stop the main TTS manager (clears timer, highlight, etc.) then
        # drive speech through the SC reader or backend directly.
        self.tts_manager.stop()
        if not text:
            if self._qt_sc_reader is not None:
                self._qt_sc_reader.speak("blank")
            else:
                self.tts_manager._backend.speak("blank")
            self.statusBar().showMessage(
                f"SC  —  line {self._qt_sc_block + 1}: (blank)"
            )
            return
        text = _preprocess_tts_text(text, self.settings)
        if self._qt_sc_reader is not None:
            self._qt_sc_reader.speak(text)
        else:
            self.tts_manager._backend.speak(text)
        self.statusBar().showMessage(
            f"SC  —  line {self._qt_sc_block + 1}: {text[:80]}"
        )
