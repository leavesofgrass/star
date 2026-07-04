"""DisplayMixin — methods extracted from StarWindow (main_window.py).

Mixed into StarWindow via ``class StarWindow(DisplayMixin, ...)``; operates
on StarWindow instance state and other methods via ``self``, holding no
state of its own.  IMPORT SAFETY: references Qt at module scope — imported
lazily by main_window.py (itself imported by runner.py after the _QT guard).
"""
from .._runtime import *  # noqa: F401,F403
from ..i18n import tr
from ..themes import _load_css_themes, detect_os_color_scheme, theme_for_os_scheme
from .a11y import announce


class DisplayMixin:
    # ── Display options ─────────────────────────────────────────────────────

    def _rate_change(self, delta: int) -> None:
        new_rate = max(50, min(600, int(self.settings["tts_rate"]) + delta))
        self.tts_manager.set_rate(new_rate)
        if self._qt_sc_reader is not None:
            self._qt_sc_reader.update_rate(new_rate)
        self.statusBar().showMessage(f"Rate: {new_rate} wpm")

    def _voice_picker_qt(self) -> None:
        """Open a native voice-selection dialog.

        Lists all voices available from the active TTS backend by their
        friendly name (not the raw Windows registry ID).  The user picks
        one from a scrollable list; pressing OK applies the voice and
        speaks a short confirmation so the change is immediately audible.
        Ctrl+T opens this dialog from anywhere in the GUI.
        """
        voices = self.tts_manager.list_voices()
        if not voices:
            self.statusBar().showMessage(
                "No TTS voices found. Is pyttsx3 installed "
                "and the backend set to pyttsx3?"
            )
            return

        # Build display strings (name + language tag).
        items: List[str] = []
        for v in voices:
            name = v.get("name", v.get("id", "Unknown"))
            lang = v.get("lang", "")
            items.append(f"{name}  [{lang}]" if lang else name)

        # Highlight the current voice.
        current_id = str(self.settings.get("tts_voice", ""))
        current_idx = 0
        for i, v in enumerate(voices):
            if v.get("id") == current_id:
                current_idx = i
                break

        chosen, ok = QInputDialog.getItem(
            self,
            "Select TTS Voice",
            "Choose a voice  (Ctrl+T to reopen):",
            items,
            current_idx,
            False,  # not editable — must pick from the list
        )
        if not ok:
            return

        idx = items.index(chosen)
        v = voices[idx]
        voice_id = v.get("id", "")
        voice_name = v.get("name", voice_id)
        self.tts_manager._backend.set_voice(voice_id)
        self.settings.set("tts_voice", voice_id)
        self.statusBar().showMessage(f"Voice: {voice_name}")
        # Stop any running speech and speak a brief test phrase so the
        # user hears the new voice without having to press Play.
        self.tts_manager.stop()
        self.editor.setExtraSelections([])
        self.tts_manager._backend.speak(f"Voice changed to {voice_name}.")

    def _qt_preferences(self) -> None:
        """Open the centralized tabbed Preferences dialog (Tools ▸ Preferences,
        Ctrl+,).  Gathers Reading, Voice, Display, and General settings that were
        previously scattered across per-feature dialogs; OK/Apply write and apply,
        Cancel changes nothing."""
        from .preferences import PreferencesDialog
        PreferencesDialog(self).exec()

    def _apply_qt_theme(self, theme_name: str) -> None:
        """Apply *theme_name* to the editor widget and re-render.

        Uses _effective_palette so CSS-file themes are honored for
        both the QTextEdit stylesheet and the HTML body styling.
        """
        pal = self._effective_palette(theme_name)
        font_size = int(self.settings.get("font_size", 0)) or 14
        sheet = (
            "QTextEdit, QTextBrowser {"
            f"  background-color: {pal['bg']};"
            f"  color: {pal['fg']};"
            f"  font-size: {font_size}pt;"
            f"  selection-background-color: {pal['sel']};"
            "}"
        )
        self.editor.setStyleSheet(sheet)
        if hasattr(self, "_preview"):
            self._preview.setStyleSheet(sheet)
        # In edit mode the editor holds raw Markdown source the user is
        # editing — re-rendering it as HTML would destroy their edits.
        # Only refresh the rendered view when NOT editing; the live
        # preview pane is refreshed instead.
        if getattr(self, "_qt_edit_mode", False):
            if hasattr(self, "_preview") and self._preview.isVisible():
                self._qt_render_preview()
            return
        # Re-render so the HTML body styles match the new theme.
        if self.doc is not None:
            self.editor.setHtml(self._md_to_html(self.doc.markdown))
        else:
            self.editor.setHtml(self._welcome_html())
        # Line height is a per-document block format reset by setHtml.
        self._apply_block_spacing()

    # ── Caret browsing ───────────────────────────────────────────────
    def _caret_width(self) -> int:
        """Editor caret width honoring the caret-browsing setting (0 = hidden)."""
        return 2 if self.settings.get("qt_caret_browsing", True) else 0

    def _apply_caret_mode(self) -> None:
        """Set the read-only document view's interaction flags + caret width from
        the caret-browsing setting.

        A read-only QTextEdit is mouse-selectable but **not** keyboard-navigable
        by default, so showing the caret is not enough — caret browsing also needs
        the ``TextSelectableByKeyboard`` flag for arrow keys to move the caret and
        Shift+arrows to select.  Call only in read mode (edit mode owns the flags).
        """
        on = bool(self.settings.get("qt_caret_browsing", True))
        try:  # PyQt6
            F = Qt.TextInteractionFlag
            base = F.TextSelectableByMouse | F.LinksAccessibleByMouse
            kbd = F.TextSelectableByKeyboard
        except AttributeError:  # PyQt5
            base = Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse  # type: ignore[attr-defined]
            kbd = Qt.TextSelectableByKeyboard  # type: ignore[attr-defined]
        self.editor.setTextInteractionFlags(base | kbd if on else base)
        self.editor.setCursorWidth(2 if on else 0)

    def _qt_toggle_caret_browsing(self) -> None:
        """Toggle the visible, freely-movable document caret (View ▸ Caret
        Browsing / F7).  When on, the read-only view supports keyboard caret
        navigation, selection for highlighting, and define-word at the caret."""
        on = not bool(self.settings.get("qt_caret_browsing", True))
        self.settings["qt_caret_browsing"] = on
        if not getattr(self, "_qt_edit_mode", False):
            self._apply_caret_mode()
            if on:
                self.editor.setFocus()
        self.statusBar().showMessage(
            "Caret browsing ON — arrows move the caret; select to highlight, "
            "Ctrl+D defines the word at the caret."
            if on
            else "Caret browsing OFF — clean reader view."
        )

    def _maybe_follow_os_theme(self) -> None:
        """On startup, adopt the OS dark/light/high-contrast theme when asked.

        Honors the ``qt_follow_os_theme`` setting and never overrides an
        *explicit* user theme choice (``qt_theme_explicit``): the whole point is
        to give a sensible default that tracks the desktop appearance while
        leaving a deliberate pick untouched.  Detection is best-effort — an
        unknown scheme (older Qt / PyQt5 / no running app) leaves the saved
        theme in place.  Only writes ``theme`` when it actually changes so a
        follow-mode user keeps tracking the OS across launches.
        """
        if not bool(self.settings.get("qt_follow_os_theme", True)):
            return
        if bool(self.settings.get("qt_theme_explicit", False)):
            return
        scheme = detect_os_color_scheme()
        target = theme_for_os_scheme(scheme)
        if target and target != str(self.settings.get("theme", "")):
            # Do NOT mark this as an explicit choice — it must keep following
            # the OS on subsequent launches.
            self.settings["theme"] = target

    def _mark_theme_explicit(self) -> None:
        """Record that the user deliberately chose a theme (stops OS-follow)."""
        if not bool(self.settings.get("qt_theme_explicit", False)):
            self.settings["qt_theme_explicit"] = True

    def _next_theme(self) -> None:
        """Cycle to the next theme (built-in + custom CSS)."""
        all_themes = self._all_theme_names
        current = str(self.settings.get("theme", "dark"))
        idx = all_themes.index(current) if current in all_themes else 0
        new_theme = all_themes[(idx + 1) % len(all_themes)]
        self.settings["theme"] = new_theme
        self._mark_theme_explicit()
        self._apply_qt_theme(new_theme)
        self.statusBar().showMessage(f"Theme: {new_theme}")
        # Announce so screen-reader users hear the change without losing focus.
        announce(self.editor, tr("Theme: {name}").format(name=new_theme))

    def _qt_pick_theme(self) -> None:
        """Open a dialog listing all available themes for direct selection."""
        all_themes = self._all_theme_names
        current = str(self.settings.get("theme", "dark"))
        current_idx = all_themes.index(current) if current in all_themes else 0
        chosen, ok = QInputDialog.getItem(
            self,
            "Choose Theme",
            "Select a color theme:",
            all_themes,
            current_idx,
            False,
        )
        if ok and chosen:
            self.settings["theme"] = chosen
            self._mark_theme_explicit()
            self._apply_qt_theme(chosen)
            self.statusBar().showMessage(f"Theme: {chosen}")
            announce(self.editor, tr("Theme: {name}").format(name=chosen))

    def _qt_reload_css_themes(self) -> None:
        """Re-scan THEMES_DIR and reload all *.css theme files.

        Useful after dropping a new .css file in the themes folder
        without restarting the application.  The current theme is
        re-applied immediately if it was a CSS theme that changed.
        """
        self._css_themes = _load_css_themes()
        n = len(self._css_themes)
        current = str(self.settings.get("theme", "dark"))
        # Re-apply in case the active theme's CSS was modified on disk.
        self._apply_qt_theme(current)
        self.statusBar().showMessage(
            f"CSS themes reloaded — {n} file(s) found in {THEMES_DIR}"
        )

    def _qt_open_themes_folder(self) -> None:
        """Open THEMES_DIR in the system file manager."""
        try:
            THEMES_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        import subprocess as _sp

        try:
            if sys.platform == "win32":
                _sp.Popen(["explorer", str(THEMES_DIR)])
            elif sys.platform == "darwin":
                _sp.Popen(["open", str(THEMES_DIR)])
            else:
                _sp.Popen(["xdg-open", str(THEMES_DIR)])
            self.statusBar().showMessage(f"Opened: {THEMES_DIR}")
        except OSError as exc:
            self.statusBar().showMessage(f"Could not open folder: {exc}")

    def _show_about(self) -> None:
        """Open README.md as a document (F1 help).

        README.md ships alongside the package modules and is the
        canonical reference for every feature, keyboard shortcut, and
        setting.  Opening it in the main window gives the user full TTS,
        navigation, highlighting, and search — far more useful than a
        limited modal dialog.
        """
        readme = self._bundled_path("README.md")
        if readme is not None:
            self._open_path(str(readme))
        else:
            # Should not happen (README ships in package-data), but fall back to
            # the welcome page rather than leaving the user with no help.
            welcome = self._welcome_path
            if welcome is not None:
                self._open_path(str(welcome))
            else:
                self.statusBar().showMessage(
                    f"{APP_TITLE} v{APP_VERSION} — README.md not found", 6000
                )

    def _qt_about(self) -> None:
        """Show the About dialog: a short summary of what star is and does, plus
        a link back to the project on GitHub, with the version and licence."""
        box = QMessageBox(self)
        box.setWindowTitle(f"About {APP_NAME}")
        try:
            box.setTextFormat(Qt.TextFormat.RichText)
            box.setIcon(QMessageBox.Icon.Information)
        except AttributeError:  # PyQt5
            box.setTextFormat(Qt.RichText)  # type: ignore[attr-defined]
            box.setIcon(QMessageBox.Information)  # type: ignore[attr-defined]
        box.setText(
            f"<b>{APP_TITLE}</b><br>Version {APP_VERSION}<br><br>"
            "star reads your documents aloud — PDF, EPUB, Office files, Markdown "
            "and more — with word-by-word highlighting, your choice of "
            "text-to-speech engine, and accessibility-first reading aids. It is "
            "keyboard-driven and screen-reader friendly.<br><br>"
            f'Project &amp; source: <a href="{__url__}">{__url__}</a><br><br>'
            f"{__copyright__} · {__license__}"
        )
        # Make the GitHub link open in the user's browser.
        lbl = box.findChild(QLabel, "qt_msgbox_label")
        if lbl is not None:
            lbl.setOpenExternalLinks(True)
        box.exec() if _QT == "PyQt6" else box.exec_()

    def _set_font(self, family: str = "", size: int = 0) -> None:
        """Change the display font family and/or size.

        Persists both *qt_font_family* and *qt_font_size*, then calls
        _apply_qt_theme so the QTextEdit stylesheet (which embeds the
        font-size) is refreshed in the same step.  Without this, a theme
        cycle after a size change would silently revert to the old size.
        """
        if family:
            self.settings["qt_font_family"] = family
        if size > 0:
            self.settings["qt_font_size"] = size
            # Keep font_size in sync so _apply_qt_theme always reads the
            # correct value regardless of which key it checks.
            self.settings["font_size"] = size
        fam = self._effective_font_family()
        fsz = int(self.settings.get("qt_font_size", 14))
        # setFont sets the base font for the widget (with letter/word
        # spacing); _apply_qt_theme then re-renders the HTML with the
        # matching font-size in the stylesheet and re-applies line height.
        self.editor.setFont(self._make_editor_font())
        self._apply_qt_theme(str(self.settings.get("theme", "dark")))
        self.statusBar().showMessage(f"Font: {fam} {fsz}pt")

    def _qt_copy(self) -> None:
        "Copy selected text or current paragraph to the clipboard."
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText()
        else:
            try:
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            except AttributeError:
                cursor.select(QTextCursor.BlockUnderCursor)  # PyQt5
            text = cursor.selectedText()
        if text:
            QApplication.clipboard().setText(text)
            self.statusBar().showMessage(f"Copied {len(text)} chars")

    def _qt_reading_level(self) -> None:
        "Show Flesch-Kincaid reading level for the current document."
        if not self.doc or not self.doc.plain_text:
            self.statusBar().showMessage("No document loaded")
            return
        text = self.doc.plain_text[:50000]
        words = text.split()
        n_words = max(1, len(words))
        sentences = re.split(r"[.!?]+", text)
        n_sentences = max(1, len([s for s in sentences if s.strip()]))

        def _syl(w):
            w = w.lower().rstrip(".,;:!?")
            c = len(re.findall(r"[aeiou]+", w))
            if w.endswith("e") and c > 1:
                c -= 1
            return max(1, c)

        n_syllables = sum(_syl(w) for w in words)
        ease = (
            206.835
            - 1.015 * (n_words / n_sentences)
            - 84.6 * (n_syllables / n_words)
        )
        grade = (
            0.39 * (n_words / n_sentences) + 11.8 * (n_syllables / n_words) - 15.59
        )
        ease = max(0.0, min(100.0, ease))
        grade = max(0.0, grade)
        level = (
            "elementary"
            if grade < 6
            else "middle school"
            if grade < 9
            else "high school"
            if grade < 13
            else "college"
            if grade < 16
            else "graduate"
        )
        self.statusBar().showMessage(
            f"Reading level: Grade {grade:.1f} ({level})  Ease: {ease:.0f}/100",
            8000,
        )

