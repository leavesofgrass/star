"""The Qt GUI, split out of the former monolithic star/gui.py.

This package replaces the single star/gui.py module.  It keeps the public
surface unchanged: `from star.gui import _run_qt_gui` (used by star/app.py)
still works via this re-export shim.  Submodules:

  * runner.py      - _run_qt_gui(): Qt setup, the crash-log hook, and launch.
  * main_window.py - StarWindow + the _RSVPOverlay widget.
  * mixin_*.py     - StarWindow's methods, grouped by responsibility.
"""
from .runner import _run_qt_gui

__all__ = ["_run_qt_gui"]
