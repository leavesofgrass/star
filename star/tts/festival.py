"""FestivalBackend (Festival CLI)."""
from .._runtime import *  # noqa: F401,F403
from .base import TTSBackend


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
