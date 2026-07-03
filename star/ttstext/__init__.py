"""Text preprocessing for TTS: SSML/DECtalk markup, abbreviation and
pronunciation expansion, number/date normalization, table narration
(package split from ttstext.py).

Re-exports the full public surface of the former ``star/ttstext.py`` module so
every ``from star.ttstext import X`` / ``from ..ttstext import X`` keeps
resolving unchanged.
"""
from .._runtime import *  # noqa: F401,F403

from .markdown import _strip_markdown_for_tts
from .ssml import _text_to_dectalk, _text_to_ssml
from .abbreviations import (
    _ABBREV_PAIRS,
    _ABBREV_RE,
    _apply_pronunciations,
    _expand_abbreviations,
)
from .numbers import (
    _MONTHS_NUM,
    _ONES,
    _TENS,
    _decimal_digits_to_words,
    _int_to_words,
    _normalize_numbers,
    _ordinal_to_words,
    _year_to_words,
)
from .tables import _tables_to_narration
from .mathspeech import _normalize_math_inline
from .pipeline import _preprocess_tts_text

# Explicit re-export surface (mirrors the old flat module).  These are the names
# defined in the original ``ttstext.py``; the shared ``_runtime`` namespace
# (re, List, Dict, Settings, …) is re-exported by the ``import *`` above.
__all__ = [
    "_strip_markdown_for_tts",
    "_text_to_ssml",
    "_text_to_dectalk",
    "_ABBREV_PAIRS",
    "_ABBREV_RE",
    "_expand_abbreviations",
    "_apply_pronunciations",
    "_ONES",
    "_TENS",
    "_MONTHS_NUM",
    "_int_to_words",
    "_year_to_words",
    "_ordinal_to_words",
    "_decimal_digits_to_words",
    "_normalize_numbers",
    "_tables_to_narration",
    "_preprocess_tts_text",
    "_normalize_math_inline",
]
