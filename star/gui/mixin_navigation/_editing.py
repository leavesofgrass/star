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
from ...stats import _record_library
from ...ttstext import _strip_markdown_for_tts
from ..a11y import announce


class EditNavMixin:
    # ─ document editing ───────────────────────────────────────────────

    def _qt_edit_mode_toggle(self) -> None:
        """Toggle between read mode and edit mode (Ctrl+E).

        In *read mode* the editor displays rendered HTML and is
        read-only.  In *edit mode* the raw Markdown source is shown
        as plain text so the user can make changes with any standard
        text-editing shortcut (Ctrl+Z/Y, Ctrl+X/C/V, arrow keys,
        Delete, Home, End, …).  Ctrl+S saves and *keeps you editing*;
        Ctrl+E finishes (offering to save any unsaved changes first).
        """
        if not self._qt_edit_mode:
            self._qt_enter_edit_mode()
        else:
            self._qt_finish_editing()

    def _qt_ask_unsaved(self) -> str:
        """Ask Save / Discard / Cancel about unsaved edits.

        Returns ``"save"``, ``"discard"``, or ``"cancel"``.  Shared by the two
        "leaving edit mode with unsaved changes" flows (finish editing, and
        opening another document mid-edit) so they behave identically."""
        try:
            Save = QMessageBox.StandardButton.Save
            Discard = QMessageBox.StandardButton.Discard
            Cancel = QMessageBox.StandardButton.Cancel
        except AttributeError:  # PyQt5
            Save = QMessageBox.Save        # type: ignore[attr-defined]
            Discard = QMessageBox.Discard  # type: ignore[attr-defined]
            Cancel = QMessageBox.Cancel    # type: ignore[attr-defined]
        ret = QMessageBox.question(
            self,
            tr("Finish Editing"),
            tr("Save changes before leaving edit mode?"),
            Save | Discard | Cancel,
        )
        if ret == Save:
            return "save"
        if ret == Discard:
            return "discard"
        return "cancel"

    def _qt_finish_editing(self) -> None:
        """Leave edit mode (Ctrl+E), offering to save unsaved changes first.

        With Ctrl+S now keeping you in edit mode for a smooth live-edit loop,
        Ctrl+E is the deliberate "I'm done" action — so a stray press must
        never silently discard work.  If the document is dirty the user is
        asked Save / Discard / Cancel."""
        if getattr(self, "_qt_edit_dirty", False):
            choice = self._qt_ask_unsaved()
            if choice == "cancel":
                return
            if choice == "save" and not self._qt_persist_edits():
                # Save-As cancelled or the write failed — stay in edit mode
                # rather than lose the changes.
                return
        self._qt_exit_edit_mode(save=False)

    def _qt_teardown_edit_state(self) -> None:
        """Reset edit-mode state WITHOUT re-rendering — for when a *different*
        document is about to replace the current one (the caller renders it).

        Idempotent: a no-op when not editing.  Because Ctrl+S now keeps the user
        in edit mode, every document-replacement path must call this (directly
        or via _qt_confirm_leave_edit_for_replace) so the editor never stays
        editable over the newly-loaded document — otherwise a later Ctrl+S would
        overwrite that file with edit-mode (markdown-stripped) text."""
        if not getattr(self, "_qt_edit_mode", False):
            return
        try:
            self.editor.document().contentsChanged.disconnect(
                self._qt_on_edit_contents_changed
            )
        except (RuntimeError, TypeError):
            pass
        if getattr(self, "_spell_highlighter", None) is not None:
            try:
                self._spell_highlighter.setDocument(None)
            except Exception:  # noqa: BLE001
                pass
            self._spell_highlighter = None
        self._qt_edit_mode = False
        self._qt_edit_dirty = False
        if getattr(self, "_edit_toolbar", None) is not None:
            self._edit_toolbar.setVisible(False)
        if getattr(self, "_preview", None) is not None:
            self._preview.setVisible(False)
        self.editor.setReadOnly(True)

    def _qt_confirm_leave_edit_for_replace(self) -> bool:
        """Resolve edit mode before another document replaces the current one.

        Returns ``True`` to proceed with the replacement, ``False`` only if the
        user chose Cancel when asked about unsaved changes.  Called from
        _open_path so opening a file mid-edit prompts to save (Save/Discard/
        Cancel) exactly like Ctrl+E, then tears edit mode down."""
        if not getattr(self, "_qt_edit_mode", False):
            return True
        if getattr(self, "_qt_edit_dirty", False) and self._modal_ok():
            choice = self._qt_ask_unsaved()
            if choice == "cancel":
                return False
            if choice == "save" and not self._qt_persist_edits():
                return False  # Save-As cancelled / write failed — don't discard
        self._qt_teardown_edit_state()
        return True

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
        # Reveal the Markdown formatting toolbar for authoring.
        if getattr(self, "_edit_toolbar", None) is not None:
            self._edit_toolbar.setVisible(True)
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
                "Ctrl+S: save (keep editing)  ·  Ctrl+E: finish"
            )
        else:
            self.statusBar().showMessage(
                "✏  EDIT MODE — Markdown source  ·  "
                "Ctrl+S: save (keep editing)  ·  Ctrl+E: finish  ·  "
                "Ctrl+Shift+Z: live preview"
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
        """Leave edit mode and render the document read-only.

        This is the single "restore read mode" path.  *save* persists the
        edits first (bailing without leaving edit mode if a Save-As is
        cancelled or the write fails).  It then rebuilds everything the read
        view needs — rendered HTML, the table of contents, annotations, and
        the TTS word maps — so playback and navigation match the saved text.
        """
        if not self._qt_edit_mode:
            return
        if save and not self._qt_persist_edits():
            return  # cancelled / write failed — stay in edit mode, keep the text
        # Capture whether the content changed BEFORE teardown clears edit state:
        # only a real change needs the (background) word-map rebuild, so a plain
        # discard / clean finish never spawns the daemon thread that races Qt
        # teardown (the exit-139 flake — see _qt_rebuild_word_maps_async).
        maps_stale = getattr(self, "_qt_maps_stale", False)
        # Disconnect the dirty listener, detach the spell highlighter, reset the
        # edit flags, hide the toolbar/preview, and make the editor read-only.
        self._qt_teardown_edit_state()
        # Re-render the (possibly updated) Markdown as the read-only view.
        md = self.doc.markdown if self.doc else ""
        self._apply_caret_mode()
        self.editor.setHtml(self._md_to_html(md))
        self._apply_block_spacing()
        self._qt_apply_user_highlights()
        # Now that the editor holds the *rendered* text, rebuild the read-view
        # aids from it (the TOC / annotations map onto visible lines, so they can
        # only be built here).  These are cheap and main-thread, so run always.
        self._qt_build_toc()
        self._qt_build_annotations()
        self._qt_refresh_vocab_highlight()
        # The word + sentence maps only change when the text did — rebuild them
        # (off the UI thread) only after an actual save, matching the pre-edit
        # maps built at load time when nothing changed.
        if maps_stale:
            self._qt_rebuild_word_maps_async()
            self._qt_maps_stale = False
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
        """Toggle the live HTML preview pane (Ctrl+Shift+Z).

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

    def _qt_persist_edits(self) -> bool:
        """Write the edited Markdown to disk and update the in-memory document.

        Returns ``True`` on success, ``False`` if the user cancelled the
        Save-As dialog or the write failed.  Does **not** change edit mode or
        re-render — callers decide whether to stay editing or restore read
        mode, so this is shared by ``_qt_save`` (stay) and
        ``_qt_exit_edit_mode`` (leave).
        """
        if not self.doc:
            return False

        # Capture the edited source from the plain-text editor.
        new_md = self.editor.toPlainText()

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
        prompted = False
        if orig and orig.suffix.lower() in text_exts:
            try:
                orig.write_text(new_md, encoding="utf-8")
                saved_path = str(orig)
            except OSError as exc:
                self._status_error(f"Save error: {exc}")
                return False
        else:
            # Binary or non-text format (or a brand-new doc) — prompt for a .md
            # path.  ``prompted`` marks that a real destination was chosen so we
            # adopt it below and never re-prompt on the next save.
            prompted = True
            stem = orig.stem if orig else "document"
            parent = str(orig.parent) if orig else ""
            dest, _ = QFileDialog.getSaveFileName(
                self,
                "Save As Markdown",
                str(Path(parent) / (stem + ".md")),
                "Markdown (*.md *.markdown)",
            )
            if not dest:
                return False
            try:
                Path(dest).write_text(new_md, encoding="utf-8")
                saved_path = dest
            except OSError as exc:
                self._status_error(f"Save error: {exc}")
                return False

        # --- update in-memory document ---------------------------------
        self.doc.markdown = new_md
        self.doc.plain_text = _strip_markdown_for_tts(
            new_md,
            skip_code=bool(self.settings.get("tts_skip_code", True)),
            table_mode=str(self.settings.get("table_reading_mode", "structured")),
        )
        self._qt_edit_dirty = False
        # The saved text differs from what the read-view maps were built against,
        # so the next return to read mode must rebuild them.
        self._qt_maps_stale = True
        # Adopt the chosen path after ANY Save-As — a brand-new document (File ▸
        # New, no path) OR a converted document whose source was a non-text file
        # (report.pdf → report.md).  Without this, doc.path stays the .pdf, so
        # every subsequent Ctrl+S in the live-edit loop re-opens the Save-As
        # dialog.  Adopting makes the next Ctrl+S write the .md in place, and the
        # document lands in Recents / the library with its title tracking the file.
        if prompted:
            self.doc.path = saved_path
            self.doc.title = Path(saved_path).stem or self.doc.title
            try:
                _record_library(self.settings, self.doc)
            except Exception:  # noqa: BLE001 — the bookshelf is best-effort
                pass
        self._qt_last_saved_path = saved_path
        return True

    def _qt_rebuild_word_maps_async(self) -> None:
        """Rebuild the TTS + Qt word maps off the UI thread from the editor.

        Must be called with the editor showing the *rendered* read-mode text
        (the maps correlate ``doc.plain_text`` with visible editor lines)."""
        if not self.doc:
            return
        qt_plain = self.editor.document().toPlainText()
        doc_ref = self.doc

        def _rebuild() -> None:
            # Bail if the window is tearing down: skip the (potentially large)
            # work rather than churn a daemon thread against a closing window.
            if getattr(self, "_closing", False):
                return
            try:
                plain = doc_ref.plain_text or ""
                flat = qt_plain.splitlines()
                doc_ref.word_map = _build_word_map(plain, flat)
                if getattr(self, "_closing", False):
                    return
                self.tts_manager.set_word_map(doc_ref.word_map)
                self._build_qt_word_map(plain, qt_plain)
                # Sentence map — same algorithm as _on_doc_loaded_impl's _build()
                # so next/prev-sentence nav + sentence-granularity highlighting
                # track the edited text instead of the pre-edit boundaries.
                wm = doc_ref.word_map
                if wm and plain:
                    char_starts = [0]
                    for _m in _SENTENCE_SPLIT_RE.finditer(plain):
                        char_starts.append(_m.end())
                    _wi = 0
                    word_starts = []
                    for cs in char_starts:
                        while _wi < len(wm) and wm[_wi].tts_offset < cs:
                            _wi += 1
                        word_starts.append(min(_wi, len(wm) - 1))
                    seen: set = set()
                    result = []
                    for ws in word_starts:
                        if ws not in seen:
                            seen.add(ws)
                            result.append(ws)
                    self._qt_sentence_starts = result if result else [0]
            except Exception:
                pass

        import threading as _threading

        _threading.Thread(target=_rebuild, daemon=True).start()

    def _qt_save(self) -> None:
        """Save the current document — and keep the user in the flow.

        In *edit mode*: the edited Markdown is written back to the original
        file (for .md / .markdown / .txt / .rst / .org …); for any other
        format a Save-As dialog is shown.  Crucially, the user **stays in edit
        mode** afterwards so there is a smooth live-edit loop — type/format,
        Ctrl+S, keep going — instead of being kicked back to read mode on every
        save.  The live preview (if shown) refreshes to the saved source.
        Ctrl+E finishes editing.

        In *read mode*: falls through to the Markdown export dialog (same as
        File → Export → Export as Markdown…).
        """
        if not self._qt_edit_mode:
            # Not editing — offer markdown export.
            self._qt_export_markdown()
            return

        if not self.doc:
            return

        if not self._qt_persist_edits():
            return  # cancelled Save-As or write failed — nothing changed

        # Stay in edit mode: the editor keeps the raw Markdown source and the
        # cursor, so the user can carry on editing immediately.
        saved_path = getattr(self, "_qt_last_saved_path", "")
        if self._preview.isVisible():
            self._qt_render_preview()
        self.statusBar().showMessage(
            f"Saved → {saved_path}  ·  still editing (Ctrl+E to finish)"
        )
        announce(self.editor, "Saved. Still editing.")
        self.editor.setFocus()
