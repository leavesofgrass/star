"""star — Speaking Terminal Access Reader (package).

Refactored from the original single-file ``star.py`` into logical
submodules.  Public entry point: ``star.app.main`` (also ``python -m star``
and the ``star`` console script).
"""
from ._runtime import __author__, __copyright__, __license__, __version__
from .app import main

__all__ = ["main", "__version__", "__author__", "__copyright__", "__license__"]
