"""Speak-time TTS text preprocessing pipeline (the orchestrator)."""
from .._runtime import *  # noqa: F401,F403

from .abbreviations import _apply_pronunciations, _expand_abbreviations
from .numbers import _normalize_numbers
from .mathspeech import _normalize_math_inline


def _preprocess_tts_text(text: str, settings: "Settings") -> str:
    """Apply all speak-time text normalizations before SSML wrapping.

    Called in _tts_play_from_word() and _tts_speak_current_line() on the
    plain-text slice.  Each step is gated by its own settings flag so users
    can disable individual normalizations independently.

    Steps:
      1. Pronunciation lexicon    (use_pronunciations)
      2. Abbreviation expansion   (expand_abbreviations)
      3. Number normalization     (normalize_numbers)
    """
    # User pronunciation overrides run first so domain terms are fixed before
    # any other normalization can split or reshape them.
    if settings.get("use_pronunciations", True):
        lexicon = settings.get("pronunciations") or {}
        if lexicon:
            text = _apply_pronunciations(text, lexicon)

    if settings.get("expand_abbreviations", True):
        custom = settings.get("abbrev_expansions") or {}
        text = _expand_abbreviations(text, custom if custom else None)

    if settings.get("normalize_numbers", True):
        text = _normalize_numbers(text)

    if settings.get("normalize_math", True):
        text = _normalize_math_inline(text)

    return text
