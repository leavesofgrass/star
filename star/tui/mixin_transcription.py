"""Speech-to-text for the TUI: voice-dictated notes and audio transcription.

Methods of StarApp, mirroring the GUI's TranscriptionMixin (the backends —
StreamRecorder and the Whisper helpers — are shared).  M-x ``dictate-note``
records until the user presses Enter (Esc cancels) and attaches the
transcribed note at the reading position; M-x ``transcribe-file <path>``
opens a Whisper transcript of an audio file as a readable document.
Transcription runs on a daemon thread; results come back to the curses loop
through ``_load_queue`` (documents) or ``_bg_queue`` (everything else).
"""
from .._runtime import *  # noqa: F401,F403
from ..documents import Document
from ..transcribe import StreamRecorder, _transcribe_audio, _transcribe_samples


class TuiTranscriptionMixin:

    # ── Voice-dictated notes (M-x dictate-note) ────────────────────────────

    def _dictate_note_cmd(self) -> None:
        """Record a voice memo until the user says stop; save it as a note.

        Same contract as the GUI dialog: no fixed time limit — a live status
        line shows the elapsed time, Enter stops and transcribes, Esc
        discards.  The reading voice is paused before the mic opens so the
        note doesn't transcribe star's own speech.
        """
        if not self.doc or not self.doc.word_map:
            self.notify("Open a document before dictating a note.", error=True)
            return
        if not _AUDIO_IN:
            self.notify(
                "Dictation needs a microphone stack: pip install sounddevice numpy",
                error=True,
            )
            return
        if not _WHISPER:
            self.notify(
                "Dictation needs Whisper: pip install openai-whisper",
                error=True,
            )
            return
        # Pause the reading voice BEFORE the mic opens (on a laptop the mic
        # sits next to the speakers — Whisper would transcribe star's own
        # voice into the note).  Word saved so the toggle resumes in place.
        if self.tts.speaking:
            saved = self.tts.current_word_idx
            self._tts_stop()
            if saved >= 0:
                self._tts_paused_at_word = saved
        try:
            recorder = StreamRecorder()
            recorder.start()
        except Exception as exc:  # noqa: BLE001 — no mic / device busy
            self.notify(f"Could not start recording: {exc}", error=True)
            return

        # Capture the anchor NOW — the caret may move while Whisper runs.
        word_idx = max(0, self._current_word_for_nav())
        anchor = ""
        wm = self.doc.word_map
        if wm and 0 <= word_idx < len(wm):
            dl = wm[word_idx].disp_line
            if 0 <= dl < len(self.rendered):
                anchor = "".join(t for t, _ in self.rendered[dl]).strip()[:120]

        # Modal recording loop (the pager pattern): the 150 ms getch timeout
        # doubles as the timer tick.
        cancelled = False
        while True:
            s = int(recorder.elapsed)
            self.notify(
                f"Recording {s // 60}:{s % 60:02d} — Enter: stop & transcribe, "
                "Esc: cancel",
                dur=2.0,
            )
            self.draw()
            ch = self.scr.getch()
            if ch in (10, 13, curses.KEY_ENTER):
                break
            if ch in (27, ord("q")):
                cancelled = True
                break
        if cancelled:
            recorder.cancel()
            self.notify("Dictation cancelled")
            return
        try:
            samples = recorder.stop_samples()
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Recording failed: {exc}", error=True)
            return
        if samples is None or len(samples) == 0:
            self.notify("No audio was recorded — check your microphone.", error=True)
            return

        model = str(self.settings.get("whisper_model", "base"))
        self.notify("Transcribing your note…", dur=30.0)

        def _work() -> None:
            try:
                text = _transcribe_samples(samples, model)
                self._bg_queue.put(lambda: self._dictate_done(text, word_idx, anchor))
            except Exception as exc:  # noqa: BLE001
                msg = f"Dictation failed: {exc}"
                self._bg_queue.put(lambda: self.notify(msg, error=True))

        threading.Thread(target=_work, daemon=True).start()

    def _dictate_done(self, text: str, word_idx: int, anchor: str) -> None:
        """Curses-loop callback: attach the transcribed note (or explain)."""
        text = (text or "").strip()
        if not text:
            self.notify("Dictation produced no text", error=True)
            return
        items = self._load_annotations()
        items.append(
            {
                "char_pos": 0,  # Qt-only; TUI anchors by word_idx
                "word_idx": int(word_idx),
                "anchor": anchor,
                "note": text,
                "tags": ["dictated"],
                "cite": "",
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
        )
        self._store_annotations(items)
        self.notify(f"Dictated note added ({len(text)} chars)")

    # ── Audio-file transcription (M-x transcribe-file) ─────────────────────

    def _transcribe_file_cmd(self, arg: str = "") -> None:
        """Transcribe an audio file with Whisper and open it as a document."""
        if not _WHISPER:
            self.notify(
                "Transcription needs Whisper: pip install openai-whisper",
                error=True,
            )
            return
        # Whisper decodes audio FILES through ffmpeg; without it the failure
        # is a baffling WinError long after the model loads (the GUI has the
        # same pre-check).  Dictation is exempt — it feeds samples directly.
        from ..audiobook import find_ffmpeg

        if not find_ffmpeg():
            self.notify(
                "Transcribing a file needs ffmpeg on your PATH to decode it.",
                error=True,
            )
            return
        path = (arg or "").strip().strip('"')
        if not path:
            self._enter_minibuffer(
                "Audio file to transcribe: ", on_commit=self._transcribe_file_cmd
            )
            return
        if not Path(path).is_file():
            self.notify(f"No such file: {path}", error=True)
            return
        model = str(self.settings.get("whisper_model", "base"))
        ts = bool(self.settings.get("transcribe_timestamps", False))
        self.notify(
            f"Transcribing with Whisper ({model})… this may take a while", dur=30.0
        )

        def _work() -> None:
            try:
                text = _transcribe_audio(path, model, timestamps=ts)
                if not (text or "").strip():
                    self._bg_queue.put(
                        lambda: self.notify("Transcription produced no text", error=True)
                    )
                    return
                name = Path(path).stem or "transcription"
                doc = Document(
                    path="",
                    title=f"Transcription — {name}",
                    markdown=f"# Transcription — {name}\n\n{text}\n",
                    plain_text=text,
                    format="transcription",
                )
                self._load_queue.put(doc)
            except Exception as exc:  # noqa: BLE001
                msg = f"Transcription failed: {exc}"
                self._bg_queue.put(lambda: self.notify(msg, error=True))

        threading.Thread(target=_work, daemon=True).start()
