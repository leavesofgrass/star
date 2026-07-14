"""Author from the terminal: edit the current document in the user's editor.

The Qt GUI edits Markdown in-widget (Ctrl+E — see
``gui/mixin_navigation/_editing.py``); a curses pane has no comparable
multi-line editor, so the TUI follows the classic terminal idiom (git, mutt,
ranger): suspend curses, hand the file to ``$VISUAL`` / ``$EDITOR``, and
reload the document when the editor exits.  That inherits the user's own
editor setup — including whatever screen-reader-friendly editor they already
rely on — instead of imposing a home-grown one.

Methods of StarApp; mixed into StarApp in app.py.
"""
import shlex

from .._runtime import *  # noqa: F401,F403

# Formats whose source can be edited in place and re-parsed on reload.  The
# GUI twin lives in _qt_persist_edits (gui/mixin_navigation/_editing.py) —
# anything else is round-tripped through a Markdown draft + Save-As, exactly
# like the GUI's Save-As-Markdown path for binary formats.
_TEXT_EDIT_EXTS = {
    ".md",
    ".markdown",
    ".txt",
    ".rst",
    ".org",
    ".adoc",
    ".asc",
    ".asciidoc",
}


class TuiEditingMixin:

    # ── Editor resolution / invocation ──────────────────────────────────────

    def _editor_command(self) -> List[str]:
        """The user's editor as an argv prefix, or ``[]`` when none is found.

        ``$VISUAL`` wins over ``$EDITOR`` (both are shlex-split, so values
        like ``code -w`` work); the fallback is notepad on Windows, else the
        first of nano / vi found on PATH.
        """
        for var in ("VISUAL", "EDITOR"):
            val = os.environ.get(var, "").strip()
            if val:
                return shlex.split(val, posix=(os.name != "nt"))
        if os.name == "nt":
            return ["notepad"]
        for cand in ("nano", "vi"):
            if shutil.which(cand):
                return [cand]
        return []

    def _run_editor(self, path: str) -> bool:
        """Suspend curses, run the editor on *path* (blocking), resume.

        Returns False when no editor could be resolved or launching failed —
        with the screen restored and the reason on the status line either way.
        """
        cmd = self._editor_command()
        if not cmd:
            self.notify(
                "No editor found — set $EDITOR (or $VISUAL) and try again.",
                error=True,
            )
            return False
        try:
            curses.def_prog_mode()
            curses.endwin()
            try:
                # creationflags=0, NOT _SUBPROCESS_FLAGS: this is the one
                # subprocess that must TAKE OVER the console — CREATE_NO_WINDOW
                # would detach a console editor (vim, nano) from the terminal
                # entirely.  The TUI always runs in a real console, so there is
                # no window flash to suppress here in the first place.
                subprocess.call(cmd + [path], creationflags=0)
            finally:
                curses.reset_prog_mode()
                self.scr.refresh()
        except Exception as exc:  # noqa: BLE001 — surface, never crash curses
            self.notify(f"Editor failed: {exc}", error=True)
            return False
        return True

    # ── Ctrl+E / M-x edit ───────────────────────────────────────────────────

    def _edit_cmd(self) -> None:
        """Edit the current document's source in the user's editor.

        Text formats (Markdown, plain text, reST, org, AsciiDoc) are edited
        in place and reloaded — the document cache is mtime-keyed, so the
        reload re-parses.  Anything else (PDF, EPUB, DOCX, a URL…) gets its
        Markdown conversion as a draft file; on return the draft is saved to
        a path of your choice and opened, mirroring the GUI's Save-As flow.
        """
        if not self.doc:
            self.notify("No document to edit", error=True)
            return
        self._tts_stop()
        path = self.doc.path or ""
        if (
            path
            and not path.startswith(("http://", "https://"))
            and Path(path).suffix.lower() in _TEXT_EDIT_EXTS
            and Path(path).is_file()
        ):
            if self._run_editor(path):
                self._open_async(path)
            return
        self._edit_markdown_draft(path)

    # ── Ctrl+N / M-x new-document ───────────────────────────────────────────

    def _new_document_cmd(self, arg: str = "") -> None:
        """Create a new Markdown document and write it in your editor.

        GUI parity for File ▸ New (Ctrl+N).  Prompts for a destination path
        (or takes it as the M-x argument), seeds a title heading, opens the
        file in ``$EDITOR``, and loads it as the current document afterwards.
        """
        if arg:
            self._new_document_at(arg)
            return
        self._enter_minibuffer(
            "New document path: ",
            initial=str(Path.cwd() / "untitled.md"),
            on_commit=self._new_document_at,
            completions=[],
        )

    def _new_document_at(self, dest: str) -> None:
        dest = (dest or "").strip().strip('"')
        if not dest:
            self.notify("New document cancelled")
            return
        p = Path(dest).expanduser()
        if p.suffix.lower() not in _TEXT_EDIT_EXTS:
            p = p.with_suffix(".md")
        if p.exists():
            self.notify(
                f"{p} already exists — open it and use edit instead", error=True
            )
            return
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"# {p.stem}\n\n", encoding="utf-8")
        except OSError as exc:
            self.notify(f"Could not create {p}: {exc}", error=True)
            return
        # Open even if the editor could not run — the file exists, and the
        # status line already explains what went wrong with the editor.
        self._run_editor(str(p))
        self._open_async(str(p))

    def _edit_markdown_draft(self, path: str) -> None:
        """Edit a Markdown draft of a non-text document, then Save-As."""
        stem = (Path(path).stem if path else "") or "document"
        original = self.doc.markdown or ""
        fd, tmp = tempfile.mkstemp(prefix=f"{stem}-", suffix=".md")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(original)
        if not self._run_editor(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
            return
        try:
            # utf-8-sig: strip the BOM some editors (notepad) may prepend.
            edited = Path(tmp).read_text(encoding="utf-8-sig", errors="replace")
        except OSError as exc:
            self.notify(f"Could not read the edited draft: {exc}", error=True)
            return
        if edited == original:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            self.notify("No changes made")
            return

        default_dest = (
            str(Path(path).with_suffix(".md")) if path and not path.startswith(
                ("http://", "https://")
            ) else str(Path.cwd() / f"{stem}.md")
        )

        def _save_to(dest: str) -> None:
            dest = dest.strip().strip('"')
            if not dest:
                self.notify(f"Save cancelled — draft kept at {tmp}", error=True)
                return
            dest_p = Path(dest).expanduser()
            if dest_p.suffix.lower() not in (".md", ".markdown"):
                dest_p = dest_p.with_suffix(".md")
            try:
                dest_p.parent.mkdir(parents=True, exist_ok=True)
                dest_p.write_text(edited, encoding="utf-8")
            except OSError as exc:
                self.notify(f"Save error: {exc} — draft kept at {tmp}", error=True)
                return
            try:
                os.unlink(tmp)
            except OSError:
                pass
            self._open_async(str(dest_p))

        self._enter_minibuffer(
            "Save edited Markdown as: ",
            initial=default_dest,
            on_commit=_save_to,
            completions=[],
        )
