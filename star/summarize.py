"""Extractive document summarization via sumy's LexRank algorithm.

Optional feature: requires the ``sumy`` package (``pip install sumy``).  When
it is absent the module still imports cleanly with ``_SUMY = False``, so the
rest of star runs unchanged and the GUI shows an install hint instead of the
command — the same graceful-degradation pattern every other optional feature
follows.
"""

from ._runtime import *  # noqa: F401,F403

# Detected cheaply; sumy (and the NLP stack it pulls in) is imported lazily by
# _build_summary() the first time a document is summarized.
_SUMY = _module_available("sumy")


# sumy's tokenizer, stemmer, and stop-word list are all language-specific;
# star summarizes English documents.
_LANGUAGE = "english"


def _build_summary(text: str, sentence_count: int) -> str:
    """Run LexRank over *text* and return up to *sentence_count* sentences."""
    # Deferred from startup: sumy pulls in a sizeable NLP stack.
    from sumy.nlp.stemmers import Stemmer
    from sumy.nlp.tokenizers import Tokenizer
    from sumy.parsers.plaintext import PlaintextParser
    from sumy.summarizers.lex_rank import LexRankSummarizer
    from sumy.utils import get_stop_words

    parser = PlaintextParser.from_string(text, Tokenizer(_LANGUAGE))
    summarizer = LexRankSummarizer(Stemmer(_LANGUAGE))
    summarizer.stop_words = get_stop_words(_LANGUAGE)
    sentences = summarizer(parser.document, sentence_count)
    return " ".join(str(s) for s in sentences).strip()


def summarize_document(text: str, sentence_count: int = 7) -> str:
    """Return an extractive summary of *text* using sumy's LexRank algorithm.

    *sentence_count* is the maximum number of sentences in the summary.  The
    returned string is the highest-ranked sentences joined back into a single
    paragraph; an empty input yields an empty summary.

    Raises ``RuntimeError`` with install guidance when sumy is not available,
    or when sumy's NLTK tokenizer data is missing and cannot be downloaded
    automatically.
    """
    if not _SUMY:
        raise RuntimeError("Summarization requires sumy:\n    pip install sumy")
    text = (text or "").strip()
    if not text:
        return ""
    n = max(1, int(sentence_count))
    try:
        return _build_summary(text, n)
    except LookupError:
        # sumy's Tokenizer relies on NLTK's "punkt" sentence-tokenizer data,
        # which is not bundled and is absent on a first run.  Fetch it once
        # and retry, rather than failing the whole feature — but ONLY when
        # automatic installs are allowed: this was the sole download that
        # bypassed the auto_install / STAR_NO_AUTOINSTALL kill-switch.
        from . import autodeps

        if not autodeps.enabled():
            raise RuntimeError(
                "Summarization needs NLTK tokenizer data and automatic "
                "installs are disabled.  Install it manually with:\n"
                "    python -m nltk.downloader punkt punkt_tab"
            ) from None
        try:
            import nltk

            nltk.download("punkt", quiet=True)
            nltk.download("punkt_tab", quiet=True)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Summarization needs NLTK tokenizer data and the automatic "
                "download failed.  Install it manually with:\n"
                "    python -m nltk.downloader punkt punkt_tab"
            ) from exc
        return _build_summary(text, n)
