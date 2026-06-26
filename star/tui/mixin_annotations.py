"""Annotations / notes: capture, list, search, export, browser.

Methods of StarApp, split out of the former monolithic star/tui.py.
Mixed into StarApp in app.py; calls other groups via ``self``.
"""
from .._runtime import *  # noqa: F401,F403
from ._screen import _addstr, _fillrow
from ..annotations import _annotation_matches, _format_annotations, _parse_tags


class AnnotationsMixin:

    # ── Annotations / notes (TUI) ──────────────────────────────────────────

    def _annot_key(self) -> str:
        """Per-document key under which annotations are stored."""
        if not self.doc:
            return ""
        return self.doc.path or self.doc.title or ""

    def _load_annotations(self) -> List[Dict[str, Any]]:
        """Saved notes for the current document, sorted by position."""
        key = self._annot_key()
        if not key:
            return []
        store = self.settings.get("annotations", {}) or {}
        items = [dict(a) for a in store.get(key, [])]
        items.sort(key=lambda a: int(a.get("word_idx", a.get("char_pos", 0)) or 0))
        return items

    def _store_annotations(self, items: List[Dict[str, Any]]) -> None:
        key = self._annot_key()
        if not key:
            return
        store = dict(self.settings.get("annotations", {}) or {})
        if items:
            store[key] = items
        else:
            store.pop(key, None)
        self.settings.set("annotations", store)

    def _annotate(self) -> None:
        """Add a note at the current reading position (key 'a' / M-x annotate)."""
        if not self.doc or not self.doc.word_map:
            self.notify("No document loaded.", error=True)
            return
        self._enter_minibuffer("Note: ", on_commit=self._annotate_note_cb)

    def _annotate_note_cb(self, note: str) -> None:
        note = note.strip()
        if not note:
            return
        self._pending_note = note
        self._enter_minibuffer(
            "Tags (optional, comma-separated): ", on_commit=self._annotate_tags_cb
        )

    def _annotate_tags_cb(self, tag_str: str) -> None:
        note = getattr(self, "_pending_note", "")
        if not note:
            return
        self._pending_note = ""
        wm = self.doc.word_map if self.doc else []
        word_idx = self._current_word_for_nav()
        if word_idx < 0:
            word_idx = 0
        anchor = ""
        if wm and 0 <= word_idx < len(wm):
            dl = wm[word_idx].disp_line
            if 0 <= dl < len(self.rendered):
                anchor = "".join(t for t, _ in self.rendered[dl]).strip()[:120]
        items = self._load_annotations()
        items.append(
            {
                "char_pos": 0,  # Qt-only; TUI anchors by word_idx
                "word_idx": int(word_idx),
                "anchor": anchor,
                "note": note,
                "tags": _parse_tags(tag_str),
                "cite": "",
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
        )
        self._store_annotations(items)
        tags = _parse_tags(tag_str)
        self.notify(
            f"Note added ({len(items)} total)"
            + (f"  tags: {', '.join(tags)}" if tags else "")
        )

    def _annotations_list(self, query: str = "") -> None:
        """Show all notes (optionally filtered) in a pager (M-x annotations-list)."""
        items = self._load_annotations()
        if not items:
            self.notify("No notes yet. Press 'a' or M-x annotate to add one.")
            return
        rows = [(i, a) for i, a in enumerate(items) if _annotation_matches(a, query)]
        if not rows:
            self.notify(f"No notes match '{query}'.")
            return
        title = self.doc.title if self.doc else "document"
        lines = [f"# Notes — {title}", ""]
        if query:
            lines.append(f"*Filter: {query} — {len(rows)}/{len(items)} shown*")
            lines.append("")
        for i, a in rows:
            first = (a.get("note", "") or "").splitlines()
            head = first[0] if first else "(empty)"
            lines.append(f"## [{i}] {head}")
            if a.get("anchor"):
                lines.append(f"> {a['anchor']}")
            meta = "  ".join(f"#{t}" for t in a.get("tags", []) or [])
            if a.get("cite"):
                meta += ("  " if meta else "") + f"@{a['cite']}"
            if meta:
                lines.append(f"`{meta}`")
            lines.append(a.get("note", ""))
            if a.get("ts"):
                lines.append(f"*{a['ts']}*")
            lines.append("")
        lines.append("---")
        lines.append(
            "M-x annotation-goto <n> · annotation-delete <n> · annotations-export"
        )
        self._show_text_pager("Notes", "\n".join(lines))

    def _annotations_search(self) -> None:
        self._enter_minibuffer(
            "Filter notes (text or #tag): ",
            on_commit=lambda q: self._annotations_list(q),
        )

    def _annotation_goto(self, arg: str) -> None:
        items = self._load_annotations()
        try:
            i = int(str(arg).strip())
        except (ValueError, TypeError):
            self.notify("Usage: annotation-goto <n>", error=True)
            return
        if not (0 <= i < len(items)):
            self.notify(f"No note #{i}", error=True)
            return
        wm = self.doc.word_map if self.doc else []
        wi = int(items[i].get("word_idx", 0) or 0)
        if wm and 0 <= wi < len(wm):
            self._scroll_to_line(wm[wi].disp_line)
            self.notify(f"Note #{i}: {items[i].get('note', '')[:50]}")
        else:
            self.notify("Note position unavailable", error=True)

    def _annotation_delete(self, arg: str) -> None:
        items = self._load_annotations()
        try:
            i = int(str(arg).strip())
        except (ValueError, TypeError):
            self.notify("Usage: annotation-delete <n>", error=True)
            return
        if not (0 <= i < len(items)):
            self.notify(f"No note #{i}", error=True)
            return
        del items[i]
        self._store_annotations(items)
        self.notify(f"Note #{i} deleted ({len(items)} left)")

    def _annotations_export(self) -> None:
        items = self._load_annotations()
        if not items:
            self.notify("No notes to export.", error=True)
            return
        p = Path(self.doc.path) if self.doc and self.doc.path else Path("notes")
        default = str(p.parent / (p.stem + "_notes.md"))
        self._enter_minibuffer(
            "Export notes to (.md/.json/.bib/.ris/.txt): ",
            initial=default,
            on_commit=self._annotations_export_cb,
        )

    def _annotations_export_cb(self, dest: str) -> None:
        dest = dest.strip()
        if not dest:
            return
        items = self._load_annotations()
        meta = getattr(self.doc, "metadata", {}) or {}
        title = self.doc.title if self.doc else "notes"
        author = meta.get("author") or meta.get("creator") or ""
        try:
            content = _format_annotations(
                items,
                Path(dest).suffix.lower(),
                title,
                author,
                self.doc.path if self.doc else "",
            )
            Path(dest).write_text(content, encoding="utf-8")
            self.notify(f"Exported {len(items)} note(s) → {dest}")
        except OSError as e:
            self.notify(f"Export error: {e}", error=True)

    # ── Saved note-filter presets ───────────────────────────────────────

    def _notes_presets(self) -> Dict[str, str]:
        return dict(self.settings.get("annotation_filter_presets", {}) or {})

    def _notes_preset_save(self, name: str, query: str) -> None:
        name = (name or "").strip()
        if not name:
            return
        presets = self._notes_presets()
        presets[name] = query
        self.settings.set("annotation_filter_presets", presets)

    # ── Inline prompt helpers (used inside the interactive notes browser) ──

    def _inline_prompt(self, prompt: str, initial: str = "") -> Optional[str]:
        """Read a line of text on the bottom row; return it, or None on Esc."""
        buf = list(initial)
        while True:
            h, w = self.scr.getmaxyx()
            _fillrow(self.scr, h - 1, self._a("minibuf"))
            shown = (prompt + "".join(buf))[: w - 1]
            _addstr(self.scr, h - 1, 0, shown, self._a("minibuf"))
            try:
                self.scr.move(h - 1, min(len(shown), w - 1))
            except curses.error:
                pass
            self.scr.refresh()
            ch = self.scr.getch()
            if ch in (10, 13, curses.KEY_ENTER):
                return "".join(buf)
            if ch in (27, 7):
                return None
            if ch in (curses.KEY_BACKSPACE, 127, 8):
                if buf:
                    buf.pop()
            elif 32 <= ch < 127:
                buf.append(chr(ch))

    def _inline_confirm(self, prompt: str) -> bool:
        """Show *prompt* on the bottom row; return True only on 'y'."""
        h, w = self.scr.getmaxyx()
        _fillrow(self.scr, h - 1, self._a("minibuf"))
        _addstr(self.scr, h - 1, 0, prompt[: w - 1], self._a("minibuf"))
        self.scr.refresh()
        return self.scr.getch() in (ord("y"), ord("Y"))

    # ── Interactive notes browser ───────────────────────────────────────

    def _notes_browser(self) -> None:
        """A dedicated, interactive notes mode for the TUI.

        Arrow keys / j,k select; Enter jumps to the note; r reads from it;
        e edits, d deletes, / filters, p cycles saved filter presets, s saves
        the current filter as a preset, x exports, q/Esc exits.
        """
        if not self.doc or not self.doc.word_map:
            self.notify("No document loaded.", error=True)
            return
        flt = ""
        sel = 0
        preset_names = list(self._notes_presets().keys())
        preset_idx = -1
        while True:
            all_items = self._load_annotations()
            rows = [
                (i, a) for i, a in enumerate(all_items) if _annotation_matches(a, flt)
            ]
            if rows:
                sel = max(0, min(sel, len(rows) - 1))
            else:
                sel = 0
            h, w = self.scr.getmaxyx()
            view_h = max(1, h - 2)
            top = 0 if sel < view_h else sel - view_h + 1
            self.scr.erase()
            hdr = f" Notes — {(self.doc.title or '')[:38]}  ({len(rows)}/{len(all_items)})"
            if flt:
                hdr += f"  filter: {flt}"
            _fillrow(self.scr, 0, self._a("title_bar"))
            _addstr(self.scr, 0, 0, hdr[: w - 1], self._a("title_bar"))
            if rows:
                for vi in range(top, min(len(rows), top + view_h)):
                    i, a = rows[vi]
                    note = (a.get("note", "") or "").splitlines()
                    head = note[0] if note else "(empty)"
                    tags = " ".join(f"#{t}" for t in a.get("tags", []) or [])
                    cite = f" @{a['cite']}" if a.get("cite") else ""
                    line = f"[{i}] {head}{('   ' + tags) if tags else ''}{cite}"
                    attr = curses.A_REVERSE if vi == sel else self._a("normal")
                    _addstr(self.scr, 1 + vi - top, 0, line[: w - 1].ljust(w - 1), attr)
            else:
                _addstr(
                    self.scr,
                    2,
                    2,
                    "No notes match.  /=filter  a=add (after exit)  q=quit",
                    self._a("dim"),
                )
            foot = (
                " ↑↓ move  ↵ jump  r read  e edit  d delete  / filter"
                "  p preset  s save  x export  q quit "
            )
            _fillrow(self.scr, h - 1, self._a("status"))
            _addstr(self.scr, h - 1, 0, foot[: w - 1], self._a("status"))
            self.scr.refresh()

            ch = self.scr.getch()
            if ch in (ord("q"), ord("Q"), 27, 7):
                return
            elif ch in (curses.KEY_DOWN, ord("j")):
                sel = min(sel + 1, max(0, len(rows) - 1))
            elif ch in (curses.KEY_UP, ord("k")):
                sel = max(sel - 1, 0)
            elif ch == curses.KEY_NPAGE:
                sel = min(sel + view_h, max(0, len(rows) - 1))
            elif ch == curses.KEY_PPAGE:
                sel = max(sel - view_h, 0)
            elif ch == curses.KEY_HOME:
                sel = 0
            elif ch == curses.KEY_END:
                sel = max(0, len(rows) - 1)
            elif ch in (10, 13, curses.KEY_ENTER) and rows:
                self._annotation_goto(str(rows[sel][0]))
                return
            elif ch == ord("r") and rows:
                self._tts_play_from_word(int(rows[sel][1].get("word_idx", 0) or 0))
            elif ch == ord("e") and rows:
                i = rows[sel][0]
                new = self._inline_prompt(f"Edit [{i}]: ", rows[sel][1].get("note", ""))
                if new is not None and new.strip():
                    items = self._load_annotations()
                    if 0 <= i < len(items):
                        items[i]["note"] = new.strip()
                        items[i]["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                        self._store_annotations(items)
            elif ch == ord("d") and rows:
                i = rows[sel][0]
                if self._inline_confirm(f"Delete note [{i}]? (y/n) "):
                    self._annotation_delete(str(i))
                    sel = max(0, sel - 1)
            elif ch == ord("/"):
                res = self._inline_prompt("Filter (text or #tag): ", flt)
                if res is not None:
                    flt = res.strip()
                    sel = 0
            elif ch == ord("p"):
                preset_names = list(self._notes_presets().keys())
                if preset_names:
                    preset_idx = (preset_idx + 1) % len(preset_names)
                    name = preset_names[preset_idx]
                    flt = self._notes_presets()[name]
                    sel = 0
                    self.notify(f"Preset: {name}  ({flt})")
                else:
                    self.notify("No saved presets. Press s to save one.")
            elif ch == ord("s"):
                name = self._inline_prompt("Save current filter as preset: ")
                if name and name.strip():
                    self._notes_preset_save(name, flt)
                    self.notify(f"Saved preset '{name.strip()}'")
            elif ch == ord("x"):
                return self._annotations_export()
