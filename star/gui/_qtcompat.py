"""PyQt5/PyQt6 enum-compatibility constants, shared across the GUI package.

Several Qt enums were reorganized between PyQt5 and PyQt6 (nested enum scopes
in PyQt6 vs. top-level attributes in PyQt5).  The GUI resolves each once and
refers to the resolved constant everywhere else.

These constants depend only on the installed PyQt version, not on any runtime
state, so they live at module scope where ``StarWindow`` and its mixin modules
can import them:

    from ._qtcompat import _USER_ROLE, _QUEUED, _KEEP_ANCHOR

IMPORT SAFETY: this module references Qt names (``Qt``, ``QTextCursor``, …) at
module scope, so it is **only import-safe when PyQt is installed**.  Like
``help_window.py`` and ``graph_view.py``, it must be imported lazily — from
inside ``_run_qt_gui`` or a StarWindow method — never at the top of an eagerly
imported module.  ``runner.py`` keeps ``import star.gui`` safe without PyQt by
importing this module only after its ``_QT`` check passes.
"""
from .._runtime import *  # noqa: F401,F403

# QTextCursor.MoveMode enum was reorganized in PyQt6; handle both.
try:
    _KEEP_ANCHOR = QTextCursor.MoveMode.KeepAnchor  # PyQt6
except AttributeError:
    _KEEP_ANCHOR = QTextCursor.KeepAnchor  # PyQt5  # type: ignore[attr-defined]

# QueuedConnection constant also changed location.
try:
    _QUEUED = Qt.ConnectionType.QueuedConnection  # PyQt6
except AttributeError:
    _QUEUED = Qt.QueuedConnection  # PyQt5  # type: ignore[attr-defined]

# DockWidgetArea enum (PyQt6 uses nested enum; PyQt5 uses top-level).
try:
    _LEFT_DOCK = Qt.DockWidgetArea.LeftDockWidgetArea  # PyQt6
    _RIGHT_DOCK = Qt.DockWidgetArea.RightDockWidgetArea  # PyQt6
except AttributeError:
    _LEFT_DOCK = Qt.LeftDockWidgetArea  # type: ignore[attr-defined]  # PyQt5
    _RIGHT_DOCK = Qt.RightDockWidgetArea  # type: ignore[attr-defined]  # PyQt5

# ItemDataRole.UserRole enum (PyQt6 nested; PyQt5 top-level).
try:
    _USER_ROLE = Qt.ItemDataRole.UserRole  # PyQt6
except AttributeError:
    _USER_ROLE = Qt.UserRole  # type: ignore[attr-defined]  # PyQt5

# Enums used by the reading-accessibility features (spacing, reading aids,
# highlight tuning).  Each was reorganized between PyQt5 and 6.
try:
    _PROPORTIONAL = QTextBlockFormat.LineHeightTypes.ProportionalHeight  # PyQt6
except AttributeError:
    _PROPORTIONAL = QTextBlockFormat.ProportionalHeight  # type: ignore[attr-defined]
try:
    _DOC_SELECTION = QTextCursor.SelectionType.Document  # PyQt6
except AttributeError:
    _DOC_SELECTION = QTextCursor.Document  # type: ignore[attr-defined]
try:
    _FULL_WIDTH_SEL = QTextFormat.Property.FullWidthSelection  # PyQt6
except AttributeError:
    _FULL_WIDTH_SEL = QTextFormat.FullWidthSelection  # type: ignore[attr-defined]
try:
    _PCT_SPACING = QFont.SpacingType.PercentageSpacing  # PyQt6
except AttributeError:
    _PCT_SPACING = QFont.PercentageSpacing  # type: ignore[attr-defined]
try:
    _SINGLE_UNDERLINE = QTextCharFormat.UnderlineStyle.SingleUnderline  # PyQt6
    _WAVE_UNDERLINE = QTextCharFormat.UnderlineStyle.WaveUnderline
except AttributeError:
    _SINGLE_UNDERLINE = QTextCharFormat.SingleUnderline  # type: ignore[attr-defined]
    _WAVE_UNDERLINE = QTextCharFormat.WaveUnderline  # type: ignore[attr-defined]

# WA_StyledBackground widget attribute (PyQt6 nested; PyQt5 top-level).
try:
    _WA_STYLED_BG = Qt.WidgetAttribute.WA_StyledBackground  # PyQt6
except AttributeError:
    _WA_STYLED_BG = Qt.WA_StyledBackground  # type: ignore[attr-defined]  # PyQt5
