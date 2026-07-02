"""VoicesMixin — the rich Voice Manager dialog for StarWindow.

The historic voice picker (``_voice_picker_qt`` in mixin_display.py) is a single
``QInputDialog`` list of the *active* backend's voices.  This mixin adds a fuller
**Voice Manager** (Speech ▸ Voice Manager…, Ctrl+Shift+F2) that:

* lists every voice from the active backend **and** the downloadable Piper voice
  catalog in one place;
* filters the list live by language or name;
* **previews** a voice (speaks a short sample) without committing to it;
* **sets** a voice as the current TTS voice;
* keeps a persistent **favorites** list (``tts_favorite_voices`` in settings);
* offers **one-click download** for catalog Piper voices, with status feedback.

IMPORT SAFETY: references Qt at module scope — imported lazily by main_window.py
(itself imported by runner.py after the ``_QT`` guard), like the other
``mixin_*.py`` modules.  All user-facing strings flow through ``tr()`` so the
dialog is translated alongside the rest of the chrome.
"""
from .._runtime import *  # noqa: F401,F403
from ..i18n import tr

# A short, language-neutral-ish sample spoken when previewing a voice.  Kept
# English (the source language) and translated per-catalog so a non-English UI
# hears a matching phrase.
_PREVIEW_TEXT = "The quick brown fox jumps over the lazy dog."


class VoicesMixin:
    # ── favorites persistence ───────────────────────────────────────────────

    def _favorite_voices(self) -> "List[str]":
        """Return the persisted favorite-voice id list (never ``None``)."""
        favs = self.settings.get("tts_favorite_voices", [])
        return list(favs) if isinstance(favs, list) else []

    def _toggle_favorite_voice(self, voice_id: str) -> bool:
        """Add/remove *voice_id* from favorites; return the new membership state.

        Persists immediately (Settings.set writes atomically).  Returns True when
        the voice is now a favorite, False when it was removed.
        """
        favs = self._favorite_voices()
        if voice_id in favs:
            favs.remove(voice_id)
            is_fav = False
        else:
            favs.append(voice_id)
            is_fav = True
        self.settings.set("tts_favorite_voices", favs)
        return is_fav

    # ── data assembly ───────────────────────────────────────────────────────

    def _collect_voices(self) -> "List[Dict[str, str]]":
        """Return the merged voice list shown in the manager.

        Rows are dicts with at least ``id``, ``name``, ``lang``, and ``kind``
        (``"voice"`` for an installed engine voice, ``"piper_dl"`` for a
        downloadable catalog model).  Installed engine voices come first, then
        any not-yet-downloaded Piper catalog voices.
        """
        rows: "List[Dict[str, str]]" = []
        seen_ids: set = set()

        # 1) Voices the active backend can speak right now.
        try:
            for v in self.tts_manager.list_voices():
                vid = str(v.get("id", "") or v.get("name", ""))
                if not vid or vid in seen_ids:
                    continue
                seen_ids.add(vid)
                rows.append(
                    {
                        "id": vid,
                        "name": str(v.get("name", vid)),
                        "lang": str(v.get("lang", "")),
                        "kind": "voice",
                    }
                )
        except Exception:
            pass

        # 2) Downloadable Piper catalog voices (installed ones point at their
        #    cached path; the rest are offered for one-click download).
        try:
            for c in self.tts_manager.piper_catalog():
                if c.get("installed"):
                    vid = c.get("path", "")
                    kind = "voice"
                else:
                    vid = "piper:" + c.get("key", "")
                    kind = "piper_dl"
                if not vid or vid in seen_ids:
                    continue
                seen_ids.add(vid)
                rows.append(
                    {
                        "id": vid,
                        "name": str(c.get("name", "")),
                        "lang": str(c.get("lang", "")),
                        "kind": kind,
                        "key": str(c.get("key", "")),
                        "quality": str(c.get("quality", "")),
                    }
                )
        except Exception:
            pass
        return rows

    def _voice_row_label(self, row: "Dict[str, str]") -> str:
        """Human label for one voice row, marking favorites and downloadables."""
        star = "★ " if row["id"] in self._favorite_voices() else ""
        lang = f"  [{row['lang']}]" if row.get("lang") else ""
        if row.get("kind") == "piper_dl":
            q = f" ({row['quality']})" if row.get("quality") else ""
            return f"{star}⬇ {row['name']}{q}{lang}  — " + tr("download")
        return f"{star}{row['name']}{lang}"

    # ── the dialog ──────────────────────────────────────────────────────────

    def _qt_voice_manager(self) -> None:
        """Open the Voice Manager dialog (Speech ▸ Voice Manager…)."""
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("Voice Manager"))
        dlg.setMinimumWidth(520)
        dlg.setAccessibleName(tr("Voice Manager"))
        layout = QVBoxLayout(dlg)

        # Filter row.
        filt_row = QHBoxLayout()
        filt_lbl = QLabel(tr("Filter:"))
        filt = QLineEdit()
        filt.setPlaceholderText(tr("Filter by language or name…"))
        filt.setAccessibleName(tr("Filter voices"))
        filt.setClearButtonEnabled(True)
        fav_only = QCheckBox(tr("Favorites only"))
        fav_only.setAccessibleName(tr("Show favorites only"))
        filt_row.addWidget(filt_lbl)
        filt_row.addWidget(filt, 1)
        filt_row.addWidget(fav_only)
        layout.addLayout(filt_row)

        # Voice list.
        lst = QListWidget()
        lst.setAccessibleName(tr("Voices"))
        lst.setAccessibleDescription(
            tr("All available voices. Preview speaks a sample; Set as Current "
               "applies the voice; Favorite pins it; download fetches a Piper model.")
        )
        lst.setMinimumHeight(260)
        layout.addWidget(lst, 1)

        status = QLabel("")
        status.setWordWrap(True)
        layout.addWidget(status)

        # Buttons.
        btn_row = QHBoxLayout()
        preview_btn = QPushButton(tr("Preview"))
        preview_btn.setAccessibleDescription(tr("Speak a short sample in this voice"))
        set_btn = QPushButton(tr("Set as Current"))
        set_btn.setAccessibleDescription(tr("Use this voice for speech"))
        fav_btn = QPushButton(tr("Toggle Favorite"))
        fav_btn.setAccessibleDescription(tr("Add or remove this voice from favorites"))
        dl_btn = QPushButton(tr("Download"))
        dl_btn.setAccessibleDescription(tr("Download this Piper voice model"))
        for b in (preview_btn, set_btn, fav_btn, dl_btn):
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        close_box = QDialogButtonBox()
        try:
            _close = QDialogButtonBox.StandardButton.Close
        except AttributeError:  # PyQt5
            _close = QDialogButtonBox.Close  # type: ignore[attr-defined]
        close_box.setStandardButtons(_close)
        close_box.rejected.connect(dlg.reject)
        close_box.accepted.connect(dlg.accept)
        layout.addWidget(close_box)

        # Mutable state shared with the nested callbacks.
        state: "Dict[str, Any]" = {"rows": [], "visible": []}

        def _refresh() -> None:
            """Rebuild ``state['rows']`` and repopulate the filtered list."""
            state["rows"] = self._collect_voices()
            _apply_filter()

        def _apply_filter() -> None:
            needle = filt.text().strip().lower()
            only_fav = fav_only.isChecked()
            favs = self._favorite_voices()
            lst.clear()
            visible: "List[Dict[str, str]]" = []
            for row in state["rows"]:
                if only_fav and row["id"] not in favs:
                    continue
                if needle:
                    hay = (row.get("name", "") + " " + row.get("lang", "")).lower()
                    if needle not in hay:
                        continue
                visible.append(row)
                lst.addItem(self._voice_row_label(row))
            state["visible"] = visible
            if visible and lst.currentRow() < 0:
                lst.setCurrentRow(0)
            dl_btn.setEnabled(any(r.get("kind") == "piper_dl" for r in visible))

        def _current_row() -> "Optional[Dict[str, str]]":
            i = lst.currentRow()
            vis = state["visible"]
            return vis[i] if 0 <= i < len(vis) else None

        def _on_preview() -> None:
            row = _current_row()
            if row is None or row.get("kind") == "piper_dl":
                status.setText(tr("Download this voice before previewing it."))
                return
            try:
                self.tts_manager.stop()
                self.editor.setExtraSelections([])
                self.tts_manager._backend.set_voice(row["id"])
                self.tts_manager._backend.speak(tr(_PREVIEW_TEXT))
                status.setText(tr("Previewing:") + " " + row["name"])
            except Exception:
                status.setText(tr("Preview failed for this voice."))

        def _on_set() -> None:
            row = _current_row()
            if row is None:
                return
            if row.get("kind") == "piper_dl":
                status.setText(tr("Download this voice before selecting it."))
                return
            try:
                self.tts_manager._backend.set_voice(row["id"])
                self.settings.set("tts_voice", row["id"])
                self.tts_manager.stop()
                self.statusBar().showMessage(tr("Voice:") + " " + row["name"])
                status.setText(tr("Current voice:") + " " + row["name"])
            except Exception:
                status.setText(tr("Could not set this voice."))

        def _on_fav() -> None:
            row = _current_row()
            if row is None:
                return
            is_fav = self._toggle_favorite_voice(row["id"])
            status.setText(
                (tr("Added to favorites:") if is_fav else tr("Removed from favorites:"))
                + " " + row["name"]
            )
            _apply_filter()

        def _on_download() -> None:
            row = _current_row()
            if row is None or row.get("kind") != "piper_dl":
                status.setText(tr("Select a downloadable Piper voice first."))
                return
            key = row.get("key", "")
            status.setText(tr("Downloading {name}…").format(name=row["name"]))
            dl_btn.setEnabled(False)
            preview_btn.setEnabled(False)
            QApplication.processEvents()
            path = ""
            try:
                path = self.tts_manager.download_piper_model(key)
            except Exception:
                path = ""
            preview_btn.setEnabled(True)
            if path:
                status.setText(tr("Downloaded {name}.").format(name=row["name"]))
                # Switch to the Piper backend if needed and adopt the new model.
                try:
                    if self.tts_manager.backend_name != "piper":
                        self.tts_manager.change_backend("piper")
                    self.tts_manager._backend.set_voice(path)
                    self.settings.set("tts_backend", "piper")
                    self.settings.set("tts_voice", path)
                    self.settings.set("piper_model", path)
                except Exception:
                    pass
                _refresh()
            else:
                status.setText(
                    tr("Could not download {name} (offline?).").format(name=row["name"])
                )
                dl_btn.setEnabled(True)

        preview_btn.clicked.connect(lambda _c=False: _on_preview())
        set_btn.clicked.connect(lambda _c=False: _on_set())
        fav_btn.clicked.connect(lambda _c=False: _on_fav())
        dl_btn.clicked.connect(lambda _c=False: _on_download())
        filt.textChanged.connect(lambda _t: _apply_filter())
        fav_only.stateChanged.connect(lambda _s: _apply_filter())
        lst.itemDoubleClicked.connect(lambda _i: _on_set())

        _refresh()
        dlg.exec()
