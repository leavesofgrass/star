"""DocOpsMixin — methods extracted from StarWindow (main_window.py).

Mixed into StarWindow via ``class StarWindow(DocOpsMixin, ...)``; operates
on StarWindow instance state and other methods via ``self``, holding no
state of its own.  IMPORT SAFETY: references Qt at module scope — imported
lazily by main_window.py (itself imported by runner.py after the _QT guard).
"""
from .._runtime import *  # noqa: F401,F403
from ..citations import _fetch_citation_by_doi


class DocOpsMixin:
    # ── Archive ingestion (Qt GUI) ─────────────────────────────────────────

    def _qt_open_archive(self) -> None:
        """Open a ZIP / TAR / 7z / RAR archive (File ▸ Open Archive…)."""
        from ..archive import list_members
        dest, _ = QFileDialog.getOpenFileName(
            self,
            "Open Archive",
            str(Path.home()),
            "Archives (*.zip *.tar *.tar.gz *.tgz *.tar.xz *.tar.bz2 *.7z *.rar);;All Files (*)",
        )
        if not dest:
            return
        try:
            members = list_members(dest)
        except Exception as e:
            self.statusBar().showMessage(f"Cannot read archive: {e}")
            return
        if not members:
            self.statusBar().showMessage("No readable documents in archive")
            return
        if len(members) == 1:
            from ..archive import make_ref
            ref = make_ref(dest, members[0])
            self._load_document(ref)
            return
        # Multiple members: let user pick one (or load the index)
        labels = members
        chosen, ok = QInputDialog.getItem(
            self, "Archive Members", f"Open member from {Path(dest).name}:", labels, 0, False
        )
        if ok and chosen:
            from ..archive import make_ref
            ref = make_ref(dest, chosen)
            self._load_document(ref)
        else:
            # Load the index document
            self._load_document(dest)

    # ── Metadata editor (Qt GUI) ───────────────────────────────────────────

    def _qt_metadata_editor(self) -> None:
        """Open the Metadata Editor for the current document."""
        if not self.doc:
            self.statusBar().showMessage("No document loaded")
            return
        key = self.doc.path or self.doc.title or ""
        if not key:
            return
        library: Dict[str, Any] = dict(self.settings.get("library") or {})
        entry: Dict[str, Any] = dict(library.get(key) or {})
        meta: Dict[str, Any] = dict(entry.get("meta") or {})

        dlg = QDialog(self)
        dlg.setWindowTitle("Document Metadata")
        dlg.resize(550, 380)
        layout = QVBoxLayout(dlg)

        fields = [("title", "Title"), ("author", "Author"), ("year", "Year"),
                  ("doi", "DOI"), ("isbn", "ISBN"), ("publisher", "Publisher")]
        edits: Dict[str, Any] = {}
        form = QFormLayout()
        for fname, flabel in fields:
            edit = QLineEdit(str(meta.get(fname) or ""))
            edits[fname] = edit
            form.addRow(flabel + ":", edit)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        lookup_doi_btn = QPushButton("Look up DOI")
        lookup_isbn_btn = QPushButton("Look up ISBN")
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        for b in (lookup_doi_btn, lookup_isbn_btn, save_btn, cancel_btn):
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        status_lbl = QLabel("")
        layout.addWidget(status_lbl)

        def _fill(data: Dict[str, Any]) -> None:
            for fname, _ in fields:
                if data.get(fname):
                    edits[fname].setText(str(data[fname]))

        def _lookup_doi() -> None:
            doi = edits["doi"].text().strip()
            if not doi:
                status_lbl.setText("Enter a DOI first")
                return
            status_lbl.setText(f"Looking up {doi!r}…")
            def _do():
                try:
                    c = _fetch_citation_by_doi(doi)
                    _fill(c)
                    status_lbl.setText("DOI metadata filled")
                except Exception as e:
                    status_lbl.setText(f"DOI lookup failed: {e}")
            threading.Thread(target=_do, daemon=True).start()

        def _lookup_isbn() -> None:
            isbn = edits["isbn"].text().strip()
            if not isbn:
                status_lbl.setText("Enter an ISBN first")
                return
            from ..citations import _valid_isbn, _fetch_metadata_by_isbn
            if not _valid_isbn(isbn):
                status_lbl.setText(f"ISBN {isbn!r} failed checksum validation")
                return
            status_lbl.setText(f"Looking up ISBN {isbn!r}…")
            def _do():
                m, msg = _fetch_metadata_by_isbn(isbn)
                if m:
                    _fill(m)
                    status_lbl.setText("ISBN metadata filled")
                else:
                    status_lbl.setText(f"Lookup: {msg}")
            threading.Thread(target=_do, daemon=True).start()

        def _save() -> None:
            for fname, _ in fields:
                val = edits[fname].text().strip()
                if val:
                    meta[fname] = val
                elif fname in meta:
                    del meta[fname]
            entry["meta"] = meta
            library[key] = entry
            self.settings.set("library", library)
            self.statusBar().showMessage("Metadata saved")
            dlg.accept()

        lookup_doi_btn.clicked.connect(_lookup_doi)
        lookup_isbn_btn.clicked.connect(_lookup_isbn)
        save_btn.clicked.connect(_save)
        cancel_btn.clicked.connect(dlg.reject)
        dlg.exec()

    # ── Video export (Qt GUI) ──────────────────────────────────────────────

    def _qt_export_video(self) -> None:
        """Export current document as a karaoke MP4 video (File ▸ Export ▸ Video…)."""
        if not self.doc:
            self.statusBar().showMessage("No document loaded")
            return
        if not self.doc.plain_text.strip():
            self.statusBar().showMessage("Document has no readable text")
            return
        vid = self.settings.get("video") or {}
        last_dir = vid.get("last_export_dir") or str(
            Path(self.doc.path).parent if self.doc.path else Path.home()
        )
        p = Path(self.doc.path) if self.doc.path else Path("export")
        default = str(Path(last_dir) / (p.stem + ".mp4"))
        dest, _ = QFileDialog.getSaveFileName(
            self, "Export as Video", default, "Video (*.mp4);;All Files (*)"
        )
        if not dest:
            return
        self.statusBar().showMessage("Rendering karaoke video… this may take a minute")
        doc = self.doc
        backend = self.tts_manager._backend

        def _do_export() -> None:
            from ..video import export_video
            try:
                result = export_video(doc, self.settings, dest, tts_backend=backend)
                if result.get("error"):
                    self._export_audio_signal.emit(f"Video export error: {result['error']}")
                else:
                    cues = result.get("cues", 0)
                    self._export_audio_signal.emit(f"Video exported → {dest}  ({cues} sentences)")
                    vid2 = dict(self.settings.get("video") or {})
                    vid2["last_export_dir"] = str(Path(dest).parent)
                    self.settings.set("video", vid2)
            except Exception as exc:
                self._export_audio_signal.emit(f"Video export error: {exc}")

        threading.Thread(target=_do_export, daemon=True).start()

    def _qt_pick_backend(self) -> None:
        """Choose the active TTS engine (pyttsx3 / espeak / piper / …).

        Lets the user switch to a neural backend such as Piper
        without editing settings.json.  Switching to a backend with no
        available voice keeps the previous engine and explains why.
        """
        engines = [
            "auto",
            "pyttsx3",
            "espeak",
            "festival",
            "piper",
            "coqui",
            "dectalk",
            "none",
        ]
        current = str(self.settings.get("tts_backend", "auto"))
        cur_idx = engines.index(current) if current in engines else 0
        chosen, ok = QInputDialog.getItem(
            self,
            "Choose TTS Engine",
            "Speech backend:",
            engines,
            cur_idx,
            False,
        )
        if not ok:
            return
        backend_name = "silent" if chosen == "none" else chosen
        self.tts_manager.change_backend(backend_name)
        active = self.tts_manager.backend_name
        if chosen in ("piper", "coqui") and active != chosen:
            hint = (
                "Install the piper binary and a .onnx voice model, then set"
                " 'piper_model' in settings.json."
                if chosen == "piper"
                else "Install Coqui TTS (pip install TTS)."
            )
            self.statusBar().showMessage(
                f"{chosen} unavailable — using {active}. {hint}"
            )
        else:
            self.statusBar().showMessage(f"TTS engine: {active}")

