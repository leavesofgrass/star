"""DocumentMixin — methods extracted from StarWindow (main_window.py).

Mixed into StarWindow via ``class StarWindow(DocumentMixin, ...)``; operates
on StarWindow instance state and other methods via ``self``, holding no
state of its own.  IMPORT SAFETY: references Qt at module scope — imported
lazily by main_window.py (itself imported by runner.py after the _QT guard).
"""
from .._runtime import *  # noqa: F401,F403
from ..documents import Document, _build_word_map, load_document
from ..i18n import is_rtl, tr
from ..mathrender import has_math, render_math_to_unicode
from ..pagination import Paginator, paginate
from ..stats import _record_library
from .a11y import announce


class DocumentMixin:
    # ── Document loading ─────────────────────────────────────────────────────

    def _qt_open_url(self) -> None:
        """Prompt for a URL and open it as a document."""
        url, ok = QInputDialog.getText(self, "Open URL", "Enter a web address:")
        if ok and url.strip():
            self._open_path(url.strip())

    def _open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Document",
            "",
            "All Supported "
            "(*.pdf *.doc *.dot *.docx *.ppt *.pptx *.odt "
            "*.epub *.html *.htm *.md *.txt "
            "*.rst *.rest *.adoc *.asciidoc *.asc "
            "*.wiki *.mediawiki *.textile *.creole "
            "*.tex *.ltx *.org "
            "*.csv *.tsv *.xlsx *.r *.rmd)"
            ";;Word / PowerPoint (*.doc *.dot *.docx *.ppt *.pptx)"
            ";;Wiki / Markup "
            "(*.rst *.rest *.adoc *.asciidoc *.asc "
            "*.wiki *.mediawiki *.textile *.creole)"
            ";;LaTeX (*.tex *.ltx)"
            ";;Org-mode (*.org)"
            ";;PDF (*.pdf)"
            ";;All Files (*)",
        )
        if path:
            self._open_path(path)

    def _open_path(self, path: str) -> None:
        # A directory is a library source, not a document — register it and open
        # the Library browser (any folder, e.g. a synced Dropbox/OneDrive folder).
        if path and not path.startswith(("http://", "https://")) and Path(path).is_dir():
            self._qt_open_folder_as_library(path)
            return
        # Save where we were in the *current* document before replacing it.
        self._qt_save_reading_position()
        self.statusBar().showMessage(f"Loading {Path(path).name} …")
        QApplication.processEvents()
        self._pending_doc: Optional[Document] = None

        def _work() -> None:
            try:
                self._pending_doc = load_document(path, self.settings)
            except Exception as _exc:  # noqa: BLE001
                # Never let the background thread die silently and leave
                # the UI frozen.  Create a minimal error document instead
                # so _on_doc_loaded always has something to display.
                _err = Document(
                    path=path,
                    title=f"Error — {Path(path).name}",
                    markdown=(
                        f"# Could not open {Path(path).name}\n\n"
                        f"```\n{_exc}\n```\n\n"
                        "Check that the file exists and is not locked."
                    ),
                    plain_text=str(_exc),
                    format="error",
                )
                self._pending_doc = _err
            # Signal the GUI thread to call _on_doc_loaded.
            # Using a pyqtSignal guarantees safe cross-thread delivery;
            # QMetaObject.invokeMethod with a plain string requires the
            # method to be a registered @pyqtSlot and fails silently on
            # Windows when that registration is missing.
            self._doc_loaded_signal.emit()

        threading.Thread(target=_work, daemon=True).start()

    def _on_doc_loaded(self) -> None:
        # Wrap the entire slot body so that any exception is caught here
        # rather than propagating through PyQt6’s event loop and crashing
        # app.exec() — the symptom on Windows is a brief console window
        # that closes too quickly to read the traceback.
        try:
            self._on_doc_loaded_impl()
        except Exception as _exc:  # noqa: BLE001
            import traceback as _tb

            detail = _tb.format_exc()
            self.statusBar().showMessage(f"Error displaying document: {_exc}")
            # Never modal on a closing window: this slot runs from a queued
            # signal, so a late failure during teardown would otherwise open
            # a dialog nobody can dismiss (the suite-hang class).
            if self._modal_ok():
                try:
                    QMessageBox.critical(
                        self,
                        "Document Display Error",
                        f"Could not display the document.\n\n{detail[:1000]}",
                    )
                except Exception:
                    pass

    def _on_doc_loaded_impl(self) -> None:
        """Inner implementation of _on_doc_loaded, called inside a
        try/except wrapper to prevent slot exceptions from escaping
        into the Qt event loop."""
        doc = getattr(self, "_pending_doc", None)
        if not doc:
            return
        # Disarm auto-play up front: if a previous load armed it and THIS load
        # turns out to be an error page (or the welcome doc), a still-pending
        # flag must not read a traceback aloud when the restore signal lands.
        self._auto_play_pending = False
        self.doc = doc
        # Reset any pagination state from a previously open document; the render
        # decision (whole document vs. windowed) is (re)made below per document.
        self._paginator = None
        self._page_blocks = []
        self._page_block_starts = []
        # Fast size gate (GUI thread, no word map yet): when pagination is opted
        # in and the document is very large, render only a *provisional* leading
        # window instead of laying out the whole HTML — the one-shot full layout
        # is exactly the stall pagination exists to avoid.  The background build
        # then confirms the real page boundaries and re-renders precisely.  For
        # normal-sized documents this is a no-op and the whole document renders
        # exactly as before (byte-for-byte unchanged path).
        provisional = self._page_provisional_render(doc)
        # Remember, so the background build can render the whole document if it
        # ultimately decides *not* to paginate after a provisional window.
        self._page_provisional = provisional
        if not provisional:
            self.editor.setHtml(self._md_to_html(doc.markdown or ""))
            self._apply_block_spacing()  # line-height (reset by setHtml)
        self.editor.setExtraSelections([])  # clear leftover TTS highlights
        # Build the ToC panel from the new document's headings.
        self._qt_build_toc()
        # Populate the Notes panel from saved annotations for this document.
        self._qt_build_annotations()
        # Restore any saved user highlights for this document.
        self._qt_apply_user_highlights()
        # Rebuild the difficult-word overlay for the new document (no-op
        # unless the overlay is toggled on); also repaints the highlights.
        self._qt_refresh_vocab_highlight()

        # Read Qt plain text NOW (main thread required) then hand off.  The word
        # map is aligned against this text; the syllable-splitting aid inserts
        # visible middots into the *rendered* HTML (and thus toPlainText()),
        # which would break the word→offset search.  So when it's on, derive the
        # word-map text from an un-syllabified render — keeping speech and
        # highlighting identical whether or not the aid is displayed.
        #
        # When a provisional window is showing, the visible editor holds only
        # part of the document, so the whole-document word map must be aligned
        # against a *scratch* render of the full markdown (a throwaway
        # QTextDocument — it parses the HTML but never does the expensive visual
        # layout of the visible widget), not the on-screen text.
        if provisional:
            qt_plain = self._scratch_plain_text(doc.markdown or "")
        elif self.settings.get("qt_syllable_split", False):
            qt_plain = self._plain_text_without_syllables(doc.markdown or "")
        else:
            qt_plain = self.editor.document().toPlainText()

        def _build() -> None:
            try:
                plain = doc.plain_text or ""
                # TTSManager word map (line-based, used for timer highlighting)
                flat = qt_plain.splitlines()
                doc.word_map = _build_word_map(plain, flat)
                self.tts_manager.set_word_map(doc.word_map)
                # Decide pagination now that the word map (and thus the true word
                # count) is known.  When the document qualifies, set up the
                # paginator (block→word alignment) and signal the GUI thread to
                # render the initial window — that GUI-thread render also rebuilds
                # the windowed word→char map.  Otherwise the whole document is
                # already rendered, so build the map for it here in the thread.
                did_paginate = self._page_setup_if_large(doc)
                if did_paginate or getattr(self, "_page_provisional", False):
                    # Either we are paginating, or a provisional leading window is
                    # on screen that must now be reconciled (precise window
                    # render when paginating, or a full render when not) on the
                    # GUI thread.  _page_render_initial_window handles both and
                    # rebuilds the appropriate word→char map itself.
                    self._paginate_signal.emit()
                else:
                    # Qt char-offset map for the whole rendered document
                    # (used by _apply_word_highlight).
                    self._build_qt_word_map(plain, qt_plain)
                # Sentence map — same algorithm as StarApp._build_sentence_map
                wm = doc.word_map
                if wm and plain:
                    char_starts = [0]
                    for _m in _SENTENCE_SPLIT_RE.finditer(plain):
                        char_starts.append(_m.end())
                    _wi = 0
                    word_starts: List[int] = []
                    for cs in char_starts:
                        while _wi < len(wm) and wm[_wi].tts_offset < cs:
                            _wi += 1
                        word_starts.append(min(_wi, len(wm) - 1))
                    seen: set = set()
                    result: List[int] = []
                    for ws in word_starts:
                        if ws not in seen:
                            seen.add(ws)
                            result.append(ws)
                    self._qt_sentence_starts = result if result else [0]
                # Signal the main thread to restore the reading position
                # now that the word map and sentence map are both ready.
                self._restore_signal.emit()
            except Exception:
                pass  # word map is best-effort; TTS works without it

        threading.Thread(target=_build, daemon=True).start()
        if getattr(doc, "format", "") == "error":
            # A failed load must not read as a success ("Opened: Error — x").
            # _record_library skips error docs internally, so only the message
            # and the announcement need the branch.
            self.statusBar().showMessage(f"Could not open: {doc.title}")
            announce(
                self.editor,
                tr("Could not open {title}").format(title=doc.title),
            )
            return
        # Record this document in the library / bookshelf — but not the bundled
        # welcome page, which auto-loads at startup and would otherwise clutter
        # the library and recents on every launch.
        if not self._is_welcome(doc):
            _record_library(self.settings, doc)
            # Start reading automatically once the word map is ready — the
            # documented tts_auto_play behavior the TUI has always had (see
            # star/tui/mixin_document.py), consumed by _qt_maybe_auto_play on
            # the _restore_signal so playback begins from the restored
            # position.  The welcome page is excluded, mirroring the TUI.
            self._auto_play_pending = bool(self.settings.get("tts_auto_play", False))
        self.statusBar().showMessage(f"Opened: {doc.title}")
        # Announce the load to assistive tech without stealing focus from the
        # document view (pairs with the visible status-bar message).
        announce(self.editor, tr("Loaded {title}").format(title=doc.title))

    # ── Word-position mapping ─────────────────────────────────────────

    def _build_qt_word_map(self, plain_text: str, qt_text: str) -> None:
        """Populate self._qt_word_map: a list where index i is the
        absolute character offset of the i-th TTS word inside the Qt
        document text.

        Uses a rolling forward search so that repeated words match in
        document order.  Runs in a background thread (no Qt calls).

        Words whose only occurrence in the document text is *before*
        search_from (e.g. column-header names repeated in structured
        table-row narration) are assigned last_good_pos so the highlight
        advances linearly rather than jumping backward to the header row.
        """
        result: List[int] = []
        qt_lower = qt_text.lower()
        token_re = re.compile(r"\b\w[\w'-]*")
        search_from = 0
        last_good_pos = 0  # last position from a forward-matched word

        for m in token_re.finditer(plain_text):
            word = m.group().lower()
            pos = qt_lower.find(word, search_from)
            if pos >= 0:
                result.append(pos)
                search_from = pos + 1  # advance past this occurrence
                last_good_pos = pos
            else:
                # Forward search failed.  Check if the word exists at all.
                global_pos = qt_lower.find(word, 0)
                if global_pos >= 0:
                    # Only a backward match exists (e.g. a table column
                    # header repeated in row narration).  Use last_good_pos
                    # so the highlight doesn't jump back to the header.
                    result.append(last_good_pos)
                else:
                    result.append(0)  # not found anywhere
                # Don't update search_from; we haven't moved forward.

        self._qt_word_map = result

    def _build_qt_word_map_windowed(
        self, word_start: int, word_end: int, qt_text: str
    ) -> None:
        """Populate self._qt_word_map for a *rendered window* of the document.

        The list is always full-document length (one entry per word in
        ``doc.word_map``); words inside ``[word_start, word_end)`` get their real
        character offset inside *qt_text* (the plain text of the currently
        rendered page window), and every word outside that range carries the
        sentinel ``-1``.  Keeping the map full-length means every consumer's
        index arithmetic (highlight, caret nav, Define-Word, restore-position)
        is unchanged: the only new rule is "an entry of -1 means that word is not
        on screen yet — advance the window first" (see _page_ensure_word_visible).

        Uses the same rolling forward-search as :meth:`_build_qt_word_map`, but
        anchored to just the window's words, so it stays O(window size) rather
        than O(document).
        """
        wm = self.doc.word_map if self.doc else []
        n = len(wm)
        result: List[int] = [-1] * n
        if not wm:
            self._qt_word_map = result
            return
        word_start = max(0, word_start)
        word_end = min(n, word_end)
        qt_lower = qt_text.lower()
        search_from = 0
        last_good_pos = 0
        for i in range(word_start, word_end):
            word = wm[i].word.lower()
            if not word:
                result[i] = last_good_pos
                continue
            pos = qt_lower.find(word, search_from)
            if pos >= 0:
                result[i] = pos
                search_from = pos + 1
                last_good_pos = pos
            else:
                global_pos = qt_lower.find(word, 0)
                result[i] = last_good_pos if global_pos >= 0 else 0
        self._qt_word_map = result

    # ── Large-document pagination ─────────────────────────────────────
    #
    # See star/pagination.py and docs/PERFORMANCE.md.  Rationale: QTextEdit lays
    # out a document's whole HTML at once, so a 100k+-word document stalls on
    # open and drags every later scroll/repaint.  When enabled and past the size
    # gate we render only a *window* of pages; the full plain text + word map
    # stay resident, and the word→char map is rebuilt per window so highlight,
    # caret nav, and Define-Word remain correct across page boundaries.

    def _scratch_plain_text(self, md: str) -> str:
        """Plain text of the fully-rendered *md* via a throwaway QTextDocument.

        Renders the whole document's HTML into an off-screen QTextDocument and
        reads its plain text.  This parses the markup but skips the expensive
        visual layout the on-screen QTextEdit performs, so it is cheap even for
        very large documents — used to align the whole-document word map while
        only a page window is shown in the visible editor.  Honors the syllable
        aid the same way :meth:`_plain_text_without_syllables` does.
        """
        try:
            from PyQt6.QtGui import QTextDocument
        except ImportError:
            from PyQt5.QtGui import QTextDocument  # type: ignore[no-redef]
        if self.settings.get("qt_syllable_split", False):
            return self._plain_text_without_syllables(md)
        scratch = QTextDocument()
        scratch.setHtml(self._md_to_html(md))
        return scratch.toPlainText()

    def _page_highlighting_active(self, doc: Any) -> bool:
        """True when per-char rendered-offset highlighting is in play for *doc*.

        Pagination and rendered-char-offset highlighting are incompatible: user
        highlights and the difficult-word (vocab) overlay both store/paint
        *absolute* character offsets into the whole-document render, but pagination
        only ever renders a window, so those offsets would land on the wrong text
        (BUG 1 / BUG 2).  When either is active for this document we render the
        whole document instead of paginating.  The guard checks:

        * a stored ``user_highlights`` list for the document's path, and
        * the ``qt_vocab_highlight`` overlay toggle.
        """
        if bool(self.settings.get("qt_vocab_highlight", False)):
            return True
        path_key = (getattr(doc, "path", None) or "__no_path__") if doc else "__no_path__"
        hl = self.settings.get("user_highlights", {}).get(path_key, [])
        return bool(hl)

    def _page_provisional_render(self, doc: Any) -> bool:
        """Render a cheap leading window if *doc* is a pagination candidate.

        A GUI-thread, word-map-free heuristic run *before* the background build:
        estimates the word count from the plain text (a whitespace split) and, if
        pagination is enabled and the estimate clears the threshold, renders only
        the leading markdown blocks — enough to fill the initial window — so the
        first paint never pays the whole-document layout cost.  Returns True when
        it rendered a provisional window (the caller then skips the full render),
        False otherwise (normal whole-document path, completely unchanged).
        """
        if not bool(self.settings.get("qt_paginate_large_docs", False)):
            return False
        # Never show a windowed provisional render when per-char highlighting is
        # active — a leading window would paint highlights at window-relative
        # offsets (BUG 1/2).  Render the whole document instead.
        if self._page_highlighting_active(doc):
            return False
        plain = doc.plain_text or ""
        # Cheap upper-bound word estimate — a split is far faster than tokenizing.
        est_words = plain.count(" ") + 1
        threshold = int(self.settings.get("qt_paginate_threshold_words", 60000))
        if est_words < max(1, threshold):
            return False
        blocks = self._page_split_markdown_blocks(doc.markdown or "")
        if len(blocks) <= 1:
            return False
        # Leading window: enough blocks to comfortably cover the eventual window
        # span (window_pages on each side + the active page).  A block is ~one
        # paragraph; take a generous prefix and let the precise re-render trim it.
        wpp = int(self.settings.get("qt_paginate_words_per_page", 1200))
        win_pages = int(self.settings.get("qt_paginate_window_pages", 2))
        target_words = wpp * (win_pages + 1)
        token_re = re.compile(r"\b\w[\w'-]*")
        chosen: List[str] = []
        acc = 0
        for blk in blocks:
            chosen.append(blk)
            acc += len(token_re.findall(blk))
            if acc >= target_words:
                break
        if len(chosen) >= len(blocks):
            return False  # whole doc fits the leading window — just render it whole
        self.editor.setHtml(self._md_to_html("\n\n".join(chosen)))
        self._apply_block_spacing()
        return True

    def _page_split_markdown_blocks(self, md: str) -> List[str]:
        """Split *md* into rendering blocks at blank lines.

        Blank-line separated blocks are the natural page-boundary unit: each is a
        whole paragraph / heading / table / list, so a page never bisects one.
        Fenced code blocks are kept intact (a blank line inside ``` … ``` does
        not split them) so code renders correctly within a window.
        """
        lines = (md or "").split("\n")
        blocks: List[str] = []
        cur: List[str] = []
        in_fence = False
        for ln in lines:
            if ln.lstrip().startswith("```"):
                in_fence = not in_fence
                cur.append(ln)
                continue
            if not ln.strip() and not in_fence:
                if cur:
                    blocks.append("\n".join(cur))
                    cur = []
            else:
                cur.append(ln)
        if cur:
            blocks.append("\n".join(cur))
        return blocks or [md or ""]

    def _page_align_block_starts(
        self, blocks: List[str], word_map: List[Any]
    ) -> List[int]:
        """Return the global word-map index at which each block begins.

        Rather than trusting a per-block token count (which drifts from the TTS
        word map whenever markdown syntax, skipped code, or table narration make
        the two tokenizations disagree), each block is anchored by rolling its
        leading tokens forward through the word map.  This keeps page boundaries
        aligned to real word indices even on structured documents.
        """
        token_re = re.compile(r"\b\w[\w'-]*")
        n = len(word_map)
        starts: List[int] = []
        cursor = 0
        # Bound the forward scan for each block's anchor so a token that never
        # matches (a markdown artifact absent from the TTS plain text) can't make
        # the whole alignment O(n²); past the cap we keep the rolling cursor.
        _scan_cap = 4096
        for blk in blocks:
            toks = token_re.findall(blk.lower())
            # Anchor this block at the first word-map word (from the rolling
            # cursor) that matches its first token; fall back to the cursor.
            anchor = cursor
            if toks:
                first = toks[0]
                limit = min(n, cursor + _scan_cap)
                j = cursor
                while j < limit:
                    if word_map[j].word.lower() == first:
                        anchor = j
                        break
                    j += 1
                else:
                    anchor = min(cursor, n)
            starts.append(min(anchor, n))
            # Advance the cursor past this block's token count from its anchor so
            # the next block searches forward, not from the top.
            cursor = min(anchor + len(toks), n)
        # Enforce monotonic, in-range, first-block-at-0 invariants the paginator
        # relies on.
        starts = starts or [0]
        starts[0] = 0
        for i in range(1, len(starts)):
            if starts[i] < starts[i - 1]:
                starts[i] = starts[i - 1]
        return starts

    def _page_setup_if_large(self, doc: Any) -> bool:
        """Decide pagination for *doc*; set up the paginator when it qualifies.

        Returns True when the document is being paginated (the caller must then
        render the initial window on the GUI thread), False when the whole
        document is rendered as usual.  Called from the word-map build thread —
        pure Python, no Qt calls, so it is thread-safe.
        """
        if not bool(self.settings.get("qt_paginate_large_docs", False)):
            return False
        # Do not paginate a document that has stored user highlights or the vocab
        # overlay on: both rely on absolute rendered-char offsets that a windowed
        # render would misplace (BUG 1/2).  Render whole instead.
        if self._page_highlighting_active(doc):
            return False
        wm = getattr(doc, "word_map", None) or []
        threshold = int(self.settings.get("qt_paginate_threshold_words", 60000))
        if len(wm) < max(1, threshold):
            return False
        blocks = self._page_split_markdown_blocks(doc.markdown or "")
        block_starts = self._page_align_block_starts(blocks, wm)
        pages = paginate(
            len(wm),
            block_starts,
            words_per_page=int(
                self.settings.get("qt_paginate_words_per_page", 1200)
            ),
        )
        if len(pages) <= 1:
            return False  # fits in a single page — no benefit to paging
        self._page_blocks = blocks
        self._page_block_starts = block_starts
        self._paginator = Paginator(
            pages,
            window_pages=int(self.settings.get("qt_paginate_window_pages", 2)),
        )
        return True

    def _page_window_markdown(self) -> str:
        """Markdown for the paginator's current window of pages.

        Joins the blocks whose global word index falls in the window's
        ``[word_start, word_end)`` span, reconstructing the blank-line
        separation so the windowed markdown renders exactly as that slice of the
        whole document would.
        """
        pg = self._paginator
        if pg is None or not self._page_blocks:
            return self.doc.markdown if self.doc else ""
        w0, w1 = pg.word_start, pg.word_end
        starts = self._page_block_starts
        chosen: List[str] = []
        for i, blk in enumerate(self._page_blocks):
            b_start = starts[i]
            b_end = starts[i + 1] if i + 1 < len(starts) else len(
                self.doc.word_map if self.doc else []
            )
            # Include the block if its word range overlaps the window span.
            if b_end > w0 and b_start < w1:
                chosen.append(blk)
        return "\n\n".join(chosen)

    def _page_render_window(self, restore_caret_word: Optional[int] = None) -> None:
        """Render the paginator's current window into the editor and rebuild the
        windowed word→char map.

        Must run on the GUI thread (it touches the editor).  When
        *restore_caret_word* is given and lands inside the new window, the text
        cursor is placed on it so the caret/ruler stay put across a re-render.
        """
        pg = self._paginator
        if pg is None:
            return
        md = self._page_window_markdown()
        self.editor.setHtml(self._md_to_html(md))
        self._apply_block_spacing()
        # Rebuild the windowed word→char map against the freshly rendered text.
        qt_plain = self.editor.document().toPlainText()
        self._build_qt_word_map_windowed(pg.word_start, pg.word_end, qt_plain)
        # Re-apply persisted user highlights (their stored offsets are validated
        # against the rendered length, so out-of-window ones are simply skipped).
        self._qt_apply_user_highlights()
        if restore_caret_word is not None and pg.covers_word(restore_caret_word):
            off = self._qt_word_map[restore_caret_word]
            if off is not None and off >= 0:
                cursor = QTextCursor(self.editor.document())
                cursor.setPosition(off)
                self.editor.setTextCursor(cursor)
                self.editor.ensureCursorVisible()
        # Keep the reading-ruler overlay tracking the caret after a re-render.
        ruler = getattr(self, "_reading_ruler", None)
        if ruler is not None:
            try:
                ruler.follow_caret()
            except Exception:
                pass

    def _page_render_initial_window(self) -> None:
        """GUI-thread handler (via _paginate_signal) for the first render right
        after a large document loads.

        Two cases: the document is being paginated (render the precise initial
        window), or a provisional leading window was shown but pagination was
        ultimately declined (render the whole document so nothing is missing).
        """
        if self._paginator is None:
            # Provisional window shown but not paginating → render the whole doc
            # and build the whole-document word→char map, matching the normal
            # path exactly from here on.
            if getattr(self, "_page_provisional", False) and self.doc:
                self.editor.setHtml(self._md_to_html(self.doc.markdown or ""))
                self._apply_block_spacing()
                qt_plain = self.editor.document().toPlainText()
                self._build_qt_word_map(self.doc.plain_text or "", qt_plain)
                self._qt_apply_user_highlights()
                self._qt_build_toc()
            self._page_provisional = False
            return
        self._page_provisional = False
        self._page_render_window()
        # Rebuild the ToC now that only a window is rendered — headings resolve
        # against whatever is on screen; the ToC still lists all headings from
        # doc.markdown, so navigation via the ToC advances the window as needed.
        try:
            self._qt_build_toc()
        except Exception:
            pass
        self.statusBar().showMessage(
            tr("Large document — paginated ({n} pages) for performance").format(
                n=self._paginator.n_pages
            )
        )

    def _page_disable_and_render_whole(self) -> bool:
        """Turn pagination off for the open document and render it whole.

        Used by features that need the *entire* document present in the editor
        at once — currently Find, whose match offsets and highlight-all must span
        the whole document, not just the visible window.  This is the documented,
        safe degradation for large documents: paging is suspended (the one-shot
        layout cost is paid once) so the feature is fully correct rather than
        silently limited to the visible pages.  Returns True if it did anything.
        """
        if self._paginator is None or not self.doc:
            return False
        # Remember the current reading word so we can keep the caret in place.
        try:
            cur_word = self._qt_current_word_for_nav()
        except Exception:
            cur_word = 0
        self._paginator = None
        self._page_blocks = []
        self._page_block_starts = []
        self.editor.setHtml(self._md_to_html(self.doc.markdown or ""))
        self._apply_block_spacing()
        qt_plain = self.editor.document().toPlainText()
        self._build_qt_word_map(self.doc.plain_text or "", qt_plain)
        self._qt_apply_user_highlights()
        self._qt_build_toc()
        # Restore the caret onto the word the reader was on.
        qwm = self._qt_word_map
        if 0 <= cur_word < len(qwm) and qwm[cur_word] >= 0:
            cursor = QTextCursor(self.editor.document())
            cursor.setPosition(qwm[cur_word])
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()
        self.statusBar().showMessage(
            tr("Whole document loaded for search (pagination paused)")
        )
        return True

    def _page_ensure_word_visible(self, word_idx: int) -> bool:
        """Ensure the rendered window covers *word_idx*, re-rendering if needed.

        The single choke-point every feature calls before it dereferences
        ``self._qt_word_map[word_idx]`` under pagination.  Returns True if the
        window moved (a re-render happened), False if the word was already on
        screen (or pagination is off).  Safe to call on the GUI thread only.
        """
        pg = self._paginator
        if pg is None:
            return False
        if pg.covers_word(word_idx):
            return False
        pg.window_for_word(word_idx)
        self._page_render_window(restore_caret_word=word_idx)
        return True

    # ── HTML rendering ────────────────────────────────────────────────

    def _effective_palette(self, theme_name: str) -> Dict[str, Any]:
        """Return the palette dict for *theme_name*.

        Lookup order:
          1. Custom CSS themes loaded from THEMES_DIR (have key '_css').
          2. Built-in _PALETTES.
          3. Fallback: dark built-in palette.

        Uses getattr so this method is safe to call even before
        _css_themes is assigned (e.g. during very early init).
        """
        css_themes: Dict[str, Any] = getattr(self, "_css_themes", {})
        if theme_name in css_themes:
            return css_themes[theme_name]
        return self._PALETTES.get(theme_name, self._PALETTES["dark"])

    @property
    def _all_theme_names(self) -> List[str]:
        """Built-in palette names (cycle order) then any custom CSS theme names."""
        builtin = list(self._PALETTES)
        extra = [n for n in sorted(self._css_themes) if n not in builtin]
        return builtin + extra

    def _md_inline(self, text: str) -> str:
        """Apply inline Markdown (images→alt/caption, links, code, bold, italic,
        and visual LaTeX math)."""
        import html as _h

        # Inline math → Unicode for display (the raw LaTeX is kept in the TTS
        # plain-text, which is stripped separately and never sees this).
        if has_math(text):
            text = render_math_to_unicode(text)
        # images → a labelled placeholder (Qt can't fetch remote images).  Show
        # the alt text; when it's missing, fall back to the file's name so the
        # reader still knows an image is present rather than getting nothing.
        text = re.sub(r"!\[([^\]]*)\]\(([^)\s]*)[^)]*\)", self._md_image_label, text)
        # links → anchors
        text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)[^)]*\)", r'<a href="\2">\1</a>', text)
        # inline code (content escaped so e.g. <html> shows literally)
        text = re.sub(r"`([^`]+)`", lambda m: "<code>" + _h.escape(m.group(1)) + "</code>", text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
        return text

    @staticmethod
    def _md_image_label(m: "re.Match") -> str:
        """Render an image reference as a visible alt-text label.

        Uses the alt text when present; otherwise derives a readable fallback
        from the image URL's file name so images with no alt attribute are not
        rendered as an empty span (an accessibility gap).
        """
        alt = (m.group(1) or "").strip()
        src = (m.group(2) or "").strip()
        if not alt:
            stem = Path(src).stem if src else ""
            stem = stem.replace("_", " ").replace("-", " ").strip()
            alt = stem or "image"
        return f'<span class="imgalt">🖼 {alt}</span>'

    @staticmethod
    def _parse_table_aligns(sep_line: str, ncols: int) -> List[str]:
        """Parse a Markdown table separator row into per-column alignments.

        ``:---`` → ``left`` · ``---:`` → ``right`` · ``:---:`` → ``center`` ·
        otherwise ``""`` (default).  Returns a list of length *ncols*.
        """
        specs = [c.strip() for c in sep_line.strip().strip("|").split("|")]
        aligns: List[str] = []
        for spec in specs:
            left = spec.startswith(":")
            right = spec.endswith(":")
            if left and right:
                aligns.append("center")
            elif right:
                aligns.append("right")
            elif left:
                aligns.append("left")
            else:
                aligns.append("")
        # Pad / truncate to the header column count.
        if len(aligns) < ncols:
            aligns += [""] * (ncols - len(aligns))
        return aligns[:ncols]

    @staticmethod
    def _align_attr(aligns: List[str], col: int) -> str:
        """Return an ``align="…"`` attribute for *col* (empty when default)."""
        if 0 <= col < len(aligns) and aligns[col]:
            return f' align="{aligns[col]}"'
        return ""

    def _footnotes_to_anchors(self, md: str) -> str:
        """Rewrite Markdown footnote references/definitions into anchored HTML.

        * A reference ``word[^label]`` becomes a superscript, visually-distinct
          anchor (``fnref-label``) linking to ``#fn-label``.
        * Each definition ``[^label]: text`` is collected and re-emitted as a
          "Footnotes" list at the end, each item named ``fn-label`` with a
          backlink (``↩``) to its first reference.

        Runs *before* the block parser so the emitted ``<sup>``/``<a>`` markup
        survives to the final HTML.  It only fires when both a reference and a
        matching definition exist, so the inline/deferred/skip footnote_mode
        handling in the loader (which may have already resolved markers) is left
        untouched — there is simply nothing here to rewrite in those cases.
        """
        if "[^" not in md:
            return md

        # Collect definitions:  [^label]: text  (single line).
        definitions: "Dict[str, str]" = {}

        def _grab(m: "re.Match") -> str:
            definitions[m.group(1)] = m.group(2).strip()
            return ""

        body = re.sub(
            r"^[ \t]*\[\^([^\]]+)\]:[ \t]*(.+)$", _grab, md, flags=re.MULTILINE
        )
        if not definitions:
            return md

        order: "List[str]" = []

        def _ref(m: "re.Match") -> str:
            label = m.group(1)
            if label not in definitions:
                return m.group(0)  # dangling ref — leave as-is
            if label not in order:
                order.append(label)
            num = order.index(label) + 1
            return (
                f'<sup class="fnref"><a name="fnref-{label}" '
                f'href="#fn-{label}">[{num}]</a></sup>'
            )

        body = re.sub(r"\[\^([^\]]+)\]", _ref, body)
        if not order:
            return md  # definitions but no references — nothing to anchor

        # Remove the blank lines a stripped definition block leaves behind at EOF.
        body = re.sub(r"\n{3,}", "\n\n", body).rstrip()

        lines = ["", "## Footnotes", ""]
        for label in order:
            num = order.index(label) + 1
            text = definitions.get(label, "")
            lines.append(
                f'<a name="fn-{label}"></a>{num}. {text} '
                f'<a class="fnback" href="#fnref-{label}">↩</a>'
            )
        return body + "\n" + "\n".join(lines) + "\n"

    def _md_body_to_html(self, md: str) -> str:
        """Render Markdown block structure to QTextEdit-friendly HTML.

        Handles fenced code blocks, ATX headings (h1–h6), pipe tables, ordered /
        unordered lists, blockquotes, horizontal rules, and paragraphs — enough
        for star's documents (and its own README) to render with real structure.
        """
        import html as _h

        md = self._footnotes_to_anchors(md)

        lines = (md or "").split("\n")
        out: List[str] = []
        list_open: Optional[str] = None
        i, n = 0, len(lines)

        def close_list() -> None:
            nonlocal list_open
            if list_open:
                out.append(f"</{list_open}>")
                list_open = None

        while i < n:
            line = lines[i]
            stripped = line.strip()

            if stripped.startswith("```"):  # fenced code block
                close_list()
                i += 1
                code: List[str] = []
                while i < n and not lines[i].strip().startswith("```"):
                    code.append(_h.escape(lines[i]))
                    i += 1
                i += 1  # consume closing fence
                out.append("<pre>" + "\n".join(code) + "</pre>")
                continue

            # pipe table: a row followed by a |---|---| separator line
            if (
                "|" in line
                and i + 1 < n
                and "-" in lines[i + 1]
                and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[i + 1])
            ):
                close_list()
                header_cells = [c.strip() for c in stripped.strip("|").split("|")]
                # Column alignments parsed from the separator row's colons:
                #   :---  left · ---:  right · :---:  center.  The Qt rich-text
                # subset honors the ``align`` attribute on <th>/<td>.
                aligns = self._parse_table_aligns(lines[i + 1], len(header_cells))
                # Header row: scope="col" + emphasis distinguish headers for
                # assistive tech and sighted readers alike.
                head = "".join(
                    f'<th scope="col"{self._align_attr(aligns, ci)}>'
                    f"{self._md_inline(c)}</th>"
                    for ci, c in enumerate(header_cells)
                )
                rows = ['<thead><tr>' + head + "</tr></thead>"]
                body_rows: List[str] = []
                i += 2
                while i < n and "|" in lines[i] and lines[i].strip():
                    body_cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                    cell_html: List[str] = []
                    for ci, c in enumerate(body_cells):
                        # First column of each body row acts as a row header.
                        if ci == 0:
                            cell_html.append(
                                f'<th scope="row"{self._align_attr(aligns, ci)}>'
                                f"{self._md_inline(c)}</th>"
                            )
                        else:
                            cell_html.append(
                                f"<td{self._align_attr(aligns, ci)}>"
                                f"{self._md_inline(c)}</td>"
                            )
                    body_rows.append("<tr>" + "".join(cell_html) + "</tr>")
                    i += 1
                if body_rows:
                    rows.append("<tbody>" + "".join(body_rows) + "</tbody>")
                out.append('<table border="1" cellspacing="0">' + "".join(rows) + "</table>")
                continue

            m = re.match(r"^(#{1,6})\s+(.*)$", line)  # ATX heading
            if m:
                close_list()
                lvl = len(m.group(1))
                out.append(f"<h{lvl}>{self._md_inline(m.group(2))}</h{lvl}>")
                i += 1
                continue

            if re.match(r"^\s*([-*_])\1\1+\s*$", line):  # horizontal rule
                close_list()
                out.append("<hr>")
                i += 1
                continue

            if stripped.startswith(">"):  # blockquote
                close_list()
                quote: List[str] = []
                while i < n and lines[i].strip().startswith(">"):
                    quote.append(self._md_inline(lines[i].strip().lstrip(">").strip()))
                    i += 1
                out.append("<blockquote>" + "<br>".join(quote) + "</blockquote>")
                continue

            ulm = re.match(r"^\s*[-*+]\s+(.*)$", line)
            olm = re.match(r"^\s*\d+\.\s+(.*)$", line)
            if ulm or olm:
                want = "ul" if ulm else "ol"
                if list_open != want:
                    close_list()
                    out.append(f"<{want}>")
                    list_open = want
                out.append(f"<li>{self._md_inline((ulm or olm).group(1))}</li>")
                i += 1
                continue

            if not stripped:  # blank line
                close_list()
                i += 1
                continue

            close_list()
            out.append(f"<p>{self._md_inline(line)}</p>")
            i += 1

        close_list()
        return "\n".join(out)

    def _plain_text_without_syllables(self, md: str) -> str:
        """Plain text of the rendered document as if syllable splitting were off.

        The word map is aligned against the editor's ``toPlainText()``.  When the
        syllable aid is on, that text carries visible middots that would break the
        word→offset search, so we render once with the aid suppressed and read the
        plain text back through a throwaway QTextDocument.  This keeps the word
        map (and therefore speech highlighting) identical regardless of whether
        the display aid is shown.
        """
        try:
            from PyQt6.QtGui import QTextDocument
        except ImportError:
            from PyQt5.QtGui import QTextDocument  # type: ignore[no-redef]
        prev = self.settings.get("qt_syllable_split", False)
        try:
            self.settings._data["qt_syllable_split"] = False
            html = self._md_to_html(md)
        finally:
            self.settings._data["qt_syllable_split"] = prev
        scratch = QTextDocument()
        scratch.setHtml(html)
        return scratch.toPlainText()

    def _md_to_html(self, md: str) -> str:
        """Convert internal Markdown to styled HTML for QTextEdit.

        When the active theme came from a CSS file the raw CSS is injected
        verbatim so every selector the user wrote is honored.  For built-in
        palettes the CSS is generated from the palette dict (all 11 keys —
        ``code_bg`` / ``link`` / ``muted`` fall back gracefully).
        """
        theme_name = self.settings.get("theme", "obsidian")
        pal = self._effective_palette(theme_name)
        custom_css: str = str(pal.get("_css", ""))

        body = self._md_body_to_html(md)
        # Bionic-reading: embolden the leading part of each word so the
        # eye is pulled forward through the text (a dyslexia reading aid).
        if self.settings.get("qt_bionic_reading", False):
            body = self._bionic_html(body)
        # Syllable splitting: insert a visible separator between syllables
        # (read·a·bil·i·ty) as a decoding aid.  DISPLAY-ONLY, exactly like
        # bionic: it transforms the rendered HTML only — the TTS plain text and
        # the highlight word map are built from the untransformed document, so
        # speech and highlighting are unaffected.
        if self.settings.get("qt_syllable_split", False):
            from .. import syllables as _syl

            sep = str(self.settings.get("qt_syllable_sep", _syl.MIDDOT)) or _syl.MIDDOT
            body = _syl.syllabify_html(body, sep)
        fam = self._effective_font_family()
        if custom_css:
            style = custom_css
            # A CSS-file / palette theme may hard-set the body font-family (the
            # Obsidian theme uses Georgia). When a reading font is active it must
            # win in the reading pane too, so append an override the cascade
            # resolves last — across text elements, but never code/pre.
            if self._reading_font_key() != "default" and fam:
                style += (
                    "\nbody, p, li, blockquote, td, th, h1, h2, h3, h4, h5, h6, a "
                    '{ font-family: "' + fam + '", sans-serif; }'
                    "\ncode, pre, code *, pre * { font-family: monospace; }"
                )
            style += self._fidelity_css(pal)
        else:
            muted = pal.get("muted", "#7d7d7d")
            code_bg = pal.get("code_bg", "#2a2a2a")
            link = pal.get("link", pal["h1"])
            style = (
                f"body{{background:{pal['bg']};color:{pal['fg']};"
                f"      font-family:{fam},sans-serif;margin:14px;}}"
                f"h1{{color:{pal['h1']}}}"
                f"h2{{color:{pal['h2']}}}"
                f"h3{{color:{pal['h3']}}}"
                f"h4,h5,h6{{color:{pal['h4']}}}"
                f"a{{color:{link};}}"
                f"code{{color:{pal['code']};background:{code_bg};font-family:monospace;}}"
                f"pre{{color:{pal['fg']};background:{code_bg};"
                f"     font-family:monospace;white-space:pre-wrap;padding:8px;}}"
                f"blockquote{{color:{muted};border-left:3px solid {muted};padding-left:10px;}}"
                f"hr{{border:0;border-top:1px solid {muted};}}"
                f"table{{border:1px solid {muted};}}"
                f"th,td{{border:1px solid {muted};padding:3px 8px;}}"
                # Header emphasis: distinct background + bold so column/row
                # headers are visually and structurally distinguishable.
                f"th{{color:{pal['h2']};background:{code_bg};font-weight:bold;}}"
                + self._fidelity_css(pal)
            )
        # Mirror the reading pane for right-to-left UI locales: an ``dir="rtl"``
        # on <html>/<body> flips text alignment and block direction so Arabic /
        # Hebrew / Persian / Urdu render naturally.  LTR locales (the default)
        # emit no ``dir`` attribute, so their HTML is byte-for-byte unchanged.
        dir_attr = ' dir="rtl"' if is_rtl() else ""
        return (
            f"<html{dir_attr}><head><style>" + style + "</style></head>"
            f"<body{dir_attr}>{body}</body></html>"
        )

    def _fidelity_css(self, pal: Dict[str, Any]) -> str:
        """Shared CSS for document-fidelity elements (footnote anchors,
        figure captions, image-alt labels) — appended to both the built-in and
        custom-CSS themes so the features render consistently regardless of
        theme source.
        """
        link = pal.get("link", pal.get("h1", "#4a9eff"))
        muted = pal.get("muted", "#7d7d7d")
        return (
            # Footnote reference markers: small, coloured, non-underlined.
            f"\nsup.fnref a, sup.fnref{{color:{link};text-decoration:none;"
            "font-weight:bold;}"
            # The backlink (↩) in the footnotes list.
            f"\na.fnback{{color:{link};text-decoration:none;}}"
            # Image alt / caption labels stand apart from body prose.
            f"\nspan.imgalt{{color:{muted};font-style:italic;}}"
            f"\np.figcaption, .figcaption{{color:{muted};font-style:italic;"
            "font-size:90%;}"
        )

