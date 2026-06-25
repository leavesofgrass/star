"""AidDialogsMixin — methods extracted from StarWindow (main_window.py).

Mixed into StarWindow via ``class StarWindow(AidDialogsMixin, ...)``; operates
on StarWindow instance state and other methods via ``self``, holding no
state of its own.  IMPORT SAFETY: references Qt at module scope — imported
lazily by main_window.py (itself imported by runner.py after the _QT guard).
"""
from .._runtime import *  # noqa: F401,F403


class AidDialogsMixin:
    # ── RSVP ─────────────────────────────────────────────────────────

    def _qt_ensure_rsvp_overlay(self) -> "_RSVPOverlay":
        """Create the RSVP overlay lazily (on first use)."""
        if self._rsvp_overlay is None:
            self._rsvp_overlay = _RSVPOverlay(self.editor, self.settings)
        return self._rsvp_overlay

    def _qt_toggle_rsvp(self) -> None:
        """Toggle the RSVP (Rapid Serial Visual Presentation) overlay."""
        new = not bool(self.settings.get("qt_rsvp_mode", False))
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

        _COLORS = [
            "cyan",
            "yellow",
            "green",
            "magenta",
            "orange",
            "red",
            "blue",
            "white",
        ]
        color_box = QComboBox()
        color_box.setEditable(True)
        color_box.addItems(_COLORS)
        color_box.setEditText(str(orig["highlight_color"] or "cyan"))
        form.addRow("Color:", color_box)

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
            self.settings._data["highlight_color"] = color_box.currentText().strip()
            self.settings._data["highlight_speed"] = speed.value()
            self.settings._data["highlight_lead_words"] = lead.value()
            self.settings._data["highlight_granularity"] = gran_box.currentText()
            self._rebuild_hl_fmt()

        gran_box.currentTextChanged.connect(lambda _v: _preview())
        style_box.currentTextChanged.connect(lambda _v: _preview())
        color_box.editTextChanged.connect(lambda _v: _preview())
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
            self.statusBar().showMessage(
                f"Highlight — {gran_box.currentText()}, "
                f"{style_box.currentText()}, "
                f"{color_box.currentText().strip()}, "
                f"{speed.value():.2f}×, lead {lead.value():+d}"
            )
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

