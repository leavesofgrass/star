"""Text-to-speech backends and the TTS manager."""
import abc

from ._runtime import *  # noqa: F401,F403
from .settings import Settings


# =============================================================================
# TTS system
# =============================================================================


class TTSBackend(abc.ABC):
    """Abstract base for all TTS engines.

    Subclasses **must** implement :meth:`available`, :meth:`speak`, and
    :meth:`stop`.  All other methods have safe no-op defaults; backends only
    override what they support.
    """

    #: Short identifier used in config and entry-points (e.g. ``"piper"``).
    #: Must match the key used in ``[project.entry-points."star.backends"]``.
    name: str = "base"

    #: Auto-selection order; lower = tried first.
    #: Built-ins use multiples of 10 (10, 20, …, 90).
    #: Third-party plugins should use values ≥ 100.
    priority: int = 50

    @abc.abstractmethod
    def available(self) -> bool:
        return False

    @abc.abstractmethod
    def speak(
        self,
        text: str,
        on_word: Optional[Callable[[int, int], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        if on_done:
            on_done()

    @abc.abstractmethod
    def stop(self) -> None:
        pass

    def set_rate(self, wpm: int) -> None:
        pass

    def set_volume(self, vol: float) -> None:
        pass

    def set_voice(self, voice_id: str) -> None:
        pass

    def list_voices(self) -> List[Dict[str, str]]:
        return []

    def export_to_wav(self, text: str, wav_path: str) -> None:
        """Synthesize *text* and write the result to *wav_path* (WAV format).

        This call is **blocking**.  Raises ``RuntimeError`` if the backend
        does not support audio file export or is unavailable.
        """
        raise RuntimeError(f"Backend '{self.name}' does not support audio file export.")

    @property
    def speaking(self) -> bool:
        return False


class FestivalBackend(TTSBackend):
    """Festival speech synthesis backend (Linux / macOS).

    Drives the Festival engine via its interactive scheme interpreter so
    reading rate and voice can be controlled without additional dependencies.
    Festival binary (``festival``) must be on PATH.

    Install:
        Debian/Ubuntu:  ``sudo apt install festival``
        Fedora/RHEL:    ``sudo dnf install festival``
        macOS (Homebrew): ``brew install festival``
    """

    name = "festival"
    priority = 60

    def __init__(self, rate: int = 265, volume: float = 1.0, voice: str = "") -> None:
        self._rate = rate
        self._volume = volume
        self._voice = voice
        self._proc: Optional[subprocess.Popen] = None
        self._speaking = False
        self._bin = shutil.which("festival")

    def available(self) -> bool:
        return self._bin is not None

    def speak(
        self,
        text: str,
        on_word: Optional[Callable[[int, int], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        self.stop()
        if not self._bin:
            if on_done:
                on_done()
            return
        self._speaking = True

        # Duration_Stretch < 1 = faster, > 1 = slower;
        # 265 wpm maps to stretch 1.0, linearly scaled.
        stretch = max(0.2, min(4.0, 265.0 / max(1, self._rate)))
        # Escape double quotes in text for the Scheme SayText call.
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')

        scheme_parts: List[str] = []
        if self._voice:
            scheme_parts.append(f"({self._voice})")  # e.g. (voice_rab_diphone)
        scheme_parts.append(f"(Parameter.set 'Duration_Stretch {stretch:.3f})")
        scheme_parts.append(f'(SayText "{escaped}")')
        scheme_parts.append("(quit)")
        scheme = "\n".join(scheme_parts) + "\n"

        def _run() -> None:
            try:
                self._proc = subprocess.Popen(
                    [self._bin],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if self._proc.stdin:
                    self._proc.stdin.write(scheme.encode("utf-8", errors="replace"))
                    self._proc.stdin.close()
                self._proc.wait()
            except Exception:
                pass
            finally:
                self._speaking = False
                if on_done:
                    on_done()

        threading.Thread(target=_run, daemon=True).start()

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass
        self._speaking = False

    def set_rate(self, wpm: int) -> None:
        self._rate = wpm

    def set_volume(self, vol: float) -> None:
        self._volume = max(0.0, min(1.0, vol))

    def set_voice(self, voice_id: str) -> None:
        """voice_id is a Festival scheme voice name, e.g. 'voice_rab_diphone'."""
        self._voice = voice_id

    def list_voices(self) -> List[Dict[str, str]]:
        """Query Festival for the list of installed voices."""
        if not self._bin:
            return []
        try:
            result = subprocess.run(
                [self._bin],
                input=b"(voice.list)\n(quit)\n",
                capture_output=True,
                timeout=10,
            )
            raw = result.stdout.decode("utf-8", errors="replace")
            # Festival prints something like: (rab_diphone en1_mbrola_3 ...)
            m = re.search(r"\(([^)]+)\)", raw)
            if m:
                return [
                    {"id": v.strip(), "name": v.strip(), "lang": ""}
                    for v in m.group(1).split()
                    if v.strip()
                ]
        except Exception:
            pass
        return []

    def export_to_wav(self, text: str, wav_path: str) -> None:
        """Synthesize *text* to *wav_path* using Festival.

        Prefers the ``text2wave`` helper (ships with most Festival
        installs); falls back to a Festival Scheme ``utt.save.wave``
        call for shorter texts when ``text2wave`` is not on PATH.
        """
        stretch = max(0.2, min(4.0, 265.0 / max(1, self._rate)))
        t2w = shutil.which("text2wave")
        if t2w:
            proc = subprocess.Popen(
                [
                    t2w,
                    "-o",
                    wav_path,
                    "-eval",
                    f"(Parameter.set 'Duration_Stretch {stretch:.3f})",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if proc.stdin:
                proc.stdin.write(text.encode("utf-8", errors="replace"))
                proc.stdin.close()
            proc.wait()
            return
        if not self._bin:
            raise RuntimeError("Festival is not available")
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        voice_cmd = f"({self._voice})\n" if self._voice else ""
        scheme = (
            f"{voice_cmd}"
            f"(Parameter.set 'Duration_Stretch {stretch:.3f})\n"
            f'(utt.save.wave (utt.synth (Utterance Text "{escaped}")) "{wav_path}")\n'
            "(quit)\n"
        )
        proc = subprocess.Popen(
            [self._bin],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if proc.stdin:
            proc.stdin.write(scheme.encode("utf-8", errors="replace"))
            proc.stdin.close()
        proc.wait()

    @property
    def speaking(self) -> bool:
        return self._speaking


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


def _apply_wav_adjustments(path: str, volume: float) -> None:
    """Scale WAV sample amplitudes by *volume* in-place.  Pure stdlib."""
    import struct
    import wave

    with wave.open(path, "rb") as wf:
        params = wf.getparams()
        frames = wf.readframes(params.nframes)

    sampwidth = params.sampwidth
    if sampwidth == 2:  # 16-bit PCM (most common)
        fmt = f"<{len(frames) // 2}h"
        samples = list(struct.unpack(fmt, frames))
        samples = [max(-32768, min(32767, int(s * volume))) for s in samples]
        frames = struct.pack(fmt, *samples)
        with wave.open(path, "wb") as wf:
            wf.setparams(params)
            wf.writeframes(frames)


def _convert_audio_format(src_wav: str, dest_path: str) -> None:
    """Convert *src_wav* (WAV) to the format implied by *dest_path*'s extension.

    Supported output formats: ``.mp3``, ``.ogg``, ``.mp4``, ``.wav``.

    Conversion priority:

    1. **ffmpeg** — recommended; handles all formats cleanly.
       Install: https://ffmpeg.org/download.html
    2. **pydub** — pure-Python fallback (``pip install pydub``).
    3. **WAV copy** — if the extension is ``.wav`` no conversion is needed.

    Raises ``RuntimeError`` when the target format requires conversion but
    no suitable tool is available.
    """
    ext = Path(dest_path).suffix.lower()
    if ext == ".wav":
        shutil.copy2(src_wav, dest_path)
        return

    # --- ffmpeg -----------------------------------------------------------
    # Prefer the bundled ffmpeg (self-contained build); fall back to a
    # system install on PATH.
    _ffmpeg = (
        str(_FFMPEG_BUNDLED) if _FFMPEG_BUNDLED.is_file() else shutil.which("ffmpeg")
    )
    if _ffmpeg:
        cmd: List[str] = [_ffmpeg, "-y", "-i", src_wav]
        if ext == ".mp3":
            cmd += ["-codec:a", "libmp3lame", "-qscale:a", "2"]
        elif ext == ".ogg":
            cmd += ["-codec:a", "libvorbis", "-q:a", "4"]
        elif ext == ".mp4":
            # Audio-only MP4 (AAC inside an MPEG-4 container).
            cmd += ["-codec:a", "aac", "-b:a", "192k", "-vn"]
        # For other extensions let ffmpeg infer the codec from the name.
        cmd.append(dest_path)
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0:
            return
        raise RuntimeError(
            f"ffmpeg conversion failed:\n{result.stderr.decode(errors='replace')}"
        )

    # --- pydub ------------------------------------------------------------
    try:
        from pydub import AudioSegment as _AS  # type: ignore[import]

        audio = _AS.from_wav(src_wav)
        fmt_map = {".mp3": "mp3", ".ogg": "ogg", ".mp4": "mp4"}
        fmt = fmt_map.get(ext, ext.lstrip("."))
        audio.export(dest_path, format=fmt)
        return
    except ImportError:
        pass

    raise RuntimeError(
        f"Cannot convert WAV to {ext!r}.\n"
        "Install ffmpeg (https://ffmpeg.org/download.html) "
        "or run: pip install pydub"
    )


# =============================================================================
# Timestamped subtitle export
# =============================================================================
#
# When STAR exports a document as audio it can also emit a synchronized
# SRT or WebVTT caption track so the highlight "travels" with the audio into
# any media player.  TTS file export gives us no per-word callbacks, so the
# timing is *estimated*: the total audio duration (read from the synthesized
# WAV) is distributed across the spoken tokens in proportion to their length.
# This is accurate enough for review/captioning and needs no external tools.


def _wav_duration_seconds(path: str) -> float:
    """Return the duration of a WAV file in seconds (0.0 on any error)."""
    import wave

    try:
        with wave.open(path, "rb") as wf:
            rate = wf.getframerate()
            frames = wf.getnframes()
            return frames / float(rate) if rate else 0.0
    except Exception:
        return 0.0


def _fmt_subtitle_time(seconds: float, vtt: bool = False) -> str:
    """Format *seconds* as an SRT (``HH:MM:SS,mmm``) or VTT (``HH:MM:SS.mmm``)
    timestamp."""
    seconds = max(0.0, seconds)
    ms = int(round(seconds * 1000))
    hh, ms = divmod(ms, 3_600_000)
    mm, ms = divmod(ms, 60_000)
    ss, ms = divmod(ms, 1000)
    sep = "." if vtt else ","
    return f"{hh:02d}:{mm:02d}:{ss:02d}{sep}{ms:03d}"


def _build_subtitle_cues(
    text: str,
    duration: float,
    word_level: bool = False,
    max_words: int = 12,
    max_chars: int = 90,
) -> List[Tuple[float, float, str]]:
    """Return ``(start_s, end_s, caption_text)`` cues spanning *duration*.

    Audio duration is apportioned to whitespace-delimited tokens by length
    (characters + 1) so longer words occupy proportionally more time.  In
    sentence mode tokens are grouped into readable caption lines that break at
    sentence boundaries (or when *max_words* / *max_chars* is reached); in
    word mode every token becomes its own cue.
    """
    tokens = [(m.group(), m.start(), m.end()) for m in re.finditer(r"\S+", text)]
    if not tokens or duration <= 0:
        return []

    weights = [len(tok) + 1 for tok, _s, _e in tokens]
    total_w = float(sum(weights)) or 1.0
    # Per-token start/end times from the cumulative weight fraction.
    spans: List[Tuple[float, float]] = []
    acc = 0
    for w in weights:
        start = duration * acc / total_w
        acc += w
        spans.append((start, duration * acc / total_w))

    if word_level:
        return [(spans[i][0], spans[i][1], tokens[i][0]) for i in range(len(tokens))]

    # Character offsets at which a new sentence begins.
    boundaries = {m.end() for m in _SENTENCE_SPLIT_RE.finditer(text)}

    cues: List[Tuple[float, float, str]] = []
    cur_words: List[str] = []
    cur_start = spans[0][0]
    cur_chars = 0
    for i, (tok, s_char, _e_char) in enumerate(tokens):
        starts_sentence = s_char in boundaries
        too_long = cur_words and (
            len(cur_words) >= max_words or cur_chars + len(tok) + 1 > max_chars
        )
        if cur_words and (starts_sentence or too_long):
            cues.append((cur_start, spans[i - 1][1], " ".join(cur_words)))
            cur_words = []
            cur_start = spans[i][0]
            cur_chars = 0
        cur_words.append(tok)
        cur_chars += len(tok) + 1
    if cur_words:
        cues.append((cur_start, spans[-1][1], " ".join(cur_words)))
    return cues


def _format_subtitles(cues: List[Tuple[float, float, str]], fmt: str = "srt") -> str:
    """Render *cues* as SRT or WebVTT text."""
    vtt = fmt.lower() == "vtt"
    out: List[str] = []
    if vtt:
        out.append("WEBVTT")
        out.append("")
    for i, (start, end, caption) in enumerate(cues, 1):
        # SRT requires end > start; nudge zero-length cues so players accept them.
        if end <= start:
            end = start + 0.05
        if not vtt:
            out.append(str(i))
        out.append(
            f"{_fmt_subtitle_time(start, vtt)} --> {_fmt_subtitle_time(end, vtt)}"
        )
        out.append(caption)
        out.append("")
    return "\n".join(out).strip() + "\n"


def _generate_subtitles(
    text: str, wav_path: str, fmt: str = "srt", word_level: bool = False
) -> str:
    """Build an SRT/VTT subtitle document for *text* synchronized to the audio
    in *wav_path*.  Returns "" when timing cannot be estimated."""
    duration = _wav_duration_seconds(wav_path)
    cues = _build_subtitle_cues(text, duration, word_level=word_level)
    if not cues:
        return ""
    return _format_subtitles(cues, fmt)


class SilentBackend(TTSBackend):
    """No-op backend when no TTS engine is available."""

    name = "silent"
    priority = 90  # last resort; only auto-selected when nothing else is available

    def available(self) -> bool:
        return True

    def speak(
        self,
        text: str,
        on_word: Optional[Callable[[int, int], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        if on_done:
            on_done()

    def stop(self) -> None:
        pass


class Pyttsx3Backend(TTSBackend):
    """pyttsx3 backend — uses SAPI5 (Windows), NSSpeechSynthesizer (macOS),
    or eSpeak-NG (Linux) via the pyttsx3 wrapper.

    Windows/SAPI5 note: calling engine.stop() corrupts the engine's internal
    state so that subsequent say() + runAndWait() calls are silently dropped.
    The fix is to create a *fresh* pyttsx3.init() engine inside every speech
    thread — each call is entirely self-contained.  The active engine is
    stored in self._active_engine so stop() can interrupt it at any time.
    """

    name = "pyttsx3"
    priority = 20

    def __init__(self, rate: int = 265, volume: float = 1.0, voice: str = ""):
        self._rate = rate
        self._volume = volume
        self._voice = voice
        self._thread: Optional[threading.Thread] = None
        self._speaking = False
        self._stop_requested = False
        # Monotonically-increasing counter incremented on every speak() call.
        # Each _run closure captures the value at launch time; only the thread
        # whose generation matches the current counter is allowed to write
        # _speaking=False.  This prevents an old thread's finally-block from
        # overwriting the True set by a newer speak() call (Windows race).
        self._gen: int = 0
        # Reference to the engine currently being used by the speech thread.
        # Stored so stop() can call engine.stop() on the right object.
        self._active_engine = None
        self._available = self._probe()

    def _probe(self) -> bool:
        """Check once at startup that pyttsx3 can create an engine."""
        if not _PYTTSX3:
            return False
        try:
            eng = _load_pyttsx3().Engine()
            eng.stop()
            return True
        except Exception:
            return False

    def _make_engine(self):
        """Create and configure a brand-new pyttsx3 engine.

        We call ``pyttsx3.Engine()`` directly instead of ``pyttsx3.init()``.
        ``init()`` caches the engine in a WeakValueDictionary and returns the
        same object on every call as long as any thread still holds a strong
        reference to it.  After a ``stop()``-while-speaking the cached engine
        has corrupted SAPI5 internal state and silently drops every subsequent
        ``say()`` + ``runAndWait()`` call on Windows.  ``Engine()`` constructs
        a fresh COM object unconditionally and never touches the cache, so each
        speech session always gets a clean SAPI5 voice.
        """
        eng = _load_pyttsx3().Engine()
        eng.setProperty("rate", self._rate)
        eng.setProperty("volume", self._volume)
        if self._voice:
            try:
                eng.setProperty("voice", self._voice)
            except Exception:
                pass
        return eng

    def available(self) -> bool:
        return self._available

    def speak(
        self,
        text: str,
        on_word: Optional[Callable[[int, int], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        if not self._available:
            if on_done:
                on_done()
            return

        # Signal any running thread to stop, then clear the flag for the new one.
        self._stop_requested = True
        self._speaking = False
        if self._active_engine is not None:
            try:
                self._active_engine.stop()
            except Exception:
                pass
            self._active_engine = None

        self._stop_requested = False
        self._gen += 1
        my_gen = self._gen
        self._speaking = True

        def _run() -> None:
            eng = None
            try:
                eng = self._make_engine()
                self._active_engine = eng  # expose to stop()

                if on_word is not None:
                    # Wrap in a guard so a bad callback never kills the engine.
                    def _word_cb(name: str, location: int, length: int) -> None:
                        try:
                            if not self._stop_requested:
                                on_word(location, length)
                        except Exception:
                            pass

                    eng.connect("started-word", _word_cb)

                eng.say(text)
                if not self._stop_requested:
                    eng.runAndWait()
            except Exception:
                pass
            finally:
                # Do NOT unconditionally clear self._active_engine here.
                # A newer speak() call may have already stored its own engine
                # in self._active_engine; clearing it would prevent stop()
                # from being able to interrupt that newer engine (Bug A:
                # Space stops setting _active_engine to None, so pause breaks).
                # Ownership of _active_engine is managed exclusively by
                # stop() and the top of speak().
                if self._active_engine is eng:
                    # Only clear if it's still *our* engine — no newer thread
                    # has replaced it yet.
                    self._active_engine = None
                # Stop our local engine object (no-op if already stopped).
                if eng is not None:
                    try:
                        eng.stop()
                    except Exception:
                        pass
                # Only the most-recently launched thread may clear _speaking
                # or fire on_done.  An older thread whose generation no longer
                # matches must not overwrite the True set by a newer speak()
                # call, and must not fire on_done (which would set
                # _current_word_idx=-1 and stop the newer thread's timer,
                # making replay always jump to word 0 — Bug B).
                if self._gen == my_gen:
                    self._speaking = False
                    if on_done is not None and not self._stop_requested:
                        on_done()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_requested = True
        self._speaking = False
        eng = self._active_engine
        if eng is not None:
            try:
                eng.stop()
            except Exception:
                pass
            self._active_engine = None

    def set_rate(self, wpm: int) -> None:
        self._rate = wpm
        eng = self._active_engine
        if eng is not None:
            try:
                eng.setProperty("rate", wpm)
            except Exception:
                pass

    def set_volume(self, vol: float) -> None:
        self._volume = max(0.0, min(1.0, vol))
        eng = self._active_engine
        if eng is not None:
            try:
                eng.setProperty("volume", self._volume)
            except Exception:
                pass

    def set_voice(self, voice_id: str) -> None:
        self._voice = voice_id

    def list_voices(self) -> List[Dict[str, str]]:
        if not self._available:
            return []
        try:
            eng = self._make_engine()
            voices = [
                {"id": v.id, "name": v.name, "lang": getattr(v, "languages", ["?"])[0]}
                for v in eng.getProperty("voices")
            ]
            eng.stop()
            return voices
        except Exception:
            return []

    def export_to_wav(self, text: str, wav_path: str) -> None:
        """Synthesize *text* to *wav_path* using pyttsx3's ``save_to_file``."""
        if not self._available:
            raise RuntimeError("pyttsx3 is not available (pip install pyttsx3)")
        eng = self._make_engine()
        try:
            eng.save_to_file(text, wav_path)
            eng.runAndWait()
        finally:
            try:
                eng.stop()
            except Exception:
                pass

    @property
    def speaking(self) -> bool:
        return self._speaking


class ESpeakBackend(TTSBackend):
    """eSpeak-NG backend via subprocess.  Provides reliable cross-platform
    speech without the pyttsx3 dependency chain."""

    name = "espeak"
    priority = 50  # CLI fallback — tried after the in-process libespeak-ng backend

    def __init__(self, rate: int = 265, volume: int = 100, voice: str = "en-us"):
        self._rate = int(rate * 0.8)  # eSpeak rate scale ≈ 80% of wpm
        self._volume = volume
        self._voice = voice
        self._proc: Optional[subprocess.Popen] = None
        self._speaking = False
        self._bin = shutil.which("espeak-ng") or shutil.which("espeak")

    def available(self) -> bool:
        return self._bin is not None

    def speak(
        self,
        text: str,
        on_word: Optional[Callable[[int, int], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        self.stop()
        if not self._bin:
            if on_done:
                on_done()
            return
        self._speaking = True
        # Auto-detect SSML: add the -m flag so eSpeak processes <break> tags.
        already_ssml = text.lstrip().startswith("<speak>")

        # eSpeak word-callback support.
        # Wrap plain text in SSML with <mark name="N"/> tags between each
        # word so eSpeak-NG outputs "MARK N" to stdout as each word is
        # spoken.  We capture stdout and fire on_word(N, word_len) in a
        # reader thread.  Falls back gracefully if eSpeak does not emit
        # marks (the on_word callback simply never fires).
        use_marks = bool(on_word) and not already_ssml
        word_lens: List[int] = []
        if use_marks:
            tokens = re.split(r"(\s+)", text)
            ssml_parts: List[str] = ["<speak>"]
            idx = 0
            for tok in tokens:
                if tok.strip():
                    ssml_parts.append(f'<mark name="{idx}"/>{tok}')
                    word_lens.append(len(tok.strip()))
                    idx += 1
                elif tok:
                    ssml_parts.append(tok)
            ssml_parts.append("</speak>")
            text = "".join(ssml_parts)

        is_ssml = use_marks or already_ssml

        def _run() -> None:
            try:
                cmd = [
                    self._bin,
                    "-v",
                    self._voice,
                    "-s",
                    str(self._rate),
                    "-a",
                    str(self._volume),
                ]
                if is_ssml:
                    cmd.append("-m")  # SSML / markup mode
                cmd.append("--stdin")
                stdout_pipe = subprocess.PIPE if use_marks else subprocess.DEVNULL
                self._proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=stdout_pipe,
                    stderr=subprocess.DEVNULL,
                )
                # Launch mark-reader thread before writing stdin so we don't
                # miss any early marks.
                if use_marks and self._proc.stdout is not None:
                    proc_stdout = self._proc.stdout

                    def _mark_reader() -> None:
                        try:
                            for raw in proc_stdout:
                                line = raw.decode("utf-8", errors="replace").strip()
                                if line.startswith("MARK "):
                                    try:
                                        widx = int(line[5:])
                                        wlen = (
                                            word_lens[widx]
                                            if widx < len(word_lens)
                                            else 1
                                        )
                                        if on_word:
                                            on_word(widx, wlen)
                                    except (ValueError, IndexError):
                                        pass
                        except Exception:
                            pass

                    threading.Thread(target=_mark_reader, daemon=True).start()

                if self._proc.stdin:
                    self._proc.stdin.write(text.encode("utf-8", errors="replace"))
                    self._proc.stdin.close()
                self._proc.wait()
            except Exception:
                pass
            finally:
                self._speaking = False
                if on_done:
                    on_done()

        threading.Thread(target=_run, daemon=True).start()

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass
        self._speaking = False

    def set_rate(self, wpm: int) -> None:
        self._rate = int(wpm * 0.8)

    def set_volume(self, vol: float) -> None:
        self._volume = int(vol * 100)

    def set_voice(self, voice_id: str) -> None:
        self._voice = voice_id

    def list_voices(self) -> List[Dict[str, str]]:
        if not self._bin:
            return []
        try:
            out = subprocess.check_output(
                [self._bin, "--voices"], stderr=subprocess.DEVNULL, text=True
            )
            voices = []
            for line in out.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 4:
                    voices.append({"id": parts[2], "name": parts[3], "lang": parts[1]})
            return voices
        except Exception:
            return []

    def export_to_wav(self, text: str, wav_path: str) -> None:
        """Synthesize *text* to *wav_path* using eSpeak/eSpeak-NG (-w flag)."""
        if not self._bin:
            raise RuntimeError("espeak / espeak-ng is not available")
        cmd = [
            self._bin,
            "-v",
            self._voice,
            "-s",
            str(self._rate),
            "-a",
            str(self._volume),
            "-w",
            wav_path,
            "--stdin",
        ]
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if proc.stdin:
            proc.stdin.write(text.encode("utf-8", errors="replace"))
            proc.stdin.close()
        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"espeak exited with code {proc.returncode}")

    @property
    def speaking(self) -> bool:
        return self._speaking


class ESpeakLibBackend(TTSBackend):
    """eSpeak-NG driven in-process through libespeak-ng (ctypes).

    Unlike :class:`ESpeakBackend`, which shells out to the ``espeak-ng`` CLI,
    this calls the libespeak-ng C API directly.  Its synth callback delivers a
    per-word event for every spoken word, tagged with the word's character
    position in the text *and its audio position* (ms into the output stream).
    Forwarding those events to the highlight makes the reading position follow
    actual playback instead of a free-running words-per-minute estimate — the
    fix for the highlight running ahead of the audio.

    Audio uses ``AUDIO_OUTPUT_PLAYBACK``: libespeak-ng owns playback (exactly as
    the subprocess backend does), and word events fire as audio is produced.
    The library is preferred over the subprocess backend when it is available —
    the vendored ``libespeak-ng.dll`` in the self-contained Windows build, or a
    system ``libespeak-ng`` on Linux/macOS — and falls back to the subprocess
    backend otherwise.
    """

    name = "espeak"
    priority = 40  # in-process libespeak-ng — preferred over the CLI (real word events)

    # speak_lib.h constants.
    _AUDIO_OUTPUT_PLAYBACK = 0
    _CHARS_UTF8 = 1
    _EVENT_WORD = 1
    _PARAM_RATE = 1
    _PARAM_VOLUME = 2

    # libespeak-ng keeps global state, so the library is loaded and initialised
    # exactly once and shared by every instance (class-level singletons).
    _lib = None
    _data_path = None
    _callback_type = None
    _EVENT = None
    _VOICE = None
    _init_tried = False
    _init_lock = threading.Lock()

    def __init__(self, rate: int = 265, volume: int = 100, voice: str = "en-us"):
        self._rate = int(rate)
        self._volume = int(volume)
        self._voice = voice or "en-us"
        self._speaking = False
        # Generation counter: bumped by every speak()/stop() so a callback or
        # worker from a cancelled/superseded utterance can detect it is stale.
        self._gen = 0
        # Live reference to the CFUNCTYPE callback object; it must outlive the
        # synthesis call or ctypes would free it and libespeak-ng would call
        # into freed memory.
        self._cb = None
        # Set on stop()/supersede so the worker loop and any in-flight synth
        # callback bail out promptly (responsive silencing).
        self._stop_evt = threading.Event()
        # Seconds added to each word's audio-position target when pacing the
        # highlight, to compensate for output-device latency.  TTSManager keeps
        # it in sync with the espeak_highlight_offset_ms setting.
        self._hl_offset = 0.12
        self._ensure_library()

    # -- library lifecycle ------------------------------------------------
    @classmethod
    def _ensure_library(cls):
        if cls._init_tried:
            return cls._lib
        with cls._init_lock:
            if cls._init_tried:
                return cls._lib
            cls._init_tried = True
            cls._load_and_init()
        return cls._lib

    @staticmethod
    def _candidate_libs():
        """(library path, data dir) pairs to try, most-specific first."""
        import ctypes.util

        cands = []
        # 1) Vendored DLL (self-contained Windows build): data dir is alongside.
        if _ESPEAK_NG_DLL.is_file():
            cands.append((str(_ESPEAK_NG_DLL), str(_ESPEAK_NG_DIR)))
        # 2) System library (Linux/macOS source installs; uses its own data).
        found = ctypes.util.find_library("espeak-ng") or ctypes.util.find_library(
            "espeak_ng"
        )
        if found:
            cands.append((found, None))
        for n in (
            "libespeak-ng.so.1",
            "libespeak-ng.so",
            "libespeak-ng.1.dylib",
            "libespeak-ng.dylib",
            "libespeak-ng.dll",
        ):
            cands.append((n, None))
        return cands

    @classmethod
    def _load_and_init(cls):
        import ctypes

        class _ID(ctypes.Union):
            _fields_ = [
                ("number", ctypes.c_int),
                ("name", ctypes.c_char_p),
                ("string", ctypes.c_char * 8),
            ]

        class _EVENT(ctypes.Structure):
            _fields_ = [
                ("type", ctypes.c_int),
                ("unique_identifier", ctypes.c_uint),
                ("text_position", ctypes.c_int),  # 1-based char index in the text
                ("length", ctypes.c_int),
                ("audio_position", ctypes.c_int),  # ms into the output stream
                ("sample", ctypes.c_int),
                ("user_data", ctypes.c_void_p),
                ("id", _ID),
            ]

        class _VOICE(ctypes.Structure):
            _fields_ = [
                ("name", ctypes.c_char_p),
                ("languages", ctypes.c_char_p),
                ("identifier", ctypes.c_char_p),
                ("gender", ctypes.c_ubyte),
                ("age", ctypes.c_ubyte),
                ("variant", ctypes.c_ubyte),
                ("xx1", ctypes.c_ubyte),
                ("score", ctypes.c_int),
                ("spare", ctypes.c_void_p),
            ]

        cb_type = ctypes.CFUNCTYPE(
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_short),
            ctypes.c_int,
            ctypes.POINTER(_EVENT),
        )

        for path, data in cls._candidate_libs():
            try:
                lib = ctypes.CDLL(path)
                lib.espeak_Initialize.restype = ctypes.c_int
                lib.espeak_Initialize.argtypes = [
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.c_char_p,
                    ctypes.c_int,
                ]
                lib.espeak_SetSynthCallback.argtypes = [cb_type]
                lib.espeak_SetParameter.argtypes = [
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.c_int,
                ]
                lib.espeak_SetVoiceByName.restype = ctypes.c_int
                lib.espeak_SetVoiceByName.argtypes = [ctypes.c_char_p]
                lib.espeak_Synth.restype = ctypes.c_int
                lib.espeak_Synth.argtypes = [
                    ctypes.c_void_p,
                    ctypes.c_size_t,
                    ctypes.c_uint,
                    ctypes.c_int,
                    ctypes.c_uint,
                    ctypes.c_uint,
                    ctypes.POINTER(ctypes.c_uint),
                    ctypes.c_void_p,
                ]
                lib.espeak_Synchronize.restype = ctypes.c_int
                lib.espeak_Cancel.restype = ctypes.c_int
                lib.espeak_ListVoices.restype = ctypes.POINTER(ctypes.POINTER(_VOICE))
                lib.espeak_ListVoices.argtypes = [ctypes.POINTER(_VOICE)]
                srate = lib.espeak_Initialize(
                    cls._AUDIO_OUTPUT_PLAYBACK,
                    0,
                    data.encode("utf-8") if data else None,
                    0,
                )
                if srate is None or srate < 0:
                    continue
                cls._lib = lib
                cls._data_path = data
                cls._callback_type = cb_type
                cls._EVENT = _EVENT
                cls._VOICE = _VOICE
                return
            except (OSError, AttributeError):
                continue

    def available(self) -> bool:
        return type(self)._lib is not None

    @staticmethod
    def _chunk_offsets(text: str, max_len: int = 400) -> "List[Tuple[str, int]]":
        """Split *text* into ``(chunk, char_offset)`` pairs at sentence
        boundaries, further splitting any over-long sentence at whitespace.

        Speaking one chunk at a time — rather than handing the whole, possibly
        document-length, slice to a single synth call — bounds how much audio is
        ever queued in the engine, so a stop request silences within the
        current chunk instead of after the entire passage.
        """
        segments: List[Tuple[str, int]] = []
        pos = 0
        for m in _SENTENCE_SPLIT_RE.finditer(text):
            seg = text[pos : m.end()]
            if seg:
                segments.append((seg, pos))
            pos = m.end()
        if pos < len(text):
            segments.append((text[pos:], pos))
        out: List[Tuple[str, int]] = []
        for seg, off in segments:
            if not seg.strip():
                continue
            if len(seg) <= max_len:
                out.append((seg, off))
                continue
            i = 0
            while i < len(seg):
                end = min(i + max_len, len(seg))
                if end < len(seg):
                    sp = seg.rfind(" ", i + 1, end)
                    if sp > i:
                        end = sp + 1
                piece = seg[i:end]
                if piece.strip():
                    out.append((piece, off + i))
                i = end
        return out or [(text, 0)]

    # -- speech -----------------------------------------------------------
    def speak(
        self,
        text: str,
        on_word: Optional[Callable[[int, int], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        self.stop()
        lib = type(self)._lib
        if lib is None:
            if on_done:
                on_done()
            return
        self._gen += 1
        my_gen = self._gen
        self._speaking = True
        self._stop_evt.clear()

        try:
            if self._voice:
                lib.espeak_SetVoiceByName(self._voice.encode("utf-8", "replace"))
            lib.espeak_SetParameter(self._PARAM_RATE, max(80, min(450, self._rate)), 0)
            lib.espeak_SetParameter(
                self._PARAM_VOLUME, max(0, min(200, self._volume)), 0
            )
        except Exception:
            pass

        chunks = self._chunk_offsets(text)

        # Highlight pacing.  In PLAYBACK mode libespeak-ng synthesizes a whole
        # chunk's audio in a burst and delivers ALL of that chunk's WORD events
        # nearly at once — well ahead of when each word is actually heard — so
        # firing on_word the instant the event arrives made the highlight race a
        # sentence ahead of the audio.  Each WORD event, however, carries an
        # ``audio_position`` (ms into the chunk's output stream) telling us when
        # the word is heard.  We therefore enqueue every event with a wall-clock
        # target time (chunk playback start + audio_position + a latency offset)
        # and a dedicated pacer thread fires on_word at that time, so the
        # highlight follows actual playback instead of synthesis.
        #
        # (text_position is a 1-based character index into the chunk; adding the
        # chunk's base offset yields an absolute plain-text offset, which
        # TTSManager maps to a word-map index exactly as it does for pyttsx3.
        # It counts characters for the ASCII/Latin text that dominates here;
        # non-ASCII input could need a byte->char correction, tracked as a
        # follow-up.)
        pace_q: "queue.Queue" = queue.Queue()

        def _make_cb(base_offset: int, chunk_start: float):
            def _synth_cb(wav, numsamples, evp):
                if self._gen != my_gen or self._stop_evt.is_set():
                    return 1  # abort this chunk's synthesis
                try:
                    if on_word:
                        i = 0
                        while evp[i].type != 0:  # espeakEVENT_LIST_TERMINATED
                            e = evp[i]
                            if e.type == self._EVENT_WORD:
                                target = (
                                    chunk_start
                                    + e.audio_position / 1000.0
                                    + self._hl_offset
                                )
                                pace_q.put(
                                    (
                                        target,
                                        base_offset + e.text_position - 1,
                                        e.length,
                                        my_gen,
                                    )
                                )
                            i += 1
                except Exception:
                    pass
                return 0

            return _synth_cb

        def _pace() -> None:
            # Fire each queued word highlight at its scheduled playback time.
            # Sleeps are interruptible via _stop_evt for prompt silencing, and
            # any item from a superseded utterance (gen mismatch) is dropped.
            while True:
                try:
                    item = pace_q.get(timeout=0.2)
                except queue.Empty:
                    if self._stop_evt.is_set() or self._gen != my_gen:
                        return
                    continue
                if item is None:
                    return  # end-of-utterance sentinel
                target, offset, length, gen = item
                if gen != self._gen or self._stop_evt.is_set():
                    continue
                delay = target - time.monotonic()
                if delay > 0 and self._stop_evt.wait(delay):
                    continue  # stopped while waiting
                if gen != self._gen or self._stop_evt.is_set():
                    continue
                if on_word:
                    try:
                        on_word(offset, length)
                    except Exception:
                        pass

        pacer = threading.Thread(target=_pace, daemon=True)
        pacer.start()

        def _run() -> None:
            try:
                for chunk_text, base in chunks:
                    if self._gen != my_gen or self._stop_evt.is_set():
                        break
                    # Reference point for this chunk's word targets, captured
                    # just before synthesis.  espeak_Synth queues audio and
                    # returns; espeak_Synchronize then blocks until this chunk
                    # finishes playing, so chunks play back to back from here.
                    chunk_start = time.monotonic()
                    cb = type(self)._callback_type(_make_cb(base, chunk_start))
                    self._cb = cb  # keep a live ref for this chunk
                    lib.espeak_SetSynthCallback(cb)
                    raw = chunk_text.encode("utf-8", "replace")
                    lib.espeak_Synth(
                        raw, len(raw) + 1, 0, 0, 0, self._CHARS_UTF8, None, None
                    )
                    lib.espeak_Synchronize()
            except Exception:
                pass
            finally:
                # Signal the pacer to drain and exit.  Only the current
                # utterance's worker waits for the last highlights to paint and
                # then clears state / fires on_done; a newer speak()/stop()
                # bumps _gen so a superseded worker skips both.
                pace_q.put(None)
                if self._gen == my_gen:
                    pacer.join(timeout=1.0)
                    self._speaking = False
                    if on_done:
                        on_done()

        threading.Thread(target=_run, daemon=True).start()

    def stop(self) -> None:
        # Bump the generation and set the stop event first so the worker loop
        # and any in-flight synth callback bail out, then cancel the engine's
        # current audio and flush its queue.
        self._gen += 1
        self._stop_evt.set()
        self._speaking = False
        lib = type(self)._lib
        if lib is not None:
            try:
                lib.espeak_Cancel()
            except Exception:
                pass

    def set_rate(self, wpm: int) -> None:
        self._rate = int(wpm)

    def set_volume(self, vol: float) -> None:
        self._volume = int(vol * 100)

    def set_highlight_offset_ms(self, ms: int) -> None:
        """Latency compensation (ms) added to each paced highlight target."""
        self._hl_offset = max(0.0, float(ms) / 1000.0)

    def set_voice(self, voice_id: str) -> None:
        if voice_id:
            self._voice = voice_id

    def list_voices(self) -> List[Dict[str, str]]:
        lib = type(self)._lib
        if lib is None:
            return []
        try:
            arr = lib.espeak_ListVoices(None)
        except Exception:
            return []
        out: List[Dict[str, str]] = []
        i = 0
        while arr and arr[i]:
            v = arr[i].contents
            name = v.name.decode("utf-8", "replace") if v.name else ""
            ident = v.identifier.decode("utf-8", "replace") if v.identifier else ""
            # languages is a priority byte followed by the language name; the
            # leading byte is dropped to recover the first language tag.
            langs = v.languages or b""
            lang = langs[1:].decode("utf-8", "replace") if len(langs) > 1 else ""
            out.append({"id": ident, "name": name, "lang": lang})
            i += 1
        return out

    @property
    def speaking(self) -> bool:
        return self._speaking


class DECtalkDLLBackend(TTSBackend):
    """DECtalk backend driven directly through the bundled ``DECtalk.dll``
    via ctypes (Windows only).

    Unlike :class:`DECtalkBackend`, which shells out to a ``say``/``dtalk``
    command-line tool, this calls the DECtalk C API (ttsapi.h) in-process, so
    the classic DECtalk voices work in the self-contained Windows build using
    only the vendored ``DECtalk.dll`` + ``dtalk_us.dic`` (no CLI needed).  Live
    speech streams straight to the sound card (``OWN_AUDIO_DEVICE``); audio
    export renders to a WAV file (``TextToSpeechOpenWaveOutFile``).

    The DECtalk source (and the NVDA synth driver this implementation follows)
    are at github.com/dectalk/dectalk.
    """

    name = "dectalk"
    priority = 10  # in-process DECtalk.dll ("Perfect Paul") — first in auto when present

    # DECtalk C API constants (ttsapi.h).
    _TTS_FORCE = 1
    _OWN_AUDIO_DEVICE = 1
    _DO_NOT_USE_AUDIO_DEVICE = 0x80000000
    _WAVE_MAPPER = 0xFFFFFFFF
    _WAVE_FORMAT_1M16 = 0x00000004  # 11025 Hz, 16-bit, mono (DECtalk native)

    # SMIT (shared-memory) licence blob the DLL reads when a speaker starts.
    # The mapping-name prefix encodes the build arch (``a32``/``a64``); we
    # install the blob under both so whichever the DLL looks for is present.
    # Sourced from the upstream DECtalk NVDA driver.
    _LICENSE_MAP_NAMES = (b"a32DECtalkDllFileMap", b"a64DECtalkDllFileMap")
    _LICENSE_BLOB = (
        b"\0\0\0\0r250hRm2no9fmP75YwvRhnRB81Uv6vZOTb7SdKWKae8k3BXL8U6r??3B0P91"
    )

    # The nine predefined DECtalk speakers.  Each maps to a single-letter
    # voice code used by the ``[:n<x>]`` inline command (first letters are all
    # distinct), which is the canonical, widely-supported selector.
    _VOICES = (
        ("Paul", "Perfect Paul"),
        ("Betty", "Beautiful Betty"),
        ("Harry", "Huge Harry"),
        ("Frank", "Frail Frank"),
        ("Dennis", "Doctor Dennis"),
        ("Kit", "Kit the Kid"),
        ("Ursula", "Uppity Ursula"),
        ("Rita", "Rough Rita"),
        ("Wendy", "Whispering Wendy"),
    )
    _NAME_TO_LETTER = {name.lower(): name[0].lower() for name, _ in _VOICES}
    _VOICE_LETTERS = set(_NAME_TO_LETTER.values())

    _dll = None  # cached ctypes handle (class-level; load once per process)
    _license_kept: List[object] = []  # keep mapping handles/views alive
    _load_lock = threading.Lock()
    _probe_ok = None  # cached result of a real engine-startup probe

    def __init__(self, rate: int = 265, voice: str = "Paul"):
        self._rate = rate
        self._voice = voice or "Paul"
        self._handle = None  # active OWN_AUDIO_DEVICE handle while speaking
        self._speaking = False
        self._lib = self._load_library()

    # -- DLL loading + licence install ------------------------------------
    @classmethod
    def _load_library(cls):
        if os.name != "nt" or not _DECTALK_DLL.is_file():
            return None
        with cls._load_lock:
            if cls._dll is not None:
                return cls._dll
            try:
                import ctypes
                from ctypes import wintypes

                # Install the licence blob into shared memory *before* the DLL
                # starts a speaker (it reads the mapping during startup).
                k32 = ctypes.windll.kernel32
                k32.CreateFileMappingA.restype = wintypes.HANDLE
                k32.CreateFileMappingA.argtypes = [
                    wintypes.HANDLE,
                    ctypes.c_void_p,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    ctypes.c_char_p,
                ]
                k32.MapViewOfFile.restype = ctypes.c_void_p
                k32.MapViewOfFile.argtypes = [
                    wintypes.HANDLE,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    wintypes.DWORD,
                    ctypes.c_size_t,
                ]
                INVALID = wintypes.HANDLE(-1)
                for name in cls._LICENSE_MAP_NAMES:
                    h_map = k32.CreateFileMappingA(INVALID, None, 0x04, 0, 512, name)
                    if not h_map:
                        continue
                    view = k32.MapViewOfFile(h_map, 0x0002, 0, 0, 0)
                    if view:
                        ctypes.memmove(view, cls._LICENSE_BLOB, len(cls._LICENSE_BLOB))
                        cls._license_kept.append((h_map, view))

                dll = ctypes.CDLL(str(_DECTALK_DLL))
                # Prototype the entry points we use so 64-bit handles/args are
                # not truncated to int.
                dll.TextToSpeechStartup.restype = ctypes.c_int
                dll.TextToSpeechStartup.argtypes = [
                    wintypes.HWND,
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.c_uint,
                    wintypes.DWORD,
                ]
                dll.TextToSpeechSpeak.restype = ctypes.c_int
                dll.TextToSpeechSpeak.argtypes = [
                    ctypes.c_void_p,
                    ctypes.c_char_p,
                    wintypes.DWORD,
                ]
                dll.TextToSpeechSync.restype = ctypes.c_int
                dll.TextToSpeechSync.argtypes = [ctypes.c_void_p]
                dll.TextToSpeechReset.restype = ctypes.c_int
                dll.TextToSpeechReset.argtypes = [ctypes.c_void_p, ctypes.c_int]
                dll.TextToSpeechShutdown.restype = ctypes.c_int
                dll.TextToSpeechShutdown.argtypes = [ctypes.c_void_p]
                dll.TextToSpeechOpenWaveOutFile.restype = ctypes.c_int
                dll.TextToSpeechOpenWaveOutFile.argtypes = [
                    ctypes.c_void_p,
                    ctypes.c_char_p,
                    wintypes.DWORD,
                ]
                dll.TextToSpeechCloseWaveOutFile.restype = ctypes.c_int
                dll.TextToSpeechCloseWaveOutFile.argtypes = [ctypes.c_void_p]
                cls._dll = dll
            except Exception:
                cls._dll = None
            return cls._dll

    def available(self) -> bool:
        # Loading the DLL is necessary but not sufficient: the engine also has
        # to start (dictionary + licensing).  Probe a real, audio-free startup
        # once and cache it, so we never advertise (or default to) a DECtalk
        # that cannot actually speak.
        if self._lib is None:
            return False
        cls = type(self)
        if cls._probe_ok is None:
            handle = self._startup(own_audio=False)
            if handle is not None:
                cls._probe_ok = True
                try:
                    self._lib.TextToSpeechShutdown(handle)
                except Exception:
                    pass
            else:
                cls._probe_ok = False
        return bool(cls._probe_ok)

    # -- helpers ----------------------------------------------------------
    def _voice_letter(self) -> str:
        """Single-letter DECtalk voice code for the current voice.

        Accepts a full speaker name ("Paul") or a one-letter code ("p").
        Anything else (e.g. a stale SAPI voice id left in settings) falls
        back to Perfect Paul rather than picking a wrong speaker.
        """
        v = (self._voice or "").strip().lower()
        if v in self._NAME_TO_LETTER:
            return self._NAME_TO_LETTER[v]
        if len(v) == 1 and v in self._VOICE_LETTERS:
            return v
        return "p"

    def list_voices(self) -> List[Dict[str, str]]:
        return [
            {"id": name, "name": friendly, "lang": "en-us"}
            for name, friendly in self._VOICES
        ]

    def _startup(self, own_audio: bool):
        """Create a DECtalk speaker handle, or return None on failure.

        The engine loads ``dtalk_us.dic`` relative to the current directory,
        so we briefly chdir into the DLL's folder (serialised on the load
        lock) for the duration of the startup call, then restore the cwd.
        """
        import ctypes

        handle = ctypes.c_void_p()
        opts = self._OWN_AUDIO_DEVICE if own_audio else self._DO_NOT_USE_AUDIO_DEVICE
        rc = -1
        with self._load_lock:
            try:
                prev = os.getcwd()
            except Exception:
                prev = ""
            try:
                os.chdir(str(_DECTALK_DLL.parent))
                rc = self._lib.TextToSpeechStartup(
                    None, ctypes.byref(handle), self._WAVE_MAPPER, opts
                )
            finally:
                if prev:
                    try:
                        os.chdir(prev)
                    except Exception:
                        pass
        if rc != 0 or not handle.value:
            return None
        return handle

    def _markup(self, text: str) -> bytes:
        rate = min(650, max(75, int(self._rate)))
        return f"[:n{self._voice_letter()}][:rate {rate}]{text}".encode(
            "latin-1", errors="replace"
        )

    # -- live speech (streams to the sound card) --------------------------
    def speak(
        self,
        text: str,
        on_word: Optional[Callable[[int, int], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        self.stop()
        if self._lib is None:
            if on_done:
                on_done()
            return
        self._speaking = True
        payload = self._markup(text)

        def _run() -> None:
            handle = None
            try:
                handle = self._startup(own_audio=True)
                if handle is None:
                    return
                self._handle = handle
                self._lib.TextToSpeechSpeak(handle, payload, self._TTS_FORCE)
                self._lib.TextToSpeechSync(handle)  # blocks until finished
            except Exception:
                pass
            finally:
                if handle is not None:
                    try:
                        self._lib.TextToSpeechShutdown(handle)
                    except Exception:
                        pass
                self._handle = None
                self._speaking = False
                if on_done:
                    on_done()

        threading.Thread(target=_run, daemon=True).start()

    def stop(self) -> None:
        h = self._handle
        if h is not None and self._lib is not None:
            try:
                # Reset(TRUE) discards queued speech so Sync() returns promptly
                # and the worker thread can shut the engine down.
                self._lib.TextToSpeechReset(h, 1)
            except Exception:
                pass
        self._speaking = False

    def set_rate(self, wpm: int) -> None:
        self._rate = int(wpm)

    def set_voice(self, voice_id: str) -> None:
        if voice_id:
            self._voice = voice_id

    def export_to_wav(self, text: str, wav_path: str) -> None:
        """Synthesize *text* to *wav_path* (11025 Hz mono WAV) via the DLL."""
        if self._lib is None:
            raise RuntimeError("DECtalk DLL is not available")
        handle = self._startup(own_audio=False)
        if handle is None:
            raise RuntimeError("DECtalk engine failed to start")
        try:
            rc = self._lib.TextToSpeechOpenWaveOutFile(
                handle,
                str(wav_path).encode("mbcs", errors="replace"),
                self._WAVE_FORMAT_1M16,
            )
            if rc != 0:
                raise RuntimeError("DECtalk could not open the WAV output file")
            self._lib.TextToSpeechSpeak(handle, self._markup(text), self._TTS_FORCE)
            self._lib.TextToSpeechSync(handle)
            self._lib.TextToSpeechCloseWaveOutFile(handle)
        finally:
            try:
                self._lib.TextToSpeechShutdown(handle)
            except Exception:
                pass

    @property
    def speaking(self) -> bool:
        return self._speaking


class DECtalkBackend(TTSBackend):
    """DECtalk backend.  Requires the DECtalk binary (dtalk or say) to be on
    PATH or pointed to via DECTALK_BIN environment variable.
    The DECtalk source code is available at github.com/dectalk/dectalk."""

    name = "dectalk"
    priority = 70  # say/dtalk CLI fallback — tried after the in-process DECtalk.dll

    def __init__(self, rate: int = 265, voice: str = "Paul"):
        self._rate = rate
        self._voice = voice
        self._proc: Optional[subprocess.Popen] = None
        self._speaking = False
        self._bin = (
            os.environ.get("DECTALK_BIN")
            or _DECTALK_BUNDLED
            or shutil.which("dtalk")
            or shutil.which("dectalk")
        )

    def available(self) -> bool:
        return self._bin is not None

    def speak(
        self,
        text: str,
        on_word: Optional[Callable[[int, int], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        self.stop()
        if not self._bin:
            if on_done:
                on_done()
            return
        self._speaking = True
        dt_text = self._markup(text)

        def _run() -> None:
            try:
                self._proc = subprocess.Popen(
                    [self._bin],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if self._proc.stdin:
                    self._proc.stdin.write(dt_text.encode("ascii", errors="replace"))
                    self._proc.stdin.close()
                self._proc.wait()
            except Exception:
                pass
            finally:
                self._speaking = False
                if on_done:
                    on_done()

        threading.Thread(target=_run, daemon=True).start()

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass
        self._speaking = False

    def set_rate(self, wpm: int) -> None:
        self._rate = wpm

    def set_voice(self, voice_id: str) -> None:
        self._voice = voice_id

    def list_voices(self) -> List[Dict[str, str]]:
        return [
            {"id": name, "name": friendly, "lang": "en-us"}
            for name, friendly in DECtalkDLLBackend._VOICES
        ]

    def _markup(self, text: str) -> str:
        # [:rate N] is words-per-minute (75-650); [:n<x>] selects a speaker.
        rate = min(650, max(75, int(self._rate)))
        v = (self._voice or "").strip().lower()
        letter = DECtalkDLLBackend._NAME_TO_LETTER.get(
            v, v if (len(v) == 1 and v in DECtalkDLLBackend._VOICE_LETTERS) else "p"
        )
        return f"[:n{letter}][:rate {rate}]{text}"

    def export_to_wav(self, text: str, wav_path: str) -> None:
        """Synthesize *text* to *wav_path* using DECtalk's ``-w`` flag."""
        if not self._bin:
            raise RuntimeError("DECtalk is not available")
        dt_text = self._markup(text)
        proc = subprocess.Popen(
            [self._bin, "-w", wav_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if proc.stdin:
            proc.stdin.write(dt_text.encode("ascii", errors="replace"))
            proc.stdin.close()
        proc.wait()

    @property
    def speaking(self) -> bool:
        return self._speaking


class AppleSayBackend(TTSBackend):
    """macOS native speech via the built-in ``/usr/bin/say`` command.

    This gives Mac users Apple's high-quality system voices (including the
    Eloquence voices bundled with recent macOS releases) with **zero extra
    dependencies** — no ``pyobjc``, no Homebrew, no ``espeak``.  Because it is
    always present on macOS it is ranked above eSpeak in ``auto`` mode so the
    program never silently falls back to the robotic eSpeak voice on a Mac.

    ``say`` does not emit per-word events, so word highlighting is driven by
    the timer in :class:`TTSManager` (the same path used for Festival/Coqui).
    """

    name = "applesay"
    priority = 30

    def __init__(self, rate: int = 265, volume: float = 1.0, voice: str = ""):
        self._rate = int(rate)
        self._volume = volume
        self._voice = voice
        self._proc: Optional[subprocess.Popen] = None
        self._speaking = False
        self._bin = shutil.which("say") if sys.platform == "darwin" else None

    def available(self) -> bool:
        return self._bin is not None

    def _cmd(self, extra: Optional[List[str]] = None) -> List[str]:
        cmd = [self._bin, "-r", str(max(50, self._rate))]
        if self._voice:
            cmd += ["-v", self._voice]
        if extra:
            cmd += extra
        return cmd

    def speak(
        self,
        text: str,
        on_word: Optional[Callable[[int, int], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        self.stop()
        if not self._bin:
            if on_done:
                on_done()
            return
        self._speaking = True

        def _run() -> None:
            try:
                # `say` reads the text to speak from stdin when no string
                # operand is given, which avoids ARG_MAX limits on long docs.
                self._proc = subprocess.Popen(
                    self._cmd(),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if self._proc.stdin:
                    self._proc.stdin.write(text.encode("utf-8", errors="replace"))
                    self._proc.stdin.close()
                self._proc.wait()
            except Exception:
                pass
            finally:
                self._speaking = False
                if on_done:
                    on_done()

        threading.Thread(target=_run, daemon=True).start()

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass
        self._speaking = False

    def set_rate(self, wpm: int) -> None:
        self._rate = int(wpm)

    def set_volume(self, vol: float) -> None:
        self._volume = max(0.0, min(1.0, vol))

    def set_voice(self, voice_id: str) -> None:
        self._voice = voice_id

    def list_voices(self) -> List[Dict[str, str]]:
        if not self._bin:
            return []
        try:
            out = subprocess.check_output(
                [self._bin, "-v", "?"], stderr=subprocess.DEVNULL, text=True
            )
        except Exception:
            return []
        voices: List[Dict[str, str]] = []
        for line in out.splitlines():
            # Format: "Reed                en_US    # comment"
            m = re.match(r"^(.+?)\s+([a-z]{2}[-_][A-Z]{2})\s*#?", line)
            if m:
                voices.append(
                    {
                        "id": m.group(1).strip(),
                        "name": m.group(1).strip(),
                        "lang": m.group(2),
                    }
                )
        return voices

    def export_to_wav(self, text: str, wav_path: str) -> None:
        """Synthesize *text* to a WAVE file using ``say -o`` (LEI16 PCM)."""
        if not self._bin:
            raise RuntimeError("macOS 'say' command is not available")
        cmd = self._cmd(
            ["-o", wav_path, "--file-format=WAVE", "--data-format=LEI16@22050"]
        )
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if proc.stdin:
            proc.stdin.write(text.encode("utf-8", errors="replace"))
            proc.stdin.close()
        proc.wait()
        if proc.returncode not in (0, None):
            raise RuntimeError(f"say exited with code {proc.returncode}")

    @property
    def speaking(self) -> bool:
        return self._speaking


class _SCReader:
    """Persistent single-line TTS reader for Speech Cursor mode.

    Problem being solved
    --------------------
    ``_sc_read_line`` used to call ``pyttsx3.Engine()`` on *every* line.  On
    Windows that COM initialization takes 200–500 ms, creating a window where
    ``_active_engine`` is ``None``.  If the user exits SC mode during that
    window ``Pyttsx3Backend.stop()`` cannot reach the engine via
    ``eng.stop()``; the ``_stop_requested`` flag may also lose the race,
    allowing ``runAndWait()`` to start — speech continues after the mode is
    gone.

    Solution
    --------
    One ``pyttsx3.Engine`` is built when SC mode is entered and reused for
    every line.  ``stop()`` always has a live COM object to call
    ``eng.stop()`` on, so SAPI5 is interrupted in under a frame.  If a
    mid-speech stop corrupts SAPI5 state (the known Windows issue), the next
    ``speak()`` call rebuilds the engine *inside its own background thread*
    so the curses UI never blocks.
    """

    def __init__(self, rate: int, volume: float) -> None:
        self._rate = rate
        self._volume = volume
        self._eng = None  # persistent pyttsx3 Engine
        self._thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()  # signals _run to abort
        self._needs_rebuild = False  # engine may be corrupt

    # ── internal ──────────────────────────────────────────────────────

    def _build(self) -> Any:
        eng = _load_pyttsx3().Engine()
        eng.setProperty("rate", self._rate)
        eng.setProperty("volume", self._volume)
        return eng

    @property
    def _busy(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ── public API ────────────────────────────────────────────────────

    def start(self) -> None:
        """Build the persistent engine (call once when SC mode is entered)."""
        if not _PYTTSX3:
            return
        try:
            self._eng = self._build()
        except Exception:
            self._eng = None

    def speak(self, text: str) -> None:
        """Stop current speech (if any) and read *text*.

        Always returns immediately — never blocks the UI thread.
        If a mid-speech stop corrupted the engine the rebuild happens
        inside the new speech thread, not on the caller.
        """
        if not _PYTTSX3:
            return

        if self._busy:
            # Signal old thread to abort and interrupt SAPI5.
            # Engine state may be corrupt after stop-while-busy.
            self._stop_flag.set()
            if self._eng:
                try:
                    self._eng.stop()
                except Exception:
                    pass
            self._needs_rebuild = True

        self._stop_flag.clear()
        rate = self._rate
        volume = self._volume
        needs_rebuild = self._needs_rebuild
        eng_ref = [self._eng]  # mutable cell so _run can update it
        stop_flag = self._stop_flag
        reader = self

        def _run() -> None:
            eng = eng_ref[0]
            try:
                if needs_rebuild or eng is None:
                    eng = _load_pyttsx3().Engine()
                    eng.setProperty("rate", rate)
                    eng.setProperty("volume", volume)
                    eng_ref[0] = eng
                    reader._eng = eng
                    reader._needs_rebuild = False
                if stop_flag.is_set():
                    return
                eng.say(text)
                if stop_flag.is_set():
                    return
                eng.runAndWait()
            except Exception:
                reader._needs_rebuild = True
            finally:
                if stop_flag.is_set():
                    reader._needs_rebuild = True  # interrupted → may be corrupt

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Interrupt speech immediately.  Non-blocking — safe to call from
        the curses main loop."""
        self._stop_flag.set()
        eng = self._eng
        if eng:
            try:
                eng.stop()  # SAPI5 Skip — takes effect in < one audio frame
            except Exception:
                pass
        if self._busy:
            self._needs_rebuild = True

    def update_rate(self, rate: int) -> None:
        """Propagate a speech-rate change to the live engine."""
        self._rate = rate
        eng = self._eng
        if eng and not self._busy:
            try:
                eng.setProperty("rate", rate)
            except Exception:
                pass

    def close(self) -> None:
        """Stop speech and release the engine on SC mode exit."""
        self.stop()
        self._eng = None


class TTSManager:
    """Manages the active TTS backend and word-position tracking."""

    #: Engine names never chosen in ``auto`` mode: piper/coqui need an explicit
    #: opt-in (downloaded model), and ``silent`` is the last-resort fallback.
    _AUTO_SKIP = frozenset({"silent", "piper", "coqui"})

    def __init__(self, settings: Settings):
        self._settings = settings
        self._backend: TTSBackend = SilentBackend()
        self._word_map: List["WordPos"] = []
        self._current_word_idx: int = -1
        self._on_highlight: Optional[Callable[[int], None]] = None  # callback(word_idx)
        self._on_done: Optional[Callable[[], None]] = None
        self._timer_thread: Optional[threading.Thread] = None
        self._timer_stop = threading.Event()
        # Monotonically-increasing counter, incremented every time a new timer
        # thread is started.  Each _tick closure captures its own value so it
        # can detect that a newer timer has taken over and exit immediately.
        # This prevents multiple stale timers from calling _on_highlight
        # simultaneously, which caused the highlight to jump erratically.
        self._timer_gen: int = 0
        # Last word index confirmed by a pyttsx3 word-boundary callback.
        # -1 means no callback has fired yet for the current utterance
        # (either SSML mode where callbacks are skipped, or engine still
        # starting up).  The timer uses this to pace itself: it won't run
        # more than _MAX_AHEAD words ahead of the confirmed position.
        self._last_cb_word_idx: int = -1
        # Monotonic timestamp of the most recent pyttsx3 word callback.
        # 0.0 means no callback has fired for this utterance.  Used by the
        # timer's pacing guard: if no callback has arrived for longer than
        # _CB_TIMEOUT seconds the guard is bypassed so the highlight never
        # stalls while speech continues (SAPI5 callbacks can go silent).
        self._last_cb_time: float = 0.0
        # True only while the active backend emits real per-word events that
        # track audio progress (currently just pyttsx3's SAPI5 word callbacks;
        # eSpeak-NG's CLI does not emit mark events, so its marks cannot be
        # used as a signal here).  The highlight timer reads this to anchor its
        # first paint to the first real event (≈ audio onset) instead of to the
        # speak() call, which precedes audible output by the engine's start-up
        # latency and otherwise gives the highlight a constant head start.
        self._expect_callbacks: bool = False
        # True when the active backend paces its word callbacks to real audio
        # position (the in-process eSpeak-NG backend).  Those callbacks are
        # playback-accurate, so the highlight timer can track them tightly
        # instead of allowing the looser slack SAPI5's lagging callbacks need.
        self._paced_playback: bool = False
        self._select_backend(settings["tts_backend"])

    def _select_backend(self, preference: str) -> None:
        """Pick the active backend from the plugin registry.

        Backend classes are discovered via the ``star.backends`` entry-points
        (built-ins and any installed third-party plugins) and walked in
        ``priority`` order.  An explicit *preference* tries only the engines
        registered under that name — ``"espeak"`` and ``"dectalk"`` each map to
        two implementations (in-process then CLI), tried in priority order.
        ``"auto"`` walks every auto-eligible engine and takes the first that
        reports itself available; everything falls back to :class:`SilentBackend`.
        """
        from .plugins import PluginRegistry

        rate = int(self._settings["tts_rate"])
        vol = float(self._settings["tts_volume"])

        classes = sorted(PluginRegistry.get().backends, key=lambda c: c.priority)

        chosen: Optional[TTSBackend] = None
        if preference and preference != "auto":
            # Explicit engine: try only the implementations registered under
            # this name, lowest priority first (e.g. libespeak-ng before the
            # eSpeak CLI; DECtalk.dll before the say/dtalk CLI).
            for cls in classes:
                if cls.name != preference:
                    continue
                cand = self._construct_backend(cls)
                if cand.available():
                    chosen = cand
                    break
        else:
            # Auto: walk every auto-eligible engine in priority order.  The
            # bundled DECtalk.dll ("Perfect Paul") sorts first, then pyttsx3,
            # the macOS `say` voice (ranked above eSpeak so a Mac never falls to
            # the robotic eSpeak voice), eSpeak, Festival, and the DECtalk CLI.
            for cls in classes:
                if cls.name in self._AUTO_SKIP:
                    continue
                cand = self._construct_backend(cls)
                if cand.available():
                    chosen = cand
                    break

        self._backend = chosen or SilentBackend()
        self._backend.set_rate(rate)
        self._backend.set_volume(vol)
        self._resolve_default_voice()

    def _construct_backend(self, cls: "type[TTSBackend]") -> TTSBackend:
        """Instantiate *cls* with the per-engine constructor arguments derived
        from settings.  Engines that share a ``name`` (eSpeak's and DECtalk's two
        implementations each) take identical arguments, so keying on ``name`` is
        safe.  Unknown / third-party backends are tried with the common
        ``(rate, volume, voice)`` signature, then with no arguments.
        """
        rate = int(self._settings["tts_rate"])
        vol = float(self._settings["tts_volume"])
        voice = str(self._settings["tts_voice"])
        name = cls.name
        if name == "espeak":
            return cls(rate=rate, voice=voice or "en-us")
        if name == "dectalk":
            return cls(rate=rate, voice=voice)
        if name == "piper":
            # A `tts_voice` ending in .onnx wins; otherwise the dedicated
            # `piper_model` setting supplies the model path.
            piper_voice = (
                voice
                if voice.lower().endswith(".onnx")
                else str(self._settings.get("piper_model", ""))
            )
            return cls(rate=rate, volume=vol, voice=piper_voice)
        try:
            return cls(rate=rate, volume=vol, voice=voice)
        except TypeError:
            return cls()

    def _resolve_default_voice(self) -> None:
        """Pick a sensible default voice when the user hasn't chosen one.

        When ``tts_voice`` is empty, prefer a voice whose name contains the
        ``tts_prefer_voice`` substring (default ``"eloquence"``), favoring a
        US-English variant.  This makes the bundled Eloquence voices the
        default on macOS while leaving the engine default untouched when no
        match is found.  The user's explicit voice choice always wins.
        """
        if str(self._settings.get("tts_voice", "")):
            return  # user has an explicit voice; never override it
        prefer = str(self._settings.get("tts_prefer_voice", "")).strip().lower()
        if not prefer:
            return
        try:
            voices = self._backend.list_voices()
        except Exception:
            voices = []
        if not voices:
            return
        matches = [
            v
            for v in voices
            if prefer in (v.get("name", "") + " " + v.get("id", "")).lower()
        ]
        if not matches:
            return
        # Favor a US-English variant of the preferred voice family.
        best = next(
            (m for m in matches if "us" in str(m.get("lang", "")).lower()),
            matches[0],
        )
        vid = best.get("id") or best.get("name")
        if vid:
            self._backend.set_voice(vid)

    @property
    def backend_name(self) -> str:
        return self._backend.name

    @property
    def speaking(self) -> bool:
        return self._backend.speaking

    @property
    def current_word_idx(self) -> int:
        return self._current_word_idx

    def set_word_map(self, word_map: List["WordPos"]) -> None:
        self._word_map = word_map

    def set_on_highlight(self, cb: Optional[Callable[[int], None]]) -> None:
        self._on_highlight = cb

    def set_on_done(self, cb: Optional[Callable[[], None]]) -> None:
        self._on_done = cb

    def speak(
        self,
        text: str,
        start_word_idx: int = 0,
        text_offset: int = 0,
    ) -> None:
        """Begin speaking *text*.

        Parameters
        ----------
        text:
            The string actually passed to the TTS engine.  This may be a
            *slice* of the full document plain text (everything from the
            desired start position to the end) so that the engine does not
            re-read content that has already been heard.
        start_word_idx:
            Index into the full word_map of the first word in *text*.  Used
            to seed the highlight timer at the right position.
        text_offset:
            Character offset of the first character of *text* within the
            full plain-text string.  Used to translate the byte offsets that
            pyttsx3 reports back into absolute word-map indices.
        """
        # Increment the timer generation BEFORE signalling the old timer to
        # stop.  This ensures that an old timer currently mid-loop-body will
        # see the new generation on its very next gen-check and return without
        # calling _on_highlight, preventing a stray high-word flash followed
        # by the new timer's start-word snap (the "snap back" bug).
        self._timer_gen += 1
        self._timer_stop.set()
        self._current_word_idx = max(0, start_word_idx)
        self._last_cb_word_idx = -1  # no confirmed position yet for this utterance
        self._last_cb_time = 0.0  # reset callback timestamp for this utterance

        def on_done() -> None:
            self._timer_stop.set()
            self._current_word_idx = -1
            if self._on_highlight:
                self._on_highlight(-1)
            if self._on_done:
                self._on_done()

        # pyttsx3 word callbacks supplement the timer when they fire reliably
        # (they may not on all Windows/SAPI5 configurations).  The timer is
        # always started as the primary highlight mechanism.
        if isinstance(self._backend, (Pyttsx3Backend, ESpeakLibBackend)):
            # The in-process eSpeak-NG backend paces its callbacks to real audio
            # position, so they are playback-accurate (unlike SAPI5's, which lag
            # and burst).  Flag that for the timer, and keep the backend's
            # latency-compensation offset in sync with the user setting so the
            # highlight is not painted slightly before the word is heard.
            self._paced_playback = isinstance(self._backend, ESpeakLibBackend)
            if self._paced_playback:
                self._backend.set_highlight_offset_ms(
                    int(self._settings.get("espeak_highlight_offset_ms", 120))
                )

            def on_word_cb(location: int, length: int) -> None:
                """Translate TTS-relative location back to a word-map index.

                *location* is relative to the *text* slice passed to speak().
                Adding *text_offset* converts it to an absolute offset in the
                full plain-text string, which is what word_map stores.

                We update *_current_word_idx* here so the timer can adopt the
                accurate engine position on its next tick, but we deliberately
                do NOT call *_on_highlight* directly.  SAPI5 callbacks arrive
                asynchronously and can lag or burst; calling _on_highlight from
                the callback caused the highlight to snap backward to an older
                word while the timer had already advanced forward.
                """
                # text_offset == -1 means SSML mode: character offsets in
                # the callback point into the SSML string, not the plain
                # text.  Skip the lookup and let the timer handle highlight.
                if text_offset < 0:
                    return
                abs_loc = location + text_offset
                for i, wp in enumerate(self._word_map):
                    if wp.tts_offset <= abs_loc < wp.tts_offset + wp.tts_len + 1:
                        # Monotonic write: only advance, never retreat.
                        # Delayed or out-of-order SAPI5 callbacks for earlier
                        # words must not clobber a later confirmed position
                        # (which would make _tts_toggle save the wrong pause
                        # word and cause a backward snap on resume).
                        if i >= self._current_word_idx:
                            self._current_word_idx = i
                            self._last_cb_word_idx = i
                            self._last_cb_time = time.monotonic()
                        break

            self._expect_callbacks = True
            self._backend.speak(text, on_word=on_word_cb, on_done=on_done)
        else:
            self._expect_callbacks = False
            self._paced_playback = False
            self._backend.speak(text, on_done=on_done)

        # Always start the timer — it is the reliable baseline for all backends.
        self._start_timer_highlight(start_word_idx)

    def _start_timer_highlight(self, start_idx: int) -> None:
        """Timer-based word highlight advance.  Works for every backend.

        If the word map is not yet built (async loading still running), the
        timer waits up to 10 s for it to appear before advancing.

        A monotonic *_timer_gen* counter is captured at launch.  Every loop
        iteration confirms its value still matches; if a newer timer has been
        started (via a new speak() call) the old thread exits immediately.
        This prevents multiple stale timers from racing to call _on_highlight
        with different word indices, which was the primary cause of the
        highlight jumping all over the place.
        """
        self._timer_stop.clear()
        # _timer_gen was already incremented by speak() or stop() before
        # this method was called; just capture the current value.
        my_gen = self._timer_gen
        rate = int(self._settings["tts_rate"])
        # Timer interval: run at the nominal speech rate (1.0 × wpm) so the
        # highlight tracks audio as closely as possible.  The _MAX_AHEAD guard
        # below is the true throttle for pyttsx3/SAPI5; slowing the timer
        # (< 1.0) only causes the highlight to fall behind.
        hl_speed = float(self._settings.get("highlight_speed", 1.0))
        interval = 60.0 / max(1.0, rate * max(0.1, hl_speed))
        # How many words ahead of the last callback-confirmed position the
        # timer is allowed to advance before it pauses for one tick.
        # Only active when pyttsx3 word callbacks are firing; _last_cb_word_idx
        # stays -1 in SSML mode and for non-pyttsx3 backends (guard inactive).
        #
        # 4 words of slack covers the typical SAPI5 callback delay (1-3 words
        # late) without letting the highlight race too far ahead of audio.  The
        # in-process eSpeak-NG backend paces its callbacks to actual playback
        # position, so its confirmed index is itself accurate: cap the lead at a
        # single word so the highlight sits on the word being spoken rather than
        # drifting up to four ahead.
        _MAX_AHEAD = 1 if self._paced_playback else 4
        # If no callback has arrived within this many seconds the guard is
        # bypassed entirely: SAPI5 sometimes stops firing callbacks mid-text,
        # and without this escape the highlight would freeze while speech
        # continues.  1.5 s ≈ 6 words at 240 wpm — long enough to ride out
        # normal punctuation pauses, short enough to feel responsive.
        _CB_TIMEOUT = 1.5
        # First-audio anchor window.  When the backend reports real per-word
        # events, the timer holds its first paint until the first event arrives
        # (≈ audio onset) so the highlight does not start counting from the
        # speak() call — which precedes audible output by the engine's start-up
        # latency and gives the highlight a constant head start.  Bounded so the
        # highlight can never stall if events fail to arrive (e.g. a SAPI5
        # configuration that delivers no word callbacks): after this long the
        # timer proceeds in free-running mode, exactly as before.
        _ANCHOR_TIMEOUT = 0.75

        def _tick() -> None:
            # Wait for the word map to be populated (built asynchronously).
            deadline = time.monotonic() + 10.0
            while not self._timer_stop.is_set():
                if self._word_map:
                    break
                if time.monotonic() > deadline:
                    return  # gave up waiting
                time.sleep(0.05)

            # Exit immediately if a newer timer was started while we waited.
            if self._timer_gen != my_gen:
                return

            # First-audio anchor: when the backend emits real per-word events,
            # wait for the first one before painting anything so the highlight
            # clock aligns to audible output rather than to the speak() call.
            # This removes the constant head start the highlight otherwise has
            # from the engine's start-up latency.  Only pyttsx3 sets
            # _expect_callbacks today, so every other backend skips this and
            # behaves exactly as before.  _last_cb_word_idx is a single int
            # written by the engine callback thread; reading it here is atomic
            # under the GIL, so this advisory check needs no lock.
            if self._expect_callbacks:
                anchor_deadline = time.monotonic() + _ANCHOR_TIMEOUT
                while not self._timer_stop.is_set():
                    if self._timer_gen != my_gen:
                        return
                    if self._last_cb_word_idx >= 0:
                        break  # first real word event seen — anchored
                    if time.monotonic() > anchor_deadline:
                        break  # no events arriving — proceed free-running
                    time.sleep(0.01)

            idx = max(0, start_idx)
            while not self._timer_stop.wait(interval):
                # Bail out as soon as a newer timer generation takes over.
                if self._timer_gen != my_gen:
                    return
                # Adopt the engine's position when it has run ahead of the
                # timer estimate (e.g. fast speech or SSML pauses consumed).
                # Never go backward — that would cause the highlight to jump
                # back to a word that was already spoken.
                if self._current_word_idx > idx:
                    idx = self._current_word_idx
                # Pacing guard: keep the highlight within _MAX_AHEAD words
                # of the last callback-confirmed audio position.  Only active
                # while callbacks are both firing AND recent; if SAPI5 stops
                # sending callbacks (_CB_TIMEOUT exceeded) the guard is
                # bypassed so the highlight never freezes mid-document.
                if (
                    self._last_cb_word_idx >= 0
                    and idx >= self._last_cb_word_idx + _MAX_AHEAD
                    and (time.monotonic() - self._last_cb_time) < _CB_TIMEOUT
                ):
                    continue  # hold briefly — callbacks are active but lagging
                if idx < len(self._word_map):
                    # Second gen-check immediately before the display call.
                    # Closes the narrow window between the first check above
                    # and this point where a new speak() could have bumped
                    # the generation, avoiding a stray _on_highlight flash.
                    if self._timer_gen != my_gen:
                        return
                    self._current_word_idx = idx
                    if self._on_highlight:
                        self._on_highlight(idx)
                    idx += 1
                # Don't break when we reach the end — the backend may still
                # be speaking padding/trailing punctuation.

        self._timer_thread = threading.Thread(target=_tick, daemon=True)
        self._timer_thread.start()

    def stop(self) -> None:
        # Same ordering as speak(): bump generation first so any running timer
        # exits cleanly before the stop event is processed.
        self._timer_gen += 1
        self._timer_stop.set()
        self._backend.stop()
        self._current_word_idx = -1
        self._last_cb_word_idx = -1
        self._last_cb_time = 0.0

    @property
    def last_cb_word_idx(self) -> int:
        """Last word index confirmed by a pyttsx3 word-boundary callback.
        -1 when no callback has fired for the current utterance (SSML mode
        or before the engine has produced the first word).  More accurate
        than *current_word_idx* for pause/resume because it reflects the
        actual audio position rather than the timer\'s forward estimate.
        """
        return self._last_cb_word_idx

    def set_rate(self, wpm: int) -> None:
        self._settings["tts_rate"] = wpm
        self._backend.set_rate(wpm)

    def set_volume(self, vol: float) -> None:
        self._settings["tts_volume"] = vol
        self._backend.set_volume(vol)

    def change_backend(self, name: str) -> None:
        self.stop()
        self._settings["tts_backend"] = name
        self._select_backend(name)

    def list_voices(self) -> List[Dict[str, str]]:
        return self._backend.list_voices()

    def export_audio(
        self,
        text: str,
        dest_path: str,
        subtitle_path: Optional[str] = None,
        subtitle_format: str = "srt",
        subtitle_word_level: bool = False,
    ) -> None:
        """Synthesize *text* and save it to *dest_path*.

        The output format is inferred from the file extension:

        * ``.wav``  — written directly by the backend (no extras needed).
        * ``.mp3``  — requires **ffmpeg** or **pydub**.
        * ``.ogg``  — requires **ffmpeg** or **pydub**.
        * ``.mp4``  — requires **ffmpeg** or **pydub** (audio-only AAC).

        When *subtitle_path* is given a synchronized SRT/VTT caption track is
        written there using the same synthesized audio, so no second synthesis
        is needed.  *subtitle_format* is ``"srt"`` or ``"vtt"``
        and *subtitle_word_level* emits one cue per word instead of grouping
        tokens into sentence-length caption lines.

        This method **blocks** until synthesis and conversion are complete.
        Call it from a background thread when used in a GUI to avoid
        freezing the interface.
        """
        ext = Path(dest_path).suffix.lower()
        if ext == ".wav":
            self._backend.export_to_wav(text, dest_path)
            if subtitle_path:
                self._write_subtitles(
                    text,
                    dest_path,
                    subtitle_path,
                    subtitle_format,
                    subtitle_word_level,
                )
            return
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_wav = tmp.name
        try:
            self._backend.export_to_wav(text, tmp_wav)
            if subtitle_path:
                self._write_subtitles(
                    text,
                    tmp_wav,
                    subtitle_path,
                    subtitle_format,
                    subtitle_word_level,
                )
            _convert_audio_format(tmp_wav, dest_path)
        finally:
            try:
                Path(tmp_wav).unlink(missing_ok=True)
            except Exception:
                pass

    @staticmethod
    def _write_subtitles(
        text: str,
        wav_path: str,
        sub_path: str,
        fmt: str = "srt",
        word_level: bool = False,
    ) -> None:
        """Generate and write an SRT/VTT caption track for the synthesized WAV."""
        subs = _generate_subtitles(text, wav_path, fmt=fmt, word_level=word_level)
        if subs:
            Path(sub_path).write_text(subs, encoding="utf-8")

    def export_subtitles(
        self,
        text: str,
        sub_path: str,
        fmt: str = "srt",
        word_level: bool = False,
    ) -> None:
        """Synthesize *text* to a temporary WAV solely to measure its duration,
        then write a synchronized SRT/VTT caption track to *sub_path*.

        Use this when only captions are wanted (no audio file).  **Blocks**
        until synthesis is complete.
        """
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_wav = tmp.name
        try:
            self._backend.export_to_wav(text, tmp_wav)
            self._write_subtitles(text, tmp_wav, sub_path, fmt, word_level)
        finally:
            try:
                Path(tmp_wav).unlink(missing_ok=True)
            except Exception:
                pass
