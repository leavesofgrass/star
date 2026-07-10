"""TranscriptionMixin — methods extracted from StarWindow (main_window.py).

Mixed into StarWindow via ``class StarWindow(TranscriptionMixin, ...)``; operates
on StarWindow instance state and other methods via ``self``, holding no
state of its own.  IMPORT SAFETY: references Qt at module scope — imported
lazily by main_window.py (itself imported by runner.py after the _QT guard).
"""
from .._runtime import *  # noqa: F401,F403
from ..documents import Document
from ..i18n import tr
from ..transcribe import StreamRecorder, _transcribe_audio, _transcribe_samples
from .a11y import announce


class TranscriptionMixin:
    # ── Speech recognition (Whisper) ───────────────────

    def _qt_require_optional_feature(self, feature_key: str, human_name: str) -> bool:
        """True if *feature_key*'s packages are importable now.

        Otherwise offer to auto-install them and return False.  star's users are
        students who don't know Python — a missing add-on is a one-click download
        in the background, never a ``pip install`` instruction."""
        from .. import autodeps

        pkgs = autodeps.FEATURES.get(feature_key, [])
        if pkgs and not autodeps.missing(pkgs):
            return True
        # A frozen (PyInstaller) build cannot install packages into itself —
        # sys.executable IS star.exe, so the friendly "Install it now?" button
        # would spawn star once per package and add nothing.  Be honest
        # instead of offering a download that always fails.
        if getattr(sys, "frozen", False):
            QMessageBox.information(
                self,
                tr("{feature} not included").format(feature=human_name),
                tr("This standalone build of star doesn't include {feature}, "
                   "and features can't be added to it. To use {feature}, "
                   "install star with pip (pip install star-reader) — it can "
                   "download features on demand.").format(feature=human_name),
            )
            return False
        _label, _detail, mb = autodeps.FEATURE_INFO.get(feature_key, (human_name, "", 0))
        size = f"~{mb} MB" if mb < 1000 else f"~{mb / 1000:.1f} GB"
        try:
            yes, no = QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No
        except AttributeError:  # PyQt5
            yes, no = QMessageBox.Yes, QMessageBox.No  # type: ignore[attr-defined]
        ret = QMessageBox.question(
            self,
            tr("Install {feature}?").format(feature=human_name),
            tr("{feature} needs an add-on that isn't installed yet (about a {size} "
               "download). Install it now? star downloads it in the background while "
               "you keep reading — then restart star to use {feature}.").format(
                   feature=human_name, size=size),
            yes | no,
        )
        if ret == yes:
            self._qt_start_feature_install(feature_key, human_name)
        return False

    def _qt_start_feature_install(self, feature_key: str, human_name: str) -> None:
        """Download a feature's packages on a worker thread, with real feedback.

        Uses install_feature_now (ignores the once-per-machine markers — this is
        an explicit request — and reports success), then _deps_installed_signal
        delivers the outcome to the GUI thread."""
        from .. import autodeps

        autodeps.set_enabled(True)
        self.statusBar().showMessage(
            tr("Downloading {feature}…").format(feature=human_name), 0
        )
        # A multi-minute download with no audible start is indistinguishable
        # from a no-op for a screen-reader user — set the expectation now.
        announce(
            self.editor,
            tr("Downloading {feature} — you can keep reading; star will "
               "announce when it is ready.").format(feature=human_name),
        )

        def _work() -> None:
            ready = False
            try:
                ok = autodeps.install_feature_now(feature_key)
                if ok:
                    # Flip the stale availability flags + clear import caches so
                    # the feature works right now instead of dead-ending on a
                    # "pip install" message.
                    ready = autodeps.refresh_feature(feature_key)
            except Exception:
                ok = False
            try:
                self._deps_installed_signal.emit(human_name, ok, ready)
            except Exception:
                pass

        threading.Thread(target=_work, name="star-feature-install", daemon=True).start()

    def _on_feature_installed(self, human_name: str, ok: bool, ready: bool) -> None:
        """GUI-thread slot: report the outcome of a feature download.

        Every outcome is announced as well as shown — the download was
        requested minutes ago, so a blind user is not watching the status bar
        when it lands."""
        if not ok:
            msg = tr("Couldn't install {feature} — check your connection and "
                     "try again.").format(feature=human_name)
            duration = 12000
        elif ready:
            msg = tr("{feature} installed — you can use it now.").format(
                feature=human_name)
            duration = 12000
        else:
            msg = tr("{feature} installed — restart star to use it.").format(
                feature=human_name)
            duration = 15000
        self.statusBar().showMessage(msg, duration)
        announce(self.editor, msg)

    def _qt_transcribe_file(self) -> None:
        """Transcribe an audio file with Whisper and open it as a document."""
        if not self._qt_require_optional_feature("transcribe", tr("Speech recognition")):
            return
        # Whisper decodes audio through ffmpeg; without it the failure is a
        # baffling "[WinError 2] The system cannot find the file specified"
        # AFTER the model loads.  Pre-check like the M4B exporter does.
        from ..audiobook import find_ffmpeg

        if not find_ffmpeg():
            QMessageBox.warning(
                self,
                "Transcribe Audio",
                "Transcription needs ffmpeg to decode the audio file.\n\n"
                "Install ffmpeg and make sure it is on your PATH, then try again.",
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
        announce(self.editor, tr("Transcribing — this may take a while"))

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
            # Say what failed, not just the naked exception text.
            self._status_error(f"Transcription failed: {src[7:]}")
            return
        if not text:
            msg = tr("Transcription produced no text")
            self.statusBar().showMessage(msg)
            announce(self.editor, msg)
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
        announce(
            self.editor,
            tr("Transcript of {name} is open — press Space to read it").format(
                name=name),
        )

    def _qt_dictate_note(self) -> None:
        """Record a voice memo — until the user says stop — and add it as a note.

        No "how many seconds?" guess up front: a live recording dialog shows an
        elapsed timer and a Stop button (Enter), plus Cancel (Esc) to discard.
        The mic is captured through a non-blocking stream so the dialog stays
        responsive; on Stop the audio is transcribed (Whisper) on a background
        thread and attached as a note at the reading position, exactly as
        before.
        """
        if not self.doc:
            self.statusBar().showMessage("Open a document before dictating a note")
            return
        if not self._qt_require_optional_feature("transcribe", tr("Voice dictation")):
            return
        # Pause the reading voice BEFORE the mic opens: star's natural flow is
        # "hear something important → dictate", and on a laptop the mic sits
        # next to the speakers — Whisper would transcribe star's own voice
        # into the note.  This mirrors the pause half of _tts_toggle (word
        # saved, position stored), so Space resumes exactly where the reading
        # stopped once the note is done.
        if self.tts_manager.speaking:
            saved = self.tts_manager.current_word_idx
            self._tts_stop(announce_state=False)
            if saved >= 0:
                self._tts_paused_at_word = saved
            msg = tr("Reading paused while you dictate")
            self.statusBar().showMessage(msg)
            announce(self.editor, msg)
        try:
            recorder = StreamRecorder()
            recorder.start()
        except Exception as exc:  # noqa: BLE001 — no mic / no sounddevice
            self._status_error(f"Could not start recording: {exc}")
            return

        char_pos, anchor = self._qt_current_anchor()
        # Capture the target document NOW: Whisper runs for many seconds and
        # the user may open another document meanwhile — the note must land on
        # the one it was dictated on, at the position it was dictated at.
        annot_key = self._annot_key()
        word_idx = self._qt_char_to_word(int(char_pos))

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Dictate Note"))
        dlg.setModal(True)
        lay = QVBoxLayout(dlg)
        label = QLabel(tr("🎙  Recording…  0:00"))
        label.setAccessibleName(tr("Recording status"))
        lay.addWidget(label)
        hint = QLabel(tr("Speak now. Press Stop (or Enter) when you're done."))
        lay.addWidget(hint)
        try:  # PyQt6
            _ok_flag = QDialogButtonBox.StandardButton.Ok
            _cancel_flag = QDialogButtonBox.StandardButton.Cancel
        except AttributeError:  # PyQt5
            _ok_flag = QDialogButtonBox.Ok  # type: ignore[attr-defined]
            _cancel_flag = QDialogButtonBox.Cancel  # type: ignore[attr-defined]
        box = QDialogButtonBox(_ok_flag | _cancel_flag)
        stop_btn = box.button(_ok_flag)
        if stop_btn is not None:
            stop_btn.setText(tr("Stop && Transcribe"))
            stop_btn.setDefault(True)
        box.accepted.connect(dlg.accept)
        box.rejected.connect(dlg.reject)
        lay.addWidget(box)

        # Live elapsed timer, driven on the GUI thread (recording itself runs
        # on the sounddevice callback thread, so this only paints).
        timer = QTimer(dlg)

        def _tick() -> None:
            s = int(recorder.elapsed)
            label.setText(tr("🎙  Recording…  {m}:{s:02d}").format(m=s // 60, s=s % 60))

        timer.timeout.connect(_tick)
        timer.start(200)

        accepted = dlg.exec() if _QT == "PyQt6" else dlg.exec_()
        timer.stop()

        try:
            _ok_val = QDialog.DialogCode.Accepted
        except AttributeError:  # PyQt5
            _ok_val = QDialog.Accepted
        if accepted != _ok_val:
            recorder.cancel()
            msg = tr("Dictation cancelled")
            self.statusBar().showMessage(msg)
            announce(self.editor, msg)
            return

        try:
            samples = recorder.stop_samples()
        except Exception as exc:  # noqa: BLE001
            self._status_error(f"Recording failed: {exc}")
            return
        if samples is None or len(samples) == 0:
            msg = tr("No audio was recorded — check your microphone")
            self.statusBar().showMessage(msg)
            announce(self.editor, msg)
            return

        model = str(self.settings.get("whisper_model", "base"))
        # Whisper takes 5–30+ seconds; without an audible cue a blind user
        # hears nothing between pressing Stop and the note landing.
        msg = tr("Transcribing your note — this takes a moment")
        self.statusBar().showMessage(msg)
        announce(self.editor, msg)

        def _work() -> None:
            # _transcribe_samples feeds the audio to Whisper directly (no WAV,
            # no ffmpeg subprocess → no console-window flash in star.exe).
            try:
                text = _transcribe_samples(samples, model)
                self._dictate_signal.emit(
                    text, str(int(char_pos)), anchor, annot_key, str(int(word_idx))
                )
            except Exception as exc:  # noqa: BLE001
                self._dictate_signal.emit("", "ERROR", str(exc), "", "")

        threading.Thread(target=_work, daemon=True).start()

    def _qt_on_dictated(
        self, text: str, char_pos_s: str, anchor: str,
        key: str = "", word_idx_s: str = "",
    ) -> None:
        """Main-thread handler for a completed dictation → save as a note.

        *key* / *word_idx_s* are captured at record time (empty when an older
        caller omits them → fall back to the open document), so the note is
        stored against the document it was dictated on rather than whichever
        one happens to be open when Whisper finishes.
        """
        if char_pos_s == "ERROR":
            msg = tr("Dictation failed: {error}").format(error=anchor)
            self.statusBar().showMessage(msg)
            announce(self.editor, msg)
            return
        if not text:
            msg = tr("Dictation produced no text — check your microphone")
            self.statusBar().showMessage(msg)
            announce(self.editor, msg)
            return
        key = key or self._annot_key()
        if not key:
            self.statusBar().showMessage("Dictated note lost: its document is gone")
            return
        word_idx = int(word_idx_s) if word_idx_s else self._qt_char_to_word(
            int(char_pos_s or 0))
        items = self._qt_load_annotations(key)
        items.append(
            {
                "char_pos": int(char_pos_s or 0),
                "word_idx": word_idx,
                "anchor": anchor,
                "note": text,
                "tags": ["dictated"],
                "cite": "",
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
        )
        self._qt_store_annotations(items, key)
        # Only refresh/reveal the notes panel when the note belongs to the
        # document that is currently open (the user may have moved on).
        if key == self._annot_key():
            self._qt_build_annotations()
            if not self._annot_dock.isVisible():
                self._annot_dock.setVisible(True)
                self.settings["qt_show_notes"] = True
        self.statusBar().showMessage(f"Dictated note added ({len(text)} chars)")
        announce(self.editor, tr("Dictated note added"))

    # ── Voice typing: dictate directly INTO the document ───────────────────

    def _qt_voice_typing_toggle(self) -> None:
        """Toggle speech-to-text into the document at the cursor (voice typing).

        Unlike Dictate Note — which files a separate annotation — this inserts
        the transcribed words into the document itself, so a student can
        compose by voice.  Toggle on, speak, toggle off to insert what you
        said; repeat to keep going.  Whisper is not a streaming recognizer, so
        the text lands when you toggle off, not word by word.
        """
        if getattr(self, "_qt_vt_busy", False):
            self.statusBar().showMessage("Still transcribing — one moment…")
            self._qt_vt_sync_action()
            return
        if getattr(self, "_qt_vt_active", False):
            self._qt_voice_typing_stop()
        else:
            self._qt_voice_typing_start()

    def _qt_voice_typing_start(self) -> None:
        if not self.doc:
            self.statusBar().showMessage("Open a document before voice typing")
            self._qt_vt_sync_action()
            return
        if not self._qt_require_optional_feature("transcribe", tr("Voice typing")):
            self._qt_vt_sync_action()
            return
        # Insertion needs an editable document; enter edit mode if necessary and
        # park the cursor at the end so dictation appends (common for composing).
        if not getattr(self, "_qt_edit_mode", False):
            self._qt_enter_edit_mode()
            cur = self.editor.textCursor()
            cur.setPosition(len(self.editor.toPlainText()))
            self.editor.setTextCursor(cur)
        # Pause the reading voice so the mic doesn't capture star speaking.
        if self.tts_manager.speaking:
            self._tts_stop(announce_state=False)
        try:
            self._qt_vt_recorder = StreamRecorder()
            self._qt_vt_recorder.start()
        except Exception as exc:  # noqa: BLE001 — no mic / no sounddevice
            self._status_error(f"Could not start voice typing: {exc}")
            self._qt_vt_recorder = None
            self._qt_vt_sync_action()
            return
        self._qt_vt_active = True
        # Live elapsed indicator on the GUI thread (recording runs on the
        # sounddevice callback thread; this only repaints the status line).
        self._qt_vt_timer = QTimer(self)
        self._qt_vt_timer.timeout.connect(self._qt_vt_tick)
        self._qt_vt_timer.start(250)
        self._qt_vt_sync_action()
        msg = tr("Voice typing on — speak, then toggle off to insert")
        self.statusBar().showMessage(msg)
        announce(self.editor, msg)

    def _qt_vt_tick(self) -> None:
        rec = getattr(self, "_qt_vt_recorder", None)
        if rec is None:
            return
        s = int(rec.elapsed)
        self.statusBar().showMessage(
            tr("🎙  Voice typing…  {m}:{s:02d}  ·  toggle off to insert").format(
                m=s // 60, s=s % 60)
        )

    def _qt_voice_typing_stop(self) -> None:
        self._qt_vt_active = False
        timer = getattr(self, "_qt_vt_timer", None)
        if timer is not None:
            timer.stop()
            self._qt_vt_timer = None
        rec = getattr(self, "_qt_vt_recorder", None)
        self._qt_vt_recorder = None
        self._qt_vt_sync_action()
        if rec is None:
            return
        try:
            samples = rec.stop_samples()
        except Exception as exc:  # noqa: BLE001
            self._status_error(f"Voice typing failed: {exc}")
            return
        if samples is None or len(samples) == 0:
            msg = tr("No audio was recorded — check your microphone")
            self.statusBar().showMessage(msg)
            announce(self.editor, msg)
            return
        model = str(self.settings.get("whisper_model", "base"))
        self._qt_vt_busy = True
        msg = tr("Transcribing your speech…")
        self.statusBar().showMessage(msg)
        announce(self.editor, msg)

        def _work() -> None:
            try:
                text = _transcribe_samples(samples, model)
                self._voice_type_signal.emit(text, "")
            except Exception as exc:  # noqa: BLE001
                self._voice_type_signal.emit("", str(exc))

        threading.Thread(target=_work, daemon=True).start()

    def _qt_on_voice_typed(self, text: str, error: str) -> None:
        """Main-thread handler: insert the recognized speech at the cursor."""
        self._qt_vt_busy = False
        if error:
            msg = tr("Voice typing failed: {error}").format(error=error)
            self.statusBar().showMessage(msg)
            announce(self.editor, msg)
            return
        text = (text or "").strip()
        if not text:
            msg = tr("No speech was recognized")
            self.statusBar().showMessage(msg)
            announce(self.editor, msg)
            return
        cursor = self.editor.textCursor()
        # Smart spacing: keep a gap from preceding non-space text, and leave a
        # trailing space so the next dictation doesn't run words together.
        pos = cursor.position()
        prev = self.editor.toPlainText()[max(0, pos - 1):pos]
        prefix = "" if (pos == 0 or prev in (" ", "\n", "\t")) else " "
        cursor.insertText(prefix + text + " ")
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()
        msg = tr("Inserted {n} characters").format(n=len(text))
        self.statusBar().showMessage(msg)
        announce(self.editor, msg)

    def _qt_vt_sync_action(self) -> None:
        """Reflect the on/off state in the checkable menu item."""
        act = getattr(self, "_qt_vt_action", None)
        if act is not None:
            try:
                act.setChecked(bool(getattr(self, "_qt_vt_active", False)))
            except Exception:  # noqa: BLE001
                pass

