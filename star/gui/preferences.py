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

from ..i18n import available_languages, get_language, tr
from ..settings import DEFAULTS, WHISPER_MODELS
from ..themes import BUILT_IN_THEME_NAMES
from .a11y import announce

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
_WHISPER_MODELS = list(WHISPER_MODELS)
_TABLE_MODES = ["structured", "flat", "skip"]


def _std_button(box, name: str):
    """Return a QDialogButtonBox.StandardButton value across PyQt6/PyQt5."""
    try:  # PyQt6
        return getattr(box.StandardButton, name)
    except AttributeError:  # PyQt5
        return getattr(box, name)  # type: ignore[attr-defined]


def _link_checkboxes(a, b) -> None:
    """Keep two checkboxes mirroring each other.

    The convenience tabs deliberately duplicate a few controls (accessibility:
    more than one way to reach the same setting), so the copies must stay in
    lock-step — and Restore Defaults, which sets the canonical widget, then
    propagates to the mirror through these signals."""
    def _mk(dst):
        def _f(v):
            if dst.isChecked() != v:
                dst.setChecked(v)
        return _f
    a.toggled.connect(_mk(b))
    b.toggled.connect(_mk(a))


def _link_combos(a, b) -> None:
    """Keep two combo boxes mirroring each other (see _link_checkboxes)."""
    def _mk(dst):
        def _f(i):
            if dst.currentIndex() != i:
                dst.setCurrentIndex(i)
        return _f
    a.currentIndexChanged.connect(_mk(b))
    b.currentIndexChanged.connect(_mk(a))


class PreferencesDialog(QDialog):
    """One tabbed dialog for every reader preference (apply-on-OK)."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.settings = win.settings
        self.setWindowTitle(tr("Preferences"))
        # Open maximized: the tabs hold a lot of settings and a small dialog
        # forces scrolling (explicitly unwanted).  The resize() first gives
        # "restore down" a sensible floor instead of a postage stamp.
        self.resize(900, 700)
        try:  # PyQt6
            self.setWindowState(Qt.WindowState.WindowMaximized)
        except AttributeError:  # PyQt5
            self.setWindowState(Qt.WindowMaximized)  # type: ignore[attr-defined]

        outer = QVBoxLayout(self)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)

        # State dicts for the swatch color-pickers (mirrors the aid dialogs).
        self._hl_color = {"v": str(self.settings.get("highlight_color", "cyan") or "")}
        self._sent_color = {"v": str(self.settings.get("sentence_highlight_color", "") or "")}
        self._ruler_color = {"v": str(self.settings.get("qt_ruler_color", "") or "")}
        self._line_color = {"v": str(self.settings.get("qt_current_line_color", "") or "")}
        self._rsvp_text_color = {"v": str(self.settings.get("qt_rsvp_text_color", "") or "")}
        self._rsvp_bg_color = {"v": str(self.settings.get("qt_rsvp_bg_color", "") or "")}

        self._build_reading_tab()
        self._build_reading_aids_tab()   # convenience: pick your aid combination
        self._build_voice_tab()
        self._build_display_tab()
        self._build_fonts_tab()          # convenience: all font + spacing options
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
                tr(
                    "Reset every field on all tabs to the shipped defaults "
                    "(nothing is saved until OK or Apply)"
                )
            )
        outer.addWidget(buttons)

    # ── colour swatch helper (shared with the karaoke dialog pattern) ────────

    def _make_swatch(self, state: dict, allow_theme: bool, theme_label: str = "",
                     empty_text: str = "", name: str = ""):
        """Build a swatch QPushButton (opens QColorDialog); optionally wrap it
        with a second button that clears the colour to *empty* (theme/highlight).

        *state* is a ``{"v": hexstr}`` dict mutated in place; a ``repaint``
        callback is stored on it so Restore Defaults can refresh the swatch.
        *name* becomes the accessible name — the visible text is just a hex
        string, useless to a screen reader without it.  Returns the widget to
        place in the form (the button itself, or a wrapper with the extra
        button)."""
        # Defaults resolved at call time (not def time) so the active UI
        # language is honored — the dialog is rebuilt on every open.
        theme_label = theme_label or tr("Use theme")
        empty_text = empty_text or tr("Theme default")
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
            chosen = QColorDialog.getColor(start, self, tr("Choose color"))
            if chosen.isValid():
                state["v"] = chosen.name()
                state["repaint"]()

        btn.clicked.connect(_pick)
        _paint()
        # A state dict may back MORE than one swatch (the Reading Aids tab
        # mirrors colors from the Reading tab), so "repaint" fans out to every
        # button built on it.  Runtime-only; _write_settings reads "v" alone.
        state.setdefault("_painters", []).append(_paint)

        def _paint_all() -> None:
            for p in state.get("_painters", []):
                p()

        state["repaint"] = _paint_all
        if not allow_theme:
            return btn
        wrap = QWidget()
        hb = QHBoxLayout(wrap)
        hb.setContentsMargins(0, 0, 0, 0)
        hb.addWidget(btn, 1)
        clear_btn = QPushButton(theme_label)
        if name:
            clear_btn.setAccessibleName(f"{name} — {theme_label}")

        def _clear() -> None:
            state["v"] = ""
            state["repaint"]()

        clear_btn.clicked.connect(_clear)
        hb.addWidget(clear_btn)
        # Tabbing into the composite row lands on the swatch, not the wrapper.
        wrap.setFocusProxy(btn)
        return wrap

    # ── Reading tab ──────────────────────────────────────────────────────────

    def _build_reading_tab(self) -> None:
        w = QWidget()
        form = QFormLayout(w)

        # Master switch: everything karaoke-related below grays out with it.
        self.hl_master = QCheckBox(tr("Highlight the word being spoken"))
        self.hl_master.setChecked(
            bool(self.settings.get("highlight_current_word", True))
        )
        form.addRow(tr("Spoken-word highlight:"), self.hl_master)

        self.style_box = QComboBox()
        self.style_box.addItems(_HIGHLIGHT_STYLES)
        cur = str(self.settings.get("highlight_style", "background"))
        self.style_box.setCurrentIndex(
            _HIGHLIGHT_STYLES.index(cur) if cur in _HIGHLIGHT_STYLES else 0
        )
        form.addRow(tr("Highlight style:"), self.style_box)

        hl_swatch = self._make_swatch(
            self._hl_color, False, name=tr("Word highlight color")
        )
        form.addRow(tr("Word color:"), hl_swatch)
        sent_swatch = self._make_swatch(
            self._sent_color, True,
            name=tr("Sentence highlight color"),
        )
        form.addRow(tr("Sentence color:"), sent_swatch)

        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.5, 1.5)
        self.speed_spin.setSingleStep(0.05)
        self.speed_spin.setDecimals(2)
        self.speed_spin.setValue(float(self.settings.get("highlight_speed", 1.0) or 1.0))
        form.addRow(tr("Highlight speed (× WPM):"), self.speed_spin)

        self.lead_spin = QSpinBox()
        self.lead_spin.setRange(-5, 5)
        self.lead_spin.setValue(int(self.settings.get("highlight_lead_words", 1)))
        form.addRow(tr("Lead / lag (words):"), self.lead_spin)

        self.gran_box = QComboBox()
        self.gran_box.addItems(_HIGHLIGHT_GRANS)
        curg = str(self.settings.get("highlight_granularity", "word"))
        self.gran_box.setCurrentIndex(
            _HIGHLIGHT_GRANS.index(curg) if curg in _HIGHLIGHT_GRANS else 0
        )
        form.addRow(tr("Highlight granularity:"), self.gran_box)

        # Gray out the karaoke rows when the master switch is off (the values
        # are still written on apply — they simply have no effect until it is
        # back on, mirroring _apply_word_highlight's paint gate).
        self._hl_dependents = (
            self.style_box, hl_swatch, sent_swatch,
            self.speed_spin, self.lead_spin, self.gran_box,
        )

        def _sync_hl_enabled(on: bool) -> None:
            for dep in self._hl_dependents:
                dep.setEnabled(on)

        self.hl_master.toggled.connect(_sync_hl_enabled)
        _sync_hl_enabled(self.hl_master.isChecked())

        # Reading ruler.
        self.ruler_height = QSpinBox()
        self.ruler_height.setRange(16, 160)
        self.ruler_height.setSuffix(" px")
        self.ruler_height.setValue(int(self.settings.get("qt_ruler_height", 40) or 40))
        form.addRow(tr("Reading-ruler height:"), self.ruler_height)

        self.ruler_opacity = QSpinBox()
        self.ruler_opacity.setRange(0, 100)
        self.ruler_opacity.setSuffix(" %")
        self.ruler_opacity.setValue(int(self.settings.get("qt_ruler_opacity", 22) or 22))
        form.addRow(tr("Reading-ruler opacity:"), self.ruler_opacity)

        form.addRow(
            tr("Reading-ruler color:"),
            self._make_swatch(
                self._ruler_color, True,
                theme_label=tr("Use highlight color"),
                empty_text=tr("Highlight color"),
                name=tr("Reading ruler color"),
            ),
        )

        # RSVP.
        self.rsvp_pos = QComboBox()
        self.rsvp_pos.addItems(_RSVP_POSITIONS)
        curp = str(self.settings.get("qt_rsvp_position", "top-center"))
        self.rsvp_pos.setCurrentIndex(
            _RSVP_POSITIONS.index(curp) if curp in _RSVP_POSITIONS else 0
        )
        form.addRow(tr("RSVP position:"), self.rsvp_pos)

        self.rsvp_font = QSpinBox()
        self.rsvp_font.setRange(12, 200)
        self.rsvp_font.setSuffix(" pt")
        self.rsvp_font.setValue(int(self.settings.get("qt_rsvp_font_size", 48) or 48))
        form.addRow(tr("RSVP font size:"), self.rsvp_font)

        self.rsvp_ctx = QCheckBox(tr("Show previous / next word"))
        self.rsvp_ctx.setChecked(bool(self.settings.get("qt_rsvp_context", True)))
        form.addRow(tr("RSVP context:"), self.rsvp_ctx)

        # Misc reading toggles.
        self.current_line = QCheckBox(tr("Tint the line being read"))
        self.current_line.setChecked(
            bool(self.settings.get("qt_current_line_highlight", False))
        )
        form.addRow(tr("Current-line highlight:"), self.current_line)

        self.autoscroll = QCheckBox(tr("Follow the spoken word"))
        self.autoscroll.setChecked(bool(self.settings.get("qt_autoscroll", True)))
        form.addRow(tr("Auto-scroll:"), self.autoscroll)

        self.syllable_sep = QLineEdit(str(self.settings.get("qt_syllable_sep", "·")))
        self.syllable_sep.setMaxLength(1)
        self.syllable_sep.setToolTip(tr("Single character shown between syllables"))
        form.addRow(tr("Syllable separator:"), self.syllable_sep)

        self.caret_browsing = QCheckBox(tr("Caret browsing (movable text cursor)"))
        self.caret_browsing.setToolTip(
            tr("Show a movable caret in the reading view — keyboard "
               "navigation, selection for highlights, define-word (F7)")
        )
        self.caret_browsing.setChecked(bool(self.settings.get("qt_caret_browsing", True)))
        form.addRow(tr("Caret browsing:"), self.caret_browsing)

        self.table_mode = QComboBox()
        self.table_mode.addItems(_TABLE_MODES)
        curtm = str(self.settings.get("table_reading_mode", "structured"))
        self.table_mode.setCurrentIndex(
            _TABLE_MODES.index(curtm) if curtm in _TABLE_MODES else 0
        )
        self.table_mode.setToolTip(
            tr("How tables are read aloud: structured narrates rows and "
               "columns, flat reads cells left to right, skip omits tables. "
               "Applies when a document is (re)opened.")
        )
        form.addRow(tr("Table reading:"), self.table_mode)

        self.skip_code = QCheckBox(tr("Skip code blocks when reading aloud"))
        self.skip_code.setToolTip(
            tr("Leave fenced code out of the narration. Applies when a "
               "document is (re)opened.")
        )
        self.skip_code.setChecked(bool(self.settings.get("tts_skip_code", True)))
        form.addRow(tr("Code blocks:"), self.skip_code)

        self.tabs.addTab(w, tr("Reading"))

    # ── Reading Aids tab (convenience: pick your combination) ─────────────────

    def _build_reading_aids_tab(self) -> None:
        """A friendly one-stop panel of on/off reading aids.

        Some (highlight, current-line, auto-scroll) mirror the Reading tab —
        redundant on purpose, since many users benefit from more than one way
        to reach a setting.  Others (reading ruler, syllable splitting,
        difficult-word highlight, RSVP) are surfaced here in Preferences for
        the first time, having previously lived only in the View menu."""
        w = QWidget()
        form = QFormLayout(w)
        intro = QLabel(tr(
            "Turn on the reading aids you find helpful — mix and match freely. "
            "Each is also available from the Reading tab or the View menu."
        ))
        intro.setWordWrap(True)
        form.addRow(intro)

        # Mirrors of the Reading tab (kept in sync).  Each visual aid pairs
        # its toggle with a color swatch so every element's color is
        # changeable right here (swatches share state with the Reading tab —
        # the same color, whichever tab you set it from).
        self.aid_highlight = QCheckBox(tr("Highlight the word being spoken"))
        self.aid_highlight.setChecked(self.hl_master.isChecked())
        _link_checkboxes(self.hl_master, self.aid_highlight)
        form.addRow(
            self.aid_highlight,
            self._make_swatch(self._hl_color, False, name=tr("Word highlight color")),
        )

        self.aid_current_line = QCheckBox(tr("Tint the line being read"))
        self.aid_current_line.setChecked(self.current_line.isChecked())
        _link_checkboxes(self.current_line, self.aid_current_line)
        form.addRow(
            self.aid_current_line,
            self._make_swatch(
                self._line_color, True, name=tr("Line tint color")
            ),
        )

        self.aid_autoscroll = QCheckBox(tr("Auto-scroll to follow the spoken word"))
        self.aid_autoscroll.setChecked(self.autoscroll.isChecked())
        _link_checkboxes(self.autoscroll, self.aid_autoscroll)
        form.addRow(self.aid_autoscroll)

        # New in Preferences — canonical here (previously View-menu only).
        self.aid_bionic = QCheckBox(tr("Bionic reading (embolden word starts)"))
        self.aid_bionic.setChecked(bool(self.settings.get("qt_bionic_reading", False)))
        form.addRow(self.aid_bionic)

        self.aid_ruler = QCheckBox(tr("Reading ruler (a movable focus band)"))
        self.aid_ruler.setChecked(bool(self.settings.get("qt_reading_ruler", False)))
        form.addRow(
            self.aid_ruler,
            self._make_swatch(
                self._ruler_color, True,
                theme_label=tr("Use highlight color"),
                empty_text=tr("Highlight color"),
                name=tr("Reading ruler color"),
            ),
        )

        self.aid_syllables = QCheckBox(tr("Syllable splitting (read·a·bil·i·ty)"))
        self.aid_syllables.setChecked(bool(self.settings.get("qt_syllable_split", False)))
        form.addRow(self.aid_syllables)

        self.aid_vocab = QCheckBox(tr("Highlight difficult words"))
        self.aid_vocab.setChecked(bool(self.settings.get("qt_vocab_highlight", False)))
        form.addRow(self.aid_vocab)

        self.aid_rsvp = QCheckBox(tr("RSVP speed-reading overlay"))
        self.aid_rsvp.setChecked(bool(self.settings.get("qt_rsvp_mode", False)))
        form.addRow(self.aid_rsvp)
        form.addRow(
            tr("RSVP word color:"),
            self._make_swatch(
                self._rsvp_text_color, True, name=tr("RSVP word color")
            ),
        )
        form.addRow(
            tr("RSVP panel color:"),
            self._make_swatch(
                self._rsvp_bg_color, True, name=tr("RSVP panel color")
            ),
        )

        self.tabs.addTab(w, tr("Reading Aids"))

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
        form.addRow(tr("TTS engine:"), self.engine_box)

        self.rate_spin = QSpinBox()
        self.rate_spin.setRange(50, 400)
        self.rate_spin.setSuffix(" wpm")
        self.rate_spin.setValue(int(self.settings.get("tts_rate", 265) or 265))
        form.addRow(tr("Speech rate:"), self.rate_spin)

        self.volume_spin = QSpinBox()
        self.volume_spin.setRange(0, 100)
        self.volume_spin.setSuffix(" %")
        self.volume_spin.setValue(
            int(round(float(self.settings.get("tts_volume", 1.0) or 1.0) * 100))
        )
        form.addRow(tr("Volume:"), self.volume_spin)

        self.prefer_voice = QLineEdit(str(self.settings.get("tts_prefer_voice", "")))
        self.prefer_voice.setToolTip(tr("Substring of a preferred default voice name"))
        form.addRow(tr("Preferred voice:"), self.prefer_voice)

        self.auto_play = QCheckBox(tr("Start reading when a document opens"))
        self.auto_play.setToolTip(
            tr("Begin speaking automatically from your saved position whenever "
               "a document is opened")
        )
        self.auto_play.setChecked(bool(self.settings.get("tts_auto_play", False)))
        form.addRow("", self.auto_play)

        self.eleven_key = QLineEdit(str(self.settings.get("elevenlabs_api_key", "")))
        try:  # PyQt6
            self.eleven_key.setEchoMode(QLineEdit.EchoMode.Password)
        except AttributeError:  # PyQt5
            self.eleven_key.setEchoMode(QLineEdit.Password)  # type: ignore[attr-defined]
        self.eleven_key.setToolTip(tr("Opt-in ElevenLabs cloud voice key (empty = disabled)"))
        form.addRow(tr("ElevenLabs API key:"), self.eleven_key)

        self.bitrate_box = QComboBox()
        self.bitrate_box.addItems(_AUDIOBOOK_BITRATES)
        curb = str(self.settings.get("audiobook_bitrate", "128k"))
        self.bitrate_box.setCurrentIndex(
            _AUDIOBOOK_BITRATES.index(curb) if curb in _AUDIOBOOK_BITRATES else 4
        )
        form.addRow(tr("Audiobook bitrate:"), self.bitrate_box)

        self.whisper_box = QComboBox()
        self.whisper_box.addItems(_WHISPER_MODELS)
        curw = str(self.settings.get("whisper_model", "base"))
        self.whisper_box.setCurrentIndex(
            _WHISPER_MODELS.index(curw) if curw in _WHISPER_MODELS else 1
        )
        self.whisper_box.setToolTip(
            tr("Whisper model size for dictation and transcription. base ships "
               "inside the packaged app and works offline; larger sizes are "
               "more accurate and download once on first use "
               "(small ~500 MB, large-v3-turbo ~1.6 GB).")
        )
        form.addRow(tr("Dictation model:"), self.whisper_box)

        self.transcript_ts = QCheckBox(tr("Timestamp transcripts ([hh:mm:ss])"))
        self.transcript_ts.setToolTip(
            tr("Prefix transcribed audio with the segment start times")
        )
        self.transcript_ts.setChecked(
            bool(self.settings.get("transcribe_timestamps", False))
        )
        form.addRow("", self.transcript_ts)

        self.ssml = QCheckBox(tr("SSML prosody (richer pausing)"))
        self.ssml.setToolTip(
            tr("Wrap speech in SSML for fuller sentence/clause pauses — may "
               "loosen word-highlight accuracy on some engines")
        )
        self.ssml.setChecked(bool(self.settings.get("use_ssml", False)))
        form.addRow("", self.ssml)

        self.tabs.addTab(w, tr("Voice"))

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
        form.addRow(tr("Reading font:"), self.reading_font)

        # Display font — a "Choose…" button opens QFontDialog; the picked family
        # + size are staged into these members and written on apply.
        self._font_family = str(self.settings.get("qt_font_family", ""))
        self._font_size = int(self.settings.get("qt_font_size", 14) or 14)
        self.font_btn = QPushButton()
        self.font_btn.setAccessibleName(tr("Display font"))
        self._refresh_font_btn()
        self.font_btn.clicked.connect(self._choose_font)
        form.addRow(tr("Display font:"), self.font_btn)

        # Built-ins plus any custom *.css themes (same list as Choose Theme…).
        try:
            theme_names = list(self.win._all_theme_names)
        except Exception:
            theme_names = list(BUILT_IN_THEME_NAMES)
        self._theme_names = theme_names
        self.theme_box = QComboBox()
        self.theme_box.addItems(theme_names)
        curt = str(self.settings.get("theme", "galaxy"))
        self._orig_theme = curt  # to detect a deliberate change on apply
        self.theme_box.setCurrentIndex(
            theme_names.index(curt) if curt in theme_names else 0
        )
        form.addRow(tr("Theme:"), self.theme_box)

        self.follow_os = QCheckBox(tr("Match the OS dark / light appearance"))
        self._orig_follow_os = bool(self.settings.get("qt_follow_os_theme", True))
        self.follow_os.setChecked(self._orig_follow_os)
        form.addRow(tr("Follow OS theme:"), self.follow_os)

        # Custom-theme maintenance (previously View-menu items).  These act
        # immediately — they manage files on disk, not staged settings.
        theme_tools = QWidget()
        tt = QHBoxLayout(theme_tools)
        tt.setContentsMargins(0, 0, 0, 0)
        reload_btn = QPushButton(tr("Reload CSS themes"))
        reload_btn.setToolTip(tr("Rescan the themes folder for *.css files"))
        open_btn = QPushButton(tr("Open themes folder…"))
        open_btn.setToolTip(
            tr("Every theme is an editable CSS file — copy one, rename it, "
               "and edit freely")
        )

        def _reload_themes() -> None:
            try:
                self.win._qt_reload_css_themes()
            except Exception:
                return
            # Refresh the combo so a just-added file is choosable right away.
            try:
                names = list(self.win._all_theme_names)
            except Exception:
                return
            cur = self.theme_box.currentText()
            self._theme_names = names
            self.theme_box.clear()
            self.theme_box.addItems(names)
            if cur in names:
                self.theme_box.setCurrentIndex(names.index(cur))

        reload_btn.clicked.connect(_reload_themes)
        open_btn.clicked.connect(
            lambda: getattr(self.win, "_qt_open_themes_folder", lambda: None)()
        )
        tt.addWidget(reload_btn)
        tt.addWidget(open_btn)
        form.addRow(tr("Custom themes:"), theme_tools)

        self.tabs.addTab(w, tr("Display"))

    # ── Fonts tab (convenience: fonts + text spacing in one place) ────────────

    def _build_fonts_tab(self) -> None:
        """All font and text-spacing options together — reading font and
        display font mirror the Display tab; line height and letter/word
        spacing are surfaced here (previously settings-file only)."""
        w = QWidget()
        form = QFormLayout(w)
        intro = QLabel(tr(
            "Fonts and text spacing in one place. The reading and display fonts "
            "are also on the Display tab."
        ))
        intro.setWordWrap(True)
        form.addRow(intro)

        # Reading font (mirror of the Display tab).
        self.font_reading = QComboBox()
        self.font_reading.addItems(_READING_FONTS)
        self.font_reading.setCurrentIndex(self.reading_font.currentIndex())
        _link_combos(self.reading_font, self.font_reading)
        form.addRow(tr("Reading font:"), self.font_reading)

        # Display font — a second "Choose…" button sharing the same staged
        # family/size state (_refresh_font_btn updates both buttons).
        self.font_btn2 = QPushButton()
        self.font_btn2.setAccessibleName(tr("Display font"))
        self.font_btn2.clicked.connect(self._choose_font)
        form.addRow(tr("Display font:"), self.font_btn2)
        self._refresh_font_btn()

        # Text spacing (accessibility) — new in Preferences.
        self.line_height = QDoubleSpinBox()
        self.line_height.setRange(1.0, 3.0)
        self.line_height.setSingleStep(0.1)
        self.line_height.setDecimals(1)
        self.line_height.setValue(float(self.settings.get("qt_line_height", 1.5) or 1.5))
        form.addRow(tr("Line height (×):"), self.line_height)

        self.letter_spacing = QDoubleSpinBox()
        self.letter_spacing.setRange(-5.0, 30.0)
        self.letter_spacing.setSingleStep(0.5)
        self.letter_spacing.setDecimals(1)
        self.letter_spacing.setSuffix(" %")
        self.letter_spacing.setValue(
            float(self.settings.get("qt_letter_spacing", 0.0) or 0.0))
        form.addRow(tr("Letter spacing:"), self.letter_spacing)

        self.word_spacing = QDoubleSpinBox()
        self.word_spacing.setRange(0.0, 40.0)
        self.word_spacing.setSingleStep(1.0)
        self.word_spacing.setDecimals(1)
        self.word_spacing.setSuffix(" px")
        self.word_spacing.setValue(
            float(self.settings.get("qt_word_spacing", 0.0) or 0.0))
        form.addRow(tr("Word spacing:"), self.word_spacing)

        self.tabs.addTab(w, tr("Fonts"))

    def _refresh_font_btn(self) -> None:
        fam = self._font_family or tr("(default)")
        txt = f"{fam}  {self._font_size}pt  —  " + tr("Choose…")
        self.font_btn.setText(txt)
        if getattr(self, "font_btn2", None) is not None:
            self.font_btn2.setText(txt)

    def _choose_font(self) -> None:
        current = QFont(self._font_family or "", self._font_size)
        font, ok = QFontDialog.getFont(current, self, tr("Choose Display Font"))
        if ok:
            self._font_family = font.family()
            self._font_size = max(6, font.pointSize())
            self._refresh_font_btn()

    # ── General tab ──────────────────────────────────────────────────────────

    def _build_general_tab(self) -> None:
        w = QWidget()
        form = QFormLayout(w)

        # Interface language — native names shown untranslated so a user can
        # always find their own.  Stored as the language code.
        self.lang_box = QComboBox()
        self._lang_codes: list = []
        cur_lang = get_language()
        for disp, code in available_languages():
            self.lang_box.addItem(disp)
            self._lang_codes.append(code)
        self._orig_lang = cur_lang
        if cur_lang in self._lang_codes:
            self.lang_box.setCurrentIndex(self._lang_codes.index(cur_lang))
        self.lang_box.setToolTip(
            tr("Language for the menus, toolbar, and messages")
        )
        form.addRow(tr("Interface language:"), self.lang_box)

        self.auto_install = QCheckBox(tr("Auto-install optional features on demand"))
        self.auto_install.setChecked(bool(self.settings.get("auto_install", True)))
        form.addRow(tr("Optional features:"), self.auto_install)

        self.auto_updates = QCheckBox(tr("Check for updates on startup"))
        self.auto_updates.setChecked(bool(self.settings.get("auto_check_updates", False)))
        form.addRow(tr("Updates:"), self.auto_updates)

        self.sync_policy = QComboBox()
        self.sync_policy.addItems(_SYNC_POLICIES)
        curs = str(self.settings.get("sync_conflict_policy", "newest"))
        self.sync_policy.setCurrentIndex(
            _SYNC_POLICIES.index(curs) if curs in _SYNC_POLICIES else 0
        )
        form.addRow(tr("Sync conflict policy:"), self.sync_policy)

        self.footnote_mode = QComboBox()
        self.footnote_mode.addItems(_FOOTNOTE_MODES)
        curfn = str(self.settings.get("footnote_mode", "inline"))
        self.footnote_mode.setCurrentIndex(
            _FOOTNOTE_MODES.index(curfn) if curfn in _FOOTNOTE_MODES else 0
        )
        form.addRow(tr("Footnotes:"), self.footnote_mode)

        self.paginate = QCheckBox(tr("Paginate very large documents"))
        self.paginate.setChecked(bool(self.settings.get("qt_paginate_large_docs", False)))
        form.addRow(tr("Large documents:"), self.paginate)

        self.paginate_threshold = QSpinBox()
        self.paginate_threshold.setRange(10000, 1000000)
        self.paginate_threshold.setSingleStep(10000)
        self.paginate_threshold.setSuffix(" words")
        self.paginate_threshold.setValue(
            int(self.settings.get("qt_paginate_threshold_words", 60000) or 60000)
        )
        form.addRow(tr("Pagination threshold:"), self.paginate_threshold)

        self.tabs.addTab(w, tr("General"))

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
        self.hl_master.setChecked(bool(D["highlight_current_word"]))
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
        self.caret_browsing.setChecked(bool(D["qt_caret_browsing"]))
        _combo(self.table_mode, _TABLE_MODES, "table_reading_mode")
        self.skip_code.setChecked(bool(D["tts_skip_code"]))
        # Reading Aids tab (mirrors of the above follow via _link_checkboxes).
        self.aid_bionic.setChecked(bool(D["qt_bionic_reading"]))
        self.aid_ruler.setChecked(bool(D["qt_reading_ruler"]))
        self._line_color["v"] = str(D["qt_current_line_color"])
        self._line_color["repaint"]()
        self._rsvp_text_color["v"] = str(D["qt_rsvp_text_color"])
        self._rsvp_text_color["repaint"]()
        self._rsvp_bg_color["v"] = str(D["qt_rsvp_bg_color"])
        self._rsvp_bg_color["repaint"]()
        self.aid_syllables.setChecked(bool(D["qt_syllable_split"]))
        self.aid_vocab.setChecked(bool(D["qt_vocab_highlight"]))
        self.aid_rsvp.setChecked(bool(D["qt_rsvp_mode"]))
        # Fonts tab (reading/display font mirror the Display resets below).
        self.line_height.setValue(float(D["qt_line_height"]))
        self.letter_spacing.setValue(float(D["qt_letter_spacing"]))
        self.word_spacing.setValue(float(D["qt_word_spacing"]))
        # Voice.  "auto" is always first in the engine combo.
        self.engine_box.setCurrentIndex(0)
        self.rate_spin.setValue(int(D["tts_rate"]))
        self.volume_spin.setValue(int(round(float(D["tts_volume"]) * 100)))
        self.prefer_voice.setText(str(D["tts_prefer_voice"]))
        self.auto_play.setChecked(bool(D["tts_auto_play"]))
        self.eleven_key.setText(str(D["elevenlabs_api_key"]))
        _combo(self.bitrate_box, _AUDIOBOOK_BITRATES, "audiobook_bitrate")
        _combo(self.whisper_box, _WHISPER_MODELS, "whisper_model")
        self.transcript_ts.setChecked(bool(D["transcribe_timestamps"]))
        self.ssml.setChecked(bool(D["use_ssml"]))
        # Display.
        _combo(self.reading_font, _READING_FONTS, "qt_reading_font")
        self._font_family = str(D["qt_font_family"])
        self._font_size = int(D["qt_font_size"])
        self._refresh_font_btn()
        _combo(self.theme_box, self._theme_names, "theme")
        self.follow_os.setChecked(bool(D["qt_follow_os_theme"]))
        # General.
        default_lang = str(D["ui_language"])
        if default_lang in self._lang_codes:
            self.lang_box.setCurrentIndex(self._lang_codes.index(default_lang))
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
        d["highlight_current_word"] = self.hl_master.isChecked()
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
        d["qt_caret_browsing"] = self.caret_browsing.isChecked()
        d["table_reading_mode"] = self.table_mode.currentText()
        d["tts_skip_code"] = self.skip_code.isChecked()
        # Reading Aids tab (on/off toggles + per-aid colors surfaced there).
        d["qt_bionic_reading"] = self.aid_bionic.isChecked()
        d["qt_reading_ruler"] = self.aid_ruler.isChecked()
        d["qt_syllable_split"] = self.aid_syllables.isChecked()
        d["qt_vocab_highlight"] = self.aid_vocab.isChecked()
        d["qt_rsvp_mode"] = self.aid_rsvp.isChecked()
        d["qt_current_line_color"] = self._line_color["v"]
        d["qt_rsvp_text_color"] = self._rsvp_text_color["v"]
        d["qt_rsvp_bg_color"] = self._rsvp_bg_color["v"]
        # Fonts tab (text spacing).
        d["qt_line_height"] = self.line_height.value()
        d["qt_letter_spacing"] = self.letter_spacing.value()
        d["qt_word_spacing"] = self.word_spacing.value()
        # Voice.
        chosen_engine = self.engine_box.currentText()
        d["tts_backend"] = "silent" if chosen_engine == "none" else chosen_engine
        d["tts_rate"] = self.rate_spin.value()
        d["tts_volume"] = self.volume_spin.value() / 100.0
        d["tts_prefer_voice"] = self.prefer_voice.text()
        d["tts_auto_play"] = self.auto_play.isChecked()
        d["elevenlabs_api_key"] = self.eleven_key.text()
        d["audiobook_bitrate"] = self.bitrate_box.currentText()
        d["whisper_model"] = self.whisper_box.currentText()
        d["transcribe_timestamps"] = self.transcript_ts.isChecked()
        d["use_ssml"] = self.ssml.isChecked()
        # Display.
        d["qt_reading_font"] = self.reading_font.currentText()
        d["qt_font_family"] = self._font_family
        d["qt_font_size"] = self._font_size
        d["theme"] = self.theme_box.currentText()
        d["qt_follow_os_theme"] = self.follow_os.isChecked()
        # General.  (ui_language is applied via _set_ui_language in _apply so
        # the chrome rebuilds; write the staged code here all the same.)
        if self._lang_codes:
            d["ui_language"] = self._lang_codes[self.lang_box.currentIndex()]
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
                rsvp.set_colors()
            except Exception:
                pass

        # Display font BEFORE theme: _set_font persists family/size and ends by
        # re-applying the theme itself, so this order avoids one transient
        # render at the stale size.
        try:
            win._set_font(
                family=str(self.settings.get("qt_font_family", "")),
                size=int(self.settings.get("qt_font_size", 14)),
            )
        except Exception:
            pass

        # Theme — mirror the toolbar/menu pickers: a deliberate theme change here
        # marks the choice "explicit" (qt_theme_explicit) so OS-follow won't
        # override it on the next launch.  Conversely, ticking "Follow OS theme"
        # without changing the theme re-arms OS auto-detection by clearing the flag.
        new_theme = str(self.settings.get("theme", "galaxy"))
        theme_changed = new_theme != self._orig_theme
        if theme_changed:
            self.settings._data["qt_theme_explicit"] = True
        elif self.follow_os.isChecked() and not self._orig_follow_os:
            self.settings._data["qt_theme_explicit"] = False
        try:
            win._apply_qt_theme(new_theme)
            if theme_changed:
                # Mirror the menu pickers so screen-reader users hear the
                # switch (the status bar is not spoken by Qt's a11y bridge).
                announce(win.editor, tr("Theme: {name}").format(name=new_theme))
                self._orig_theme = new_theme  # Apply twice ≠ announce twice
        except Exception:
            pass

        # Reading font — route a *change* through the same helper as the
        # M-x reading-font command so the on-demand OFL fetch and the legacy
        # qt_dyslexia_font sync all happen.
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

        # Reading ruler — show/hide the overlay to match the toggle, and keep
        # the View-menu check in sync.
        try:
            ruler_on = bool(self.settings.get("qt_reading_ruler", False))
            win._apply_reading_ruler(ruler_on)
            if hasattr(win, "_ruler_act"):
                win._ruler_act.setChecked(ruler_on)
        except Exception:
            pass

        # RSVP overlay — show/hide to match the toggle (mirrors _qt_toggle_rsvp).
        try:
            rsvp_on = bool(self.settings.get("qt_rsvp_mode", False))
            if rsvp_on:
                ov = win._qt_ensure_rsvp_overlay()
                ov.show()
                ov.raise_()
            elif getattr(win, "_rsvp_overlay", None) is not None:
                win._rsvp_overlay.hide()
            if hasattr(win, "_rsvp_act"):
                win._rsvp_act.setChecked(rsvp_on)
        except Exception:
            pass

        # Text spacing — rebuild the editor font (letter/word spacing live in
        # QFont) and re-apply the line-height block format.
        try:
            win.editor.setFont(win._make_editor_font())
            win._apply_block_spacing()
        except Exception:
            pass

        # Keep the View-menu checkmarks for the other aids in sync with the
        # values just written from the Reading Aids tab.
        for _attr, _key in (
            ("_syllable_act", "qt_syllable_split"),
            ("_vocab_act", "qt_vocab_highlight"),
            ("_current_line_act", "qt_current_line_highlight"),
            ("_bionic_act", "qt_bionic_reading"),
            ("_caret_act", "qt_caret_browsing"),
        ):
            act = getattr(win, _attr, None)
            if act is not None:
                try:
                    act.setChecked(bool(self.settings.get(_key, False)))
                except Exception:
                    pass

        # Caret browsing — reflect the checkbox onto the live reading view
        # (bionic needs no extra hook: _apply_qt_theme above re-renders with
        # the new qt_bionic_reading already written).
        try:
            if not getattr(win, "_qt_edit_mode", False):
                win._apply_caret_mode()
        except Exception:
            pass

        # Interface language — route a *change* through the same helper as
        # the old View-menu radios so the chrome rebuilds live.
        try:
            new_lang = str(self.settings.get("ui_language", "en"))
            if new_lang != self._orig_lang:
                win._set_ui_language(new_lang)
                self._orig_lang = new_lang  # Apply twice ≠ rebuild twice
        except Exception:
            pass

        # Persist everything.
        try:
            self.settings.save()
        except Exception:
            pass

        try:
            win.statusBar().showMessage(tr("Preferences applied"))
        except Exception:
            pass
        try:
            # The status bar is invisible to screen readers — announce too.
            announce(win.editor, tr("Preferences applied"))
        except Exception:
            pass
