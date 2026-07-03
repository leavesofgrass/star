"""EditNavMixin — document edit mode, spell check, live preview, save.

Split out of the former ``mixin_navigation.py`` monolith; methods moved
verbatim.  Mixed into StarWindow via ``NavigationMixin``; holds no state of
its own, operating on StarWindow instance state via ``self``.

IMPORT SAFETY: references Qt at module scope — imported lazily by
main_window.py (itself imported by runner.py after the _QT guard).
"""
from ..._runtime import *  # noqa: F401,F403
from ...documents import _build_word_map
from ...i18n import tr
from ...spellcheck import _SPELL, SpellHighlighter, misspelled_words
from ...ttstext import _strip_markdown_for_tts


class EditNavMixin:
    # ─ document editing ───────────────────────────────────────────────

    def _qt_edit_mode_toggle(self) -> None:
        """Toggle between read mode and edit mode (Ctrl+E).

        In *read mode* the editor displays rendered HTML and is
        read-only.  In *edit mode* the raw Markdown source is shown
        as plain text so the user can make changes with any standard
        text-editing shortcut (Ctrl+Z/Y, Ctrl+X/C/V, arrow keys,
        Delete, Home, End, …).  Ctrl+S saves; Ctrl+E exits without
        saving.
        """
        if not self._qt_edit_mode:
            self._qt_enter_edit_mode()
        else:
            self._qt_exit_edit_mode(save=False)

    def _qt_enter_edit_mode(self) -> None:
        """Switch the editor to editable Markdown source view."""
        if not self.doc:
            self.statusBar().showMessage("No document to edit")
            return
        self.tts_manager.stop()
        self.editor.setReadOnly(False)
        self.editor.setCursorWidth(2)  # visible text cursor
        # Show raw Markdown so the user edits the source, not HTML.
        self.editor.setPlainText(self.doc.markdown or "")
        self.editor.document().setModified(False)
        self._qt_edit_mode = True
        self._qt_edit_dirty = False
        self.editor.document().contentsChanged.connect(
            self._qt_on_edit_contents_changed
        )
        # Attach the red-squiggle spell highlighter while editing (only when
        # pyspellchecker and a Qt QSyntaxHighlighter are both available).
        if _SPELL and SpellHighlighter is not None:
            try:
                self._spell_highlighter = SpellHighlighter(self.editor.document())
            except Exception:  # noqa: BLE001
                self._spell_highlighter = None
        # If the live-preview preference is on, show the preview pane now
        # and render the current source into it.
        if self.settings.get("qt_edit_preview", False):
            self._preview.setVisible(True)
            self._qt_render_preview()
            self.statusBar().showMessage(
                "✏  EDIT MODE — Markdown source + live preview  ·  "
                "Ctrl+S: save  ·  Ctrl+E: discard & exit"
            )
        else:
            self.statusBar().showMessage(
                "✏  EDIT MODE — Markdown source  ·  "
                "Ctrl+S: save  ·  Ctrl+E: discard & exit  ·  "
                "Ctrl+Shift+L: live preview"
            )

    def _qt_on_edit_contents_changed(self) -> None:
        """Mark the document dirty when the user types in edit mode and,
        when the live preview is visible, schedule a debounced re-render."""
        if not self._qt_edit_dirty:
            self._qt_edit_dirty = True
            title = self.doc.title if self.doc else "document"
            self.statusBar().showMessage(
                f"✏  EDIT MODE  ·  {title}  [modified — Ctrl+S to save]"
            )
        if self._qt_edit_mode and self._preview.isVisible():
            # Re-render ~300 ms after the last keystroke (keeps typing snappy).
            self._preview_timer.start(300)

    def _qt_exit_edit_mode(self, save: bool = False) -> None:
        """Leave edit mode, optionally saving first."""
        if not self._qt_edit_mode:
            return
        if save:
            self._qt_save()
        # Disconnect the dirty listener.
        try:
            self.editor.document().contentsChanged.disconnect(
                self._qt_on_edit_contents_changed
            )
        except (RuntimeError, TypeError):
            pass
        # Detach the spell highlighter so it stops re-checking the read-only view.
        if self._spell_highlighter is not None:
            try:
                self._spell_highlighter.setDocument(None)
            except Exception:  # noqa: BLE001
                pass
            self._spell_highlighter = None
        self._qt_edit_mode = False
        self._qt_edit_dirty = False
        # The preview pane is only meaningful while editing; hide it.
        self._preview.setVisible(False)
        # Re-render the (possibly updated) Markdown.
        md = self.doc.markdown if self.doc else ""
        self.editor.setReadOnly(True)
        self._apply_caret_mode()
        self.editor.setHtml(self._md_to_html(md))
        self._apply_block_spacing()
        self._qt_apply_user_highlights()
        self.statusBar().showMessage("Read mode")

    def _qt_check_spelling(self) -> None:
        """Count and report misspelled words in the current text (F7).

        Works whether or not the live red-squiggle highlighter is running:
        it checks the editable source in edit mode, otherwise the loaded
        document's plain text.
        """
        if not self._qt_require_optional_feature("spellcheck", tr("Spell check")):
            return
        if self._qt_edit_mode:
            text = self.editor.toPlainText()
        elif self.doc:
            text = self.doc.plain_text or ""
        else:
            self.statusBar().showMessage("Open a document to check spelling")
            return
        bad = sorted(misspelled_words(text))
        if not bad:
            QMessageBox.information(
                self, "Spell check", "No misspelled words found."
            )
            return
        preview = ", ".join(bad[:25])
        if len(bad) > 25:
            preview += ", …"
        QMessageBox.information(
            self,
            "Spell check",
            f"{len(bad)} misspelled word(s) found:\n\n{preview}",
        )

    # ─ live HTML preview (edit mode) ──────────────────────────────────

    def _qt_render_preview(self) -> None:
        """Render the current editor source into the live preview pane."""
        if not self._preview.isVisible():
            return
        md = (
            self.editor.toPlainText()
            if self._qt_edit_mode
            else (self.doc.markdown if self.doc else "")
        )
        # Preserve the reader's scroll position across re-renders.
        bar = self._preview.verticalScrollBar()
        pos = bar.value() if bar else 0
        self._preview.setHtml(self._md_to_html(md))
        if bar:
            bar.setValue(min(pos, bar.maximum()))

    def _qt_toggle_preview(self) -> None:
        """Toggle the live HTML preview pane (Ctrl+Shift+L).

        The preview is meaningful only while editing the Markdown source,
        so turning it on outside edit mode enters edit mode first.
        """
        new = not bool(self.settings.get("qt_edit_preview", False))
        self.settings["qt_edit_preview"] = new
        if hasattr(self, "_preview_act"):
            self._preview_act.setChecked(new)
        if new:
            if not self._qt_edit_mode:
                if not self.doc:
                    self.statusBar().showMessage("Open a document to preview")
                    return
                # Entering edit mode shows the preview itself.
                self._qt_enter_edit_mode()
            else:
                self._preview.setVisible(True)
                self._qt_render_preview()
            self.statusBar().showMessage("Live HTML preview: ON")
        else:
            self._preview.setVisible(False)
            self.statusBar().showMessage("Live HTML preview: OFF")

    # ─ reading statistics & library ───────────

    def _qt_save(self) -> None:
        """Save the current document.

        In *edit mode*: the edited Markdown is written back to the
        original file (for .md / .markdown / .txt / .rst / .org);
        for any other format a Save-As dialog is shown.  The document
        is then re-rendered and the TTS word maps are rebuilt.

        In *read mode*: falls through to the Markdown export dialog
        (same as File → Export → Export as Markdown…).
        """
        if not self._qt_edit_mode:
            # Not editing — offer markdown export.
            self._qt_export_markdown()
            return

        if not self.doc:
            return

        # Capture the edited source from the plain-text editor.
        new_md = self.editor.toPlainText()

        # --- persist to disk -------------------------------------------
        orig = Path(self.doc.path) if self.doc.path else None
        text_exts = {
            ".md",
            ".markdown",
            ".txt",
            ".rst",
            ".org",
            ".adoc",
            ".asc",
            ".asciidoc",
        }
        if orig and orig.suffix.lower() in text_exts:
            try:
                orig.write_text(new_md, encoding="utf-8")
                saved_path = str(orig)
            except OSError as exc:
                self.statusBar().showMessage(f"Save error: {exc}")
                return
        else:
            # Binary or non-text format — prompt for a .md path.
            stem = orig.stem if orig else "document"
            parent = str(orig.parent) if orig else ""
            dest, _ = QFileDialog.getSaveFileName(
                self,
                "Save As Markdown",
                str(Path(parent) / (stem + ".md")),
                "Markdown (*.md *.markdown)",
            )
            if not dest:
                return
            try:
                Path(dest).write_text(new_md, encoding="utf-8")
                saved_path = dest
            except OSError as exc:
                self.statusBar().showMessage(f"Save error: {exc}")
                return

        # --- update in-memory document ---------------------------------
        self.doc.markdown = new_md
        self.doc.plain_text = _strip_markdown_for_tts(
            new_md,
            skip_code=bool(self.settings.get("tts_skip_code", True)),
            table_mode=str(self.settings.get("table_reading_mode", "structured")),
        )
        self._qt_edit_dirty = False

        # --- exit edit mode and re-render ------------------------------
        try:
            self.editor.document().contentsChanged.disconnect(
                self._qt_on_edit_contents_changed
            )
        except (RuntimeError, TypeError):
            pass
        self._qt_edit_mode = False
        self.editor.setReadOnly(True)
        self._apply_caret_mode()
        self.editor.setHtml(self._md_to_html(new_md))
        self._apply_block_spacing()
        self._qt_apply_user_highlights()
        self._qt_build_toc()
        self._qt_build_annotations()

        # Rebuild word maps asynchronously (same flow as _on_doc_loaded_impl)
        qt_plain = self.editor.document().toPlainText()
        doc_ref = self.doc

        def _rebuild() -> None:
            try:
                flat = qt_plain.splitlines()
                doc_ref.word_map = _build_word_map(doc_ref.plain_text, flat)
                self.tts_manager.set_word_map(doc_ref.word_map)
                self._build_qt_word_map(doc_ref.plain_text, qt_plain)
            except Exception:
                pass

        import threading as _threading

        _threading.Thread(target=_rebuild, daemon=True).start()

        self.statusBar().showMessage(f"Saved → {saved_path}")
