"""AidDialogsMixin — methods extracted from StarWindow (main_window.py).

Mixed into StarWindow via ``class StarWindow(AidDialogsMixin, ...)``; operates
on StarWindow instance state and other methods via ``self``, holding no
state of its own.  IMPORT SAFETY: references Qt at module scope — imported
lazily by main_window.py (itself imported by runner.py after the _QT guard).
"""
from .._runtime import *  # noqa: F401,F403


class AidDialogsMixin:
    # ── RSVP ─────────────────────────────────────────────────────────

    def _qt_ensure_rsvp_overlay(self):
        """Create the RSVP overlay lazily (on first use).

        ``_RSVPOverlay`` lives in main_window.py; import it lazily here so this
        mixin (which main_window imports) doesn't create a circular import.
        """
        if self._rsvp_overlay is None:
            from .main_window import _RSVPOverlay
            self._rsvp_overlay = _RSVPOverlay(self.editor, self.settings)
        return self._rsvp_overlay

    def _qt_toggle_rsvp(self) -> None:
        """Toggle the RSVP (Rapid Serial Visual Presentation) overlay.

        Keyed on the overlay's actual visibility rather than the stored setting,
        so a stale ``qt_rsvp_mode`` (e.g. left True by an earlier failed toggle)
        can't require a double click to turn the overlay on."""
        currently_on = self._rsvp_overlay is not None and not self._rsvp_overlay.isHidden()
        new = not currently_on
        self.settings["qt_rsvp_mode"] = new
        if hasattr(self, "_rsvp_act"):
            self._rsvp_act.setChecked(new)
        if new:
            overlay = self._qt_ensure_rsvp_overlay()
            overlay.show()
            overlay.raise_()
        else:
            if self._rsvp_overlay is not None:
                self._rsvp_overlay.hide()
        self.statusBar().showMessage("RSVP mode: " + ("ON" if new else "OFF"))

    # ── Reading ruler / typoscope ──────────────────────────────────────

    def _apply_reading_ruler(self, on: bool) -> None:
        """Show or hide the reading-ruler overlay, wiring caret tracking.

        Teardown-safe: the ``cursorPositionChanged`` connection is made only
        while the ruler is visible and torn down the moment it hides, so a closed
        window never fires the slot into a half-destroyed overlay."""
        if not on:
            ruler = getattr(self, "_reading_ruler", None)
            if ruler is not None:
                try:
                    self.editor.cursorPositionChanged.disconnect(ruler.follow_caret)
                except (TypeError, RuntimeError):
                    pass  # never connected / already gone
                ruler.hide()
            return
        ruler = self._qt_ensure_reading_ruler()
        # Reflect any settings changes made while it was off.
        ruler.set_height(int(self.settings.get("qt_ruler_height", 40)))
        ruler.set_opacity(int(self.settings.get("qt_ruler_opacity", 22)))
        _rc = str(self.settings.get("qt_ruler_color", "") or "").strip() \
            or str(self.settings.get("highlight_color", "cyan"))
        ruler.set_color(QColor(_rc))
        try:
            self.editor.cursorPositionChanged.connect(ruler.follow_caret)
        except (TypeError, RuntimeError):
            pass
        ruler.follow_caret()
        ruler.show()
        ruler.raise_()

    def _qt_ensure_reading_ruler(self):
        """Create the reading-ruler overlay lazily (on first use)."""
        if getattr(self, "_reading_ruler", None) is None:
            from .main_window import _ReadingRulerOverlay
            self._reading_ruler = _ReadingRulerOverlay(self.editor, self.settings)
        return self._reading_ruler

    def _qt_reading_ruler_dialog(self) -> None:
        """Adjust the reading ruler's band height and opacity (previews live)."""
        keys = ("qt_ruler_height", "qt_ruler_opacity", "qt_ruler_color")
        orig = {k: self.settings.get(k) for k in keys}

        dlg = QDialog(self)
        dlg.setWindowTitle("Reading Ruler")
        form = QFormLayout(dlg)
        info = QLabel(
            "A translucent band tracks the line you're reading.\n"
            "Changes preview live — OK to keep, Cancel to revert."
        )
        info.setWordWrap(True)
        form.addRow(info)

        height = QSpinBox()
        height.setRange(16, 160)
        height.setSuffix(" px")
        height.setValue(int(orig["qt_ruler_height"] or 40))
        form.addRow("Band height:", height)

        opacity = QSpinBox()
        opacity.setRange(0, 100)
        opacity.setSuffix(" %")
        opacity.setValue(int(orig["qt_ruler_opacity"] or 22))
        form.addRow("Band opacity:", opacity)

        # Colour: a swatch button opens the system colour dialog; "Use highlight
        # color" reverts to matching the spoken-word highlight (the default).
        ruler_col = {"v": str(orig["qt_ruler_color"] or "")}

        def _hl_col() -> str:
            return str(self.settings.get("highlight_color", "cyan"))

        color_btn = QPushButton()

        def _paint_col() -> None:
            c = QColor(ruler_col["v"] or _hl_col())
            if c.isValid():
                lum = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
                fg = "#000000" if lum > 140 else "#ffffff"
                color_btn.setStyleSheet(
                    f"QPushButton{{background-color:{c.name()};color:{fg};"
                    "padding:5px;border:1px solid #888;}"
                )
                color_btn.setText(c.name() + ("" if ruler_col["v"] else "  (highlight)"))
            else:
                color_btn.setStyleSheet("")
                color_btn.setText("Highlight color")

        def _pick_col() -> None:
            start = QColor(ruler_col["v"] or _hl_col())
            if not start.isValid():
                start = QColor("#06b6d4")
            chosen = QColorDialog.getColor(start, dlg, "Choose ruler color")
            if chosen.isValid():
                ruler_col["v"] = chosen.name()
                _paint_col()
                _preview()

        color_btn.clicked.connect(_pick_col)
        _paint_col()
        col_wrap = QWidget()
        col_hb = QHBoxLayout(col_wrap)
        col_hb.setContentsMargins(0, 0, 0, 0)
        col_hb.addWidget(color_btn, 1)
        use_hl_btn = QPushButton("Use highlight color")

        def _use_hl() -> None:
            ruler_col["v"] = ""
            _paint_col()
            _preview()

        use_hl_btn.clicked.connect(_use_hl)
        col_hb.addWidget(use_hl_btn)
        form.addRow("Band color:", col_wrap)

        def _preview() -> None:
            self.settings._data["qt_ruler_height"] = height.value()
            self.settings._data["qt_ruler_opacity"] = opacity.value()
            self.settings._data["qt_ruler_color"] = ruler_col["v"]
            ruler = getattr(self, "_reading_ruler", None)
            if ruler is not None:
                ruler.set_height(height.value())
                ruler.set_opacity(opacity.value())
                ruler.set_color(QColor(ruler_col["v"] or _hl_col()))

        height.valueChanged.connect(lambda _v: _preview())
        opacity.valueChanged.connect(lambda _v: _preview())

        try:
            _ok = QDialogButtonBox.StandardButton.Ok
            _cancel = QDialogButtonBox.StandardButton.Cancel
        except AttributeError:
            _ok = QDialogButtonBox.Ok  # type: ignore[attr-defined]
            _cancel = QDialogButtonBox.Cancel  # type: ignore[attr-defined]
        buttons = QDialogButtonBox(_ok | _cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        result = dlg.exec() if _QT == "PyQt6" else dlg.exec_()
        if result:
            _preview()
            self.settings.save()
            self.statusBar().showMessage(
                f"Reading ruler — {height.value()} px, {opacity.value()}% opacity"
            )
        else:
            for k, v in orig.items():
                self.settings._data[k] = v
            ruler = getattr(self, "_reading_ruler", None)
            if ruler is not None:
                ruler.set_height(int(orig["qt_ruler_height"] or 40))
                ruler.set_opacity(int(orig["qt_ruler_opacity"] or 22))
                _oc = str(orig["qt_ruler_color"] or "") or str(
                    self.settings.get("highlight_color", "cyan")
                )
                ruler.set_color(QColor(_oc))

    def _qt_rsvp_position_dialog(self) -> None:
        """Show a 3×3 grid dialog to pick the RSVP overlay position.

        The nine buttons correspond to screen quadrants — vital for readers
        with a restricted visual field who can only comfortably focus on a
        particular area of the screen.
        """
        dlg = QDialog(self)
        dlg.setWindowTitle("RSVP Position")
        outer = QVBoxLayout(dlg)

        info = QLabel(
            "Choose where the RSVP word appears.\n"
            "Pick the quadrant that suits your visual field."
        )
        info.setWordWrap(True)
        outer.addWidget(info)

        try:
            from PyQt6.QtWidgets import QGridLayout
        except ImportError:
            from PyQt5.QtWidgets import QGridLayout  # type: ignore[no-redef]

        grid = QGridLayout()
        outer.addLayout(grid)

        current_pos = str(self.settings.get("qt_rsvp_position", "top-center"))

        def _pick(key: str) -> None:
            self.settings["qt_rsvp_position"] = key
            overlay = self._qt_ensure_rsvp_overlay()
            overlay.set_position(key)
            dlg.accept()
            self.statusBar().showMessage(f"RSVP position: {key}")

        from .main_window import _RSVPOverlay
        for row, col, key, label in _RSVPOverlay._GRID:
            btn = QPushButton(label)
            btn.setMinimumSize(80, 60)
            if key == current_pos:
                btn.setStyleSheet("font-weight: bold; border: 2px solid #82aaff;")
            _k = key  # capture loop variable
            btn.clicked.connect(lambda _checked=False, k=_k: _pick(k))
            grid.addWidget(btn, row, col)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel
                              if hasattr(QDialogButtonBox, "StandardButton")
                              else QDialogButtonBox.Cancel)  # type: ignore[attr-defined]
        bb.rejected.connect(dlg.reject)
        outer.addWidget(bb)
        dlg.exec() if hasattr(dlg, "exec") and not hasattr(dlg, "exec_") else dlg.exec_()  # type: ignore[attr-defined]

    def _qt_text_spacing_dialog(self) -> None:
        """Adjust line height, letter spacing, and word spacing.

        Changes preview live; OK keeps them, Cancel reverts.  Spacing is
        a recognized accommodation that reduces crowding for dyslexic and
        low-vision readers (WCAG 1.4.12 Text Spacing).
        """
        keys = ("qt_line_height", "qt_letter_spacing", "qt_word_spacing")
        orig = {k: self.settings.get(k) for k in keys}

        dlg = QDialog(self)
        dlg.setWindowTitle("Text Spacing")
        form = QFormLayout(dlg)
        info = QLabel(
            "Generous spacing reduces crowding (WCAG 1.4.12).\n"
            "Changes preview live — OK to keep, Cancel to revert."
        )
        info.setWordWrap(True)
        form.addRow(info)

        lh = QDoubleSpinBox()
        lh.setRange(1.0, 3.0)
        lh.setSingleStep(0.1)
        lh.setDecimals(2)
        lh.setValue(float(orig["qt_line_height"] or 1.5))
        form.addRow("Line height (×):", lh)

        le = QDoubleSpinBox()
        le.setRange(0.0, 40.0)
        le.setSingleStep(1.0)
        le.setDecimals(1)
        le.setSuffix(" %")
        le.setValue(float(orig["qt_letter_spacing"] or 0.0))
        form.addRow("Extra letter spacing:", le)

        wd = QDoubleSpinBox()
        wd.setRange(0.0, 40.0)
        wd.setSingleStep(1.0)
        wd.setDecimals(1)
        wd.setSuffix(" px")
        wd.setValue(float(orig["qt_word_spacing"] or 0.0))
        form.addRow("Extra word spacing:", wd)

        def _preview() -> None:
            # Mutate in-memory only (no disk write) so Cancel can revert.
            self.settings._data["qt_line_height"] = lh.value()
            self.settings._data["qt_letter_spacing"] = le.value()
            self.settings._data["qt_word_spacing"] = wd.value()
            self._apply_text_spacing()

        lh.valueChanged.connect(lambda _v: _preview())
        le.valueChanged.connect(lambda _v: _preview())
        wd.valueChanged.connect(lambda _v: _preview())

        try:
            _ok = QDialogButtonBox.StandardButton.Ok  # PyQt6
            _cancel = QDialogButtonBox.StandardButton.Cancel
        except AttributeError:
            _ok = QDialogButtonBox.Ok  # type: ignore[attr-defined]
            _cancel = QDialogButtonBox.Cancel  # type: ignore[attr-defined]
        buttons = QDialogButtonBox(_ok | _cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        result = dlg.exec() if _QT == "PyQt6" else dlg.exec_()
        if result:
            _preview()
            self.settings.save()
            self.statusBar().showMessage(
                f"Spacing — line {lh.value():.2f}×, letter +{le.value():.0f}%, "
                f"word +{wd.value():.0f}px"
            )
        else:
            for k, v in orig.items():
                self.settings._data[k] = v
            self._apply_text_spacing()

    def _qt_karaoke_dialog(self) -> None:
        """Tune the per-word karaoke highlight: style, color, speed, lead.

        Different readers track best with different cues — a sharp filled
        highlight, a colored underline, or bold text — and at different
        lead/lag offsets relative to the audio.
        """
        keys = (
            "highlight_style",
            "highlight_color",
            "sentence_highlight_color",
            "highlight_speed",
            "highlight_lead_words",
            "highlight_granularity",
        )
        orig = {k: self.settings.get(k) for k in keys}

        dlg = QDialog(self)
        dlg.setWindowTitle("Karaoke Highlight")
        form = QFormLayout(dlg)
        info = QLabel(
            "Tune how the spoken word is marked as it is read.\n"
            "Changes preview live — OK to keep, Cancel to revert."
        )
        info.setWordWrap(True)
        form.addRow(info)

        _GRANS = ["word", "sentence", "both"]
        gran_box = QComboBox()
        gran_box.addItems(_GRANS)
        cur_gran = str(orig["highlight_granularity"] or "word")
        gran_box.setCurrentIndex(
            _GRANS.index(cur_gran) if cur_gran in _GRANS else 0
        )
        gran_box.setToolTip(
            "Highlight the spoken word, the whole sentence (less flicker),\n"
            "or both (sentence band + word)."
        )
        form.addRow("Granularity:", gran_box)

        _STYLES = ["background", "underline", "box", "bold", "color"]
        style_box = QComboBox()
        style_box.addItems(_STYLES)
        cur_style = str(orig["highlight_style"] or "background")
        style_box.setCurrentIndex(
            _STYLES.index(cur_style) if cur_style in _STYLES else 0
        )
        form.addRow("Style:", style_box)

        # Colour pickers — a swatch button opens the system colour dialog for the
        # spoken word and (in "both" granularity) the sentence band, so the two
        # can be set to clearly distinct colours.
        word_state = {"v": str(orig["highlight_color"] or "cyan")}
        sent_state = {"v": str(orig["sentence_highlight_color"] or "")}

        def _swatch(state: dict, allow_theme: bool):
            btn = QPushButton()

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
                    btn.setText("Theme default")

            def _pick() -> None:
                start = (
                    QColor(state["v"])
                    if state["v"] and QColor(state["v"]).isValid()
                    else QColor("#888888")
                )
                chosen = QColorDialog.getColor(start, dlg, "Choose highlight color")
                if chosen.isValid():
                    state["v"] = chosen.name()
                    _paint()
                    _preview()

            btn.clicked.connect(_pick)
            _paint()
            if not allow_theme:
                return btn
            wrap = QWidget()
            hb = QHBoxLayout(wrap)
            hb.setContentsMargins(0, 0, 0, 0)
            hb.addWidget(btn, 1)
            theme_btn = QPushButton("Use theme")
            theme_btn.setToolTip("Match the theme's selection colour")

            def _use_theme() -> None:
                state["v"] = ""
                _paint()
                _preview()

            theme_btn.clicked.connect(_use_theme)
            hb.addWidget(theme_btn)
            return wrap

        word_btn = _swatch(word_state, False)
        word_btn.setToolTip(
            "Color of the spoken word (and the whole sentence in Sentence mode)"
        )
        form.addRow("Word color:", word_btn)
        sent_widget = _swatch(sent_state, True)
        sent_widget.setToolTip("Color of the sentence band (Both mode)")
        form.addRow("Sentence color:", sent_widget)

        speed = QDoubleSpinBox()
        speed.setRange(0.5, 1.5)
        speed.setSingleStep(0.05)
        speed.setDecimals(2)
        speed.setValue(float(orig["highlight_speed"] or 1.0))
        speed.setToolTip(
            "Highlight pacing relative to speech (1.0 = match WPM).\n"
            "Applies on the next play."
        )
        form.addRow("Speed (× WPM):", speed)

        lead = QSpinBox()
        lead.setRange(-5, 5)
        lead.setValue(int(orig["highlight_lead_words"] or 0))
        lead.setToolTip("Words the highlight leads (+) or lags (−) the audio")
        form.addRow("Lead / lag (words):", lead)

        def _preview() -> None:
            self.settings._data["highlight_style"] = style_box.currentText()
            self.settings._data["highlight_color"] = word_state["v"]
            self.settings._data["sentence_highlight_color"] = sent_state["v"]
            self.settings._data["highlight_speed"] = speed.value()
            self.settings._data["highlight_lead_words"] = lead.value()
            self.settings._data["highlight_granularity"] = gran_box.currentText()
            self._rebuild_hl_fmt()

        gran_box.currentTextChanged.connect(lambda _v: _preview())
        style_box.currentTextChanged.connect(lambda _v: _preview())
        speed.valueChanged.connect(lambda _v: _preview())
        lead.valueChanged.connect(lambda _v: _preview())

        try:
            _ok = QDialogButtonBox.StandardButton.Ok  # PyQt6
            _cancel = QDialogButtonBox.StandardButton.Cancel
        except AttributeError:
            _ok = QDialogButtonBox.Ok  # type: ignore[attr-defined]
            _cancel = QDialogButtonBox.Cancel  # type: ignore[attr-defined]
        buttons = QDialogButtonBox(_ok | _cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        result = dlg.exec() if _QT == "PyQt6" else dlg.exec_()
        if result:
            _preview()
            self.settings.save()
            _msg = (
                f"Highlight — {gran_box.currentText()}, "
                f"{style_box.currentText()}, word {word_state['v']}"
            )
            if sent_state["v"]:
                _msg += f", sentence {sent_state['v']}"
            _msg += f", {speed.value():.2f}×, lead {lead.value():+d}"
            self.statusBar().showMessage(_msg)
        else:
            for k, v in orig.items():
                self.settings._data[k] = v
            self._rebuild_hl_fmt()

    def _qt_change_font_dialog(self) -> None:
        """Open the system font picker to choose family, style, and size.

        Uses Qt's built-in QFontDialog so the user gets the full OS
        font browser with live preview.  Both the chosen family and the
        chosen point size are applied immediately and persisted.
        """
        fam = str(self.settings.get("qt_font_family", "Georgia"))
        fsz = int(self.settings.get("qt_font_size", 14))
        current_font = QFont(fam, fsz)
        font, ok = QFontDialog.getFont(current_font, self, "Choose Display Font")
        if ok:
            self._set_font(family=font.family(), size=max(6, font.pointSize()))

