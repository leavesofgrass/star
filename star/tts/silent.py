"""SilentBackend — the no-op fallback engine."""
from .._runtime import *  # noqa: F401,F403
from .base import TTSBackend


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
