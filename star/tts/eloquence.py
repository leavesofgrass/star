"""EloquenceBackend — ETI-Eloquence via OpenEVV's 64-bit ECI library.

The voice many screen-reader users know from JAWS, NVDA, and Kurzweil 1000
("Reed" and family), driven in process through the ECI C interface that
OpenEVV reimplements (github.com/Mudb0y/openevv; Windows builds by
masonasons/OpenEVVWindows).  Eloquence delivers an index-mark callback at the
exact sample offset of every word, so star's karaoke highlight follows this
engine more precisely than any SAPI5 voice.

Licensing posture (decided by the project owner, 2026-09-25): OpenEVV's
engine code is open, but its language data derives from IBM's and its
authors state they cannot license it.  star therefore never bundles the
engine; it can *download* it, but only after the user explicitly
acknowledges that status in the consent dialog (see :func:`install_openevv`
and the GUI hook).  The acknowledgment is the user's licensing decision,
recorded once in settings.  Licensed alternatives are named in the dialog
and docs (Code Factory's Eloquence for Windows; Apple ships Eloquence built
in on macOS, where star's ``say`` backend already provides it).

Engine quirks, all measured against OpenEVV v0.3 x86_64 on 2026-09-25
(this file encodes them as rules — see tests/test_eloquence.py):

- ``eciSetParam(eciSampleRate, …)`` with ANY value reports success and then
  wedges the engine: every later ``eciAddText``/``eciInsertIndex`` returns
  failure.  The rate is therefore only ever QUERIED (default 11025 Hz).
- A callback answer of ``eciDataAbort`` (2) hangs ``eciSynchronize``
  forever (openevv-bugs/repro_abort_hang.py).  The callback always answers
  ``eciDataProcessed`` (1); interruption goes through ``eciStop``.
- ``eciSetVoiceParam`` (speed 6, volume 7) works normally and returns the
  previous value.  Word marks via ``eciInsertIndex`` before each word work
  in any order relative to text.

Windows-only and 64-bit-only: OpenEVV's 32-bit build exports cdecl where
IBM's interface is stdcall (TextWeaver ADR-0007), and star's CPython is
64-bit, so only the ``x86_64`` library is discovered.
"""
from .._runtime import *  # noqa: F401,F403
from .._runtime import _CFG_ROOT
from .base import TTSBackend

#: Where the consent-gated download unpacks the engine.
ELOQUENCE_DIR = _CFG_ROOT / "eloquence"

#: The pinned OpenEVV release star offers to download.  Version-pinned so the
#: consent dialog describes exactly what will be fetched; bump deliberately.
OPENEVV_VERSION = "v0.3"
OPENEVV_ZIP_URL = (
    "https://github.com/Mudb0y/openevv/releases/download/"
    f"{OPENEVV_VERSION}/openevv-{OPENEVV_VERSION}-windows-x86_64.zip"
)

# ECI constants (names from IBM's eci.h; values verified against OpenEVV).
_MSG_WAVEFORM = 0
_MSG_INDEX = 2
_DATA_PROCESSED = 1
_PARAM_SAMPLE_RATE = 5  # QUERY-ONLY — setting it wedges OpenEVV (docstring)
_VP_SPEED = 6
_VP_VOLUME = 7
_BUFFER_SAMPLES = 4096
_SAMPLE_RATES = (8000, 11025, 22050)
_ACTIVE_VOICE = 0  # slot 0 is the working voice; eciCopyVoice(h, n, 0) loads preset n

#: The eight ECI voice presets, in ``eciCopyVoice`` order, under the names the
#: classic screen readers made famous (the engine's own eciGetVoiceName labels
#: are the generic descriptors — "Adult Male 1" for Reed, and so on).  Probed
#: against OpenEVV 2026-09-26: all eight copies succeed, each changes the
#: rendered audio, and the engine stays healthy afterward.
_PRESET_VOICES: "Tuple[Tuple[str, int, str], ...]" = (
    ("reed", 1, "Reed"),  # Adult Male 1 — the engine default
    ("shelley", 2, "Shelley"),  # Adult Female 1
    ("bobby", 3, "Bobby"),  # Child 1
    ("rod", 4, "Rod"),  # Adult Male 2
    ("glen", 5, "Glen"),  # Adult Male 3
    ("sandy", 6, "Sandy"),  # Adult Female 2
    ("grandma", 7, "Grandma"),  # Elderly Female 1
    ("grandpa", 8, "Grandpa"),  # Elderly Male 1
)


def _preset_for_voice_id(voice_id: str) -> "Optional[int]":
    """Map a picker voice id to an ECI preset number (1-8), or ``None``.

    Accepts the slug (``"shelley"``), the display name in any case, or the
    preset number itself (``"2"``) — settings files and third-party callers
    have used all three shapes for other backends.
    """
    v = (voice_id or "").strip().lower()
    if not v:
        return None
    for slug, preset, _name in _PRESET_VOICES:
        if v == slug or v == str(preset):
            return preset
    return None

#: ECI speed (voice param 6, 0..=250) → measured words per minute, from
#: TextWeaver's calibration of ETI-Eloquence 6.x at 11025 Hz (Reed).  star
#: maps its WPM setting onto this curve by linear interpolation.
_RATE_POINTS: "List[Tuple[int, int]]" = [
    (0, 58), (10, 71), (20, 87), (30, 106), (40, 130), (50, 158),
    (55, 172), (60, 194), (65, 208), (70, 236), (75, 256), (80, 287),
    (85, 310), (90, 350), (95, 386), (100, 427), (105, 466), (110, 525),
    (115, 563), (120, 624), (125, 681), (130, 779), (135, 818), (140, 910),
    (160, 1350), (180, 1966), (200, 2414),
]


def _encode_for_engine(text: str) -> bytes:
    """Encode *text* as the cp1252 bytes the engine actually reads.

    ECI is a single-byte-codepage engine, not a UTF-8 one: fed UTF-8, an
    em-dash (U+2014 → E2 80 94) is spoken as "a-circumflex, euro" — the
    first live bug report against this backend.  cp1252 carries the common
    typography natively (em/en dashes, curly quotes, the ellipsis), and
    Windows' own ``WideCharToMultiByte`` best-fit conversion folds most of
    the rest to sensible lookalikes instead of question marks — the approach
    the OpenEVV NVDA add-on settled on after a plain ASCII fold proved
    "wrong twice over" (its textproc.py).  Falls back to Python's cp1252
    with replacement when the Win32 call is unavailable.
    """
    if _WIDE_CHAR_TO_MULTI_BYTE is not None:
        try:
            import ctypes

            n = _WIDE_CHAR_TO_MULTI_BYTE(
                1252, 0, text, len(text), None, 0, None, None
            )
            if n > 0:
                buf = ctypes.create_string_buffer(n)
                _WIDE_CHAR_TO_MULTI_BYTE(
                    1252, 0, text, len(text), buf, n, None, None
                )
                return buf.raw[:n]
        except Exception:  # noqa: BLE001 — fall through to the pure encoder
            pass
    return text.encode("cp1252", "replace")


try:
    import ctypes as _ct_probe

    _WIDE_CHAR_TO_MULTI_BYTE = _ct_probe.windll.kernel32.WideCharToMultiByte
except (ImportError, AttributeError, OSError):
    _WIDE_CHAR_TO_MULTI_BYTE = None


def _speed_for_wpm(wpm: float) -> int:
    """The ECI speed whose measured rate best matches *wpm* (clamped)."""
    try:
        w = float(wpm)
    except (TypeError, ValueError):
        return 50
    if w <= _RATE_POINTS[0][1]:
        return _RATE_POINTS[0][0]
    for (s0, w0), (s1, w1) in zip(_RATE_POINTS, _RATE_POINTS[1:]):
        if w <= w1:
            frac = (w - w0) / (w1 - w0) if w1 > w0 else 0.0
            return round(s0 + frac * (s1 - s0))
    return _RATE_POINTS[-1][0]


def find_eci_library() -> "Optional[str]":
    """Locate a 64-bit OpenEVV ``eci.dll``, or ``None``.

    First existing file wins:

    1. ``STAR_ECI_LIBRARY`` — an explicit path (any ECI-compatible library).
    2. star's own consent-gated install (:data:`ELOQUENCE_DIR`).
    3. The OpenEVVWindows SAPI5 installer's location in Program Files.
    4. The OpenEVV NVDA add-on's bundled engine.
    """
    override = os.environ.get("STAR_ECI_LIBRARY", "").strip()
    if override:
        return override if Path(override).is_file() else None
    candidates = [
        ELOQUENCE_DIR / "eci-x86_64" / "eci.dll",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "OpenEVV" / "lib_64" / "eci.dll",
        Path(os.environ.get("APPDATA", "")) / "nvda" / "addons" / "openevv"
        / "synthDrivers" / "_openevv" / "lib" / "x86_64" / "eci.dll",
    ]
    for c in candidates:
        try:
            if c.is_file():
                return str(c)
        except OSError:
            continue
    return None


def license_acknowledged(settings: Any) -> bool:
    """Whether the user has recorded the OpenEVV licensing acknowledgment."""
    try:
        return bool(settings.get("eloquence_license_ack", False))
    except Exception:  # noqa: BLE001
        return False


#: The consent dialog / TUI prompt text.  Shown before any download; the
#: user's Yes is recorded in settings as ``eloquence_license_ack``.
CONSENT_TEXT = (
    "star can download OpenEVV {version}, a community reimplementation of the "
    "ETI-Eloquence speech engine (the classic screen-reader voice).\n\n"
    "OpenEVV's program code is open source, but its language data derives "
    "from IBM's ViaVoice, and OpenEVV's own authors state they cannot "
    "license that data. No one can grant you a license to it through this "
    "download. Whether to install and use it is your decision.\n\n"
    "Licensed alternatives: Code Factory sells Eloquence for Windows "
    "(codefactoryglobal.com); on macOS, Apple ships the Eloquence voices "
    "built in, and star already uses them.\n\n"
    "Download OpenEVV {version} (~4 MB) from its GitHub releases?"
)


def install_openevv(settings: Any, *, acknowledged: bool) -> "Optional[str]":
    """Download and unpack the pinned OpenEVV release; return the dll path.

    Refuses (returns ``None``) unless *acknowledged* is True — the caller
    must have shown :data:`CONSENT_TEXT` and received an explicit yes, which
    is then recorded so the dialog is one-time.  Honors the global
    ``STAR_NO_AUTOINSTALL`` opt-out like every other on-demand install.
    Extracts only the 64-bit engine plus OpenEVV's own README/NOTICE/LICENSE
    (kept beside it for provenance).
    """
    if not acknowledged or os.environ.get("STAR_NO_AUTOINSTALL"):
        return None
    try:
        settings.set("eloquence_license_ack", True)
    except Exception:  # noqa: BLE001
        pass
    import io
    import urllib.request
    import zipfile as _zipfile

    try:
        with urllib.request.urlopen(OPENEVV_ZIP_URL, timeout=120) as resp:
            data = resp.read()
        ELOQUENCE_DIR.mkdir(parents=True, exist_ok=True)
        with _zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                # Only the payload star uses; no absolute paths or traversal.
                if name.startswith("eci-x86_64/") or name in (
                    "LICENSE", "NOTICE", "README.md",
                ):
                    z.extract(name, ELOQUENCE_DIR)
        dll = ELOQUENCE_DIR / "eci-x86_64" / "eci.dll"
        return str(dll) if dll.is_file() else None
    except Exception:  # noqa: BLE001 — surfaced by the caller as a status message
        return None


class _EciEngine:
    """Thin ctypes wrapper owning one ECI handle on one thread.

    ECI answers callbacks on the thread that calls into it, and the NVDA
    driver's rule ("every method from the one thread") is adopted wholesale:
    :class:`EloquenceBackend` creates this object on its worker thread and
    never touches it from another.
    """

    def __init__(self, dll_path: str):
        import ctypes

        self._ct = ctypes
        try:
            self._cookie = os.add_dll_directory(os.path.dirname(dll_path))
        except (AttributeError, OSError):
            self._cookie = None
        self._lib = ctypes.WinDLL(dll_path)
        self._CB = ctypes.WINFUNCTYPE(
            ctypes.c_int, ctypes.c_void_p, ctypes.c_int,
            ctypes.c_long, ctypes.c_void_p,
        )
        lib = self._lib
        lib.eciNew.restype = ctypes.c_void_p
        lib.eciDelete.argtypes = [ctypes.c_void_p]
        lib.eciAddText.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.eciInsertIndex.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.eciSynthesize.argtypes = [ctypes.c_void_p]
        lib.eciSynchronize.argtypes = [ctypes.c_void_p]
        lib.eciStop.argtypes = [ctypes.c_void_p]
        lib.eciRegisterCallback.argtypes = [
            ctypes.c_void_p, self._CB, ctypes.c_void_p,
        ]
        lib.eciSetOutputBuffer.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
        ]
        lib.eciGetParam.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.eciSetVoiceParam.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ]
        lib.eciGetVoiceParam.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
        ]
        lib.eciCopyVoice.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]

        self._h = ctypes.c_void_p(lib.eciNew())
        if not self._h:
            raise RuntimeError("eciNew returned no engine instance")
        #: Which preset the working voice holds; None until a copy is made
        #: (a fresh engine starts on the Reed voicing without one).
        self.loaded_preset: "Optional[int]" = None
        self._buf = (ctypes.c_short * _BUFFER_SAMPLES)()
        self._pcm = bytearray()
        self._marks: "List[Tuple[int, int]]" = []  # (index, sample_offset)
        self._samples = 0
        # Kept on the instance: the engine holds this pointer for life.
        self._cb = self._CB(self._on_message)
        lib.eciRegisterCallback(self._h, self._cb, None)
        if not lib.eciSetOutputBuffer(self._h, _BUFFER_SAMPLES, self._buf):
            raise RuntimeError("eciSetOutputBuffer was refused")
        # QUERY-ONLY: setting eciSampleRate wedges OpenEVV (module docstring).
        code = lib.eciGetParam(self._h, _PARAM_SAMPLE_RATE)
        self.sample_rate = _SAMPLE_RATES[max(0, min(int(code), 2))]

    def _on_message(self, _h, msg, lparam, _data):  # noqa: ANN001
        if msg == _MSG_WAVEFORM:
            n = int(lparam)
            self._pcm += self._ct.string_at(self._buf, n * 2)
            self._samples += n
        elif msg == _MSG_INDEX:
            self._marks.append((int(lparam), self._samples))
        return _DATA_PROCESSED  # NEVER eciDataAbort: it hangs eciSynchronize

    def load_preset(self, preset: int) -> bool:
        """Copy ECI preset *preset* (1-8) into the working voice.

        A copy replaces **every** setting of the working voice, so callers
        must re-apply speed and volume afterward (``speak`` always does).
        """
        ok = bool(self._lib.eciCopyVoice(self._h, int(preset), _ACTIVE_VOICE))
        if ok:
            self.loaded_preset = int(preset)
        return ok

    def set_speed(self, speed: int) -> None:
        self._lib.eciSetVoiceParam(self._h, 0, _VP_SPEED, int(speed))

    def set_volume(self, volume_0_100: int) -> None:
        self._lib.eciSetVoiceParam(
            self._h, 0, _VP_VOLUME, max(0, min(100, int(volume_0_100)))
        )

    def synth_marked(
        self, words: "List[str]"
    ) -> "Tuple[bytes, List[Tuple[int, int]]]":
        """Synthesize *words* with an index mark before each.

        Returns ``(pcm16_mono, [(word_index, sample_offset), …])``.  Blocks
        until the engine finishes (synthesis runs far faster than playback).
        """
        self._pcm = bytearray()
        self._marks = []
        self._samples = 0
        for i, w in enumerate(words):
            self._lib.eciInsertIndex(self._h, i)
            # cp1252, never UTF-8 — see _encode_for_engine (the em-dash bug).
            self._lib.eciAddText(self._h, _encode_for_engine(w + " "))
        self._lib.eciSynthesize(self._h)
        self._lib.eciSynchronize(self._h)
        return bytes(self._pcm), list(self._marks)

    def stop(self) -> None:
        try:
            self._lib.eciStop(self._h)
        except Exception:  # noqa: BLE001
            pass

    def close(self) -> None:
        if self._h:
            try:
                self._lib.eciDelete(self._h)
            except Exception:  # noqa: BLE001
                pass
            self._h = None
        if self._cookie is not None:
            try:
                self._cookie.close()
            except OSError:
                pass


class EloquenceBackend(TTSBackend):
    """ETI-Eloquence (OpenEVV) — exact word timing, in process, Windows."""

    name = "eloquence"
    # 18: above pyttsx3 (20), so a machine where the user installed Eloquence
    # speaks with it by default — installing it IS the opt-in (and it is
    # star's own tts_prefer_voice default).  available() is False everywhere
    # the engine is absent and off Windows, so nothing else changes.
    priority = 18

    def __init__(self, rate: int = 265, volume: float = 1.0, voice: str = ""):
        self._rate = int(rate)
        self._volume = max(0.0, min(1.0, float(volume)))
        self._voice = voice  # an ECI preset id — see _PRESET_VOICES
        self._engine: "Optional[_EciEngine]" = None
        self._gen = 0
        self._speaking = False
        self._stop_evt = threading.Event()

    @classmethod
    def available(cls) -> bool:
        return sys.platform == "win32" and find_eci_library() is not None

    # -- engine lifecycle (worker-thread only) ------------------------------

    def _ensure_engine(self) -> "Optional[_EciEngine]":
        if self._engine is not None:
            return self._engine
        path = find_eci_library()
        if not path:
            return None
        try:
            self._engine = _EciEngine(path)
        except Exception:  # noqa: BLE001 — unavailable is a normal outcome
            self._engine = None
        return self._engine

    # -- TTSBackend interface ------------------------------------------------

    def speak(
        self,
        text: str,
        on_word: "Optional[Callable[[int, int], None]]" = None,
        on_done: "Optional[Callable[[], None]]" = None,
    ) -> None:
        self.stop()
        self._gen += 1
        my_gen = self._gen
        self._stop_evt.clear()
        self._speaking = True

        # Sentence chunks bound how much audio is queued, so a stop request
        # silences within the current chunk (the espeaklib pattern; its
        # splitter is reused verbatim).
        from .espeak import ESpeakLibBackend

        chunks = ESpeakLibBackend._chunk_offsets(text)

        def _run() -> None:
            import winsound

            try:
                eng = self._ensure_engine()
                if eng is None:
                    return
                preset = _preset_for_voice_id(self._voice)
                if preset is not None and eng.loaded_preset != preset:
                    eng.load_preset(preset)
                # Always after any preset copy: a copy replaces every voice
                # setting, including these two.
                eng.set_speed(_speed_for_wpm(self._rate))
                eng.set_volume(round(self._volume * 100))
                for chunk_text, base in chunks:
                    if self._gen != my_gen or self._stop_evt.is_set():
                        break
                    words = _split_words(chunk_text)
                    if not words:
                        continue
                    pcm, marks = eng.synth_marked([w for w, _off in words])
                    if not pcm or self._gen != my_gen or self._stop_evt.is_set():
                        break
                    # winsound refuses SND_MEMORY|SND_ASYNC ("cannot play
                    # asynchronously from memory"), so the synchronous
                    # from-memory play runs on its own thread while this one
                    # paces the word marks; stop() purges it with
                    # PlaySound(None, 0), which unblocks the player thread.
                    wav = _wav_bytes(pcm, eng.sample_rate)
                    player = threading.Thread(
                        target=winsound.PlaySound,
                        args=(wav, winsound.SND_MEMORY),
                        daemon=True,
                        name="star-eloquence-play",
                    )
                    player.start()
                    start = time.monotonic()
                    end_s = len(pcm) / 2 / eng.sample_rate
                    if on_word:
                        for idx, sample in marks:
                            if idx >= len(words):
                                continue
                            target = start + sample / eng.sample_rate
                            delay = target - time.monotonic()
                            if delay > 0 and self._stop_evt.wait(delay):
                                break
                            if self._gen != my_gen or self._stop_evt.is_set():
                                break
                            word, off = words[idx]
                            try:
                                on_word(base + off, len(word))
                            except Exception:  # noqa: BLE001
                                pass
                    # Let the chunk finish playing before the next begins.
                    remain = (start + end_s) - time.monotonic()
                    if remain > 0 and self._stop_evt.wait(remain):
                        break
            except Exception:  # noqa: BLE001 — a broken engine must not wedge TTS
                pass
            finally:
                if self._gen == my_gen:
                    self._speaking = False
                    try:
                        winsound.PlaySound(None, 0)
                    except Exception:  # noqa: BLE001
                        pass
                    if on_done:
                        try:
                            on_done()
                        except Exception:  # noqa: BLE001
                            pass

        threading.Thread(target=_run, daemon=True, name="star-eloquence").start()

    def stop(self) -> None:
        self._stop_evt.set()
        self._speaking = False
        eng = self._engine
        if eng is not None:
            eng.stop()
        if sys.platform == "win32":
            try:
                import winsound

                winsound.PlaySound(None, 0)
            except Exception:  # noqa: BLE001
                pass

    def set_rate(self, wpm: int) -> None:
        self._rate = int(wpm)

    def set_volume(self, vol: float) -> None:
        self._volume = max(0.0, min(1.0, float(vol)))

    def set_voice(self, voice_id: str) -> None:
        self._voice = voice_id or ""

    def list_voices(self) -> "List[Dict[str, str]]":
        if not self.available():
            return []
        return [
            {"id": slug, "name": f"{name} (Eloquence)", "lang": "en-US"}
            for slug, _preset, name in _PRESET_VOICES
        ]

    @property
    def speaking(self) -> bool:
        return self._speaking


def _split_words(chunk: str) -> "List[Tuple[str, int]]":
    """``(word, char_offset)`` for each whitespace-separated token."""
    out: "List[Tuple[str, int]]" = []
    i = 0
    for w in chunk.split():
        j = chunk.index(w, i)
        out.append((w, j))
        i = j + len(w)
    return out


def _wav_bytes(pcm: bytes, sample_rate: int) -> bytes:
    """Wrap 16-bit mono PCM in a WAV header for winsound's SND_MEMORY."""
    import io
    import wave

    bio = io.BytesIO()
    with wave.open(bio, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return bio.getvalue()
