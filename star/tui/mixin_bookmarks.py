"""Bookmarks, navigation history, chapter jumps, recent files.

Methods of StarApp, split out of the former monolithic star/tui.py.
Mixed into StarApp in app.py; calls other groups via ``self``.
"""
from .._runtime import *  # noqa: F401,F403


class BookmarksMixin:

    # ── SSML toggle ─────────────────────────────────────────────────────

    # ── Bookmarks, history, search & utility commands ───────────────────
    def _bookmark_set(self, name: str = "") -> None:
        "Set a named bookmark at the current reading position."
        if not self.doc or not self.doc.word_map:
            self.notify("No document loaded.", error=True)
            return
        doc_path = self.doc.path or self.doc.title
        bookmarks = dict(self.settings.get("bookmarks", {}))
        doc_bm = dict(bookmarks.get(doc_path, {}))
        if not name:
            n = 1
            while f"mark{n}" in doc_bm:
                n += 1
            name = f"mark{n}"
        cur = self._current_word_for_nav()
        offset = self.doc.word_map[cur].tts_offset
        total_chars = len(self.doc.plain_text)
        pct = int(100 * offset / max(1, total_chars))
        doc_bm[name] = {
            "offset": offset,
            "pct": pct,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        bookmarks[doc_path] = doc_bm
        self.settings.set("bookmarks", bookmarks)
        self.notify(f"Bookmark set: {name}  ({pct}%)")

    def _bookmark_goto(self, name: str) -> None:
        "Jump to a named bookmark in the current document."
        if not self.doc or not self.doc.word_map:
            self.notify("No document loaded.", error=True)
            return
        name = (name or "").strip()
        if not name:
            self.notify("Usage: bookmark-goto <name>", error=True)
            return
        doc_path = self.doc.path or self.doc.title
        doc_bm = self.settings.get("bookmarks", {}).get(doc_path, {})
        if name not in doc_bm:
            self.notify(f"Bookmark '{name}' not found.", error=True)
            return
        target_offset = int(doc_bm[name].get("offset", 0))
        wm = self.doc.word_map
        # Find the word whose tts_offset is closest to the saved offset.
        best, best_dist = 0, abs(wm[0].tts_offset - target_offset)
        for i, wp in enumerate(wm):
            dist = abs(wp.tts_offset - target_offset)
            if dist < best_dist:
                best_dist, best = dist, i
            if wp.tts_offset > target_offset + best_dist:
                break  # offsets are monotonically increasing; no closer match ahead
        self._history_push()
        self._sentence_jump(best, f"Jumping to bookmark '{name}'")

    def _bookmark_list(self) -> None:
        "List all bookmarks for the current document in the status bar."
        if not self.doc:
            self.notify("No document loaded.", error=True)
            return
        doc_path = self.doc.path or self.doc.title
        doc_bm = self.settings.get("bookmarks", {}).get(doc_path, {})
        if not doc_bm:
            self.notify("No bookmarks for this document.")
            return
        parts = [
            f"{k} ({v.get('pct', '?')}%, {str(v.get('ts', ''))[:10]})"
            for k, v in sorted(doc_bm.items())
        ]
        self.notify("Bookmarks — " + "  |  ".join(parts), dur=8.0)

    def _bookmark_delete(self, name: str) -> None:
        "Remove a named bookmark from the current document."
        if not self.doc:
            self.notify("No document loaded.", error=True)
            return
        name = (name or "").strip()
        if not name:
            self.notify("Usage: bookmark-delete <name>", error=True)
            return
        doc_path = self.doc.path or self.doc.title
        bookmarks = dict(self.settings.get("bookmarks", {}))
        doc_bm = dict(bookmarks.get(doc_path, {}))
        if name not in doc_bm:
            self.notify(f"Bookmark '{name}' not found.", error=True)
            return
        del doc_bm[name]
        bookmarks[doc_path] = doc_bm
        self.settings.set("bookmarks", bookmarks)
        self.notify(f"Bookmark '{name}' deleted.")

    # ── Navigation history ──────────────────────────────

    def _history_push(self, offset: int = -1) -> None:
        "Record the current TTS offset in the navigation history before a jump."
        if not self.doc or not self.doc.word_map:
            return
        if offset < 0:
            cur = self._current_word_for_nav()
            if 0 <= cur < len(self.doc.word_map):
                offset = self.doc.word_map[cur].tts_offset
            else:
                return
        # When branching off mid-history (user navigated back then jumped elsewhere),
        # discard all forward entries so the list stays consistent.
        if self._nav_hist_pos >= 0:
            self._nav_history = self._nav_history[: self._nav_hist_pos + 1]
            self._nav_hist_pos = -1
        self._nav_history.append(offset)
        max_size = int(self.settings.get("nav_history_size", 50))
        if len(self._nav_history) > max_size:
            self._nav_history = self._nav_history[-max_size:]

    def _history_back(self) -> None:
        "Navigate to the previous position in the navigation history."
        if not self._nav_history:
            self.notify("Navigation history is empty.")
            return
        total = len(self._nav_history)
        if self._nav_hist_pos == -1:
            # First back-step: jump to the most recently saved position.
            new_pos = total - 1
        elif self._nav_hist_pos > 0:
            new_pos = self._nav_hist_pos - 1
        else:
            self.notify("No earlier history.")
            return
        self._nav_hist_pos = new_pos
        self.notify(f"History: position {new_pos + 1}/{total}")
        self._jump_to_offset(self._nav_history[new_pos])

    def _history_forward(self) -> None:
        "Navigate forward after having gone back in navigation history."
        if self._nav_hist_pos < 0:
            self.notify("No forward history.")
            return
        total = len(self._nav_history)
        new_pos = self._nav_hist_pos + 1
        if new_pos >= total:
            self._nav_hist_pos = -1
            self.notify("History: at present position.")
            return
        self._nav_hist_pos = new_pos
        self.notify(f"History: position {new_pos + 1}/{total}")
        self._jump_to_offset(self._nav_history[new_pos])

    def _jump_to_offset(self, target_offset: int) -> None:
        "Scroll to the word in the current document closest to *target_offset*."
        if not self.doc or not self.doc.word_map:
            return
        wm = self.doc.word_map
        best = len(wm) - 1
        for i, wp in enumerate(wm):
            if wp.tts_offset >= target_offset:
                best = i
                break
        dest_line = wm[best].disp_line
        was_speaking = self.tts.speaking
        self.tts.stop()
        self._highlight_line = self._highlight_col_start = self._highlight_col_end = -1
        total = len(self.rendered)
        self.scroll = max(0, min(dest_line, total - 1) if total else 0)
        if was_speaking:
            self._tts_play_from_word(best)

    # ── Chapter navigation ──────────────────────────────

    def _chapter_next(self) -> None:
        "Jump to the next chapter in the document."
        if not self.doc or not self.doc.word_map:
            return
        chapters = getattr(self.doc, "chapters", None)
        if not chapters:
            self.notify("No chapter navigation available for this document.")
            return
        cur = self._current_word_for_nav()
        current_ch_idx = 0
        for i, (_, _, widx) in enumerate(chapters):
            if widx <= cur:
                current_ch_idx = i
        next_idx = current_ch_idx + 1
        if next_idx >= len(chapters):
            self.notify("Already at the last chapter.")
            return
        title, _, dest_word = chapters[next_idx]
        self._history_push()
        self._sentence_jump(
            dest_word, f"Chapter {next_idx + 1}/{len(chapters)}: {title}"
        )

    def _chapter_prev(self) -> None:
        "Jump to the previous chapter, or to the current chapter start if well into it."
        if not self.doc or not self.doc.word_map:
            return
        chapters = getattr(self.doc, "chapters", None)
        if not chapters:
            self.notify("No chapter navigation available for this document.")
            return
        cur = self._current_word_for_nav()
        current_ch_idx = 0
        for i, (_, _, widx) in enumerate(chapters):
            if widx <= cur:
                current_ch_idx = i
        _, _, ch_start_word = chapters[current_ch_idx]
        # Mirror the double-tap rewind idiom used by sentence navigation:
        # if the reader is more than 5 words into the chapter, replay its start;
        # otherwise go one chapter back.
        if cur - ch_start_word > 5:
            dest_idx = current_ch_idx
        elif current_ch_idx == 0:
            self.notify("Already at the first chapter.")
            return
        else:
            dest_idx = current_ch_idx - 1
        title, _, dest_word = chapters[dest_idx]
        self._history_push()
        self._sentence_jump(
            dest_word, f"Chapter {dest_idx + 1}/{len(chapters)}: {title}"
        )

    def _chapter_list(self) -> None:
        "Show all chapter titles for the current document in the status bar."
        if not self.doc:
            self.notify("No document loaded.", error=True)
            return
        chapters = getattr(self.doc, "chapters", None)
        if not chapters:
            self.notify("No chapter navigation available for this document.")
            return
        parts = [f"{i + 1}. {title}" for i, (title, _, _) in enumerate(chapters)]
        self.notify("Chapters — " + "  |  ".join(parts), dur=10.0)

    def _chapter_goto(self, name_or_num: str) -> None:
        "Jump to a chapter by 1-based number or partial case-insensitive title match."
        if not self.doc or not self.doc.word_map:
            return
        chapters = getattr(self.doc, "chapters", None)
        if not chapters:
            self.notify("No chapter navigation available for this document.")
            return
        name_or_num = (name_or_num or "").strip()
        if not name_or_num:
            self._chapter_list()
            return
        if name_or_num.isdigit():
            n = int(name_or_num) - 1  # convert to 0-based index
            if 0 <= n < len(chapters):
                title, _, dest_word = chapters[n]
                self._history_push()
                self._sentence_jump(
                    dest_word, f"Chapter {n + 1}/{len(chapters)}: {title}"
                )
            else:
                self.notify(
                    f"Chapter number out of range (1–{len(chapters)}).", error=True
                )
            return
        # Partial title match — take the first hit.
        needle = name_or_num.lower()
        for i, (title, _, dest_word) in enumerate(chapters):
            if needle in title.lower():
                self._history_push()
                self._sentence_jump(
                    dest_word, f"Chapter {i + 1}/{len(chapters)}: {title}"
                )
                return
        self.notify(f"No chapter matching '{name_or_num}'.", error=True)

    # ── Recent files ──────────────────

    def _recent_files(self) -> None:
        "Show the recent-files list and open the selected entry via minibuffer."
        recent: List[str] = self.settings.get("recent_files", [])
        if not recent:
            self.notify("No recent files.")
            return
        # Preview up to 10 entries in the status bar.
        preview_parts = [f"{i + 1}. {path}" for i, path in enumerate(recent[:10])]
        self.notify("Recent: " + "  |  ".join(preview_parts), dur=8.0)

        def _on_pick(value: str) -> None:
            value = value.strip()
            if not value:
                return
            if value.isdigit():
                n = int(value) - 1
                if 0 <= n < len(recent):
                    self._open_async(recent[n])
                else:
                    self.notify(f"No recent file #{int(value)}.", error=True)
            else:
                # User typed a path directly.
                self._open_async(value)

        self._enter_minibuffer(
            prompt=f"Open recent [1–{min(len(recent), 10)}] or path: ",
            on_commit=_on_pick,
        )
