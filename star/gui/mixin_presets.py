"""PresetsMixin — methods extracted from StarWindow (main_window.py).

Mixed into StarWindow via ``class StarWindow(PresetsMixin, ...)``; operates
on StarWindow instance state and other methods via ``self``, holding no
state of its own.  IMPORT SAFETY: references Qt at module scope — imported
lazily by main_window.py (itself imported by runner.py after the _QT guard).
"""
from .._runtime import *  # noqa: F401,F403
from ..stats import _apply_profile_values, _delete_profile, _save_profile
from ._qtcompat import _USER_ROLE


class PresetsMixin:
    # ── Voice & profile presets ───────────────────────────────────────

    def _qt_apply_loaded_settings(self) -> None:
        """Re-apply runtime state after a profile's values were written to
        settings: backend/voice/rate/volume, theme, font, spacing, the
        karaoke highlight format, and the checkable reading-aid actions."""
        try:
            self.tts_manager.change_backend(
                str(self.settings.get("tts_backend", "auto"))
            )
            voice = str(self.settings.get("tts_voice", ""))
            if voice:
                self.tts_manager._backend.set_voice(voice)
            self.tts_manager.set_rate(int(self.settings.get("tts_rate", 265)))
            self.tts_manager.set_volume(float(self.settings.get("tts_volume", 1.0)))
        except Exception:
            pass
        # Visual settings.
        self.editor.setFont(self._make_editor_font())
        self._rebuild_hl_fmt()
        self._apply_qt_theme(str(self.settings.get("theme", "dark")))
        self._apply_text_spacing()
        # Sync the checkable reading-aid menu actions.
        for attr, key in (
            ("_dyslexia_font_act", "qt_dyslexia_font"),
            ("_bionic_act", "qt_bionic_reading"),
            ("_current_line_act", "qt_current_line_highlight"),
            ("_vocab_act", "qt_vocab_highlight"),
        ):
            act = getattr(self, attr, None)
            if act is not None:
                act.setChecked(bool(self.settings.get(key, False)))
        # A profile may have flipped the difficult-word overlay; rebuild it.
        self._qt_refresh_vocab_highlight()

    def _qt_save_profile(self) -> None:
        """Save the current settings as a named profile."""
        name, ok = QInputDialog.getText(
            self,
            "Save Profile",
            "Profile name (voice, rate, theme, font, spacing, highlight):",
        )
        if not ok or not name.strip():
            return
        _save_profile(self.settings, name)
        self.statusBar().showMessage(f"Profile saved: {name.strip()}")

    def _qt_load_profile(self) -> None:
        """Pick a saved profile and apply it in one step."""
        profiles = self.settings.get("profiles", {}) or {}
        if not profiles:
            self.statusBar().showMessage(
                "No profiles saved — use Profiles → Save Current Settings"
            )
            return
        names = sorted(profiles)
        chosen, ok = QInputDialog.getItem(
            self, "Load Profile", "Apply which profile?", names, 0, False
        )
        if not ok or chosen not in profiles:
            return
        _apply_profile_values(self.settings, chosen)
        self._qt_apply_loaded_settings()
        self.statusBar().showMessage(f"Profile loaded: {chosen}")

    def _qt_delete_profile(self) -> None:
        """Pick a saved profile and delete it."""
        profiles = self.settings.get("profiles", {}) or {}
        if not profiles:
            self.statusBar().showMessage("No profiles to delete")
            return
        names = sorted(profiles)
        chosen, ok = QInputDialog.getItem(
            self, "Delete Profile", "Delete which profile?", names, 0, False
        )
        if not ok or chosen not in profiles:
            return
        _delete_profile(self.settings, chosen)
        self.statusBar().showMessage(f"Profile deleted: {chosen}")

    # ── Pronunciation lexicon editor ───────────────────────────

    def _qt_pronunciations(self) -> None:
        """Open the pronunciation-lexicon editor.

        Maps domain terms (drug names, anatomy, acronyms) to a spoken form
        so TTS pronounces them correctly.  Entries apply to every backend
        and are stored in settings under ``pronunciations``.
        """
        dlg = QDialog(self)
        dlg.setWindowTitle("Pronunciation Lexicon")
        dlg.resize(560, 460)
        lay = QVBoxLayout(dlg)

        enabled = QCheckBox("Apply pronunciations while reading")
        enabled.setChecked(bool(self.settings.get("use_pronunciations", True)))
        enabled.toggled.connect(
            lambda v: self.settings.set("use_pronunciations", bool(v))
        )
        lay.addWidget(enabled)

        info = QLabel(
            "Term → spoken form.  Matching is whole-word and case-insensitive."
        )
        info.setWordWrap(True)
        lay.addWidget(info)

        lst = QListWidget()
        lay.addWidget(lst)

        def _refresh() -> None:
            lst.clear()
            lex = self.settings.get("pronunciations", {}) or {}
            for term in sorted(lex):
                item = QListWidgetItem(f"{term}  →  {lex[term]}")
                item.setData(_USER_ROLE, term)
                lst.addItem(item)

        def _store(lex: Dict[str, str]) -> None:
            self.settings.set("pronunciations", lex)
            _refresh()

        def _add() -> None:
            term, ok = QInputDialog.getText(
                dlg, "Add Pronunciation", "Term (as written):"
            )
            if not ok or not term.strip():
                return
            spoken, ok2 = QInputDialog.getText(
                dlg, "Add Pronunciation", f"Spoken form for “{term.strip()}”:"
            )
            if not ok2 or not spoken.strip():
                return
            lex = dict(self.settings.get("pronunciations", {}) or {})
            lex[term.strip()] = spoken.strip()
            _store(lex)

        def _edit() -> None:
            item = lst.currentItem()
            if item is None:
                return
            term = item.data(_USER_ROLE)
            lex = dict(self.settings.get("pronunciations", {}) or {})
            spoken, ok = QInputDialog.getText(
                dlg,
                "Edit Pronunciation",
                f"Spoken form for “{term}”:",
                text=str(lex.get(term, "")),
            )
            if not ok:
                return
            if spoken.strip():
                lex[term] = spoken.strip()
            else:
                lex.pop(term, None)
            _store(lex)

        def _delete() -> None:
            item = lst.currentItem()
            if item is None:
                return
            term = item.data(_USER_ROLE)
            lex = dict(self.settings.get("pronunciations", {}) or {})
            lex.pop(term, None)
            _store(lex)

        row = QHBoxLayout()
        for _lbl, _fn in (
            ("Add…", _add),
            ("Edit…", _edit),
            ("Delete", _delete),
        ):
            b = QPushButton(_lbl)
            b.clicked.connect(lambda _chk=False, f=_fn: f())
            row.addWidget(b)
        lay.addLayout(row)

        lst.itemActivated.connect(lambda _it: _edit())
        _refresh()
        dlg.exec() if _QT == "PyQt6" else dlg.exec_()

