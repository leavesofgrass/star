"""NavigationMixin — methods extracted from StarWindow (main_window.py).

Mixed into StarWindow via ``class StarWindow(NavigationMixin, ...)``; operates
on StarWindow instance state and other methods via ``self``, holding no
state of its own.  IMPORT SAFETY: references Qt at module scope — imported
lazily by main_window.py (itself imported by runner.py after the _QT guard).

This is a package: the former single-file ``NavigationMixin`` was carved into
cohesive sub-mixins (speech cursor, core sentence/paragraph/heading/table
navigation, edit-mode + preview + save, reading-position memory).  Every
method name is unique across the sub-mixins, so MRO order is immaterial; the
assembled ``NavigationMixin`` exposes exactly the same members as before.
"""
from ._core import CoreNavMixin
from ._editing import EditNavMixin
from ._position import ReadingPositionMixin
from ._speechcursor import SpeechCursorNavMixin


class NavigationMixin(
    SpeechCursorNavMixin,
    CoreNavMixin,
    EditNavMixin,
    ReadingPositionMixin,
):
    """Core keyboard navigation for StarWindow (assembled from sub-mixins)."""

    pass


__all__ = ["NavigationMixin"]
