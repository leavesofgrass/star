"""DocumentMixin — methods extracted from StarWindow (main_window.py).

Mixed into StarWindow via ``class StarWindow(DocumentMixin, ...)``; operates
on StarWindow instance state and other methods via ``self``, holding no
state of its own.  IMPORT SAFETY: references Qt at module scope — imported
lazily by main_window.py (itself imported by runner.py after the _QT guard).
"""
from .._runtime import *  # noqa: F401,F403
from ..documents import Document, _build_word_map, load_document
from ..stats import _record_library


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
        self.doc = doc
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

        # Read Qt plain text NOW (main thread required) then hand off.
        qt_plain = self.editor.document().toPlainText()

        def _build() -> None:
            try:
                plain = doc.plain_text or ""
                # TTSManager word map (line-based, used for timer highlighting)
                flat = qt_plain.splitlines()
                doc.word_map = _build_word_map(plain, flat)
                self.tts_manager.set_word_map(doc.word_map)
                # Qt char-offset map (used by _apply_word_highlight)
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
        # Record this document in the library / bookshelf.
        _record_library(self.settings, doc)
        self.statusBar().showMessage(f"Opened: {doc.title}")

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
        """Apply inline Markdown (images→alt, links, code, bold, italic)."""
        import html as _h

        # images → alt text (Qt can't fetch remote images; badges become labels)
        text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
        # links → anchors
        text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)[^)]*\)", r'<a href="\2">\1</a>', text)
        # inline code (content escaped so e.g. <html> shows literally)
        text = re.sub(r"`([^`]+)`", lambda m: "<code>" + _h.escape(m.group(1)) + "</code>", text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
        return text

    def _md_body_to_html(self, md: str) -> str:
        """Render Markdown block structure to QTextEdit-friendly HTML.

        Handles fenced code blocks, ATX headings (h1–h6), pipe tables, ordered /
        unordered lists, blockquotes, horizontal rules, and paragraphs — enough
        for star's documents (and its own README) to render with real structure.
        """
        import html as _h

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
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                rows = ["<tr>" + "".join(f"<th>{self._md_inline(c)}</th>" for c in cells) + "</tr>"]
                i += 2
                while i < n and "|" in lines[i] and lines[i].strip():
                    body_cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                    rows.append(
                        "<tr>" + "".join(f"<td>{self._md_inline(c)}</td>" for c in body_cells) + "</tr>"
                    )
                    i += 1
                out.append("<table>" + "".join(rows) + "</table>")
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
        fam = self._effective_font_family()
        if custom_css:
            style = custom_css
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
                f"th,td{{border:1px solid {muted};padding:3px 8px;}}"
                f"th{{color:{pal['h2']};}}"
            )
        return (
            "<html><head><style>" + style + "</style></head>"
            f"<body>{body}</body></html>"
        )

