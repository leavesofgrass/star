"""AnnotationsMixin — methods extracted from StarWindow (main_window.py).

Mixed into StarWindow via ``class StarWindow(AnnotationsMixin, ...)``; operates
on StarWindow instance state and other methods via ``self``, holding no
state of its own.  IMPORT SAFETY: references Qt at module scope — imported
lazily by main_window.py (itself imported by runner.py after the _QT guard).
"""
from .._runtime import *  # noqa: F401,F403
from ..annotations import _annotation_matches, _format_annotations, _parse_tags
from ..flashcards import _GENANKI, export_anki_deck
from ._qtcompat import _USER_ROLE


class AnnotationsMixin:
    # ── Annotations / Notes panel ────────────────────────────────────────

    def _annot_key(self) -> str:
        """Per-document key under which annotations are stored."""
        if not self.doc:
            return ""
        return self.doc.path or self.doc.title or ""

    def _qt_load_annotations(self) -> List[Dict[str, Any]]:
        """Return a mutable copy of the saved annotations for this document,
        sorted by document position."""
        key = self._annot_key()
        if not key:
            return []
        store = self.settings.get("annotations", {}) or {}
        items = [dict(a) for a in store.get(key, [])]
        items.sort(key=lambda a: int(a.get("char_pos", 0)))
        return items

    def _qt_store_annotations(self, items: List[Dict[str, Any]]) -> None:
        """Persist *items* as the annotation list for this document."""
        key = self._annot_key()
        if not key:
            return
        store = dict(self.settings.get("annotations", {}) or {})
        if items:
            store[key] = items
        else:
            store.pop(key, None)
        self.settings.set("annotations", store)

    def _qt_build_annotations(self) -> None:
        """Populate the Notes dock list from saved annotations.

        Each row stores the annotation's char position (_USER_ROLE + 1)
        and its index in the saved list (_USER_ROLE) so edit/delete can
        target the right entry even when the visible list is filtered.
        The filter box performs full-text search over the note, anchor,
        and tags; a `#tag` term filters by tag.
        """
        self._annot_list.clear()
        items = self._qt_load_annotations()
        query = self._annot_filter.text() if hasattr(self, "_annot_filter") else ""
        doc_len = max(1, self.editor.document().characterCount())
        shown = 0
        for idx, a in enumerate(items):
            if not _annotation_matches(a, query):
                continue
            shown += 1
            note = str(a.get("note", "")).strip()
            anchor = str(a.get("anchor", "")).strip()
            tags = a.get("tags", []) or []
            cite = str(a.get("cite", "")).strip()
            pct = int(100 * int(a.get("char_pos", 0)) / doc_len)
            first = note.splitlines()[0] if note else "(empty note)"
            label = f"{pct:>3}%  {first}"
            meta = ""
            if tags:
                meta += "  ".join(f"#{t}" for t in tags)
            if cite:
                meta += ("  " if meta else "") + f"@{cite}"
            if anchor:
                label += f"\n        “{anchor[:48]}”"
            if meta:
                label += f"\n        {meta}"
            item = QListWidgetItem(label)
            item.setData(_USER_ROLE, idx)
            item.setData(_USER_ROLE + 1, int(a.get("char_pos", 0)))
            item.setToolTip(note or anchor)
            self._annot_list.addItem(item)
        if query and hasattr(self, "_annot_dock"):
            self._annot_dock.setWindowTitle(f"Notes ({shown}/{len(items)})")
        elif hasattr(self, "_annot_dock"):
            self._annot_dock.setWindowTitle(
                f"Notes ({len(items)})" if items else "Notes"
            )

    def _qt_current_anchor(self) -> Tuple[int, str]:
        """Return (char_pos, anchor_text) for a new note.

        Uses the selection if there is one (so the user can annotate a
        specific passage), otherwise the cursor's paragraph as context.
        """
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            char_pos = cursor.selectionStart()
            anchor = cursor.selectedText()
        else:
            char_pos = cursor.position()
            anchor = cursor.block().text()
        # selectedText() uses U+2029 for line breaks; normalize whitespace.
        anchor = " ".join(anchor.split())[:120]
        return char_pos, anchor

    def _qt_add_annotation(self) -> None:
        """Prompt for note text and attach it at the current position."""
        if not self.doc:
            self.statusBar().showMessage("Open a document before adding notes")
            return
        char_pos, anchor = self._qt_current_anchor()
        text, ok = QInputDialog.getMultiLineText(
            self,
            "Add Note",
            f"Note for: “{anchor[:60]}”" if anchor else "Note:",
            "",
        )
        if not ok or not text.strip():
            return
        # Optional tags (comma/space separated; leading # optional).
        tag_str, _ok2 = QInputDialog.getText(
            self, "Tags (optional)", "Tags, comma-separated:"
        )
        tags = _parse_tags(tag_str)
        items = self._qt_load_annotations()
        items.append(
            {
                "char_pos": int(char_pos),
                "word_idx": self._qt_char_to_word(int(char_pos)),
                "anchor": anchor,
                "note": text.strip(),
                "tags": tags,
                "cite": "",
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
        )
        self._qt_store_annotations(items)
        self._qt_build_annotations()
        if not self._annot_dock.isVisible():
            self._annot_dock.setVisible(True)
            self.settings["qt_show_notes"] = True
        self.statusBar().showMessage(
            f"Note added{(' with tags: ' + ', '.join(tags)) if tags else ''}"
        )

    def _qt_selected_annotation_index(self) -> int:
        """Index (into the saved list) of the selected note, or -1."""
        item = self._annot_list.currentItem()
        if item is None:
            return -1
        data = item.data(_USER_ROLE)
        return int(data) if data is not None else -1

    def _qt_edit_annotation(self) -> None:
        """Edit the text of the selected note."""
        idx = self._qt_selected_annotation_index()
        items = self._qt_load_annotations()
        if idx < 0 or idx >= len(items):
            self.statusBar().showMessage("Select a note to edit")
            return
        text, ok = QInputDialog.getMultiLineText(
            self, "Edit Note", "Note:", str(items[idx].get("note", ""))
        )
        if not ok:
            return
        if not text.strip():
            # Empty text deletes the note.
            del items[idx]
        else:
            items[idx]["note"] = text.strip()
            items[idx]["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._qt_store_annotations(items)
        self._qt_build_annotations()
        self.statusBar().showMessage("Note updated")

    def _qt_delete_annotation(self) -> None:
        """Delete the selected note."""
        idx = self._qt_selected_annotation_index()
        items = self._qt_load_annotations()
        if idx < 0 or idx >= len(items):
            self.statusBar().showMessage("Select a note to delete")
            return
        del items[idx]
        self._qt_store_annotations(items)
        self._qt_build_annotations()
        self.statusBar().showMessage("Note deleted")

    def _qt_annotation_charpos(self, item: QListWidgetItem) -> int:
        """Resolve a Qt character position for a notes-list *item*.

        Prefers the stored Qt char position; falls back to the note's
        word index (how TUI-created notes are anchored) mapped through
        the Qt word map so notes made in either UI navigate correctly.
        """
        data = item.data(_USER_ROLE + 1)
        char_pos = int(data) if data is not None else -1
        if char_pos and char_pos > 0:
            return char_pos
        idx = item.data(_USER_ROLE)
        items = self._qt_load_annotations()
        if idx is not None and 0 <= int(idx) < len(items):
            wi = int(items[int(idx)].get("word_idx", 0) or 0)
            if self._qt_word_map and 0 <= wi < len(self._qt_word_map):
                return self._qt_word_map[wi]
        return char_pos

    def _qt_annotation_navigate(self, item: QListWidgetItem) -> None:
        """Single-click / Enter: scroll the viewport to the note anchor."""
        char_pos = self._qt_annotation_charpos(item)
        if char_pos < 0:
            return
        doc_len = self.editor.document().characterCount()
        char_pos = max(0, min(char_pos, doc_len - 1))
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(char_pos)
        self.editor.setTextCursor(cursor)
        self.editor.ensureCursorVisible()

    def _qt_annotation_play(self, item: QListWidgetItem) -> None:
        """Double-click: start reading from the note anchor."""
        if not self.doc:
            return
        char_pos = self._qt_annotation_charpos(item)
        if char_pos < 0:
            return
        self._tts_play_from_word(self._qt_char_to_word(char_pos))

    def _qt_toggle_annotations(self) -> None:
        """Toggle the visibility of the Notes dock panel."""
        visible = not self._annot_dock.isVisible()
        self._annot_dock.setVisible(visible)
        self.settings["qt_show_notes"] = visible

    def _qt_export_annotations(self) -> None:
        """Export the current document's notes to Markdown / JSON / BibTeX / RIS.

        The format is chosen by the file extension in the save dialog.
        BibTeX and RIS emit a single reference for the source document with
        the notes attached (the standard reference-manager convention).
        """
        if not self.doc:
            self.statusBar().showMessage("No document loaded")
            return
        items = self._qt_load_annotations()
        if not items:
            self.statusBar().showMessage("No notes to export")
            return
        p = Path(self.doc.path) if self.doc.path else Path("notes")
        default = str(p.parent / (p.stem + "_notes.md"))
        dest, _flt = QFileDialog.getSaveFileName(
            self,
            "Export Notes",
            default,
            "Markdown (*.md);;JSON (*.json);;BibTeX (*.bib);;RIS (*.ris);;Text (*.txt)",
        )
        if not dest:
            return
        ext = Path(dest).suffix.lower()
        meta = getattr(self.doc, "metadata", {}) or {}
        title = self.doc.title or Path(self.doc.path or "document").stem
        author = (
            meta.get("author") or meta.get("creator") or meta.get("Author") or ""
        )
        try:
            content = _format_annotations(
                items, ext, title, author, self.doc.path or ""
            )
            Path(dest).write_text(content, encoding="utf-8")
            self.statusBar().showMessage(f"Exported {len(items)} note(s) → {dest}")
        except OSError as exc:
            self.statusBar().showMessage(f"Export error: {exc}")

    def _qt_export_anki(self) -> None:
        """Export the current document's notes as an Anki deck (.apkg).

        Each note becomes a card: the highlighted passage on the front, the
        user's note on the back.  Requires genanki and at least one note.
        """
        if not _GENANKI:
            QMessageBox.information(
                self,
                "Anki export unavailable",
                "Anki flashcard export requires genanki:\n\n"
                "    pip install genanki",
            )
            return
        if not self.doc:
            self.statusBar().showMessage("No document loaded")
            return
        items = self._qt_load_annotations()
        if not items:
            QMessageBox.information(
                self,
                "No notes to export",
                "Add a note or two first — each note becomes a flashcard.",
            )
            return
        title = self.doc.title or Path(self.doc.path or "document").stem
        p = Path(self.doc.path) if self.doc.path else Path(title)
        default = str(p.parent / (p.stem + ".apkg"))
        dest, _flt = QFileDialog.getSaveFileName(
            self, "Export Anki Flashcards", default, "Anki Deck (*.apkg)"
        )
        if not dest:
            return
        if not dest.lower().endswith(".apkg"):
            dest += ".apkg"
        try:
            export_anki_deck(items, title, dest)
            self.statusBar().showMessage(
                f"Exported {len(items)} flashcard(s) → {dest}"
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Anki export failed", str(exc))
            self.statusBar().showMessage(f"Anki export error: {exc}")

