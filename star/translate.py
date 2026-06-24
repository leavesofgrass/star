"""Document translation via deep-translator's Google Translate backend.

Optional feature: requires the ``deep-translator`` package
(``pip install deep-translator``).  When it is absent the module still imports
cleanly with ``_DEEP_TRANSLATOR = False``, so the rest of star runs unchanged
and the GUI shows an install hint instead of the command — the same
graceful-degradation pattern every other optional feature follows.

The Google backend needs no API key and no account, which keeps star's
"no cloud account required" promise intact for the offline-first features
while still offering translation to users who do have a network connection.
"""

from ._runtime import *  # noqa: F401,F403

# Detected cheaply; deep-translator (which pulls in requests + bs4) is imported
# lazily by translate_text() the first time a translation is requested.
_DEEP_TRANSLATOR = _module_available("deep_translator")


# Display name -> ISO-639-1 code.  A deliberately small, high-coverage set so
# the GUI's language picker is short enough to scan but covers the languages
# star's nursing / public-health / engineering students most often meet.
COMMON_LANGUAGES: List[Tuple[str, str]] = [
    ("English", "en"),
    ("Spanish", "es"),
    ("French", "fr"),
    ("German", "de"),
    ("Italian", "it"),
    ("Portuguese", "pt"),
    ("Dutch", "nl"),
    ("Russian", "ru"),
    ("Arabic", "ar"),
    ("Hindi", "hi"),
    ("Chinese (Simplified)", "zh-CN"),
    ("Japanese", "ja"),
    ("Korean", "ko"),
    ("Vietnamese", "vi"),
    ("Tagalog", "tl"),
]


def translate_text(
    text: str, target_lang: str = "en", source_lang: str = "auto"
) -> str:
    """Translate *text* into *target_lang* using Google Translate.

    *target_lang* / *source_lang* are ISO-639-1 codes (``source_lang="auto"``
    asks the backend to detect the source language).  An empty input yields an
    empty string.

    Raises ``RuntimeError`` with install guidance when deep-translator is not
    available.
    """
    # Empty input is a no-op that needs neither the package nor a network call,
    # so short-circuit it before the availability guard.
    text = (text or "").strip()
    if not text:
        return ""
    if not _DEEP_TRANSLATOR:
        raise RuntimeError(
            "Translation requires deep-translator:\n    pip install deep-translator"
        )
    from deep_translator import GoogleTranslator  # deferred: pulls requests + bs4

    translator = GoogleTranslator(source=source_lang, target=target_lang)
    return translator.translate(text)
