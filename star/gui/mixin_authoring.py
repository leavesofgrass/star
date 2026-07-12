"""AuthoringMixin — create documents from scratch + Markdown formatting tools.

star started as a reader; these methods make it a document-creation tool too.
``_qt_new_document`` opens a blank document straight into edit mode, and the
``_qt_md_*`` helpers back the Markdown formatting toolbar (ChromeMixin builds
it) — wrapping the selection or prefixing lines with Markdown syntax so a
student can author without memorising the markup.  All the formatting helpers
are no-ops outside edit mode (the toolbar is only shown while editing).

Mixed into StarWindow; operates on the shared QTextEdit ``self.editor``.
"""
from .._runtime import *  # noqa: F401,F403
from ..documents import Document
from ..i18n import tr
from ._qtcompat import _KEEP_ANCHOR
from .a11y import announce


class AuthoringMixin:

    # ── New document ───────────────────────────────────────────────────────

    def _qt_new_document(self) -> None:
        """Create a blank document and drop into edit mode (File ▸ New)."""
        # If we're mid-edit with unsaved changes, offer Save / Discard / Cancel
        # (via the shared helper) — the same choice as Ctrl+E and opening another
        # document, instead of a bespoke discard-or-abort prompt that could only
        # throw the work away.
        if not self._qt_confirm_leave_edit_for_replace():
            return  # user cancelled
        # An in-memory doc with no path — never touches recents/library until
        # the first save (which assigns a real path); mirrors the translation /
        # transcription result docs.
        self._pending_doc = Document(
            path="",
            title=tr("Untitled"),
            markdown="",
            plain_text="",
            format="markdown",
        )
        # A new document is authored from scratch, so open it in edit mode with
        # the live preview on and the space shared evenly with the source.  Turn
        # the preview on *before* entering edit mode (which reads the setting)
        # and keep the toggle action in sync.
        self.settings["qt_edit_preview"] = True
        if hasattr(self, "_preview_act"):
            self._preview_act.setChecked(True)
        self._on_doc_loaded()
        if not getattr(self, "_qt_edit_mode", False):
            self._qt_enter_edit_mode()
        # Even 50/50 split of editor | preview (enter-edit sizes it, but do it
        # again here in case edit mode was already active).
        self._qt_equalize_edit_split()
        self.editor.setFocus()
        self.statusBar().showMessage(tr("New document — start typing or dictate"))
        announce(self.editor, tr("New document ready for editing"))

    # ── Markdown formatting (edit-mode toolbar) ────────────────────────────

    def _md_editing(self) -> bool:
        """Formatting only applies to the editable Markdown source."""
        if getattr(self, "_qt_edit_mode", False):
            return True
        self.statusBar().showMessage(
            tr("Turn on Edit Mode (Ctrl+E) to format text")
        )
        return False

    def _md_refresh_preview_now(self) -> None:
        """Re-render the live preview at once after a formatting action.

        A discrete button/menu action should show its styled result
        immediately rather than waiting for the typing debounce, so we cancel
        any pending debounced render and render synchronously.  A no-op unless
        the live preview is actually shown."""
        prev = getattr(self, "_preview", None)
        if prev is None or not prev.isVisible():
            return
        timer = getattr(self, "_preview_timer", None)
        if timer is not None:
            try:
                timer.stop()
            except Exception:  # noqa: BLE001
                pass
        self._qt_render_preview()

    def _qt_md_wrap(self, before: str, after: str, placeholder: str = "text") -> None:
        """Wrap the selection in *before*/*after* (bold, italic, code, …).

        With no selection, a selected placeholder is inserted so the user can
        type straight over it."""
        if not self._md_editing():
            return
        cur = self.editor.textCursor()
        sel = cur.selectedText()
        if sel:
            cur.insertText(f"{before}{sel}{after}")
        else:
            cur.insertText(f"{before}{placeholder}{after}")
            end = cur.position() - len(after)
            cur.setPosition(end - len(placeholder))
            cur.setPosition(end, _KEEP_ANCHOR)  # reselect the placeholder
        self.editor.setTextCursor(cur)
        self.editor.setFocus()
        self._md_refresh_preview_now()

    def _qt_md_line_prefix(self, prefix: str, numbered: bool = False) -> None:
        """Prefix each line touched by the selection (or the current line).

        *numbered* renumbers the run 1., 2., …  Applied as one undo step."""
        if not self._md_editing():
            return
        doc = self.editor.document()
        cur = self.editor.textCursor()
        first = doc.findBlock(cur.selectionStart()).blockNumber()
        last = doc.findBlock(cur.selectionEnd()).blockNumber()
        cur.beginEditBlock()
        for i, bn in enumerate(range(first, last + 1)):
            block = doc.findBlockByNumber(bn)
            pfx = f"{i + 1}. " if numbered else prefix
            bc = self.editor.textCursor()
            bc.setPosition(block.position())
            bc.insertText(pfx)
        cur.endEditBlock()
        self.editor.setFocus()
        self._md_refresh_preview_now()

    def _qt_md_link(self) -> None:
        """Insert a Markdown link, wrapping any selection as the link text."""
        if not self._md_editing():
            return
        cur = self.editor.textCursor()
        text = cur.selectedText() or "text"
        cur.insertText(f"[{text}](https://)")
        self.editor.setTextCursor(cur)
        self.editor.setFocus()
        self._md_refresh_preview_now()

    def _qt_md_insert_rule(self) -> None:
        """Insert a horizontal rule (``---``) on its own line."""
        if not self._md_editing():
            return
        cur = self.editor.textCursor()
        cur.insertText("\n---\n")
        self.editor.setTextCursor(cur)
        self.editor.setFocus()
        self._md_refresh_preview_now()

    # ── Tables ─────────────────────────────────────────────────────────────

    @staticmethod
    def _md_table_skeleton(rows: int, cols: int) -> str:
        """Build a Markdown table skeleton with *rows* body rows and *cols*
        columns (header + separator + blank body rows)."""
        cols = max(1, cols)
        rows = max(1, rows)
        header = "| " + " | ".join(f"Column {c + 1}" for c in range(cols)) + " |"
        sep = "| " + " | ".join("---" for _ in range(cols)) + " |"
        body = "\n".join(
            "| " + " | ".join(" " for _ in range(cols)) + " |" for _ in range(rows)
        )
        return f"{header}\n{sep}\n{body}\n"

    def _qt_md_insert_table(self) -> None:
        """Insert a Markdown table, asking for its size (Format ▸ Insert Table).

        The table is placed on its own lines (blank line before/after) so it
        renders, with the first body cell selected for immediate typing."""
        if not self._md_editing():
            return
        cols, ok = QInputDialog.getInt(
            self, tr("Insert Table"), tr("Number of columns:"), 2, 1, 20, 1
        )
        if not ok:
            return
        rows, ok = QInputDialog.getInt(
            self, tr("Insert Table"), tr("Number of rows (excluding header):"),
            2, 1, 100, 1
        )
        if not ok:
            return
        cur = self.editor.textCursor()
        # Ensure the table starts on its own line.
        at_line_start = cur.atBlockStart()
        prefix = "" if at_line_start else "\n"
        cur.insertText(prefix + "\n" + self._md_table_skeleton(rows, cols) + "\n")
        self.editor.setTextCursor(cur)
        self.editor.setFocus()
        self._md_refresh_preview_now()
        announce(self.editor, tr("Inserted a {r}×{c} table").format(r=rows, c=cols))

    def _qt_md_table_add_row(self) -> None:
        """Append a blank row to the Markdown table the cursor is in.

        Matches the column count of the current table row; a no-op with a
        friendly hint when the cursor isn't on a ``|``-delimited table line."""
        if not self._md_editing():
            return
        cur = self.editor.textCursor()
        block = cur.block()
        line = block.text()
        if "|" not in line or not line.strip().startswith("|"):
            self.statusBar().showMessage(
                tr("Put the cursor inside a table row to add a row")
            )
            return
        # Column count = number of cells between the outer pipes.
        cols = max(1, line.strip().strip("|").count("|") + 1)
        new_row = "| " + " | ".join(" " for _ in range(cols)) + " |"
        # Insert after the current line.
        end = self.editor.textCursor()
        end.setPosition(block.position() + block.length() - 1)
        end.insertText("\n" + new_row)
        self.editor.setFocus()
        self._md_refresh_preview_now()

    # ── Images ─────────────────────────────────────────────────────────────

    def _qt_md_insert_image(self) -> None:
        """Insert a Markdown image reference (Format ▸ Insert Image…).

        Picks an image file; when the document has been saved, offers to write
        a path relative to it (so the reference survives a move of the pair);
        otherwise inserts the absolute path.  Alt text defaults to the file
        stem and is left selected for editing."""
        if not self._md_editing():
            return
        src, _flt = QFileDialog.getOpenFileName(
            self,
            tr("Insert Image"),
            "",
            tr("Images (*.png *.jpg *.jpeg *.gif *.webp *.bmp *.svg);;All Files (*)"),
        )
        if not src:
            return
        ref = src
        doc_path = getattr(self.doc, "path", "") if self.doc else ""
        if doc_path:
            try:
                rel = os.path.relpath(src, str(Path(doc_path).parent))
                # Only prefer the relative path when it doesn't climb out with a
                # long ../../ chain (keep references readable and portable).
                if not rel.startswith(".." + os.sep + ".." + os.sep):
                    ref = rel.replace(os.sep, "/")
            except (ValueError, OSError):
                ref = src  # different drive on Windows, etc. — keep absolute
        alt = Path(src).stem
        cur = self.editor.textCursor()
        cur.insertText(f"![{alt}]({ref})")
        self.editor.setTextCursor(cur)
        self.editor.setFocus()
        self._md_refresh_preview_now()
        announce(self.editor, tr("Inserted image {name}").format(name=Path(src).name))
