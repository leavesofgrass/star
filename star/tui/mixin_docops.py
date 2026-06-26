"""Archive ingest, metadata edit, library search, lookups, clipboard.

Methods of StarApp, split out of the former monolithic star/tui.py.
Mixed into StarApp in app.py; calls other groups via ``self``.
"""
from .._runtime import *  # noqa: F401,F403
from ..dictionary import (
    availability as _dict_availability,
    define as _dict_define,
    format_definition_markdown as _dict_markdown,
)
from ..stats import _format_reading_stats, _library_entries


class DocOpsMixin:

    # ── Clipboard copy (TUI stub) ──────────────────

    def _copy_current_line(self) -> str:
        "Return the text of the current top-visible display line."
        if not self.rendered or self.scroll >= len(self.rendered):
            return ""
        return "".join(t for t, _ in self.rendered[self.scroll]).strip()

    def _copy_to_clipboard(self) -> None:
        """Copy the current top-visible line to the system clipboard.

        Uses pyperclip when available; otherwise shows the text in the
        status bar so the user can select it manually. Never raises."""
        text = self._copy_current_line()
        if not text:
            self.notify("Nothing to copy (empty line).", error=True)
            return
        try:
            import pyperclip  # type: ignore

            pyperclip.copy(text)
            truncated = text[:60] + ("…" if len(text) > 60 else "")
            self.notify(f"Copied to clipboard: {truncated}")
        except Exception:
            # pyperclip unavailable or clipboard inaccessible — surface the text.
            self.notify(f"Copy (select manually): {text}", dur=10.0)

    # ── Reading statistics & library ─────────────

    def _reading_stats(self) -> None:
        """Show the reading-statistics dashboard in a pager (M-x reading-stats)."""
        try:
            self.stats.flush()  # make the current session's numbers fresh
        except Exception:
            pass
        path = self.doc.path if self.doc else ""
        title = self.doc.title if self.doc else ""
        text = _format_reading_stats(self.settings, path, title)
        self._show_text_pager("Reading Statistics", text)

    def _library_browser(self) -> None:
        """List library documents and open the chosen one (M-x library)."""
        entries = _library_entries(self.settings)
        if not entries:
            self.notify("Library is empty. Open a document to add it.")
            return
        preview = [
            f"{i + 1}. {e['title']} ({e['pct']}%)" for i, e in enumerate(entries[:12])
        ]
        self.notify("Library: " + "  |  ".join(preview), dur=8.0)

        def _on_pick(value: str) -> None:
            value = value.strip()
            if not value:
                return
            if value.isdigit():
                n = int(value) - 1
                if 0 <= n < len(entries):
                    self._open_async(entries[n]["path"])
                else:
                    self.notify(f"No library item #{int(value)}.", error=True)
            else:
                self._open_async(value)

        self._enter_minibuffer(
            prompt=f"Open library [1–{min(len(entries), 12)}] or path: ",
            on_commit=_on_pick,
        )

    # ── Wikipedia and PubMed shortcuts ──────────────────

    def _open_wikipedia(self, query: str) -> None:
        "Fetch and open the Wikipedia article for query via the URL loader."
        query = (query or "").strip()
        if not query:
            self.notify("Usage: wikipedia <query>", error=True)
            return
        # Use the standard wiki URL; _open_async → _load_url handles HTML → Markdown.
        encoded = urllib.parse.quote(query.replace(" ", "_"))
        url = f"https://en.wikipedia.org/wiki/{encoded}"
        self.notify(f"Opening Wikipedia: {query}")
        self._open_async(url)

    def _open_pubmed(self, pmid: str) -> None:
        "Fetch and open a PubMed abstract by PMID via the URL loader."
        pmid = (pmid or "").strip()
        if not pmid:
            self.notify("Usage: pubmed <PMID>", error=True)
            return
        url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            f"?db=pubmed&id={urllib.parse.quote(pmid)}&rettype=abstract&retmode=text"
        )
        self.notify(f"Opening PubMed abstract: PMID {pmid}")
        self._open_async(url)

    def _define_cmd(self, arg: str = "") -> None:
        """Offline definition lookup (M-x define [word], or the 'd' key on the
        word at the reading cursor).  Shows the result in the text pager."""
        word = (arg or "").strip()
        if not word and self.doc and self.doc.word_map:
            idx = self._current_word_for_nav()
            if 0 <= idx < len(self.doc.word_map):
                word = self.doc.word_map[idx].word
        if not word:
            self.notify("Usage: define <word> (or place the cursor on a word)", error=True)
            return
        ok, hint = _dict_availability(self.settings)
        if not ok:
            self.notify(hint.splitlines()[0], error=True)
            return
        result = _dict_define(word, self.settings)
        if result is None:
            self.notify(f"No definition found for '{word}'", error=True)
            return
        self._show_text_pager(f"Definition: {result.word}", _dict_markdown(result))

    def _cache_clear(self) -> None:
        "Delete all cached document files to free disk space."
        import shutil as _shutil

        try:
            if CACHE_DIR.exists():
                _shutil.rmtree(CACHE_DIR)
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                self.notify("Document cache cleared")
            else:
                self.notify("Cache is already empty")
        except OSError as e:
            self.notify(f"Cache clear error: {e}", error=True)

    # ── Archive ingestion (TUI) ────────────────────────────────────────────

    def _open_archive_prompt(self, path: str = "") -> None:
        """Open an archive and list its members; prompt to open one (M-x open-archive)."""
        from ..archive import is_archive
        if path and is_archive(path):
            self._open_archive_pick(path)
            return
        self._enter_minibuffer(
            "Archive path: ",
            on_commit=self._open_archive_pick,
        )

    def _open_archive_pick(self, archive_path: str) -> None:
        """List members of *archive_path* and prompt the user to pick one."""
        from ..archive import list_members
        archive_path = archive_path.strip()
        if not archive_path:
            return
        try:
            members = list_members(archive_path)
        except Exception as e:
            self.notify(f"Cannot read archive: {e}", error=True)
            return
        if not members:
            self.notify("No readable documents found in archive", error=True)
            return
        # Show members in a pager; user types the number to open
        text = f"Archive: {archive_path}\n\nMembers:\n"
        for i, m in enumerate(members, 1):
            text += f"  {i:3d}.  {m}\n"
        text += "\nType M-x open-archive <archive>!<member> to open a specific member."
        self._show_text_pager("Archive Contents", text)
        # Also load the archive index document
        self._open_async(archive_path)

    # ── Metadata editing (TUI) ─────────────────────────────────────────────

    def _metadata_edit_cmd(self) -> None:
        """Edit metadata (title/author/year/DOI/ISBN) for the current document."""
        if not self.doc:
            self.notify("No document open", error=True)
            return
        key = self.doc.path or self.doc.title or ""
        if not key:
            return
        library: Dict[str, Any] = dict(self.settings.get("library") or {})
        entry = dict(library.get(key) or {})
        meta: Dict[str, Any] = dict(entry.get("meta") or {})

        def _prompt_field(field: str, current: str) -> None:
            self._enter_minibuffer(
                f"Metadata — {field} [{current}]: ",
                on_commit=lambda v: _set_field(field, v.strip() or current),
            )

        def _set_field(field: str, value: str) -> None:
            meta[field] = value
            entry["meta"] = meta
            library[key] = entry
            self.settings.set("library", library)
            self.notify(f"Metadata updated: {field} = {value!r}")

        def _lookup_doi() -> None:
            doi = meta.get("doi", "")
            if not doi:
                self.notify("No DOI in metadata — set 'doi' first", error=True)
                return
            self.notify(f"Looking up DOI {doi!r}…")
            from ..citations import _fetch_citation_by_doi
            def _do():
                try:
                    c = _fetch_citation_by_doi(doi)
                    for f in ("title", "author", "year", "publisher"):
                        if c.get(f):
                            meta[f] = c[f]
                    entry["meta"] = meta
                    library[key] = entry
                    self.settings.set("library", library)
                    self.notify("DOI metadata filled")
                except Exception as e:
                    self.notify(f"DOI lookup failed: {e}", error=True)
            threading.Thread(target=_do, daemon=True).start()

        def _lookup_isbn() -> None:
            isbn = meta.get("isbn", "")
            if not isbn:
                self.notify("No ISBN in metadata — set 'isbn' first", error=True)
                return
            from ..citations import _valid_isbn, _fetch_metadata_by_isbn
            if not _valid_isbn(isbn):
                self.notify(f"ISBN {isbn!r} failed checksum validation", error=True)
                return
            self.notify(f"Looking up ISBN {isbn!r}…")
            def _do():
                m, msg = _fetch_metadata_by_isbn(isbn)
                if m:
                    for f in ("title", "author", "year", "publisher", "isbn"):
                        if m.get(f):
                            meta[f] = m[f]
                    entry["meta"] = meta
                    library[key] = entry
                    self.settings.set("library", library)
                    self.notify("ISBN metadata filled")
                else:
                    self.notify(f"ISBN lookup: {msg}", error=True)
            threading.Thread(target=_do, daemon=True).start()

        # Show current metadata and prompt for field
        lines = ["Current metadata:", ""]
        for f in ("title", "author", "year", "doi", "isbn", "publisher"):
            lines.append(f"  {f:<12} {meta.get(f, '')}")
        lines += ["", "Commands: title / author / year / doi / isbn / publisher / lookup-doi / lookup-isbn"]
        self._show_text_pager("Metadata Editor", "\n".join(lines))

        self._enter_minibuffer(
            "Edit field (title/author/year/doi/isbn/publisher/lookup-doi/lookup-isbn): ",
            on_commit=lambda v: (
                _lookup_doi() if v.strip() == "lookup-doi" else
                _lookup_isbn() if v.strip() == "lookup-isbn" else
                _prompt_field(v.strip(), meta.get(v.strip(), "")) if v.strip() else None
            ),
        )

    # ── Library search (TUI) ──────────────────────────────────────────────

    def _library_search_cmd(self, query: str = "") -> None:
        """Search the document library (M-x library-search)."""
        from ..discovery import search_library
        if not query:
            self._enter_minibuffer(
                "Library search: ",
                on_commit=self._library_search_cmd,
            )
            return
        results = search_library(self.settings, query=query)
        if not results:
            self.notify(f"No library entries match {query!r}")
            return
        lines = [f"Library search: {query!r}  ({len(results)} result(s))", ""]
        for key, entry in results[:50]:
            title = entry.get("title") or key
            meta = entry.get("meta") or {}
            author = meta.get("author") or entry.get("author") or ""
            year = meta.get("year") or ""
            tag = f" — {author}" if author else ""
            tag += f" ({year})" if year else ""
            lines.append(f"  {title}{tag}")
            lines.append(f"    {key}")
            lines.append("")
        self._show_text_pager("Library Search Results", "\n".join(lines))
