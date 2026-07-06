"""AppleSayBackend (macOS `say`)."""
from .._runtime import *  # noqa: F401,F403
from .base import TTSBackend


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
                    stderr=subprocess.DEVNULL, creationflags=_SUBPROCESS_FLAGS)
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
                [self._bin, "-v", "?"], stderr=subprocess.DEVNULL, text=True, creationflags=_SUBPROCESS_FLAGS)
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
            stderr=subprocess.DEVNULL, creationflags=_SUBPROCESS_FLAGS)
        if proc.stdin:
            proc.stdin.write(text.encode("utf-8", errors="replace"))
            proc.stdin.close()
        proc.wait()
        if proc.returncode not in (0, None):
            raise RuntimeError(f"say exited with code {proc.returncode}")

    @property
    def speaking(self) -> bool:
        return self._speaking
