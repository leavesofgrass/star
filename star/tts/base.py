"""TTSBackend — abstract base class for all speech engines."""
import abc

from .._runtime import *  # noqa: F401,F403


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
