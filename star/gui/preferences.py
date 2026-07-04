"""Centralized Preferences dialog for the Qt GUI.

A single tabbed :class:`PreferencesDialog` that gathers the settings previously
scattered across per-feature dialogs (Karaoke Highlight, Reading Ruler, RSVP
Position) plus Voice, Display, and General options into one place.

Standard Preferences semantics: **apply-on-OK**.  OK (and the Apply button)
writes every widget's value into ``win.settings``, calls the right hooks so the
change takes effect immediately, then persists with ``settings.save()``.  Cancel
writes nothing.

Mixed into nothing — this is a plain ``QDialog`` opened lazily by
``DisplayMixin._qt_preferences``.  IMPORT SAFETY: references Qt at module scope,
so it is imported lazily (inside ``_qt_preferences``) after the ``_QT`` guard,
like the mixin_*.py modules.
"""
from .._runtime import *  # noqa: F401,F403

try:  # QTabWidget is not re-exported by _runtime; import it directly.
    from PyQt6.QtWidgets import QTabWidget
except ImportError:  # PyQt5 fallback
    from PyQt5.QtWidgets import QTabWidget  # type: ignore[no-redef]

from ..settings import DEFAULTS
from ..themes import BUILT_IN_THEME_NAMES

# RSVP position keys, in the overlay's own dict order (top→bottom, left→right).
_RSVP_POSITIONS = [
    "top-left", "top-center", "top-right",
    "center-left", "center", "center-right",
    "bottom-left", "bottom-center", "bottom-right",
]

_HIGHLIGHT_STYLES = ["background", "underline", "box", "bold", "color"]
_HIGHLIGHT_GRANS = ["word", "sentence", "both"]
_READING_FONTS = ["default", "opendyslexic", "atkinson", "lexend"]
_SYNC_POLICIES = ["newest", "highest_progress", "manual"]
_FOOTNOTE_MODES = ["inline", "deferred", "skip"]
_AUDIOBOOK_BITRATES = ["32k", "48k", "64k", "96k", "128k"]


def _std_button(box, name: str):
    """Return a QDialogButtonBox.StandardButton value across PyQt6/PyQt5."""
    try:  # PyQt6
        return getattr(box.StandardButton, name)
    except AttributeError:  # PyQt5
        return getattr(box, name)  # type: ignore[attr-defined]


class PreferencesDialog(QDialog):
    """One tabbed dialog for every reader preference (apply-on-OK)."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.settings = win.settings
        self.setWindowTitle("Preferences")
        self.resize(560, 560)

        outer = QVBoxLayout(self)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)

        # State dicts for the swatch color-pickers (mirrors the aid dialogs).
        self._hl_color = {"v": str(self.settings.get("highlight_color", "cyan") or "")}
        self._sent_color = {"v": str(self.settings.get("sentence_highlight_color", "") or "")}
        self._ruler_color = {"v": str(self.settings.get("qt_ruler_color", "") or "")}

        self._build_reading_tab()
        self._build_voice_tab()
        self._build_display_tab()
        self._build_general_tab()

        # OK / Cancel / Apply / Restore Defaults — apply-on-OK; Cancel writes
        # nothing; Restore Defaults only re-stages the widgets (see method).
        buttons = QDialogButtonBox(
            _std_button(QDialogButtonBox, "Ok")
            | _std_button(QDialogButtonBox, "Cancel")
            | _std_button(QDialogButtonBox, "Apply")
            | _std_button(QDialogButtonBox, "RestoreDefaults")
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        apply_btn = buttons.button(_std_button(QDialogButtonBox, "Apply"))
        if apply_btn is not None:
            apply_btn.clicked.connect(self._apply)
        restore_btn = buttons.button(_std_button(QDialogButtonBox, "RestoreDefaults"))
        if restore_btn is not None:
            restore_btn.clicked.connect(self._restore_defaults)
            restore_btn.setToolTip(
                "Reset every field on all tabs to the shipped defaults "
                "(nothing is saved until OK or Apply)"
            )
        outer.addWidget(buttons)

    # ── colour swatch helper (shared with the karaoke dialog pattern) ────────

    def _make_swatch(self, state: dict, allow_theme: bool, theme_label: str = "",
                     empty_text: str = "Theme default", name: str = ""):
        """Build a swatch QPushButton (opens QColorDialog); optionally wrap it
        with a second button that clears the colour to *empty* (theme/highlight).

        *state* is a ``{"v": hexstr}`` dict mutated in place; a ``repaint``
        callback is stored on it so Restore Defaults can refresh the swatch.
        *name* becomes the accessible name — the visible text is just a hex
        string, useless to a screen reader without it.  Returns the widget to
        place in the form (the button itself, or a wrapper with the extra
        button)."""
        btn = QPushButton()
        if name:
            btn.setAccessibleName(name)

        def _paint() -> None:
            c = QColor(state["v"]) if state["v"] else QColor()
            if c.isValid():
                lum = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
                fg = "#000000" if lum > 140 else "#ffffff"
                btn.setStyleSheet(
                    f"QPushButton{{background-color:{c.name()};color:{fg};"
                    "padding:5px;border:1px solid #888;}"
                )
                btn.setText(c.name())
            else:
                btn.setStyleSheet("")
                btn.setText(empty_text)

        def _pick() -> None:
            start = (
                QColor(state["v"])
                if state["v"] and QColor(state["v"]).isValid()
                else QColor("#888888")
            )
            chosen = QColorDialog.getColor(start, self, "Choose color")
            if chosen.isValid():
                state["v"] = chosen.name()
                _paint()

        btn.clicked.connect(_pick)
        _paint()
        state["repaint"] = _paint  # runtime-only; _write_settings reads "v" alone
        if not allow_theme:
            return btn
        wrap = QWidget()
        hb = QHBoxLayout(wrap)
        hb.setContentsMargins(0, 0, 0, 0)
        hb.addWidget(btn, 1)
        clear_btn = QPushButton(theme_label or "Use theme")
        if name:
            clear_btn.setAccessibleName(f"{name} — {theme_label or 'Use theme'}")

        def _clear() -> None:
            state["v"] = ""
            _paint()

        clear_btn.clicked.connect(_clear)
        hb.addWidget(clear_btn)
        # Tabbing into the composite row lands on the swatch, not the wrapper.
        wrap.setFocusProxy(btn)
        return wrap

    # ── Reading tab ──────────────────────────────────────────────────────────

    def _build_reading_tab(self) -> None:
        w = QWidget()
        form = QFormLayout(w)

        self.style_box = QComboBox()
        self.style_box.addItems(_HIGHLIGHT_STYLES)
        cur = str(self.settings.get("highlight_style", "background"))
        self.style_box.setCurrentIndex(
            _HIGHLIGHT_STYLES.index(cur) if cur in _HIGHLIGHT_STYLES else 0
        )
        form.addRow("Highlight style:", self.style_box)

        form.addRow(
            "Word color:",
            self._make_swatch(self._hl_color, False, name="Word highlight color"),
        )
        form.addRow(
            "Sentence color:",
            self._make_swatch(
                self._sent_color, True, theme_label="Use theme",
                name="Sentence highlight color",
            ),
        )

        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.5, 1.5)
        self.speed_spin.setSingleStep(0.05)
        self.speed_spin.setDecimals(2)
        self.speed_spin.setValue(float(self.settings.get("highlight_speed", 1.0) or 1.0))
        form.addRow("Highlight speed (× WPM):", self.speed_spin)

        self.lead_spin = QSpinBox()
        self.lead_spin.setRange(-5, 5)
        self.lead_spin.setValue(int(self.settings.get("highlight_lead_words", 1)))
        form.addRow("Lead / lag (words):", self.lead_spin)

        self.gran_box = QComboBox()
        self.gran_box.addItems(_HIGHLIGHT_GRANS)
        curg = str(self.settings.get("highlight_granularity", "word"))
        self.gran_box.setCurrentIndex(
            _HIGHLIGHT_GRANS.index(curg) if curg in _HIGHLIGHT_GRANS else 0
        )
        form.addRow("Highlight granularity:", self.gran_box)

        # Reading ruler.
        self.ruler_height = QSpinBox()
        self.ruler_height.setRange(16, 160)
        self.ruler_height.setSuffix(" px")
        self.ruler_height.setValue(int(self.settings.get("qt_ruler_height", 40) or 40))
        form.addRow("Reading-ruler height:", self.ruler_height)

        self.ruler_opacity = QSpinBox()
        self.ruler_opacity.setRange(0, 100)
        self.ruler_opacity.setSuffix(" %")
        self.ruler_opacity.setValue(int(self.settings.get("qt_ruler_opacity", 22) or 22))
        form.addRow("Reading-ruler opacity:", self.ruler_opacity)

        form.addRow(
            "Reading-ruler color:",
            self._make_swatch(
                self._ruler_color, True,
                theme_label="Use highlight color",
                empty_text="Highlight color",
                name="Reading ruler color",
            ),
        )

        # RSVP.
        self.rsvp_pos = QComboBox()
        self.rsvp_pos.addItems(_RSVP_POSITIONS)
        curp = str(self.settings.get("qt_rsvp_position", "top-center"))
        self.rsvp_pos.setCurrentIndex(
            _RSVP_POSITIONS.index(curp) if curp in _RSVP_POSITIONS else 0
        )
        form.addRow("RSVP position:", self.rsvp_pos)

        self.rsvp_font = QSpinBox()
        self.rsvp_font.setRange(12, 200)
        self.rsvp_font.setSuffix(" pt")
        self.rsvp_font.setValue(int(self.settings.get("qt_rsvp_font_size", 48) or 48))
        form.addRow("RSVP font size:", self.rsvp_font)

        self.rsvp_ctx = QCheckBox("Show previous / next word")
        self.rsvp_ctx.setChecked(bool(self.settings.get("qt_rsvp_context", True)))
        form.addRow("RSVP context:", self.rsvp_ctx)

        # Misc reading toggles.
        self.current_line = QCheckBox("Tint the line being read")
        self.current_line.setChecked(
            bool(self.settings.get("qt_current_line_highlight", False))
        )
        form.addRow("Current-line highlight:", self.current_line)

        self.autoscroll = QCheckBox("Follow the spoken word")
        self.autoscroll.setChecked(bool(self.settings.get("qt_autoscroll", True)))
        form.addRow("Auto-scroll:", self.autoscroll)

        self.syllable_sep = QLineEdit(str(self.settings.get("qt_syllable_sep", "·")))
        self.syllable_sep.setMaxLength(1)
        self.syllable_sep.setToolTip("Single character shown between syllables")
        form.addRow("Syllable separator:", self.syllable_sep)

        self.tabs.addTab(w, "Reading")

    # ── Voice tab ────────────────────────────────────────────────────────────

    def _engine_choices(self) -> list:
        """Deduped TTS-engine list, mirroring DocOpsMixin._qt_pick_backend:
        "auto" + registry names (silent duplicates collapsed, "silent" dropped)
        + "none"."""
        try:
            from ..plugins import PluginRegistry
            reg_names = [c.name for c in PluginRegistry.get().backends]
        except Exception:
            reg_names = ["pyttsx3", "espeak", "festival", "piper", "coqui", "dectalk"]
        seen: list = []
        for n in reg_names:
            if n != "silent" and n not in seen:
                seen.append(n)
        return ["auto"] + seen + ["none"]

    def _build_voice_tab(self) -> None:
        w = QWidget()
        form = QFormLayout(w)

        self.engine_box = QComboBox()
        engines = self._engine_choices()
        self.engine_box.addItems(engines)
        # "silent" is stored for "none"; show it as "none" in the combo.
        cur = str(self.settings.get("tts_backend", "auto"))
        if cur == "silent":
            cur = "none"
        self.engine_box.setCurrentIndex(engines.index(cur) if cur in engines else 0)
        form.addRow("TTS engine:", self.engine_box)

        self.rate_spin = QSpinBox()
        self.rate_spin.setRange(50, 400)
        self.rate_spin.setSuffix(" wpm")
        self.rate_spin.setValue(int(self.settings.get("tts_rate", 265) or 265))
        form.addRow("Speech rate:", self.rate_spin)

        self.volume_spin = QSpinBox()
        self.volume_spin.setRange(0, 100)
        self.volume_spin.setSuffix(" %")
        self.volume_spin.setValue(
            int(round(float(self.settings.get("tts_volume", 1.0) or 1.0) * 100))
        )
        form.addRow("Volume:", self.volume_spin)

        self.prefer_voice = QLineEdit(str(self.settings.get("tts_prefer_voice", "")))
        self.prefer_voice.setToolTip("Substring of a preferred default voice name")
        form.addRow("Preferred voice:", self.prefer_voice)

        self.eleven_key = QLineEdit(str(self.settings.get("elevenlabs_api_key", "")))
        try:  # PyQt6
            self.eleven_key.setEchoMode(QLineEdit.EchoMode.Password)
        except AttributeError:  # PyQt5
            self.eleven_key.setEchoMode(QLineEdit.Password)  # type: ignore[attr-defined]
        self.eleven_key.setToolTip("Opt-in ElevenLabs cloud voice key (empty = disabled)")
        form.addRow("ElevenLabs API key:", self.eleven_key)

        self.bitrate_box = QComboBox()
        self.bitrate_box.addItems(_AUDIOBOOK_BITRATES)
        curb = str(self.settings.get("audiobook_bitrate", "128k"))
        self.bitrate_box.setCurrentIndex(
            _AUDIOBOOK_BITRATES.index(curb) if curb in _AUDIOBOOK_BITRATES else 4
        )
        form.addRow("Audiobook bitrate:", self.bitrate_box)

        self.tabs.addTab(w, "Voice")

    # ── Display tab ──────────────────────────────────────────────────────────

    def _build_display_tab(self) -> None:
        w = QWidget()
        form = QFormLayout(w)

        self.reading_font = QComboBox()
        self.reading_font.addItems(_READING_FONTS)
        curf = str(self.settings.get("qt_reading_font", "default"))
        self._orig_reading_font = curf  # to detect a change on apply
        self.reading_font.setCurrentIndex(
            _READING_FONTS.index(curf) if curf in _READING_FONTS else 0
        )
        form.addRow("Reading font:", self.reading_font)

        # Display font — a "Choose…" button opens QFontDialog; the picked family
        # + size are staged into these members and written on apply.
        self._font_family = str(self.settings.get("qt_font_family", ""))
        self._font_size = int(self.settings.get("qt_font_size", 14) or 14)
        self.font_btn = QPushButton()
        self.font_btn.setAccessibleName("Display font")
        self._refresh_font_btn()
        self.font_btn.clicked.connect(self._choose_font)
        form.addRow("Display font:", self.font_btn)

        self.theme_box = QComboBox()
        self.theme_box.addItems(BUILT_IN_THEME_NAMES)
        curt = str(self.settings.get("theme", "obsidian"))
        self._orig_theme = curt  # to detect a deliberate change on apply
        self.theme_box.setCurrentIndex(
            BUILT_IN_THEME_NAMES.index(curt) if curt in BUILT_IN_THEME_NAMES else 0
        )
        form.addRow("Theme:", self.theme_box)

        self.follow_os = QCheckBox("Match the OS dark / light appearance")
        self._orig_follow_os = bool(self.settings.get("qt_follow_os_theme", True))
        self.follow_os.setChecked(self._orig_follow_os)
        form.addRow("Follow OS theme:", self.follow_os)

        self.tabs.addTab(w, "Display")

    def _refresh_font_btn(self) -> None:
        fam = self._font_family or "(default)"
        self.font_btn.setText(f"{fam}  {self._font_size}pt  —  Choose…")

    def _choose_font(self) -> None:
        current = QFont(self._font_family or "", self._font_size)
        font, ok = QFontDialog.getFont(current, self, "Choose Display Font")
        if ok:
            self._font_family = font.family()
            self._font_size = max(6, font.pointSize())
            self._refresh_font_btn()

    # ── General tab ──────────────────────────────────────────────────────────

    def _build_general_tab(self) -> None:
        w = QWidget()
        form = QFormLayout(w)

        self.auto_install = QCheckBox("Auto-install optional features on demand")
        self.auto_install.setChecked(bool(self.settings.get("auto_install", True)))
        form.addRow("Optional features:", self.auto_install)

        self.auto_updates = QCheckBox("Check for updates on startup")
        self.auto_updates.setChecked(bool(self.settings.get("auto_check_updates", False)))
        form.addRow("Updates:", self.auto_updates)

        self.sync_policy = QComboBox()
        self.sync_policy.addItems(_SYNC_POLICIES)
        curs = str(self.settings.get("sync_conflict_policy", "newest"))
        self.sync_policy.setCurrentIndex(
            _SYNC_POLICIES.index(curs) if curs in _SYNC_POLICIES else 0
        )
        form.addRow("Sync conflict policy:", self.sync_policy)

        self.footnote_mode = QComboBox()
        self.footnote_mode.addItems(_FOOTNOTE_MODES)
        curfn = str(self.settings.get("footnote_mode", "inline"))
        self.footnote_mode.setCurrentIndex(
            _FOOTNOTE_MODES.index(curfn) if curfn in _FOOTNOTE_MODES else 0
        )
        form.addRow("Footnotes:", self.footnote_mode)

        self.paginate = QCheckBox("Paginate very large documents")
        self.paginate.setChecked(bool(self.settings.get("qt_paginate_large_docs", False)))
        form.addRow("Large documents:", self.paginate)

        self.paginate_threshold = QSpinBox()
        self.paginate_threshold.setRange(10000, 1000000)
        self.paginate_threshold.setSingleStep(10000)
        self.paginate_threshold.setSuffix(" words")
        self.paginate_threshold.setValue(
            int(self.settings.get("qt_paginate_threshold_words", 60000) or 60000)
        )
        form.addRow("Pagination threshold:", self.paginate_threshold)

        self.tabs.addTab(w, "General")

    # ── write + apply ────────────────────────────────────────────────────────

    def _restore_defaults(self) -> None:
        """Reset every widget on all four tabs to the shipped default.

        Staging-only, matching the dialog's semantics: nothing is written or
        applied until OK / Apply, so Cancel still discards the reset.  Values
        come from settings.DEFAULTS — the single source of truth — never from
        re-hardcoded literals."""
        D = DEFAULTS

        def _combo(box, options: list, key: str) -> None:
            val = str(D[key])
            box.setCurrentIndex(options.index(val) if val in options else 0)

        # Reading.
        _combo(self.style_box, _HIGHLIGHT_STYLES, "highlight_style")
        self._hl_color["v"] = str(D["highlight_color"])
        self._hl_color["repaint"]()
        self._sent_color["v"] = str(D["sentence_highlight_color"])
        self._sent_color["repaint"]()
        self.speed_spin.setValue(float(D["highlight_speed"]))
        self.lead_spin.setValue(int(D["highlight_lead_words"]))
        _combo(self.gran_box, _HIGHLIGHT_GRANS, "highlight_granularity")
        self.ruler_height.setValue(int(D["qt_ruler_height"]))
        self.ruler_opacity.setValue(int(D["qt_ruler_opacity"]))
        self._ruler_color["v"] = str(D["qt_ruler_color"])
        self._ruler_color["repaint"]()
        _combo(self.rsvp_pos, _RSVP_POSITIONS, "qt_rsvp_position")
        self.rsvp_font.setValue(int(D["qt_rsvp_font_size"]))
        self.rsvp_ctx.setChecked(bool(D["qt_rsvp_context"]))
        self.current_line.setChecked(bool(D["qt_current_line_highlight"]))
        self.autoscroll.setChecked(bool(D["qt_autoscroll"]))
        self.syllable_sep.setText(str(D["qt_syllable_sep"]))
        # Voice.  "auto" is always first in the engine combo.
        self.engine_box.setCurrentIndex(0)
        self.rate_spin.setValue(int(D["tts_rate"]))
        self.volume_spin.setValue(int(round(float(D["tts_volume"]) * 100)))
        self.prefer_voice.setText(str(D["tts_prefer_voice"]))
        self.eleven_key.setText(str(D["elevenlabs_api_key"]))
        _combo(self.bitrate_box, _AUDIOBOOK_BITRATES, "audiobook_bitrate")
        # Display.
        _combo(self.reading_font, _READING_FONTS, "qt_reading_font")
        self._font_family = str(D["qt_font_family"])
        self._font_size = int(D["qt_font_size"])
        self._refresh_font_btn()
        _combo(self.theme_box, list(BUILT_IN_THEME_NAMES), "theme")
        self.follow_os.setChecked(bool(D["qt_follow_os_theme"]))
        # General.
        self.auto_install.setChecked(bool(D["auto_install"]))
        self.auto_updates.setChecked(bool(D["auto_check_updates"]))
        _combo(self.sync_policy, _SYNC_POLICIES, "sync_conflict_policy")
        _combo(self.footnote_mode, _FOOTNOTE_MODES, "footnote_mode")
        self.paginate.setChecked(bool(D["qt_paginate_large_docs"]))
        self.paginate_threshold.setValue(int(D["qt_paginate_threshold_words"]))

    def _on_ok(self) -> None:
        self._apply()
        self.accept()

    def _write_settings(self) -> None:
        """Write every widget value into ``settings._data`` (no save yet)."""
        d = self.settings._data
        # Reading.
        d["highlight_style"] = self.style_box.currentText()
        d["highlight_color"] = self._hl_color["v"]
        d["sentence_highlight_color"] = self._sent_color["v"]
        d["highlight_speed"] = self.speed_spin.value()
        d["highlight_lead_words"] = self.lead_spin.value()
        d["highlight_granularity"] = self.gran_box.currentText()
        d["qt_ruler_height"] = self.ruler_height.value()
        d["qt_ruler_opacity"] = self.ruler_opacity.value()
        d["qt_ruler_color"] = self._ruler_color["v"]
        d["qt_rsvp_position"] = self.rsvp_pos.currentText()
        d["qt_rsvp_font_size"] = self.rsvp_font.value()
        d["qt_rsvp_context"] = self.rsvp_ctx.isChecked()
        d["qt_current_line_highlight"] = self.current_line.isChecked()
        d["qt_autoscroll"] = self.autoscroll.isChecked()
        d["qt_syllable_sep"] = self.syllable_sep.text() or "·"
        # Voice.
        chosen_engine = self.engine_box.currentText()
        d["tts_backend"] = "silent" if chosen_engine == "none" else chosen_engine
        d["tts_rate"] = self.rate_spin.value()
        d["tts_volume"] = self.volume_spin.value() / 100.0
        d["tts_prefer_voice"] = self.prefer_voice.text()
        d["elevenlabs_api_key"] = self.eleven_key.text()
        d["audiobook_bitrate"] = self.bitrate_box.currentText()
        # Display.
        d["qt_reading_font"] = self.reading_font.currentText()
        d["qt_font_family"] = self._font_family
        d["qt_font_size"] = self._font_size
        d["theme"] = self.theme_box.currentText()
        d["qt_follow_os_theme"] = self.follow_os.isChecked()
        # General.
        d["auto_install"] = self.auto_install.isChecked()
        d["auto_check_updates"] = self.auto_updates.isChecked()
        d["sync_conflict_policy"] = self.sync_policy.currentText()
        d["footnote_mode"] = self.footnote_mode.currentText()
        d["qt_paginate_large_docs"] = self.paginate.isChecked()
        d["qt_paginate_threshold_words"] = self.paginate_threshold.value()

    def _apply(self) -> None:
        """Write, run every live-effect hook (each guarded), then save.

        A failing hook must not abort the rest — each is wrapped in try/except so
        one broken effect can't leave later settings un-applied or unsaved."""
        win = self.win
        self._write_settings()

        # Highlight style / colors.
        try:
            win._rebuild_hl_fmt()
        except Exception:
            pass

        # Reading ruler — reflect height / opacity / color onto the live overlay.
        ruler = getattr(win, "_reading_ruler", None)
        if ruler is not None:
            try:
                ruler.set_height(int(self.settings.get("qt_ruler_height", 40)))
            except Exception:
                pass
            try:
                ruler.set_opacity(int(self.settings.get("qt_ruler_opacity", 22)))
            except Exception:
                pass
            try:
                rc = str(self.settings.get("qt_ruler_color", "") or "").strip() or str(
                    self.settings.get("highlight_color", "cyan")
                )
                ruler.set_color(QColor(rc))
            except Exception:
                pass

        # RSVP overlay — the overlay caches position/size/context on itself, so a
        # live overlay needs the new values pushed (mirrors the old dialog's flow).
        rsvp = getattr(win, "_rsvp_overlay", None)
        if rsvp is not None:
            try:
                rsvp.set_position(str(self.settings.get("qt_rsvp_position", "top-center")))
                rsvp.set_font_size(int(self.settings.get("qt_rsvp_font_size", 48)))
                rsvp.set_show_context(bool(self.settings.get("qt_rsvp_context", True)))
            except Exception:
                pass

        # Theme — mirror the toolbar/menu pickers: a deliberate theme change here
        # marks the choice "explicit" (qt_theme_explicit) so OS-follow won't
        # override it on the next launch.  Conversely, ticking "Follow OS theme"
        # without changing the theme re-arms OS auto-detection by clearing the flag.
        new_theme = str(self.settings.get("theme", "obsidian"))
        if new_theme != self._orig_theme:
            self.settings._data["qt_theme_explicit"] = True
        elif self.follow_os.isChecked() and not self._orig_follow_os:
            self.settings._data["qt_theme_explicit"] = False
        try:
            win._apply_qt_theme(new_theme)
        except Exception:
            pass

        # Display font — only re-apply when it actually changed (mirrors _set_font
        # which persists + re-renders).
        try:
            win._set_font(
                family=str(self.settings.get("qt_font_family", "")),
                size=int(self.settings.get("qt_font_size", 14)),
            )
        except Exception:
            pass

        # Reading font — route a *change* through the same helper as the
        # View ▸ Reading Aids ▸ Reading Font radios so the on-demand OFL fetch,
        # the legacy qt_dyslexia_font sync, and the menu radio all happen.
        # Writing qt_reading_font alone would change nothing on screen.
        try:
            new_rf = str(self.settings.get("qt_reading_font", "default"))
            if new_rf != self._orig_reading_font:
                win._qt_set_reading_font(new_rf)
                self._orig_reading_font = new_rf  # Apply twice ≠ fetch twice
        except Exception:
            pass

        # TTS engine — skip "auto" and unchanged; map "none"→"silent" like
        # _qt_pick_backend.  The stored value was already normalised in
        # _write_settings, so compare against the manager's active backend name.
        try:
            target = str(self.settings.get("tts_backend", "auto"))
            if target != "auto":
                active = getattr(win.tts_manager, "backend_name", None)
                if active != target:
                    win.tts_manager.change_backend(target)
        except Exception:
            pass

        # Speech rate / volume.
        try:
            win.tts_manager.set_rate(int(self.settings.get("tts_rate", 265)))
        except Exception:
            pass
        try:
            win.tts_manager.set_volume(float(self.settings.get("tts_volume", 1.0)))
        except Exception:
            pass

        # Difficult-word overlay repaint (picks up any highlight changes).
        try:
            win._qt_refresh_vocab_highlight()
        except Exception:
            pass

        # Persist everything.
        try:
            self.settings.save()
        except Exception:
            pass

        try:
            win.statusBar().showMessage("Preferences applied")
        except Exception:
            pass
