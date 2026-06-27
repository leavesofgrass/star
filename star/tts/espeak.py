"""eSpeak-NG backends: ESpeakBackend (CLI) + ESpeakLibBackend (in-process)."""
from .._runtime import *  # noqa: F401,F403
from .base import TTSBackend


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
