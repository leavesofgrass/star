"""CloudBackend — abstract base for opt-in cloud (online) neural TTS engines.

Data-egress / consent contract (read before extending)
------------------------------------------------------
A cloud backend transmits the text being read to a remote service.  To keep
star's offline-first promise, that only ever happens when the user has made an
*explicit* two-step opt-in:

1. an API key for the provider is configured in settings, and
2. the cloud voice is chosen as the active TTS engine.

``available()`` is therefore keyed **only** on whether a key is configured — it
performs no network probe, so merely having a key present never causes traffic;
real synthesis (and the first byte of egress) happens in :meth:`speak`.  Cloud
backends use a high ``priority`` so ``auto`` selection never reaches them; they
are opt-in only, exactly like Piper/Coqui.

On any failure — no key, DNS/timeout, HTTP error, malformed response — the
backend raises :class:`CloudTTSError`.  ``TTSManager`` treats that as a
recoverable signal and falls back to a local engine.  A cloud backend must
never surface a dead end or a "run pip" message.
"""
import urllib.error  # noqa: F401  (urllib.request is star-imported, .error is not)

from ..._runtime import *  # noqa: F401,F403
from ..base import TTSBackend
from ..coqui import CoquiBackend  # reused only for its cross-platform WAV player

# Cloud voices are opt-in only.  ``priority`` orders auto-selection lowest-first,
# so this deliberately-high value sorts cloud engines *last* — well after every
# local engine (Piper 100, Coqui 110).  They are also in TTSManager._AUTO_SKIP,
# so ``auto`` never lands here; egress happens only on an explicit user pick.
CLOUD_PRIORITY = 900


class CloudTTSError(RuntimeError):
    """A cloud synthesis attempt failed **recoverably**.

    Raised for a missing/blank API key, a network error (DNS, timeout, refused
    connection), a non-2xx HTTP response, or an unparseable body.  It is caught
    by :class:`~star.tts.manager.TTSManager` as a signal to fall back to a local
    engine, so the message is a diagnostic for logs — never a user dead end and
    never an instruction to install anything.
    """


class CloudBackend(TTSBackend):
    """Abstract base for cloud neural-voice backends.

    Concrete providers implement :meth:`_synth_bytes` (one urllib POST that
    returns audio bytes) and :meth:`list_voices`; everything else — key
    retrieval, playback threading, availability gating, WAV export — is shared
    here.  Audio is written to a temp WAV and played through the same
    cross-platform player the local Piper/Coqui backends use, so cloud audio
    reaches the existing playback path unchanged.
    """

    #: Concrete subclasses set this.
    name = "cloud"
    priority = CLOUD_PRIORITY

    #: Settings key that holds this provider's API key.  Subclasses override.
    #: The value is read on demand and **never logged**.
    api_key_setting: str = ""

    #: Network timeout (seconds) for a single request.
    request_timeout: float = 30.0

    def __init__(
        self,
        rate: int = 265,
        volume: float = 1.0,
        voice: str = "",
        api_key: str = "",
    ) -> None:
        self._rate = rate
        self._volume = volume
        self._voice = voice
        # An explicit key wins; otherwise it is pulled from settings lazily in
        # _get_api_key() so a key added mid-session is picked up.
        self._api_key = api_key
        self._speaking = False
        self._stop_flag = threading.Event()
        self._play_proc: Optional[subprocess.Popen] = None

    # ── API-key retrieval (never logged) ─────────────────────────────────────

    def _get_api_key(self) -> str:
        """Return the configured API key, or "" when none is set.

        Order: an explicit key passed to the constructor, then the
        ``api_key_setting`` value from the persisted settings, then the matching
        environment variable (upper-cased setting name).  The key is returned
        raw to the caller but is **never** written to logs or error messages.
        """
        if self._api_key:
            return self._api_key.strip()
        # Read from settings lazily so a key configured after construction (the
        # common first-run flow) is honoured without rebuilding the backend.
        key = ""
        if self.api_key_setting:
            try:
                from ...settings import Settings

                key = str(Settings().get(self.api_key_setting, "") or "")
            except Exception:
                key = ""
            if not key:
                env_name = self.api_key_setting.upper()
                key = str(os.environ.get(env_name, "") or "")
        return key.strip()

    def set_api_key(self, key: str) -> None:
        """Set the in-memory API key (used by tests and explicit callers)."""
        self._api_key = key or ""

    # ── availability: keyed on config only, never on a network probe ─────────

    def available(self) -> bool:
        """True iff an API key is configured.

        Deliberately does **no** network call: a probe here would send traffic
        (and could block the UI) merely because the backend was constructed.
        A key present but wrong surfaces as a :class:`CloudTTSError` at
        :meth:`speak` time, where the manager can fall back.
        """
        return bool(self._get_api_key())

    # ── REST synthesis (provider-specific) ───────────────────────────────────

    def _synth_bytes(self, text: str, api_key: str) -> bytes:
        """Synthesize *text* via the provider's REST API; return audio bytes.

        Implemented per provider using ``urllib`` only.  Must raise
        :class:`CloudTTSError` on any network/API failure.  *api_key* is passed
        in (already validated non-empty) so subclasses never re-read it.
        """
        raise NotImplementedError

    def _http_post(
        self,
        url: str,
        data: bytes,
        headers: Dict[str, str],
    ) -> bytes:
        """POST *data* to *url* and return the raw response body.

        A thin ``urllib`` wrapper that converts every failure mode into a
        :class:`CloudTTSError` (so callers get one recoverable exception type)
        and never lets the API key leak into the raised message.
        """
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            # Read a short slice of the error body for diagnostics; never include
            # request headers (which carry the key).
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:200]
            except Exception:
                pass
            raise CloudTTSError(
                f"{self.name}: HTTP {exc.code} from provider. {detail}".strip()
            ) from None
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise CloudTTSError(f"{self.name}: network error ({exc}).") from None

    def _http_get_json(self, url: str, headers: Dict[str, str]) -> Any:
        """GET *url* and parse the JSON body; return ``None`` on any failure.

        Used by ``list_voices`` where a failure should degrade to an empty list
        rather than raise (voice enumeration is best-effort, not a read action).
        """
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                return json.loads(resp.read().decode("utf-8", "replace"))
        except Exception:
            return None

    # ── TTSBackend interface ─────────────────────────────────────────────────

    def speak(
        self,
        text: str,
        on_word: Optional[Callable[[int, int], None]] = None,
        on_done: Optional[Callable[[], None]] = None,
    ) -> None:
        """Synthesize *text* remotely and play it.

        Raises :class:`CloudTTSError` synchronously when no key is configured so
        the manager can fall back before any thread is spawned.  Network / API
        failures during synthesis are swallowed inside the worker thread (the
        utterance is simply silent and ``on_done`` still fires), matching the
        local backends' behaviour; the pre-flight key check is what the manager
        relies on for fallback.
        """
        self.stop()
        api_key = self._get_api_key()
        if not api_key:
            raise CloudTTSError(
                f"{self.name}: no API key configured — configure one in Settings "
                f"to use this cloud voice, or pick a local voice."
            )
        self._speaking = True
        self._stop_flag.clear()
        # Cleared per utterance; the worker records synth/playback failures
        # here (it cannot raise across threads).  The manager inspects it in
        # its on_done wrapper to fall back to a local engine — without this,
        # a present-but-invalid key (HTTP 401) "reads" the document silently.
        self.last_error = ""

        def _run() -> None:
            tmp_path = ""
            try:
                if self._stop_flag.is_set():
                    return
                audio = self._synth_bytes(text, api_key)
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp.write(audio)
                    tmp_path = tmp.name
                cmd = CoquiBackend._player_cmd(tmp_path)
                if cmd and not self._stop_flag.is_set():
                    self._play_proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    self._play_proc.wait()
            except CloudTTSError as e:
                self.last_error = str(e)  # e.g. "elevenlabs: HTTP 401 …"
            except Exception as e:
                self.last_error = f"{type(e).__name__}: {e}"
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
        if voice_id:
            self._voice = voice_id

    def export_to_wav(self, text: str, wav_path: str) -> None:
        """Synthesize *text* remotely and write the audio to *wav_path*.

        Blocking.  Raises :class:`CloudTTSError` when no key is configured or the
        request fails, so exporters can surface a recoverable failure.
        """
        api_key = self._get_api_key()
        if not api_key:
            raise CloudTTSError(f"{self.name}: no API key configured.")
        audio = self._synth_bytes(text, api_key)
        # Safety net for every cloud provider: a .wav that doesn't start with
        # a RIFF header would silently corrupt audiobook/audio exports.
        if audio[:4] != b"RIFF":
            raise CloudTTSError(
                f"{self.name}: provider returned non-WAV audio; export aborted."
            )
        Path(wav_path).write_bytes(audio)

    @property
    def speaking(self) -> bool:
        return self._speaking


# ── timing-accuracy benchmark helper (pure, dependency-free) ─────────────────


def timing_divergence(
    offsets_a: List[float],
    offsets_b: List[float],
) -> Dict[str, float]:
    """Compare two backends' per-word timing offsets and report divergence.

    Given two equal-length sequences of word-onset timestamps (seconds from the
    start of the utterance) — for example one from a cloud backend and one from
    a local backend — return a small summary of how far apart they are, useful
    for judging whether the word-highlight sync differs enough between engines to
    warrant a per-backend offset tweak.

    Parameters
    ----------
    offsets_a, offsets_b:
        Word-onset times in seconds.  Only the leading ``min(len(a), len(b))``
        words are compared, so unequal lengths are tolerated (the trailing tail
        of the longer sequence is ignored and reported in ``compared``).

    Returns
    -------
    dict with keys:
        ``compared`` — number of word pairs compared (float for a uniform type);
        ``mean_abs`` — mean absolute difference in seconds;
        ``max_abs``  — largest absolute difference in seconds;
        ``rms``      — root-mean-square difference in seconds;
        ``mean_signed`` — mean signed (a − b) difference; positive ⇒ *a* lags.

    All-zero results are returned for empty input, so callers never divide by
    zero.  Pure and dependency-free — no numpy, no I/O.
    """
    n = min(len(offsets_a), len(offsets_b))
    if n == 0:
        return {
            "compared": 0.0,
            "mean_abs": 0.0,
            "max_abs": 0.0,
            "rms": 0.0,
            "mean_signed": 0.0,
        }
    diffs = [float(offsets_a[i]) - float(offsets_b[i]) for i in range(n)]
    abs_diffs = [abs(d) for d in diffs]
    mean_abs = sum(abs_diffs) / n
    max_abs = max(abs_diffs)
    rms = (sum(d * d for d in diffs) / n) ** 0.5
    mean_signed = sum(diffs) / n
    return {
        "compared": float(n),
        "mean_abs": mean_abs,
        "max_abs": max_abs,
        "rms": rms,
        "mean_signed": mean_signed,
    }
