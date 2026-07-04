"""CitationsMixin — methods extracted from StarWindow (main_window.py).

Mixed into StarWindow via ``class StarWindow(CitationsMixin, ...)``; operates
on StarWindow instance state and other methods via ``self``, holding no
state of its own.  IMPORT SAFETY: references Qt at module scope — imported
lazily by main_window.py (itself imported by runner.py after the _QT guard).
"""
from .._runtime import *  # noqa: F401,F403
from ..citations import _citation_label, _fetch_citation_by_doi, _format_citations, _import_citations


class CitationsMixin:
    # ── Citation manager ──────────────────────────────

    def _qt_load_citations(self) -> List[Dict[str, Any]]:
        return [dict(c) for c in (self.settings.get("citations", []) or [])]

    def _qt_store_citations(self, items: List[Dict[str, Any]]) -> None:
        self.settings.set("citations", items)

    def _qt_import_citations(self) -> None:
        """Import citations from a BibTeX / RIS / CSL-JSON file."""
        src, _flt = QFileDialog.getOpenFileName(
            self,
            "Import Citations",
            "",
            "Citations (*.bib *.ris *.json *.csl);;All Files (*)",
        )
        if not src:
            return
        try:
            imported = _import_citations(src)
        except Exception as exc:  # noqa: BLE001
            self._status_error(f"Import error: {exc}")
            return
        existing = self._qt_load_citations()
        by_id = {c.get("id"): c for c in existing if c.get("id")}
        added = 0
        for c in imported:
            cid = c.get("id")
            if cid and cid in by_id:
                by_id[cid].update(c)  # refresh existing
            else:
                existing.append(c)
                if cid:
                    by_id[cid] = c
                added += 1
        self._qt_store_citations(existing)
        self.statusBar().showMessage(
            f"Imported {len(imported)} citation(s) ({added} new); "
            f"library now {len(existing)}"
        )

    def _qt_export_citations(self) -> None:
        """Export the citation library to BibTeX / RIS / CSL-JSON."""
        items = self._qt_load_citations()
        if not items:
            self.statusBar().showMessage("Citation library is empty")
            return
        dest, _flt = QFileDialog.getSaveFileName(
            self,
            "Export Citations",
            "citations.bib",
            "BibTeX (*.bib);;RIS (*.ris);;CSL-JSON (*.json)",
        )
        if not dest:
            return
        try:
            Path(dest).write_text(
                _format_citations(items, Path(dest).suffix.lower()),
                encoding="utf-8",
            )
            self.statusBar().showMessage(
                f"Exported {len(items)} citation(s) → {dest}"
            )
        except OSError as exc:
            self._status_error(f"Export error: {exc}")

    def _qt_add_citation(self) -> None:
        """Add a citation to the library by hand (a few quick prompts)."""
        fields = [
            ("id", "Citation key (e.g. smith2020):"),
            ("title", "Title:"),
            ("author", "Author(s) (Last, First and Last, First):"),
            ("year", "Year:"),
            ("journal", "Journal / container (optional):"),
            ("doi", "DOI (optional):"),
        ]
        cite: Dict[str, Any] = {"type": "article"}
        for key, prompt in fields:
            val, ok = QInputDialog.getText(self, "Add Citation", prompt)
            if not ok:
                return
            cite[key] = val.strip()
        if not (cite.get("title") or cite.get("id")):
            self.statusBar().showMessage("Citation needs at least a title or key")
            return
        if not cite.get("id"):
            cite["id"] = (
                re.sub(r"\W+", "", cite.get("author", "ref").split(",")[0])
                + str(cite.get("year", ""))
            ) or "ref"
        items = self._qt_load_citations()
        items.append(cite)
        self._qt_store_citations(items)
        self.statusBar().showMessage(f"Added citation [{cite['id']}]")

    def _qt_add_citation_by_doi(self) -> None:
        """Fetch a citation from a DOI via Crossref and add it (background)."""
        doi, ok = QInputDialog.getText(
            self, "Add Citation by DOI", "DOI (e.g. 10.1038/nature12373):"
        )
        if not ok or not doi.strip():
            return
        self.statusBar().showMessage(f"Looking up {doi.strip()} …")

        def _work() -> None:
            try:
                cite = _fetch_citation_by_doi(doi)
                self._doi_signal.emit(json.dumps(cite))
            except Exception as exc:  # noqa: BLE001
                self._doi_signal.emit(f"ERROR: {exc}")

        threading.Thread(target=_work, daemon=True).start()

    def _qt_on_doi(self, payload: str) -> None:
        """Main-thread handler for a Crossref DOI lookup result."""
        if payload.startswith("ERROR: "):
            self.statusBar().showMessage(f"DOI lookup failed: {payload[7:]}")
            return
        try:
            cite = json.loads(payload)
        except ValueError:
            self.statusBar().showMessage("DOI lookup returned bad data")
            return
        items = self._qt_load_citations()
        if any(c.get("id") == cite.get("id") for c in items):
            self.statusBar().showMessage(f"[{cite.get('id')}] already in library")
            return
        items.append(cite)
        self._qt_store_citations(items)
        self.statusBar().showMessage(
            f"Added [{cite.get('id')}] {str(cite.get('title', ''))[:50]}"
        )

    def _qt_insert_citation(self) -> None:
        """Insert a Pandoc-style `[@key]` marker at the cursor (or copy it).

        In edit mode the marker is inserted inline; otherwise it is copied
        to the clipboard so it can be pasted after entering edit mode.
        """
        items = self._qt_load_citations()
        if not items:
            self.statusBar().showMessage("No citations — import or add one first")
            return
        labels = [_citation_label(c) for c in items]
        choice, ok = QInputDialog.getItem(
            self, "Insert Citation", "Insert which reference?", labels, 0, False
        )
        if not ok or choice not in labels:
            return
        marker = f"[@{items[labels.index(choice)].get('id', '')}]"
        if self._qt_edit_mode:
            self.editor.textCursor().insertText(marker)
            self.statusBar().showMessage(f"Inserted {marker}")
        else:
            QApplication.clipboard().setText(marker)
            self.statusBar().showMessage(
                f"Copied {marker} — enter edit mode (Ctrl+E) to insert inline"
            )

    def _qt_manage_citations(self) -> None:
        """Browse the citation library; copy a key or delete an entry."""
        items = self._qt_load_citations()
        if not items:
            self.statusBar().showMessage(
                "No citations yet — use Citations → Import or Add"
            )
            return
        labels = [_citation_label(c) for c in items]
        choice, ok = QInputDialog.getItem(
            self, "Citations", "Library (Cancel to close):", labels, 0, False
        )
        if not ok or choice not in labels:
            return
        c = items[labels.index(choice)]
        action, ok2 = QInputDialog.getItem(
            self,
            _citation_label(c),
            "Action:",
            ["Copy key to clipboard", "Link to selected note", "Delete"],
            0,
            False,
        )
        if not ok2:
            return
        if action.startswith("Copy"):
            QApplication.clipboard().setText(str(c.get("id", "")))
            self.statusBar().showMessage(f"Copied [{c.get('id', '')}]")
        elif action.startswith("Link"):
            self._qt_link_citation(c.get("id", ""))
        elif action == "Delete":
            items.remove(c)
            self._qt_store_citations(items)
            self.statusBar().showMessage("Citation deleted")

    def _qt_link_citation(self, cite_id: str) -> None:
        """Attach a citation key to the currently selected note."""
        idx = self._qt_selected_annotation_index()
        items = self._qt_load_annotations()
        if idx < 0 or idx >= len(items):
            self.statusBar().showMessage(
                "Select a note first, then link a citation"
            )
            return
        items[idx]["cite"] = cite_id
        self._qt_store_annotations(items)
        self._qt_build_annotations()
        self.statusBar().showMessage(f"Linked note to [{cite_id}]")

