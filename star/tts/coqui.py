"""CoquiBackend (neural TTS)."""
from .._runtime import *  # noqa: F401,F403
from .base import TTSBackend
from .audio import _apply_wav_adjustments


class CoquiBackend(TTSBackend):
    """Coqui TTS neural speech backend.

    Uses the ``TTS`` Python library (``pip install TTS``) to synthesize
    high-quality neural speech locally.  A suitable model is downloaded on
    first use (typically 100–400 MB) and cached under
    ``~/.local/share/tts/`` (Linux/macOS) or ``%APPDATA%\\TTS\\`` (Windows).
    A GPU is used automatically when ``torch.cuda`` is available, otherwise
    inference runs on CPU (may be slow on older machines).

    Voice selection
    ---------------
    Set ``tts_voice`` to a full Coqui model name to override the default::

        M-x tts-voice tts_models/en/vctk/vits

    Run ``star --list-voices`` after switching to the ``coqui`` backend to
    list all models available from the TTS model zoo.

    Rate control
    ------------
    Speed scaling is applied for models that accept a ``speed`` argument
    (e.g. VITS).  For other models the playback audio is resampled after
    synthesis if ``scipy`` is available; otherwise the rate setting is
    silently ignored.

    Install::

        pip install TTS        # neural TTS model + Python bindings
        pip install scipy      # optional: enables playback-speed control
    """

    name = "coqui"
    priority = 110  # opt-in only (slow model download); never auto-selected
    _DEFAULT_MODEL = "tts_models/en/ljspeech/tacotron2-DDC"

    def __init__(self, rate: int = 265, volume: float = 1.0, voice: str = "") -> None:
        self._rate = rate
        self._volume = volume
        self._model_name = voice or self._DEFAULT_MODEL
        self._tts_obj = None  # lazily initialized Coqui TTS instance (see _load_coqui)
        self._speaking = False
        self._stop_flag = threading.Event()
        self._play_proc: Optional[subprocess.Popen] = None

    def available(self) -> bool:
        return _COQUI

    # ── internal helpers ──────────────────────────────────────────────────────

    def _init(self) -> None:
        """Initialize (and possibly download) the TTS model.  Blocking."""
        if self._tts_obj is not None:
            return
        try:
            import torch  # type: ignore[import]

            gpu = torch.cuda.is_available()
        except ImportError:
            gpu = False
        self._tts_obj = _load_coqui()(
            model_name=self._model_name,
            progress_bar=False,
            gpu=gpu,
        )

    @staticmethod
    def _player_cmd(wav_path: str) -> Optional[List[str]]:
        """Return a platform-appropriate command to play a WAV file."""
        if sys.platform == "win32":
            return [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(New-Object System.Media.SoundPlayer '{wav_path}').PlaySync()",
            ]
        if sys.platform == "darwin":
            return ["afplay", wav_path]
        # Linux: try common players in preference order
        for player in ("aplay", "paplay", "play", "ffplay"):
            if shutil.which(player):
                if player == "ffplay":
                    return ["ffplay", "-nodisp", "-autoexit", wav_path]
                return [player, wav_path]
        return None

    # ── TTSBackend interface ────────────────────────────────────────────────

    def speak(
        self,
        text: str,
        on_word: Optional[Callable[[int, int], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        self.stop()
        if not _COQUI:
            if on_done:
                on_done()
            return
        self._speaking = True
        self._stop_flag.clear()
        rate = self._rate
        volume = self._volume

        def _run() -> None:
            import tempfile

            tmp_path = ""
            try:
                # Lazy model initialization (downloads on first use).
                if self._stop_flag.is_set():
                    return
                self._init()
                if self._stop_flag.is_set():
                    return

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = tmp.name

                # Speed: VITS and some other models accept a speed kwarg.
                try:
                    speed = 265.0 / max(1, rate)
                    self._tts_obj.tts_to_file(
                        text=text, file_path=tmp_path, speed=speed
                    )
                except TypeError:
                    # Model does not support speed — fall back to plain call.
                    self._tts_obj.tts_to_file(text=text, file_path=tmp_path)

                if self._stop_flag.is_set():
                    return

                # Optional volume scaling + pitch-neutral speed via scipy.
                if rate != 265 or volume != 1.0:
                    try:
                        _apply_wav_adjustments(tmp_path, volume)
                    except Exception:
                        pass  # adjustments are best-effort

                # Play the WAV file.
                cmd = self._player_cmd(tmp_path)
                if cmd and not self._stop_flag.is_set():
                    self._play_proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, creationflags=_SUBPROCESS_FLAGS)
                    self._play_proc.wait()
            except Exception:
                pass
            finally:
                self._speaking = False
                self._play_proc = None
                if tmp_path:
                    try:
                        Path(tmp_path).unlink(missing_ok=True)
                    except Exception:
                        pass
                if on_done and not self._stop_flag.is_set():
                    on_done()

        threading.Thread(target=_run, daemon=True).start()

    def stop(self) -> None:
        self._stop_flag.set()
        proc = self._play_proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
        self._speaking = False

    def set_rate(self, wpm: int) -> None:
        self._rate = wpm

    def set_volume(self, vol: float) -> None:
        self._volume = max(0.0, min(1.0, vol))

    def set_voice(self, voice_id: str) -> None:
        """voice_id is a full Coqui model name, e.g.
        ``tts_models/en/vctk/vits``.  Changing the model resets the
        cached TTS instance so the new model will be loaded on next speak."""
        if voice_id and voice_id != self._model_name:
            self._model_name = voice_id
            self._tts_obj = None  # force re-init

    def list_voices(self) -> List[Dict[str, str]]:
        """Return English-language models from the Coqui model zoo."""
        if not _COQUI:
            return []
        try:
            all_models = _load_coqui()().list_models().list_tts_models()
            return [
                {
                    "id": m,
                    "name": m.split("/")[-1].replace("_", " "),
                    "lang": m.split("/")[1] if m.count("/") >= 2 else "?",
                }
                for m in all_models
            ]
        except Exception:
            # Fallback: return just the default model so list_voices never
            # crashes.
            return [
                {
                    "id": self._DEFAULT_MODEL,
                    "name": "LJSpeech Tacotron2 (default)",
                    "lang": "en",
                }
            ]

    def export_to_wav(self, text: str, wav_path: str) -> None:
        """Synthesize *text* to *wav_path* using Coqui TTS."""
        if not _COQUI:
            raise RuntimeError("Coqui TTS is not available (pip install TTS)")
        self._init()
        try:
            speed = 265.0 / max(1, self._rate)
            self._tts_obj.tts_to_file(text=text, file_path=wav_path, speed=speed)
        except TypeError:
            # Model does not accept a speed kwarg.
            self._tts_obj.tts_to_file(text=text, file_path=wav_path)
        if self._volume != 1.0:
            _apply_wav_adjustments(wav_path, self._volume)

    @property
    def speaking(self) -> bool:
        return self._speaking
