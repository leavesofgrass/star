"""File open, markdown/braille/audio/subtitle/video export, batch convert.

Methods of StarApp, split out of the former monolithic star/tui.py.
Mixed into StarApp in app.py; calls other groups via ``self``.
"""
from .._runtime import *  # noqa: F401,F403
from ..braille import _export_braille
from ..convert import resolve_format, run_batch, supported_formats
from ..ttstext import _preprocess_tts_text


class ExportMixin:

    # ── File operations ────────────────────────────────────────────────────

    def _open_file_prompt(self) -> None:
        """Open a file path via minibuffer prompt."""
        last = str(self.settings.get("last_path", "")) or ""
        default = (
            (str(Path(last).parent) + os.sep) if last and Path(last).is_file() else ""
        )
        self._enter_minibuffer(
            "Find file: ", initial=default, on_commit=self._open_file_cb
        )

    def _open_file_cb(self, path: str) -> None:
        path = path.strip().rstrip("/\\")
        if not path:
            return
        path = os.path.expanduser(os.path.expandvars(path))
        if path.startswith(("http://", "https://")):
            self._open_async(path)
        elif os.path.exists(path):
            self._open_async(path)
        else:
            self.notify(f"File not found: {path}", error=True)

    def _open_url_prompt(self) -> None:
        self._enter_minibuffer(
            "Open URL: ", on_commit=lambda u: self._open_async(u.strip())
        )

    def _export_markdown(self) -> None:
        if not self.doc:
            self.notify("No document to export.", error=True)
            return
        p = Path(self.doc.path)
        default = (
            str(p.parent / (p.stem + "_export.md")) if self.doc.path else "export.md"
        )
        self._enter_minibuffer(
            "Export Markdown to: ", initial=default, on_commit=self._export_md_cb
        )

    def _export_md_cb(self, dest: str) -> None:
        dest = dest.strip()
        if not dest or not self.doc:
            return
        try:
            Path(dest).write_text(self.doc.markdown, encoding="utf-8")
            self.notify(f"Exported → {dest}")
        except OSError as e:
            self.notify(f"Export error: {e}", error=True)

    def _export_braille_cmd(self) -> None:
        if not self.doc:
            self.notify("No document to export.", error=True)
            return
        table = str(self.settings["braille_table"])
        brf = _export_braille(
            self.doc.plain_text,
            table,
            use_liblouis=bool(self.settings.get("braille_grade2", False)),
        )
        p = Path(self.doc.path) if self.doc.path else Path("export")
        dest = str(p.parent / (p.stem + ".brf"))
        try:
            Path(dest).write_text(brf, encoding="utf-8")
            self.notify(f"BRF exported → {dest}")
        except OSError as e:
            self.notify(f"BRF export error: {e}", error=True)

    def _export_audio_cmd(self, fmt: str = "") -> None:
        """Prompt for an output path and export TTS audio (M-x export-audio).

        *fmt* is the default file extension (wav, mp3, ogg, mp4).  When empty
        the ``audio_export_format`` setting is used (WAV by default — it needs
        no external tools).  Synthesis runs synchronously, so the TUI will be
        unresponsive until it finishes.  Use a shorter document or the
        espeak/pyttsx3 backend for faster results.
        """
        fmt = (fmt or str(self.settings.get("audio_export_format", "wav"))).lstrip(".")
        if not self.doc:
            self.notify("No document to export.", error=True)
            return
        p = Path(self.doc.path) if self.doc.path else Path("export")
        default = str(p.parent / (p.stem + f".{fmt}"))
        self._enter_minibuffer(
            f"Export audio ({fmt}) to: ",
            initial=default,
            on_commit=self._export_audio_cb,
        )

    def _export_audio_cb(self, dest: str) -> None:
        dest = dest.strip()
        if not dest or not self.doc:
            return
        text = _preprocess_tts_text(self.doc.plain_text, self.settings)
        # Optionally emit a synchronized caption track alongside the audio.
        sub_path: Optional[str] = None
        sub_fmt = str(self.settings.get("subtitle_format", "srt")).lower()
        if self.settings.get("export_subtitles_with_audio", False):
            sub_path = str(Path(dest).with_suffix(f".{sub_fmt}"))
        self.notify("Exporting audio… please wait", dur=5.0)
        try:
            self.tts.export_audio(
                text,
                dest,
                subtitle_path=sub_path,
                subtitle_format=sub_fmt,
                subtitle_word_level=bool(
                    self.settings.get("subtitle_word_level", False)
                ),
            )
            msg = f"Audio exported → {dest}"
            if sub_path:
                msg += f"  (+ {Path(sub_path).name})"
            self.notify(msg)
        except Exception as exc:
            self.notify(f"Audio export error: {exc}", error=True)

    def _export_subtitles_cmd(self) -> None:
        """Prompt for a path and export a timestamped SRT/VTT caption track
        synchronized to the document's synthesized speech (M-x
        export-subtitles).  Synthesis runs synchronously.
        """
        if not self.doc:
            self.notify("No document to export.", error=True)
            return
        fmt = str(self.settings.get("subtitle_format", "srt")).lower()
        if fmt not in ("srt", "vtt"):
            fmt = "srt"
        p = Path(self.doc.path) if self.doc.path else Path("export")
        default = str(p.parent / (p.stem + f".{fmt}"))
        self._enter_minibuffer(
            f"Export subtitles ({fmt}) to: ",
            initial=default,
            on_commit=self._export_subtitles_cb,
        )

    def _export_subtitles_cb(self, dest: str) -> None:
        dest = dest.strip()
        if not dest or not self.doc:
            return
        fmt = "vtt" if dest.lower().endswith(".vtt") else "srt"
        text = _preprocess_tts_text(self.doc.plain_text, self.settings)
        self.notify("Generating subtitles… please wait", dur=5.0)
        try:
            self.tts.export_subtitles(
                text,
                dest,
                fmt=fmt,
                word_level=bool(self.settings.get("subtitle_word_level", False)),
            )
            self.notify(f"Subtitles exported → {dest}")
        except Exception as exc:
            self.notify(f"Subtitle export error: {exc}", error=True)

    # ── Batch conversion (M-x batch-convert) ───────────────────────
    def _batch_convert(self, arg: str = "") -> None:
        """Convert many files / a folder to one format (M-x batch-convert).

        Prompts in sequence for the input (a file, a folder, or a glob), the
        output format, and the output directory, then runs the shared batch
        core.  Conversion is synchronous (like audio export), failure-isolated,
        and writes a summary log into the output directory.
        """
        start = ""
        if self.doc and self.doc.path:
            start = str(Path(self.doc.path).parent)
        self._enter_minibuffer(
            "Batch convert — file, folder, or glob: ",
            initial=start,
            on_commit=self._batch_input_cb,
        )

    def _batch_input_cb(self, src: str) -> None:
        src = src.strip()
        if not src:
            return
        self._batch_src = src
        self._enter_minibuffer(
            f"Output format ({' / '.join(supported_formats())}): ",
            initial=str(self.settings.get("batch_format", "markdown")),
            on_commit=self._batch_fmt_cb,
            completions=supported_formats(),
        )

    def _batch_fmt_cb(self, fmt: str) -> None:
        try:
            self._batch_fmt = resolve_format(fmt)
        except ValueError as exc:
            self.notify(str(exc), error=True)
            return
        src = Path(self._batch_src)
        out_default = str(src if src.is_dir() else src.parent)
        self._enter_minibuffer(
            "Output directory: ",
            initial=out_default,
            on_commit=self._batch_out_cb,
        )

    def _batch_out_cb(self, out_dir: str) -> None:
        out_dir = out_dir.strip()
        if not out_dir:
            return
        src = self._batch_src
        if any(ch in src for ch in "*?["):
            import glob as _glob

            paths: List[str] = sorted(_glob.glob(src))
        else:
            paths = [src]
        if not paths:
            self.notify("No matching input files.", error=True)
            return
        self.settings.set("batch_format", self._batch_fmt)
        self.notify("Batch converting… please wait", dur=5.0)
        try:
            summary = run_batch(paths, out_dir, self._batch_fmt, self.settings)
        except ValueError as exc:
            self.notify(str(exc), error=True)
            return
        msg = (
            f"Batch: {len(summary.succeeded)}/{summary.total} ok, "
            f"{len(summary.failed)} failed → {out_dir}"
        )
        if summary.log_path:
            msg += f"  (log: {Path(summary.log_path).name})"
        self.notify(msg, dur=8.0, error=bool(summary.failed))

    def _set_subtitle_format(self, fmt: str) -> None:
        """Set the caption format used for subtitle export (srt | vtt)."""
        fmt = (fmt or "").strip().lower()
        if fmt not in ("srt", "vtt"):
            cur = str(self.settings.get("subtitle_format", "srt"))
            self.notify(f"Subtitle format: {cur}.  Use 'subtitle-format srt|vtt'.")
            return
        self.settings.set("subtitle_format", fmt)
        self.notify(f"Subtitle format: {fmt}")

    def _set_highlight_granularity(self, gran: str) -> None:
        """Set how the spoken text is highlighted (word | sentence | both)."""
        gran = (gran or "").strip().lower()
        if gran not in ("word", "sentence", "both"):
            cur = str(self.settings.get("highlight_granularity", "word"))
            self.notify(
                f"Highlight granularity: {cur}.  "
                "Use 'highlight-granularity word|sentence|both'."
            )
            return
        self.settings.set("highlight_granularity", gran)
        # Clear any stale sentence span so the change takes effect immediately.
        if gran == "word":
            self._highlight_sent = None
        self.notify(f"Highlight granularity: {gran}")

    # ── Video export (TUI) ────────────────────────────────────────────────

    def _export_video_cmd(self, fmt: str = "") -> None:
        """Export current document as a karaoke MP4 video (M-x export-video)."""
        if not self.doc:
            self.notify("No document open", error=True)
            return
        if not self.doc.plain_text.strip():
            self.notify("Document has no readable text", error=True)
            return
        vid = self.settings.get("video") or {}
        last_dir = vid.get("last_export_dir") or str(Path.home())
        default = str(Path(last_dir) / (Path(self.doc.title or "export").stem + ".mp4"))
        self._enter_minibuffer(
            f"Export video to [{default}]: ",
            on_commit=lambda p: self._export_video_cb(p.strip() or default),
        )

    def _export_video_cb(self, dest: str) -> None:
        from ..video import export_video
        self.notify("Rendering karaoke video… (this may take a minute)")
        doc = self.doc

        def _run() -> None:
            try:
                result = export_video(doc, self.settings, dest)
                if result.get("error"):
                    self.notify(f"Video export error: {result['error']}", error=True)
                else:
                    cues = result.get("cues", 0)
                    self.notify(f"Video exported → {dest}  ({cues} sentences)")
                    vid = dict(self.settings.get("video") or {})
                    vid["last_export_dir"] = str(Path(dest).parent)
                    self.settings.set("video", vid)
            except Exception as e:
                self.notify(f"Video export failed: {e}", error=True)

        threading.Thread(target=_run, daemon=True).start()
