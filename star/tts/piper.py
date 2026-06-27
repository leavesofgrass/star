"""PiperBackend (neural, offline)."""
from .._runtime import *  # noqa: F401,F403
from .base import TTSBackend
from .audio import _apply_wav_adjustments
from .coqui import CoquiBackend  # PiperBackend reuses CoquiBackend._player_cmd


def _piper_voice_dirs() -> List[Path]:
    """Directories that may hold Piper ``*.onnx`` voice models."""
    dirs: List[Path] = []
    env = os.environ.get("PIPER_VOICE_DIR", "")
    if env:
        dirs.append(Path(env))
    dirs.append(_CFG_ROOT / "piper")
    dirs.append(Path.home() / ".local" / "share" / "piper")
    if sys.platform == "win32":
        dirs.append(Path(os.environ.get("APPDATA", Path.home())) / "piper")
    return dirs


class PiperBackend(TTSBackend):
    """Piper neural TTS backend (local, offline, free).

    `Piper <https://github.com/rhasspy/piper>`_ produces natural neural-quality
    speech entirely offline with no subscription or network dependency, which
    makes it an excellent fit for STAR's accessibility mission.  It ships as a
    standalone ``piper`` binary (no Python package required) that reads text on
    stdin and writes a WAV file.

    Setup
    -----
    1. Install the ``piper`` binary so it is on your ``PATH``
       (https://github.com/rhasspy/piper/releases).
    2. Download a voice model — a ``.onnx`` file plus its ``.onnx.json``
       config (https://huggingface.co/rhasspy/piper-voices).
    3. Point STAR at the model, either by setting ``piper_model`` in
       ``settings.json``, exporting ``PIPER_MODEL``, or dropping the files in
       one of the Piper voice directories (e.g. ``<config>/piper``) and
       selecting the backend with ``M-x tts-backend piper``.

    Voice selection
    ---------------
    A "voice" is a model path; ``set_voice`` accepts the path to any ``.onnx``
    model.  ``list_voices`` scans the known voice directories so the GUI/TUI
    pickers show installed models by name.
    """

    name = "piper"
    priority = 100  # opt-in only (needs a downloaded voice model); never auto-selected

    def __init__(self, rate: int = 265, volume: float = 1.0, voice: str = "") -> None:
        self._rate = rate
        self._volume = volume
        self._bin = _PIPER_BIN
        self._model = self._resolve_model(voice)
        self._speaking = False
        self._stop_flag = threading.Event()
        self._play_proc: Optional[subprocess.Popen] = None

    # ── model resolution ──────────────────────────────────────────────────────

    @staticmethod
    def _resolve_model(voice: str = "") -> str:
        """Return a usable ``.onnx`` model path, or "" if none can be found.

        *voice* is the caller-supplied model path (the ``piper_model`` setting,
        or a ``tts_voice`` that points at a ``.onnx`` file).  ``PIPER_MODEL``
        and the known voice directories are tried as fallbacks.
        """
        candidates: List[str] = []
        if voice:
            candidates.append(voice)
        env_model = os.environ.get("PIPER_MODEL", "")
        if env_model:
            candidates.append(env_model)
        for c in candidates:
            if c and c.lower().endswith(".onnx") and Path(c).is_file():
                return c
        # Fall back to the first model found in a known voice directory.
        for d in _piper_voice_dirs():
            try:
                found = sorted(d.glob("*.onnx"))
            except OSError:
                found = []
            if found:
                return str(found[0])
        return ""

    def _config_for(self, model: str) -> Optional[str]:
        """Return the sidecar ``.onnx.json`` config path if it exists."""
        cfg = Path(model + ".json")
        return str(cfg) if cfg.is_file() else None

    def _length_scale(self) -> float:
        """Map words-per-minute to a Piper length scale (>1 = slower)."""
        return max(0.4, min(2.5, 265.0 / max(1, self._rate)))

    def _synth(self, text: str, out_wav: str) -> None:
        """Run piper to synthesize *text* into *out_wav* (blocking).

        Tries with a ``--length_scale`` rate argument first; if the installed
        piper build rejects that flag the synthesis is retried without it so
        speech still works (just at the model's default rate).
        """
        if not self._bin or not self._model:
            raise RuntimeError("Piper binary or voice model not available")
        base = [self._bin, "--model", self._model, "--output_file", out_wav]
        cfg = self._config_for(self._model)
        if cfg:
            base += ["--config", cfg]
        attempts = [
            base + ["--length_scale", f"{self._length_scale():.3f}"],
            base,
        ]
        last_err = ""
        for cmd in attempts:
            try:
                proc = subprocess.run(
                    cmd,
                    input=text.encode("utf-8", errors="replace"),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
            except Exception as exc:  # binary vanished mid-run, etc.
                last_err = str(exc)
                continue
            if proc.returncode == 0 and Path(out_wav).is_file():
                if self._volume != 1.0:
                    try:
                        _apply_wav_adjustments(out_wav, self._volume)
                    except Exception:
                        pass
                return
            last_err = proc.stderr.decode(errors="replace") if proc.stderr else ""
        raise RuntimeError(f"piper synthesis failed: {last_err.strip()[:200]}")

    # ── TTSBackend interface ────────────────────────────────────────────────

    def available(self) -> bool:
        return bool(self._bin) and bool(self._model)

    def speak(
        self,
        text: str,
        on_word: Optional[Callable[[int, int], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        self.stop()
        if not self.available():
            if on_done:
                on_done()
            return
        self._speaking = True
        self._stop_flag.clear()

        def _run() -> None:
            tmp_path = ""
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = tmp.name
                if self._stop_flag.is_set():
                    return
                self._synth(text, tmp_path)
                cmd = CoquiBackend._player_cmd(tmp_path)
                if cmd and not self._stop_flag.is_set():
                    self._play_proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
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
        """voice_id is the path to a Piper ``.onnx`` model."""
        if voice_id and voice_id.lower().endswith(".onnx") and Path(voice_id).is_file():
            self._model = voice_id

    def list_voices(self) -> List[Dict[str, str]]:
        voices: List[Dict[str, str]] = []
        seen: set = set()
        # The currently-selected model first.
        if self._model and self._model not in seen:
            seen.add(self._model)
            voices.append(
                {"id": self._model, "name": Path(self._model).stem, "lang": ""}
            )
        for d in _piper_voice_dirs():
            try:
                models = sorted(d.glob("*.onnx"))
            except OSError:
                models = []
            for m in models:
                sid = str(m)
                if sid in seen:
                    continue
                seen.add(sid)
                voices.append({"id": sid, "name": m.stem, "lang": ""})
        return voices

    def export_to_wav(self, text: str, wav_path: str) -> None:
        """Synthesize *text* to *wav_path* using Piper."""
        self._synth(text, wav_path)

    @property
    def speaking(self) -> bool:
        return self._speaking
