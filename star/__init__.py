"""star — Speaking Terminal Access Reader (package).

Refactored from the original single-file ``star.py`` into logical
submodules.  Public entry point: ``star.app.main`` (also ``python -m star``
and the ``star`` console script).
"""
from ._runtime import __author__, __copyright__, __license__, __version__
from .app import main
from .flashcards import export_anki_deck
from .spellcheck import misspelled_words
from .summarize import summarize_document

__all__ = [
    "main",
    "summarize_document",
    "export_anki_deck",
    "misspelled_words",
    "__version__",
    "__author__",
    "__copyright__",
    "__license__",
]
