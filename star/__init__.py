"""star — Speaking Terminal Access Reader (package).

Refactored from the original single-file ``star.py`` into logical
submodules.  Public entry point: ``star.app.main`` (also ``python -m star``
and the ``star`` console script).
"""
from ._runtime import __author__, __copyright__, __license__, __version__
from .app import main
from .feeds import fetch_feed
from .flashcards import export_anki_deck
from .spellcheck import misspelled_words
from .summarize import summarize_document
from . import syllables  # noqa: F401  (register in sys.modules so refresh_feature works)
from .translate import translate_text
from .vocab import find_difficult_words

__all__ = [
    "main",
    "summarize_document",
    "export_anki_deck",
    "misspelled_words",
    "translate_text",
    "fetch_feed",
    "find_difficult_words",
    "__version__",
    "__author__",
    "__copyright__",
    "__license__",
]
