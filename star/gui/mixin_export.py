"""ExportMixin — methods extracted from StarWindow (main_window.py).

Mixed into StarWindow via ``class StarWindow(ExportMixin, ...)``; operates
on StarWindow instance state and other methods via ``self``, holding no
state of its own.  IMPORT SAFETY: references Qt at module scope — imported
lazily by main_window.py (itself imported by runner.py after the _QT guard).
"""
from .._runtime import *  # noqa: F401,F403
from ..braille import _export_braille
from ..convert import resolve_format, run_batch, supported_formats
from ..ttstext import _preprocess_tts_text
from ..watch import HotFolderWatcher, _make_logger
from ._qtcompat import _KEEP_ANCHOR


class ExportMixin:
    # ── Export methods ───────────────────────────────────────────────

    def _qt_batch_convert(self) -> None:
        """Convert many files / a folder to one format (File ▸ Batch Convert).

        Select multiple files (or, if none are chosen, a folder), pick one
        output format and one output directory, then run the shared,
        failure-isolated batch core on a background thread.
        """
        sel, _ = QFileDialog.getOpenFileNames(
            self, "Select documents to convert (Cancel to choose a folder)", ""
        )
        paths: List[str] = list(sel)
        if not paths:
            folder = QFileDialog.getExistingDirectory(
                self, "Select a folder of documents to convert"
            )
            if folder:
                paths = [folder]
        if not paths:
            return
        fmts = supported_formats()
        cur = str(self.settings.get("batch_format", "markdown"))
        idx = fmts.index(cur) if cur in fmts else 0
        fmt, ok = QInputDialog.getItem(
            self, "Batch Convert", "Convert everything to:", fmts, idx, False
        )
        if not ok or not fmt:
            return
        fmt = resolve_format(fmt)
        self.settings.set("batch_format", fmt)
        out_dir = QFileDialog.getExistingDirectory(
            self, "Choose the output directory"
        )
        if not out_dir:
            return

        def _work() -> None:
            def _progress(done: int, total: int, result) -> None:
                state = "ok" if result.ok else "FAILED"
                self._batch_progress_signal.emit(
                    f"Batch {done}/{total}: {Path(result.source).name} — {state}"
                )

            summary = run_batch(
                paths, out_dir, fmt, self.settings, progress=_progress
            )
            lines = [
                "Batch conversion complete.",
                "",
                f"Succeeded: {len(summary.succeeded)} / {summary.total}",
                f"Failed: {len(summary.failed)}",
                f"Output: {out_dir}",
            ]
            if summary.log_path:
                lines.append(f"Log: {summary.log_path}")
            if summary.failed:
                lines.append("")
                lines.append("Failures:")
                for r in summary.failed[:20]:
                    lines.append(f"  • {Path(r.source).name}: {r.error}")
                if len(summary.failed) > 20:
                    lines.append(
                        f"  …and {len(summary.failed) - 20} more (see log)."
                    )
            self._batch_done_signal.emit("\n".join(lines))

        self.statusBar().showMessage("Batch conversion started…")
        self._spawn_worker(_work)

    def _on_batch_done(self, msg: str) -> None:
        self.statusBar().showMessage("Batch conversion complete.")
        if self._modal_ok():  # never modal on a closing window
            QMessageBox.information(self, "Batch Convert", msg)

    def _qt_watch_folder(self) -> None:
        """Start or stop hot-folder watching from the GUI (toggle).

        Converts files dropped into a chosen folder in the background using
        the same pipeline as ``star --watch``, so the GUI stays fully usable
        (and keyboard-driven) while it runs.  Invoking it again stops it.
        """
        if self._watcher is not None:
            try:
                self._watcher.stop()
            finally:
                self._watcher = None
            self._watch_action.setText("Watch Folder…")
            self.statusBar().showMessage("Stopped watching folder.")
            return
        in_dir = QFileDialog.getExistingDirectory(self, "Select a folder to watch")
        if not in_dir:
            return
        out_dir = QFileDialog.getExistingDirectory(
            self, "Choose the output directory"
        )
        if not out_dir:
            return
        fmts = supported_formats()
        cur = str(self.settings.get("watch_format", "markdown"))
        idx = fmts.index(cur) if cur in fmts else 0
        fmt, ok = QInputDialog.getItem(
            self, "Watch Folder", "Convert new files to:", fmts, idx, False
        )
        if not ok or not fmt:
            return
        fmt = resolve_format(fmt)
        self.settings.set("watch_format", fmt)
        # The watcher's own logger writes <output>/star-watch.log (+ stderr);
        # add a handler that mirrors each line into the status bar.
        import logging

        logger = _make_logger(Path(out_dir))

        class _StatusHandler(logging.Handler):
            def emit(_self, record: "logging.LogRecord") -> None:
                try:
                    self._watch_signal.emit(record.getMessage())
                except Exception:
                    pass

        logger.addHandler(_StatusHandler())
        try:
            self._watcher = HotFolderWatcher(
                in_dir, out_dir, fmt, self.settings, logger=logger
            )
            self._watcher.start()
        except Exception as exc:
            self._watcher = None
            self._status_error(f"Watch error: {exc}")
            return
        self._watch_action.setText("Stop Watching Folder")
        self.statusBar().showMessage(f"Watching {in_dir} → {out_dir}  [{fmt}]")

    def _qt_export_markdown(self) -> None:
        """Save the current document as a Markdown file."""
        if not self.doc:
            self.statusBar().showMessage("No document loaded")
            return
        p = Path(self.doc.path) if self.doc.path else Path("export")
        default = str(p.parent / (p.stem + ".md"))
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export as Markdown", default, "Markdown (*.md *.markdown)"
        )
        if not dest:
            return
        try:
            Path(dest).write_text(self._qt_live_markdown(), encoding="utf-8")
            self.statusBar().showMessage(f"Exported Markdown → {dest}")
        except OSError as e:
            self._status_error(f"Export error: {e}")

    def _qt_export_pdf(self) -> None:
        """Save the current document as a PDF (via Qt's built-in printer).

        User highlights are rendered into the PDF because we temporarily
        apply them as document char-format before printing, then reload
        the HTML to revert.
        """
        if not self.doc:
            self.statusBar().showMessage("No document loaded")
            return
        p = Path(self.doc.path) if self.doc.path else Path("export")
        default = str(p.parent / (p.stem + ".pdf"))
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export as PDF", default, "PDF Files (*.pdf)"
        )
        if not dest:
            return
        try:
            try:
                from PyQt6.QtPrintSupport import QPrinter  # type: ignore

                _pdf_format = QPrinter.OutputFormat.PdfFormat
                _hi_res = QPrinter.PrinterMode.HighResolution
            except ImportError:
                from PyQt5.QtPrintSupport import QPrinter  # type: ignore

                _pdf_format = QPrinter.PdfFormat
                _hi_res = QPrinter.HighResolution
        except ImportError:
            self.statusBar().showMessage(
                "PDF export requires PyQt6.QtPrintSupport or PyQt5.QtPrintSupport"
            )
            return

        printer = QPrinter(_hi_res)
        printer.setOutputFormat(_pdf_format)
        printer.setOutputFileName(dest)

        # While editing, the editor shows raw Markdown source, not the rendered
        # HTML — so print a freshly-rendered throwaway document built from the
        # live buffer instead of the editor's own document.  (Read-mode user
        # highlights don't apply to an in-progress draft, so they're skipped in
        # that branch.)
        if getattr(self, "_qt_edit_mode", False):
            try:
                from PyQt6.QtGui import QTextDocument  # type: ignore
            except ImportError:
                from PyQt5.QtGui import QTextDocument  # type: ignore
            draft = QTextDocument()
            draft.setHtml(self._md_to_html(self._qt_live_markdown()))
            draft.print_(printer)
            self.statusBar().showMessage(f"Exported PDF (draft) → {dest}")
            return

        # Apply user highlights to the document temporarily so they
        # are baked into the PDF output.
        doc_obj = self.editor.document()
        path_key = (self.doc.path or "__no_path__") if self.doc else "__no_path__"
        highlights = self.settings._data.get("user_highlights", {}).get(
            path_key, []
        )
        for hl in highlights:
            cur = QTextCursor(doc_obj)
            cur.setPosition(hl.get("start", 0))
            cur.setPosition(hl.get("end", 0), _KEEP_ANCHOR)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(hl.get("color", "#ffff00")))
            cur.mergeCharFormat(fmt)

        doc_obj.print_(printer)
        self.statusBar().showMessage(f"Exported PDF → {dest}")

        # Revert: reload the original HTML (erases inline format changes).
        self.editor.setHtml(self._md_to_html(self.doc.markdown or ""))
        self._qt_apply_user_highlights()

    def _qt_export_brf(self) -> None:
        """Save the current document as a Braille-Ready File (.brf)."""
        if not self.doc:
            self.statusBar().showMessage("No document loaded")
            return
        p = Path(self.doc.path) if self.doc.path else Path("export")
        default = str(p.parent / (p.stem + ".brf"))
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export as Braille", default, "Braille (*.brf)"
        )
        if not dest:
            return
        table = str(self.settings.get("braille_table", "en-ueb-g2.ctb"))
        brf = _export_braille(
            self._qt_live_plain(),
            table,
            use_liblouis=bool(self.settings.get("braille_grade2", False)),
        )
        try:
            Path(dest).write_text(brf, encoding="utf-8")
            self.statusBar().showMessage(f"Exported BRF → {dest}")
        except OSError as e:
            self._status_error(f"Export error: {e}")

    def _qt_export_audio(self) -> None:
        """Export the full document as a TTS audio file.

        Synthesis runs in a background thread so the GUI stays responsive.
        **WAV is the default** because it needs no external tools; MP3,
        OGG, and MP4 output additionally require **ffmpeg** (recommended)
        or **pydub** (``pip install pydub``).
        """
        if not self.doc:
            self.statusBar().showMessage("No document loaded")
            return
        if not (self._qt_live_plain() or "").strip():
            self.statusBar().showMessage("Document has no readable text")
            return
        p = Path(self.doc.path) if self.doc.path else Path("export")
        fmt = str(self.settings.get("audio_export_format", "wav")).lstrip(".")
        default = str(p.parent / (p.stem + f".{fmt}"))
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Export as Audio",
            default,
            "Audio Files (*.wav *.mp3 *.ogg *.mp4);;All Files (*)",
        )
        if not dest:
            return
        text = _preprocess_tts_text(self._qt_live_plain(), self.settings)
        fmt = Path(dest).suffix.upper().lstrip(".") or "MP3"
        # Optionally emit a synchronized caption track next to the audio.
        sub_path: Optional[str] = None
        sub_fmt = str(self.settings.get("subtitle_format", "srt")).lower()
        if self.settings.get("export_subtitles_with_audio", False):
            sub_path = str(Path(dest).with_suffix(f".{sub_fmt}"))
        word_level = bool(self.settings.get("subtitle_word_level", False))
        self.statusBar().showMessage(
            f"Exporting {fmt} audio … this may take a while"
        )

        def _do_export() -> None:
            try:
                self.tts_manager.export_audio(
                    text,
                    dest,
                    subtitle_path=sub_path,
                    subtitle_format=sub_fmt,
                    subtitle_word_level=word_level,
                )
                msg = f"Audio exported → {dest}"
                if sub_path:
                    msg += f"  (+ {Path(sub_path).name})"
                self._export_audio_signal.emit(msg)
            except Exception as exc:
                self._export_audio_signal.emit(f"Audio export error: {exc}")

        self._spawn_worker(_do_export)

    def _qt_export_subtitles(self) -> None:
        """Export a timestamped SRT/VTT caption track synchronized to the
        document's synthesized speech.

        The format is chosen from the file extension (``.srt`` or ``.vtt``).
        Synthesis runs in a background thread so the GUI stays responsive.
        """
        if not self.doc:
            self.statusBar().showMessage("No document loaded")
            return
        if not (self._qt_live_plain() or "").strip():
            self.statusBar().showMessage("Document has no readable text")
            return
        p = Path(self.doc.path) if self.doc.path else Path("export")
        fmt = str(self.settings.get("subtitle_format", "srt")).lower()
        if fmt not in ("srt", "vtt"):
            fmt = "srt"
        default = str(p.parent / (p.stem + f".{fmt}"))
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Export Subtitles",
            default,
            "Subtitles (*.srt *.vtt);;All Files (*)",
        )
        if not dest:
            return
        out_fmt = "vtt" if dest.lower().endswith(".vtt") else "srt"
        text = _preprocess_tts_text(self.doc.plain_text, self.settings)
        word_level = bool(self.settings.get("subtitle_word_level", False))
        self.statusBar().showMessage("Generating subtitles … this may take a while")

        def _do_export() -> None:
            try:
                self.tts_manager.export_subtitles(
                    text, dest, fmt=out_fmt, word_level=word_level
                )
                self._export_audio_signal.emit(f"Subtitles exported → {dest}")
            except Exception as exc:
                self._export_audio_signal.emit(f"Subtitle export error: {exc}")

        self._spawn_worker(_do_export)

    def _qt_export_audiobook(self) -> None:
        """Export the document as a chaptered audiobook (``.m4b``).

        Chapters come from the document's Markdown headings (fallback: a single
        chapter).  Synthesis + ffmpeg muxing run on a background thread; a
        cancelable :class:`QProgressDialog` on the GUI thread shows per-chapter
        progress, driven by a short ``QTimer`` that reads worker state (so nothing
        touches Qt from the worker).  Cancel sets a flag the worker checks between
        chapters; the dialog and timer are torn down cleanly on finish or cancel.

        Requires **ffmpeg**; when it is absent the user is told to install ffmpeg
        (never to run ``pip``), matching the no-pip UX invariant.
        """
        try:
            from PyQt6.QtWidgets import QProgressDialog  # type: ignore
        except ImportError:
            from PyQt5.QtWidgets import QProgressDialog  # type: ignore

        from ..audiobook import find_ffmpeg
        from ..tts.exporters import M4BExporter

        if not self.doc:
            self.statusBar().showMessage("No document loaded")
            return
        if not (self._qt_live_plain() or "").strip():
            self.statusBar().showMessage("Document has no readable text")
            return
        if not find_ffmpeg():
            QMessageBox.warning(
                self,
                "Audiobook Export",
                "Exporting an M4B audiobook needs ffmpeg.\n\n"
                "Install ffmpeg and make sure it is on your PATH, then try again.",
            )
            return

        p = Path(self.doc.path) if self.doc.path else Path("export")
        default = str(p.parent / (p.stem + ".m4b"))
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export Audiobook (M4B)", default, "Audiobook (*.m4b);;All Files (*)"
        )
        if not dest:
            return

        # Export the live editor buffer when editing (a copy — self.doc is left
        # untouched so Discard still reverts).
        doc = self._qt_live_doc()
        backend = getattr(self.tts_manager, "_backend", None)
        # Shared worker/UI state.  Only the worker writes progress fields; only the
        # GUI timer reads them.  ``cancel`` is set by the GUI, read by the worker.
        state: Dict[str, Any] = {
            "done": False,
            "error": None,
            "cur": 0,
            "total": 0,
            "label": "Preparing…",
            "cancel": False,
        }

        dlg = QProgressDialog("Preparing audiobook…", "Cancel", 0, 0, self)
        dlg.setWindowTitle("Export Audiobook (M4B)")
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setValue(0)

        def _on_progress(cur: int, total: int, label: str) -> None:
            state["cur"], state["total"], state["label"] = cur, total, label

        def _work() -> None:
            try:
                M4BExporter().export(
                    doc,
                    dest,
                    settings=self.settings,
                    backend=backend,
                    title=getattr(doc, "title", ""),
                    progress=_on_progress,
                    cancel=lambda: state["cancel"],
                )
            except Exception as exc:  # noqa: BLE001 — surfaced via status bar
                state["error"] = str(exc)
            finally:
                state["done"] = True

        thread = self._spawn_worker(_work, name="star-audiobook-export", start=False)

        def _poll() -> None:
            if dlg.wasCanceled():
                state["cancel"] = True
            total = state["total"]
            if total:
                if dlg.maximum() != total:
                    dlg.setMaximum(total)
                dlg.setValue(min(state["cur"], total))
            dlg.setLabelText(state["label"])
            if state["done"]:
                timer.stop()
                dlg.reset()
                dlg.close()
                err = state["error"]
                if err:
                    if "cancelled" in err.lower():
                        self.statusBar().showMessage("Audiobook export cancelled")
                    else:
                        self._status_error(f"Audiobook export error: {err}")
                else:
                    self.statusBar().showMessage(f"Audiobook exported → {dest}")

        timer = QTimer(self)
        timer.setInterval(150)
        timer.timeout.connect(_poll)

        self.statusBar().showMessage("Exporting audiobook … this may take a while")
        thread.start()
        timer.start()

    # ── Plugin-registry exporters ────────────────────────────────────────────
    # File ▸ Export lists the built-in exporters that have dedicated, specialised
    # handlers above (Markdown, Anki, Audio→wav, Video→mp4).  The names below are
    # therefore already on the menu and are skipped when generating items from the
    # registry, so the dynamic section surfaces the remaining built-ins (HTML,
    # EPUB) plus any installed third-party ``star.exporters`` plugin — with no
    # change to star itself.
    _MENU_COVERED_EXPORTERS = frozenset({"markdown", "anki", "wav", "mp4", "m4b"})

    def _plugin_exporters(self) -> "List[type]":
        """Return the installed Exporter classes that should appear in the
        dynamic File ▸ Export section: available, not already covered by a
        bespoke menu item, sorted by name."""
        from ..plugins import PluginRegistry

        out = [
            cls
            for cls in PluginRegistry.get().exporters
            if cls.name not in self._MENU_COVERED_EXPORTERS and cls.available()
        ]
        return sorted(out, key=lambda c: c.name)

    def _qt_export_via_plugin(self, exporter_cls: type) -> None:
        """Generic File ▸ Export handler driving a registered Exporter plugin.

        Opens a save dialog filtered to the exporter's extensions and runs the
        export on a background thread (some exporters shell out to Pandoc or
        synthesise speech), reporting the outcome on the status bar.
        """
        if not self.doc:
            self.statusBar().showMessage("No document loaded")
            return
        exts = sorted(exporter_cls.extensions())
        primary = exts[0] if exts else ""
        p = Path(self.doc.path) if self.doc.path else Path("export")
        default = str(p.parent / (p.stem + primary))
        label = exporter_cls.name.upper()
        pattern = " ".join(f"*{e}" for e in exts) or "*"
        dest, _ = QFileDialog.getSaveFileName(
            self, f"Export as {label}", default, f"{label} ({pattern});;All Files (*)"
        )
        if not dest:
            return
        self.statusBar().showMessage(f"Exporting {label} … this may take a while")
        # Export the live editor buffer when editing (a copy; self.doc untouched).
        doc = self._qt_live_doc()
        backend = getattr(self.tts_manager, "_backend", None)

        def _work() -> None:
            try:
                exporter_cls().export(
                    doc,
                    dest,
                    settings=self.settings,
                    backend=backend,
                    title=getattr(doc, "title", ""),
                )
                self._export_audio_signal.emit(f"Exported {label} → {dest}")
            except Exception as exc:
                self._export_audio_signal.emit(f"{label} export error: {exc}")

        self._spawn_worker(_work)

