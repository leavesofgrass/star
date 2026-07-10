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
        if getattr(self, "_qt_edit_dirty", False):
            try:
                yes, no = QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No
            except AttributeError:  # PyQt5
                yes, no = QMessageBox.Yes, QMessageBox.No  # type: ignore[attr-defined]
            ret = QMessageBox.question(
                self,
                tr("New Document"),
                tr("Discard unsaved changes and start a new document?"),
                yes | no,
            )
            if ret != yes:
                return
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
        self._on_doc_loaded()
        if not getattr(self, "_qt_edit_mode", False):
            self._qt_enter_edit_mode()
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
