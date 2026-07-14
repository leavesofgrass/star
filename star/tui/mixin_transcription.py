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
from ..settings import WHISPER_MODELS
from ..transcribe import (
    StreamRecorder,
    _audio_in_now,
    _transcribe_audio,
    _transcribe_samples,
)


class TuiTranscriptionMixin:

    def _missing_feature_notify(self, feature: str, pip_hint: str) -> None:
        """Explain a missing optional feature honestly.

        A frozen (PyInstaller) build can't pip-install anything into itself,
        so the usual "pip install X" advice is a dead end there — same
        honesty rule as the GUI's feature prompt (see
        gui/mixin_transcription.py).
        """
        if getattr(sys, "frozen", False):
            self.notify(
                f"This standalone build of star doesn't include {feature}; "
                "install star with pip (pip install star-reader) to use it.",
                error=True,
            )
        else:
            self.notify(f"{feature} needs an add-on: {pip_hint}", error=True)

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
        if not _audio_in_now():
            self._missing_feature_notify(
                "voice dictation", "pip install sounddevice numpy"
            )
            return
        if not _whisper_backend_now():
            self._missing_feature_notify(
                "voice dictation", "pip install faster-whisper"
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

        # Capture the anchor AND the annotation key NOW — Whisper runs for
        # many seconds, and the user may open another document meanwhile; the
        # note must land on the document it was dictated on, not whichever
        # one is open when transcription finishes.
        annot_key = self._annot_key()
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
            if ch == 27:
                cancelled = True
                break
            if ch == curses.KEY_RESIZE:
                # The one-shot resize event must not be swallowed: re-wrap now
                # (as the main loop would), or the document stays truncated at
                # the old width after the recording ends.
                self._render_doc()
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
                self._bg_queue.put(
                    lambda: self._dictate_done(text, word_idx, anchor, annot_key)
                )
            except Exception as exc:  # noqa: BLE001
                msg = f"Dictation failed: {exc}"
                self._bg_queue.put(lambda: self.notify(msg, error=True))

        threading.Thread(target=_work, daemon=True).start()

    def _dictate_done(self, text: str, word_idx: int, anchor: str, key: str) -> None:
        """Curses-loop callback: attach the transcribed note (or explain).

        *key* is the annotation-store key captured when the recording was
        made — the store is addressed directly (not via _load/_store, which
        use the currently open document) so a document switched mid-Whisper
        can't steal the note.
        """
        text = (text or "").strip()
        if not text:
            self.notify("Dictation produced no text", error=True)
            return
        if not key:
            self.notify("Dictated note lost: its document is gone", error=True)
            return
        store = dict(self.settings.get("annotations", {}) or {})
        items = [dict(a) for a in store.get(key, [])]
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
        store[key] = items
        self.settings.set("annotations", store)
        self.notify(f"Dictated note added ({len(text)} chars)")

    # ── Audio-file transcription (M-x transcribe-file) ─────────────────────

    def _whisper_model_cmd(self, arg: str = "") -> None:
        """M-x whisper-model — pick the Whisper size used for dictation and
        transcription (mirrors the GUI's Preferences ▸ Voice ▸ Dictation
        model chooser).  With an argument it applies directly; without one it
        opens a completion minibuffer over the supported sizes."""

        def _apply(chosen: str) -> None:
            chosen = chosen.strip()
            if chosen not in WHISPER_MODELS:
                self.notify(
                    f"Unknown model size: {chosen!r} "
                    f"(choose from {', '.join(WHISPER_MODELS)})",
                    error=True,
                )
                return
            self.settings.set("whisper_model", chosen)
            self.notify(f"Dictation model: {chosen}")

        if arg:
            _apply(arg)
            return
        self._enter_minibuffer(
            "Whisper model (Tab to browse): ",
            initial=str(self.settings.get("whisper_model", "base")),
            on_commit=_apply,
            completions=list(WHISPER_MODELS),
        )

    def _transcribe_file_cmd(self, arg: str = "") -> None:
        """Transcribe an audio file with Whisper and open it as a document."""
        if not _whisper_backend_now():
            self._missing_feature_notify(
                "audio transcription", "pip install faster-whisper"
            )
            return
        # openai-whisper decodes audio FILES through ffmpeg; without it the
        # failure is a baffling WinError long after the model loads (the GUI has
        # the same pre-check).  faster-whisper decodes via bundled PyAV, so it
        # needs no ffmpeg — only gate the check on the openai backend.  Dictation
        # is exempt either way — it feeds samples directly.
        from ..audiobook import find_ffmpeg

        if _whisper_backend_now() == "openai" and not find_ffmpeg():
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
