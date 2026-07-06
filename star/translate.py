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


# deep-translator's Google backend hard-rejects requests of >= 5000 chars
# (is_input_valid raises NotValidLength before any network call), so real
# documents must be translated in pieces.  4500 leaves headroom.
_CHUNK_LIMIT = 4500


def _units(text: str, limit: int) -> "List[Tuple[str, str]]":
    """Split *text* into (piece, following_separator) units, each <= *limit*.

    Prefers paragraph boundaries, falls back to sentence boundaries inside an
    oversized paragraph, and hard-slices only a pathological unbroken run.
    Joining ``piece + sep`` for every unit reproduces *text* exactly.
    """
    out: List[Tuple[str, str]] = []
    paragraphs = text.split("\n\n")
    for i, par in enumerate(paragraphs):
        sep = "\n\n" if i < len(paragraphs) - 1 else ""
        if len(par) <= limit:
            out.append((par, sep))
            continue
        sentences = re.split(r"(?<=[.!?…])\s+", par)
        for j, sent in enumerate(sentences):
            ssep = " " if j < len(sentences) - 1 else sep
            while len(sent) > limit:  # e.g. base64 blob / no punctuation
                out.append((sent[:limit], ""))
                sent = sent[limit:]
            out.append((sent, ssep))
    return out


def _chunk_text(text: str, limit: int = _CHUNK_LIMIT) -> "List[Tuple[str, str]]":
    """Pack the units of *text* into (chunk, following_separator) pieces.

    Greedy packing keeps the number of network round-trips low while
    guaranteeing every chunk stays under the backend's request limit; the
    separators are preserved so the translated pieces reassemble with the
    original paragraph/sentence structure.
    """
    chunks: List[Tuple[str, str]] = []
    buf, buf_sep = "", ""
    for piece, sep in _units(text, limit):
        candidate = f"{buf}{buf_sep}{piece}" if buf else piece
        if buf and len(candidate) > limit:
            chunks.append((buf, buf_sep))
            buf, buf_sep = piece, sep
        else:
            buf, buf_sep = candidate, sep
    if buf:
        chunks.append((buf, buf_sep))
    return chunks


def translate_text(
    text: str,
    target_lang: str = "en",
    source_lang: str = "auto",
    progress: "Optional[Callable[[int, int], None]]" = None,
) -> str:
    """Translate *text* into *target_lang* using Google Translate.

    *target_lang* / *source_lang* are ISO-639-1 codes (``source_lang="auto"``
    asks the backend to detect the source language).  An empty input yields an
    empty string.

    Long documents are translated in pieces (the backend rejects requests of
    5000+ characters) and reassembled with their paragraph structure intact.
    *progress*, when given, is called as ``progress(done_so_far, total_pieces)``
    before each piece is sent — the GUI uses it for "part 3 of 8" status.

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
    chunks = _chunk_text(text)
    out: List[str] = []
    for idx, (piece, sep) in enumerate(chunks):
        if progress is not None:
            progress(idx + 1, len(chunks))
        if not piece.strip():  # blank runs need no network call
            out.append(piece + sep)
            continue
        out.append((translator.translate(piece) or "") + sep)
    return "".join(out).strip()
