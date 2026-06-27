"""DECtalk backends: DECtalkDLLBackend (in-process) + DECtalkBackend (CLI)."""
from .._runtime import *  # noqa: F401,F403
from .base import TTSBackend


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
