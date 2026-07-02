"""First-run optional-feature chooser (the "selection menu").

star runs fully out of the box; heavier capabilities are optional Python packages
with graceful fallbacks. Rather than silently fetching everything, this dialog
explains each feature group, offers two presets (**Thin** and **All**), and lets
the user pick exactly what to fetch. It is shown once on first launch
(:func:`maybe_prompt`) and re-openable from *Tools → Install Optional Features…*.
Installation itself is delegated to :mod:`star.autodeps` (background, best-effort).

IMPORT SAFETY: references Qt at module scope — imported lazily (never at package
import time), like the other gui dialogs.
"""
from __future__ import annotations

from .._runtime import *  # noqa: F401,F403  (Qt widgets: QDialog, QCheckBox, …)
from .. import autodeps
from .. import diagnostics
from ..i18n import available_languages, get_language, set_language, tr

try:  # QScrollArea / QComboBox aren't re-exported by _runtime
    from PyQt6.QtWidgets import QComboBox, QScrollArea
except ImportError:  # PyQt5
    from PyQt5.QtWidgets import QComboBox, QScrollArea  # type: ignore


class DependencyChooser(QDialog):
    def __init__(self, window=None) -> None:
        super().__init__(window)
        self._win = window
        self.setWindowTitle(tr("star — Optional Features"))
        self.resize(600, 560)
        self._boxes: dict[str, QCheckBox] = {}
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)

        self._build_language_row(root)

        intro = QLabel(
            tr(
                "<b>star works right now with nothing extra.</b> These optional "
                "features add capabilities by fetching a few Python packages. Pick "
                "what you'd like — you can change this any time from "
                "<i>Tools → Install Optional Features</i>.<br><br>"
                "<b>Thin</b> — the lightweight everyday reading and study aids.&nbsp; "
                "<b>All</b> — everything star can use (large speech-to-text and "
                "entity-extraction packs stay unchecked; tick them yourself)."
            ),
            self,
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        presets = QHBoxLayout()
        thin = QPushButton(tr("Thin  (~40 MB)"), self)
        _thin_tip = tr("Everyday reading & study aids only — no OCR, graph, or "
                       "large ML packs.")
        thin.setToolTip(_thin_tip)
        thin.setAccessibleName(tr("Thin preset"))
        thin.setAccessibleDescription(_thin_tip)
        thin.clicked.connect(lambda: self._apply_preset("thin"))
        allb = QPushButton(tr("All  (~150 MB)   — recommended"), self)
        _all_tip = tr("Everything except the very large speech-to-text and "
                      "named-entity packs.")
        allb.setToolTip(_all_tip)
        allb.setAccessibleName(tr("All preset"))
        allb.setAccessibleDescription(_all_tip)
        allb.clicked.connect(lambda: self._apply_preset("all"))
        presets.addWidget(thin)
        presets.addWidget(allb)
        presets.addStretch(1)
        root.addLayout(presets)

        # One checkbox per feature (light -> heavy) inside a scroll area, each with
        # its purpose, size, and install status.
        inner = QWidget(self)
        col = QVBoxLayout(inner)
        col.setContentsMargins(4, 4, 4, 4)
        for key in autodeps.FEATURE_INFO:
            label, detail, mb = autodeps.FEATURE_INFO[key]
            present = autodeps.feature_installed(key)
            size = (tr("installed") if present
                    else (f"~{mb} MB" if mb < 1000 else f"~{mb / 1000:.1f} GB"))
            cb = QCheckBox(f"{tr(label)}   ({size})", self)
            cb.setToolTip(detail)
            # Screen readers don't reliably associate the adjacent gray
            # sub-label with the checkbox, so mirror the detail text into the
            # checkbox's own accessible description.
            cb.setAccessibleName(f"{tr(label)} ({size})")
            cb.setAccessibleDescription(detail)
            sub = QLabel(f"    {detail}", self)
            sub.setWordWrap(True)
            sub.setStyleSheet("color: gray; font-size: 11px;")
            if present:
                cb.setChecked(True)
                cb.setEnabled(False)                 # already there
            self._boxes[key] = cb
            col.addWidget(cb)
            col.addWidget(sub)
        col.addStretch(1)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        scroll.setAccessibleName(tr("Optional features"))
        root.addWidget(scroll, 1)

        self._build_system_tools(root)

        actions = QHBoxLayout()
        actions.addStretch(1)
        later = QPushButton(tr("Not now"), self)
        later.clicked.connect(self._skip)
        install = QPushButton(tr("Install selected"), self)
        install.setDefault(True)
        install.clicked.connect(self._install)
        actions.addWidget(later)
        actions.addWidget(install)
        root.addLayout(actions)

        self._apply_preset("all")                    # default to the recommended set
        # Initial keyboard focus on the default action so Enter installs and
        # Escape (QDialog default) dismisses without reaching for the mouse.
        install.setFocus()

    # ── first-run language picker ─────────────────────────────────────────
    def _build_language_row(self, root) -> None:
        """A compact interface-language selector at the top of the chooser.

        First launch is the earliest natural point to pick a UI language, so it
        sits above everything else.  Choosing a language calls set_language()
        immediately and, when the host window supports a live chrome rebuild
        (_set_ui_language), triggers one so the surrounding app localises
        without a restart.  Native language names are shown untranslated so a
        user can always recognise their own.
        """
        row = QHBoxLayout()
        caption = QLabel(tr("Interface language:"), self)
        combo = QComboBox(self)
        self._lang_combo = combo
        current = get_language()
        for disp, code in available_languages():
            combo.addItem(disp, code)
            if code == current:
                combo.setCurrentIndex(combo.count() - 1)
        # Accessibility: the bare combo has no visible <label for> association,
        # so mirror the caption into its own accessible name/description.
        _acc_desc = tr("Choose the language for menus, toolbar, and messages.")
        combo.setAccessibleName(tr("Interface language"))
        combo.setAccessibleDescription(_acc_desc)
        combo.setToolTip(_acc_desc)
        caption.setBuddy(combo)
        combo.currentIndexChanged.connect(self._on_language_changed)
        row.addWidget(caption)
        row.addWidget(combo)
        row.addStretch(1)
        root.addLayout(row)

    def _on_language_changed(self, index: int) -> None:
        """Apply the picked UI language and rebuild the app chrome if possible."""
        combo = getattr(self, "_lang_combo", None)
        if combo is None:
            return
        code = str(combo.itemData(index) or "en")
        win = self._win
        # Prefer the window's own switch (persists + live-rebuilds toolbar/menu);
        # fall back to activating the catalog directly when hosted standalone.
        setter = getattr(win, "_set_ui_language", None)
        if callable(setter):
            try:
                setter(code)
            except Exception:
                set_language(code)
        else:
            set_language(code)
        # Rebuild this dialog's own chrome in the new language — but *after* this
        # signal handler returns.  _retranslate() destroys the combo that just
        # emitted currentIndexChanged; tearing it down synchronously inside its
        # own slot crashes Qt, so defer to the next event-loop turn.
        QTimer.singleShot(0, self._retranslate)

    def _retranslate(self) -> None:
        """Rebuild the dialog in the active language (drop and re-lay widgets).

        The chooser is transient (first-run / on-demand), so the simplest
        correct refresh is to clear the layout and rebuild it — no need to hold
        references to every label.  The current checkbox selection is preserved
        so a language switch mid-dialog doesn't reset the user's picks.
        """
        prev_selected = set(self.selected())
        old = self.layout()
        if old is not None:
            QWidget().setLayout(old)  # reparent the old layout off this dialog
        self.setWindowTitle(tr("star — Optional Features"))  # not set by _build()
        self._boxes = {}
        self._build()
        for key, cb in self._boxes.items():
            if cb.isEnabled():
                cb.setChecked(key in prev_selected)

    # ── system tools (read-only status) ──────────────────────────────────
    def _build_system_tools(self, root) -> None:
        """Append a read-only status list of native (non-pip) tools.

        These are separate downloads star cannot install for you (OCR, markup,
        audio/video, graph layout, TTS engines). They are *status rows*, never
        checkboxes, and are deliberately kept out of ``self._boxes``.
        """
        self._sys_rows: dict[str, QLabel] = {}
        heading = QLabel(tr("<b>System tools</b> (native engines)"), self)
        heading.setAccessibleName(tr("System tools"))
        root.addWidget(heading)

        note = QLabel(
            tr("These are separate downloads star can use but cannot install "
               "for you — put them on your PATH (or use the self-contained "
               "build, which bundles them)."),
            self,
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 11px;")
        note.setAccessibleName(tr("System tools note"))
        note.setAccessibleDescription(
            tr("Native tools listed below are not managed by star.")
        )
        root.addWidget(note)

        for tool in diagnostics.system_tools():
            available = bool(tool["available"])
            mark = "✓" if available else "✗"      # ✓ / ✗
            state = (tr("available") if available
                     else tr("not found"))
            label = tr(str(tool["label"]))
            row = QLabel(f"  {mark} {label} — {tool['enables']}", self)
            row.setWordWrap(True)
            # Accessible name announces the availability up front (the glyph
            # alone is not reliably read); description carries what it enables
            # and, when missing, how to get it.
            row.setAccessibleName(f"{label}: {state}")
            desc = str(tool["enables"])
            if not available and tool.get("install"):
                desc = f"{desc}. {tr('Install')}: {tool['install']}"
            row.setAccessibleDescription(desc)
            row.setToolTip(desc)
            self._sys_rows[str(tool["key"])] = row
            root.addWidget(row)

    # ── behaviour ────────────────────────────────────────────────────────
    def _apply_preset(self, name: str) -> None:
        chosen = set(autodeps.preset(name))
        for key, cb in self._boxes.items():
            if cb.isEnabled():                       # don't touch already-installed
                cb.setChecked(key in chosen)

    def selected(self) -> list[str]:
        """Feature keys currently checked (whether enabled or already installed)."""
        return [k for k, cb in self._boxes.items() if cb.isChecked()]

    def _status(self, msg: str) -> None:
        win = self._win
        if win is not None and hasattr(win, "statusBar"):
            try:
                win.statusBar().showMessage(msg, 8000)
            except Exception:
                pass

    def _mark_prompted(self) -> None:
        settings = getattr(self._win, "settings", None)
        if settings is None:
            return
        try:
            settings.set("deps_prompted", True)
            settings.save()
        except Exception:
            pass

    def done(self, result: int) -> None:  # noqa: N802 (Qt override)
        # One-shot: however the chooser is dismissed — Install, Not now, Esc, or
        # the window close button — don't auto-open it again. It stays reachable
        # via Tools → Install Optional Features.
        self._mark_prompted()
        super().done(result)

    def _install(self) -> None:
        autodeps.set_enabled(True)
        started: list[str] = []
        for key in self.selected():
            started += autodeps.ensure_feature(key)
        if started:
            self._status(
                tr("Installing {n} optional package(s) in the background…").format(
                    n=len(started))
            )
        else:
            self._status(tr("Selected optional features are already installed."))
        self.accept()

    def _skip(self) -> None:
        self.reject()                                # done() marks it prompted


def maybe_prompt(window) -> None:
    """Show the chooser once, on first launch (unless disabled / already prompted)."""
    settings = getattr(window, "settings", None)
    if settings is None:
        return
    if settings.get("deps_prompted", False) or not settings.get("auto_install", True):
        return
    if not autodeps.enabled():                       # STAR_NO_AUTOINSTALL kill-switch
        return
    try:
        DependencyChooser(window).exec()
    except Exception:
        pass  # a chooser failure must never block launching the app
