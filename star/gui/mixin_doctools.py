"""DocToolsMixin — document tools & sources, extracted from mixin_navigation.py.

Mixed into StarWindow; holds no state, operates via ``self``. These are
menu/command actions (reading statistics, summarize, define word, translate,
open feed, folder-as-library / bookshelf) — distinct from the core keyboard
navigation that remains in NavigationMixin.

IMPORT SAFETY: references Qt at module scope — imported lazily by main_window.py.
"""
from .._runtime import *  # noqa: F401,F403
from ..i18n import tr
from ..feeds import _FEEDPARSER, fetch_feed
from ..library import (
    add_library_folder,
    library_folders,
    scan_library,
    sidecars_by_folder,
)
from ..stats import _fmt_duration, _format_reading_stats, _library_entries
from ..dictionary import (
    availability as _dict_availability,
    define as _dict_define,
    format_definition_markdown as _dict_markdown,
)
from ..summarize import _SUMY, summarize_document
from ..translate import _DEEP_TRANSLATOR, COMMON_LANGUAGES, translate_text
from ._qtcompat import _USER_ROLE


class DocToolsMixin:
    def _stats_poll(self) -> None:
        """Feed the reading-statistics tracker (called by a 1 s QTimer)."""
        try:
            path = self.doc.path if self.doc else ""
            speaking = self.tts_manager.speaking
            wm = getattr(self.doc, "word_map", []) if self.doc else []
            widx = self.tts_manager.current_word_idx if speaking else -1
            self.stats.tick(speaking, path, widx, len(wm))
        except Exception:
            pass

    def _qt_reading_stats(self) -> None:
        """Show the reading-statistics dashboard in a dialog."""
        try:
            self.stats.flush()
        except Exception:
            pass
        path = self.doc.path if self.doc else ""
        title = self.doc.title if self.doc else ""
        html = self._md_to_html(_format_reading_stats(self.settings, path, title))
        dlg = QDialog(self)
        dlg.setWindowTitle("Reading Statistics")
        dlg.resize(560, 520)
        lay = QVBoxLayout(dlg)
        view = QTextBrowser()
        view.setHtml(html)
        lay.addWidget(view)
        try:
            _ok_btn = QDialogButtonBox.StandardButton.Ok
        except AttributeError:
            _ok_btn = QDialogButtonBox.Ok  # type: ignore[attr-defined]
        buttons = QDialogButtonBox(_ok_btn)
        buttons.accepted.connect(dlg.accept)
        lay.addWidget(buttons)
        dlg.exec() if _QT == "PyQt6" else dlg.exec_()

    def _qt_summarize(self) -> None:
        """Summarize the current document with LexRank and show the result.

        Runs on a background thread because LexRank can take a moment on a
        long document; the result is delivered to the GUI thread via
        _summary_signal.
        """
        if not _SUMY:
            QMessageBox.information(
                self,
                "Summarization unavailable",
                "Document summarization requires sumy:\n\n    pip install sumy",
            )
            return
        if not self.doc:
            self.statusBar().showMessage("Open a document to summarize")
            return
        text = self.doc.plain_text or ""
        if not text.strip():
            self.statusBar().showMessage("Nothing to summarize")
            return
        n = int(self.settings.get("summary_sentences", 7))
        self.statusBar().showMessage("Summarizing…")

        def _work() -> None:
            try:
                summary = summarize_document(text, n)
                self._summary_signal.emit(summary, "")
            except Exception as exc:  # noqa: BLE001
                self._summary_signal.emit("", str(exc))

        threading.Thread(target=_work, daemon=True).start()

    def _qt_on_summary(self, summary: str, error: str) -> None:
        """Main-thread handler: show the summary (or an error) in a dialog."""
        if error:
            QMessageBox.warning(self, "Summarization failed", error)
            self.statusBar().showMessage("Summarization failed")
            return
        if not summary:
            self.statusBar().showMessage("Summary was empty")
            return
        title = self.doc.title if self.doc else "Document"
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Summary — {title}")
        dlg.resize(560, 420)
        lay = QVBoxLayout(dlg)
        view = QTextEdit()
        view.setReadOnly(True)
        view.setPlainText(summary)
        view.setAccessibleName("Document summary")
        lay.addWidget(view)
        try:
            _ok_btn = QDialogButtonBox.StandardButton.Ok
        except AttributeError:
            _ok_btn = QDialogButtonBox.Ok  # type: ignore[attr-defined]
        buttons = QDialogButtonBox(_ok_btn)
        buttons.accepted.connect(dlg.accept)
        lay.addWidget(buttons)
        self.statusBar().showMessage("Summary ready")
        dlg.exec() if _QT == "PyQt6" else dlg.exec_()

    def _qt_define_word(self) -> None:
        """Define the selected word (or the word under the cursor) offline.

        WordNet's first access loads its corpus, so the lookup runs on a
        background thread; the result is delivered to the GUI thread via
        _define_signal.
        """
        cursor = self.editor.textCursor()
        word = cursor.selectedText().strip()
        if not word:
            sel = (
                QTextCursor.SelectionType.WordUnderCursor
                if hasattr(QTextCursor, "SelectionType")
                else QTextCursor.WordUnderCursor  # type: ignore[attr-defined]
            )
            cursor.select(sel)
            word = cursor.selectedText().strip()
        if not word:
            self.statusBar().showMessage("Select a word to define")
            return
        ok, hint = _dict_availability(self.settings)
        if not ok:
            QMessageBox.information(self, "Dictionary unavailable", hint)
            return
        self.statusBar().showMessage(f"Defining “{word}”…")

        def _work() -> None:
            try:
                result = _dict_define(word, self.settings)
                self._define_signal.emit(result, word, "")
            except Exception as exc:  # noqa: BLE001
                self._define_signal.emit(None, word, str(exc))

        threading.Thread(target=_work, daemon=True).start()

    def _qt_on_definition(self, result: object, word: str, error: str) -> None:
        """Main-thread handler: show the definition (or a not-found note)."""
        if error:
            QMessageBox.warning(self, "Lookup failed", error)
            self.statusBar().showMessage("Lookup failed")
            return
        if result is None:
            QMessageBox.information(
                self, "No definition", f"No definition found for “{word}”."
            )
            self.statusBar().showMessage("No definition found")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Definition — {word}")
        dlg.resize(520, 420)
        lay = QVBoxLayout(dlg)
        view = QTextBrowser()
        view.setHtml(self._md_to_html(_dict_markdown(result)))
        view.setAccessibleName(f"Definition of {word}")
        lay.addWidget(view)
        try:
            _ok_btn = QDialogButtonBox.StandardButton.Ok
        except AttributeError:
            _ok_btn = QDialogButtonBox.Ok  # type: ignore[attr-defined]
        buttons = QDialogButtonBox(_ok_btn)
        buttons.accepted.connect(dlg.accept)
        lay.addWidget(buttons)
        self.statusBar().showMessage("Definition ready")
        dlg.exec() if _QT == "PyQt6" else dlg.exec_()

    def _qt_translate(self) -> None:
        """Translate the current document into another language.

        Opens a dialog with a language picker and a result pane; the
        network call runs on a background thread and its result is
        delivered to the GUI thread via _translate_signal.
        """
        if not _DEEP_TRANSLATOR:
            QMessageBox.information(
                self,
                "Translation unavailable",
                "Document translation requires deep-translator:\n\n"
                "    pip install deep-translator",
            )
            return
        if not self.doc or not (self.doc.plain_text or "").strip():
            QMessageBox.information(
                self, "Nothing to translate", "Open a document first."
            )
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Translate — {self.doc.title}")
        dlg.resize(560, 460)
        lay = QVBoxLayout(dlg)

        row = QHBoxLayout()
        row.addWidget(QLabel("Translate to:"))
        combo = QComboBox()
        combo.setAccessibleName(tr("Translate to language"))
        for name, code in COMMON_LANGUAGES:
            combo.addItem(name, code)
        row.addWidget(combo, 1)
        go_btn = QPushButton("Translate")
        row.addWidget(go_btn)
        lay.addLayout(row)

        view = QTextEdit()
        view.setReadOnly(True)
        view.setAccessibleName("Translation result")
        lay.addWidget(view)
        self._translate_view = view
        self._translate_btn = go_btn

        try:
            _close_btn = QDialogButtonBox.StandardButton.Close
        except AttributeError:
            _close_btn = QDialogButtonBox.Close  # type: ignore[attr-defined]
        buttons = QDialogButtonBox(_close_btn)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)

        def _do() -> None:
            code = str(combo.itemData(combo.currentIndex()) or "en")
            self._qt_do_translate(code)

        go_btn.clicked.connect(_do)
        dlg.exec() if _QT == "PyQt6" else dlg.exec_()
        # Drop the widget references so a late result is ignored safely.
        self._translate_view = None
        self._translate_btn = None

    def _qt_do_translate(self, code: str) -> None:
        """Kick off a background translation of the current document."""
        if not self.doc:
            return
        text = self.doc.plain_text or ""
        truncated = len(text) > 15000
        text = text[:15000]
        if getattr(self, "_translate_btn", None) is not None:
            self._translate_btn.setEnabled(False)
        if getattr(self, "_translate_view", None) is not None:
            self._translate_view.setPlainText("Translating…")
        self.statusBar().showMessage(
            "Translating first 15000 characters…"
            if truncated
            else "Translating…"
        )

        def _work() -> None:
            try:
                result = translate_text(text, target_lang=code)
                self._translate_signal.emit(result, "")
            except Exception as exc:  # noqa: BLE001
                self._translate_signal.emit("", str(exc))

        threading.Thread(target=_work, daemon=True).start()

    def _qt_on_translation(self, result: str, error: str) -> None:
        """Main-thread handler: show the translation (or an error)."""
        btn = getattr(self, "_translate_btn", None)
        view = getattr(self, "_translate_view", None)
        try:
            if btn is not None:
                btn.setEnabled(True)
            if error:
                if view is not None:
                    view.setPlainText("")
                QMessageBox.warning(self, "Translation failed", error)
                self.statusBar().showMessage("Translation failed")
                return
            if view is not None:
                view.setPlainText(result or "")
            self.statusBar().showMessage("Translation ready")
        except RuntimeError:
            # The dialog (and its widgets) was closed before the result
            # arrived; nothing left to update.
            pass

    def _qt_open_feed(self) -> None:
        """Prompt for a feed URL, fetch it, and pick an article to open."""
        if not _FEEDPARSER:
            QMessageBox.information(
                self,
                "Feed reading unavailable",
                "Reading RSS / Atom feeds requires feedparser:\n\n"
                "    pip install feedparser",
            )
            return
        url, ok = QInputDialog.getText(
            self, "Open Feed", "Enter an RSS / Atom feed URL:"
        )
        if not ok or not url.strip():
            return
        url = url.strip()
        self.statusBar().showMessage(f"Fetching feed {url} …")

        def _work() -> None:
            try:
                entries = fetch_feed(url)
                self._feed_signal.emit(entries, "")
            except Exception as exc:  # noqa: BLE001
                self._feed_signal.emit([], str(exc))

        threading.Thread(target=_work, daemon=True).start()

    def _qt_on_feed(self, entries: Any, error: str) -> None:
        """Main-thread handler: list the feed's entries; open the chosen one."""
        if error or not entries:
            QMessageBox.information(
                self, "Feed", "No entries found — check the URL."
            )
            self.statusBar().showMessage("No feed entries")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Feed")
        dlg.resize(620, 460)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Choose an article to open:"))
        lst = QListWidget()
        lst.setAccessibleName(tr("Feed articles"))
        lst.setAccessibleDescription(
            tr("Articles in the feed. Select one and press Open, "
               "or double-click to open it.")
        )
        for ent in entries:
            published = ent.get("published", "")
            label = ent.get("title", "") or ent.get("url", "")
            if published:
                label = f"{label}  —  {published}"
            item = QListWidgetItem(label)
            item.setData(_USER_ROLE, ent.get("url", ""))
            if ent.get("summary"):
                item.setToolTip(re.sub(r"<[^>]+>", "", ent["summary"])[:400])
            lst.addItem(item)
        lay.addWidget(lst)

        try:
            _btns = (
                QDialogButtonBox.StandardButton.Open
                | QDialogButtonBox.StandardButton.Cancel
            )
        except AttributeError:
            _btns = QDialogButtonBox.Open | QDialogButtonBox.Cancel  # type: ignore[attr-defined]
        buttons = QDialogButtonBox(_btns)
        lay.addWidget(buttons)

        chosen = {"url": ""}

        def _accept_current() -> None:
            item = lst.currentItem()
            if item is not None:
                chosen["url"] = str(item.data(_USER_ROLE) or "")
            dlg.accept()

        def _accept_item(item: Any) -> None:
            chosen["url"] = str(item.data(_USER_ROLE) or "")
            dlg.accept()

        buttons.accepted.connect(_accept_current)
        buttons.rejected.connect(dlg.reject)
        lst.itemDoubleClicked.connect(_accept_item)
        lst.itemActivated.connect(_accept_item)  # Enter opens (keyboard parity)

        dlg.exec() if _QT == "PyQt6" else dlg.exec_()
        if chosen["url"]:
            self._open_path(chosen["url"])

    def _library_combined_entries(self) -> List[Dict[str, Any]]:
        """All library documents: configured library-folder files first (so a
        synced folder is the library), then recently-opened documents that live
        outside any library folder.  Each entry carries reading progress and a
        ``source`` label (folder name or ``recent``)."""
        positions = self.settings.get("reading_positions", {}) or {}
        stats = self.settings.get("reading_stats", {}) or {}

        def _progress(path: str) -> Tuple[int, float]:
            pct = positions.get(path, {}).get("pct")
            if pct is None:
                pct = stats.get(path, {}).get("pct", 0)
            return int(pct or 0), float(stats.get(path, {}).get("seconds", 0.0))

        sidecars = sidecars_by_folder(self.settings)
        combined: List[Dict[str, Any]] = []
        folder_paths: set = set()
        for e in scan_library(self.settings):
            pct, secs = _progress(e["path"])
            # Prefer synced sidecar progress (it reflects reading on any machine).
            side = sidecars.get(e["folder"], {}).get(e["rel"].replace("\\", "/"))
            if side and "pct" in side:
                pct = int(side.get("pct", pct) or 0)
            folder_paths.add(e["path"])
            combined.append(
                {
                    "path": e["path"],
                    "title": e["title"],
                    "format": e["format"],
                    "pct": pct,
                    "seconds": secs,
                    "last_opened": "",
                    "source": Path(e["folder"]).name or e["folder"],
                }
            )
        for r in _library_entries(self.settings):
            if r["path"] in folder_paths:
                continue
            combined.append({**r, "source": "recent"})
        return combined

    def _qt_pick_library_folder(self) -> None:
        """Choose a folder to use as a library (File ▸ Open Folder as Library…)."""
        folder = QFileDialog.getExistingDirectory(
            self, "Choose a folder to use as a library"
        )
        if folder:
            self._qt_open_folder_as_library(folder)

    def _qt_open_folder_as_library(self, folder: str) -> None:
        """Register *folder* as a library and open the Library browser."""
        resolved = add_library_folder(self.settings, folder)
        self.statusBar().showMessage(f"Library folder: {resolved}")
        self._qt_library()

    def _qt_library(self) -> None:
        """Browse the library; open the chosen document.

        Shows documents from every configured library folder (any folder, e.g. a
        synced Dropbox / OneDrive folder) plus recently-opened files, with
        progress and time read.  Enter / double-click opens the selection; the
        Add Folder… button registers another folder as a library source.
        """
        entries = self._library_combined_entries()
        folders = library_folders(self.settings)
        if not entries and not folders:
            self._qt_pick_library_folder()
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Library")
        dlg.resize(640, 480)
        lay = QVBoxLayout(dlg)
        box = QLineEdit()
        box.setPlaceholderText("Filter by title, path, or folder…  (Enter opens, Esc closes)")
        box.setAccessibleName(tr("Filter library"))
        lst = QListWidget()
        lst.setAccessibleName(tr("Library documents"))
        lst.setAccessibleDescription(
            tr("Documents in your library. Press Enter to open the "
               "selected document.")
        )
        lay.addWidget(box)
        lay.addWidget(lst)
        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Folder…")
        info = QLabel(
            f"{len(entries)} document(s) · "
            f"{len(folders)} library folder(s)" if folders else f"{len(entries)} document(s)"
        )
        btn_row.addWidget(info)
        btn_row.addStretch(1)
        btn_row.addWidget(add_btn)
        lay.addLayout(btn_row)

        def _populate(query: str = "") -> None:
            lst.clear()
            terms = query.lower().split()
            for e in entries:
                hay = (e["title"] + " " + e["path"] + " " + e.get("source", "")).lower()
                if not all(t in hay for t in terms):
                    continue
                fmt = e["format"] or "?"
                tm = _fmt_duration(e["seconds"]) if e["seconds"] else "—"
                src = e.get("source", "")
                label = (
                    f"{e['pct']:>3}%  {e['title']}\n"
                    f"        {fmt}  ·  {tm} read  ·  {src}"
                )
                it = QListWidgetItem(label)
                it.setData(_USER_ROLE, e["path"])
                it.setToolTip(e["path"])
                lst.addItem(it)
            if lst.count():
                lst.setCurrentRow(0)

        def _open() -> None:
            it = lst.currentItem() or (lst.item(0) if lst.count() else None)
            if it is None:
                return
            path = it.data(_USER_ROLE)
            dlg.accept()
            if path:
                self._open_path(str(path))

        def _add_folder() -> None:
            folder = QFileDialog.getExistingDirectory(dlg, "Add a library folder")
            if not folder:
                return
            add_library_folder(self.settings, folder)
            nonlocal entries
            entries = self._library_combined_entries()
            _populate(box.text())
            self.statusBar().showMessage(f"Library folder added: {folder}")

        _populate()
        box.textChanged.connect(_populate)
        box.returnPressed.connect(_open)
        lst.itemActivated.connect(lambda _it: _open())
        add_btn.clicked.connect(_add_folder)
        box.setFocus()
        dlg.exec() if _QT == "PyQt6" else dlg.exec_()

