"""Document loading, rendering, sentence map, reading level.

Methods of StarApp, split out of the former monolithic star/tui.py.
Mixed into StarApp in app.py; calls other groups via ``self``.
"""
from .._runtime import *  # noqa: F401,F403
from ..documents import Document, _build_word_map, load_document
from ..render import render_markdown
from ..stats import _record_library


class DocumentMixin:

    # ── Async document loading ─────────────────────────────────────────────

    def _open_async(self, path: str) -> None:
        self.loading = True
        self.loading_msg = (
            f"Loading {Path(path).name if not path.startswith('http') else path} …"
        )

        def _work() -> None:
            try:
                doc = load_document(path, self.settings)
                self._load_queue.put(doc)
            except Exception as e:
                err_doc = Document(
                    path=path,
                    title="Error",
                    format="error",
                    markdown=f"# Load Error\n\n```\n{e}\n```\n",
                )
                err_doc.plain_text = str(e)
                self._load_queue.put(err_doc)

        threading.Thread(target=_work, daemon=True).start()

    def _poll_load_queue(self) -> None:
        try:
            doc = self._load_queue.get_nowait()
        except queue.Empty:
            return
        self.loading = False
        # Persist the current document's position before replacing it.
        self._save_reading_position()
        self.doc = doc
        # Build word map in background too
        self._render_doc()
        self.scroll = 0
        self._tts_stop()  # also clears any saved pause position for old doc
        # The bundled welcome page is a real document (speech/nav work) but
        # must not pollute recents, last_path, the library, or auto-play on
        # every launch (GUI parity — see StarApp._is_welcome).
        if not self._is_welcome(doc):
            self.notify(f"Opened: {doc.title}")
            recents: List[str] = self.settings["recent_files"]
            if doc.path and doc.path not in recents:
                recents.insert(0, doc.path)
                self.settings["recent_files"] = recents[:20]
            self.settings["last_path"] = doc.path
            _record_library(self.settings, doc)  # library / bookshelf
            if self.settings["tts_auto_play"]:
                self._tts_play()

    def _render_doc(self) -> None:
        if not self.doc:
            return
        h, w = self.scr.getmaxyx()
        wrap = int(self.settings["wrap_width"]) or (w - 2)
        self.rendered = render_markdown(
            self.doc.markdown,
            wrap,
            tab_width=int(self.settings["tab_width"]),
            syntax=bool(self.settings["syntax_highlight"]),
        )

        # Build word map and sentence map asynchronously (non-blocking)
        def _build() -> None:
            flat = ["".join(t for t, _ in line) for line in self.rendered]
            self.doc.word_map = _build_word_map(self.doc.plain_text, flat)
            self.tts.set_word_map(self.doc.word_map)
            self._build_sentence_map()  # depends on word_map
            self._restore_reading_position()  # scroll to last position

        threading.Thread(target=_build, daemon=True).start()

    # ── Sentence map ──────────────────────────────────────────────────

    def _build_sentence_map(self) -> None:
        """Populate self._sentence_starts with word-map indices at which each
        sentence begins.  Runs in the background thread that also builds the
        word map, so self.doc.word_map is guaranteed to exist on entry."""
        if not self.doc or not self.doc.plain_text or not self.doc.word_map:
            self._sentence_starts = [0]
            return

        text = self.doc.plain_text
        wm = self.doc.word_map

        # Collect the character offsets where new sentences begin.
        char_starts = [0]
        for m in _SENTENCE_SPLIT_RE.finditer(text):
            char_starts.append(m.end())

        # Map each char offset to the first word at or after that offset.
        # Both char_starts and wm are ordered, so a single forward walk suffices.
        word_starts: List[int] = []
        wi = 0
        for cs in char_starts:
            while wi < len(wm) and wm[wi].tts_offset < cs:
                wi += 1
            word_starts.append(min(wi, len(wm) - 1))

        # Deduplicate while preserving order.
        seen: set = set()
        result: List[int] = []
        for ws in word_starts:
            if ws not in seen:
                seen.add(ws)
                result.append(ws)

        self._sentence_starts = result if result else [0]

    def _find_sentence_idx(self, word_idx: int) -> int:
        """Return the index in _sentence_starts of the sentence that contains
        *word_idx* (binary search; O(log n))."""
        ss = self._sentence_starts
        lo, hi, result = 0, len(ss) - 1, 0
        while lo <= hi:
            mid = (lo + hi) // 2
            if ss[mid] <= word_idx:
                result = mid
                lo = mid + 1
            else:
                hi = mid - 1
        return result

    def _current_word_for_nav(self) -> int:
        """Return the best estimate of the current reading word index.

        Priority order:
        1. Live TTS highlight (engine is actively speaking).
        2. Saved pause position (_tts_paused_at_word) set when the user
           pressed Space to pause — this is the word we stopped on, so
           replay/sentence-jump commands operate at the right place even
           while speech is not running.
        3. First word at or below the current scroll position (viewport
           fallback when no speech has started or the document was just
           opened).
        """
        if self.tts.speaking:
            # Prefer the last callback-confirmed position (actual audio
            # position) over the timer estimate (which may be ahead).
            cb = self.tts.last_cb_word_idx
            if cb >= 0:
                return cb
            idx = self.tts.current_word_idx
            if idx >= 0:
                return idx
        if self._tts_paused_at_word >= 0:
            return self._tts_paused_at_word
        if self.doc and self.doc.word_map:
            for i, wp in enumerate(self.doc.word_map):
                if wp.disp_line >= self.scroll:
                    return i
        return 0

    def _compute_reading_level_tui(self) -> str:
        """Compute Flesch-Kincaid reading level for the current document."""
        if not self.doc or not self.doc.plain_text:
            return "No document loaded"
        text = self.doc.plain_text[:50000]  # cap for speed
        words = text.split()
        n_words = max(1, len(words))
        sentences = re.split(r"[.!?]+", text)
        n_sentences = max(1, len([s for s in sentences if s.strip()]))

        def _syllables(word: str) -> int:
            word = word.lower().rstrip(".,;:!?")
            if not word:
                return 1
            count = len(re.findall(r"[aeiou]+", word))
            if word.endswith("e") and count > 1:
                count -= 1
            return max(1, count)

        n_syllables = sum(_syllables(w) for w in words)
        ease = (
            206.835 - 1.015 * (n_words / n_sentences) - 84.6 * (n_syllables / n_words)
        )
        grade = 0.39 * (n_words / n_sentences) + 11.8 * (n_syllables / n_words) - 15.59
        ease = max(0.0, min(100.0, ease))
        grade = max(0.0, grade)
        if grade < 6:
            level = "elementary"
        elif grade < 9:
            level = "middle school"
        elif grade < 13:
            level = "high school"
        elif grade < 16:
            level = "college"
        else:
            level = "graduate"
        return (
            f"Reading level: Grade {grade:.1f} ({level})  "
            f"Ease: {ease:.0f}/100  "
            f"({n_words:,} words, {n_sentences:,} sentences)"
        )
