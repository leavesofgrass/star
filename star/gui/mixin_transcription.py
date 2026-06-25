"""TranscriptionMixin — methods extracted from StarWindow (main_window.py).

Mixed into StarWindow via ``class StarWindow(TranscriptionMixin, ...)``; operates
on StarWindow instance state and other methods via ``self``, holding no
state of its own.  IMPORT SAFETY: references Qt at module scope — imported
lazily by main_window.py (itself imported by runner.py after the _QT guard).
"""
from .._runtime import *  # noqa: F401,F403
from ..documents import Document
from ..transcribe import _record_audio_to_wav, _transcribe_audio


class TranscriptionMixin:
    # ── Speech recognition (Whisper) ───────────────────

    def _qt_transcribe_file(self) -> None:
        """Transcribe an audio file with Whisper and open it as a document."""
        if not _WHISPER:
            QMessageBox.information(
                self,
                "Speech recognition unavailable",
                "Transcription requires Whisper:\n\n"
                "    pip install openai-whisper\n"
                "or  pip install faster-whisper",
            )
            return
        src, _flt = QFileDialog.getOpenFileName(
            self,
            "Transcribe Audio",
            "",
            "Audio (*.wav *.mp3 *.m4a *.ogg *.flac *.aac *.mp4);;All Files (*)",
        )
        if not src:
            return
        model = str(self.settings.get("whisper_model", "base"))
        ts = bool(self.settings.get("transcribe_timestamps", False))
        self.statusBar().showMessage(
            f"Transcribing with Whisper ({model})… this may take a while"
        )

        def _work() -> None:
            try:
                text = _transcribe_audio(src, model, timestamps=ts)
                self._transcribe_signal.emit(text, src)
            except Exception as exc:  # noqa: BLE001
                self._transcribe_signal.emit("", f"ERROR: {exc}")

        threading.Thread(target=_work, daemon=True).start()

    def _qt_on_transcribed(self, text: str, src: str) -> None:
        """Main-thread handler for a completed transcription."""
        if src.startswith("ERROR: "):
            self.statusBar().showMessage(src[7:])
            return
        if not text:
            self.statusBar().showMessage("Transcription produced no text")
            return
        name = Path(src).stem if src else "transcription"
        md = f"# Transcription — {name}\n\n{text}\n"
        self._pending_doc = Document(
            path="",
            title=f"Transcription — {name}",
            markdown=md,
            plain_text=text,
            format="transcription",
        )
        self._on_doc_loaded()
        self.statusBar().showMessage(f"Transcribed {name} ({len(text)} chars)")

    def _qt_dictate_note(self) -> None:
        """Record a short voice memo and add it as a note (Whisper)."""
        if not self.doc:
            self.statusBar().showMessage("Open a document before dictating a note")
            return
        if not _WHISPER or not _AUDIO_IN:
            QMessageBox.information(
                self,
                "Dictation unavailable",
                "Voice dictation requires Whisper and a microphone library:\n\n"
                "    pip install openai-whisper sounddevice numpy",
            )
            return
        secs, ok = QInputDialog.getInt(
            self, "Dictate Note", "Record for how many seconds?", 8, 2, 300
        )
        if not ok:
            return
        char_pos, anchor = self._qt_current_anchor()
        model = str(self.settings.get("whisper_model", "base"))
        chunk = max(2, int(self.settings.get("whisper_chunk_seconds", 6)))
        self.statusBar().showMessage(f"Recording {secs}s… speak now")

        def _work() -> None:
            # Live streaming: record in short chunks, transcribing each as
            # it arrives so the user sees text accumulate instead of waiting
            # for one long blocking pass.  Chunks are concatenated into the
            # final note.
            try:
                remaining = secs
                parts: List[str] = []
                while remaining > 0:
                    seg = min(chunk, remaining)
                    remaining -= seg
                    wav = _record_audio_to_wav(seg)
                    try:
                        piece = _transcribe_audio(wav, model)
                    finally:
                        Path(wav).unlink(missing_ok=True)
                    if piece:
                        parts.append(piece)
                        self._dictate_partial_signal.emit(" ".join(parts))
                self._dictate_signal.emit(
                    " ".join(parts), str(int(char_pos)), anchor
                )
            except Exception as exc:  # noqa: BLE001
                self._dictate_signal.emit("", "ERROR", str(exc))

        threading.Thread(target=_work, daemon=True).start()

    def _qt_on_dictate_partial(self, text: str) -> None:
        """Live status update as dictation chunks are transcribed."""
        preview = text[-80:]
        self.statusBar().showMessage(f"🎙 …{preview}")

    def _qt_on_dictated(self, text: str, char_pos_s: str, anchor: str) -> None:
        """Main-thread handler for a completed dictation → save as a note."""
        if char_pos_s == "ERROR":
            self.statusBar().showMessage(f"Dictation error: {anchor}")
            return
        if not text:
            self.statusBar().showMessage("Dictation produced no text")
            return
        items = self._qt_load_annotations()
        items.append(
            {
                "char_pos": int(char_pos_s or 0),
                "word_idx": self._qt_char_to_word(int(char_pos_s or 0)),
                "anchor": anchor,
                "note": text,
                "tags": ["dictated"],
                "cite": "",
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
        )
        self._qt_store_annotations(items)
        self._qt_build_annotations()
        if not self._annot_dock.isVisible():
            self._annot_dock.setVisible(True)
            self.settings["qt_show_notes"] = True
        self.statusBar().showMessage(f"Dictated note added ({len(text)} chars)")

