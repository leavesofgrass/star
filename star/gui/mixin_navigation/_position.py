"""ReadingPositionMixin — save / restore reading position (resume).

Split out of the former ``mixin_navigation.py`` monolith; methods moved
verbatim.  Mixed into StarWindow via ``NavigationMixin``; holds no state of
its own, operating on StarWindow instance state via ``self``.

IMPORT SAFETY: references Qt at module scope — imported lazily by
main_window.py (itself imported by runner.py after the _QT guard).
"""
from ..._runtime import *  # noqa: F401,F403
from ...library import (
    progress_for,
    record_progress,
)


class ReadingPositionMixin:
    # ── Reading position memory ──────────────────────────────────────

    def _qt_save_reading_position(self) -> None:
        """Persist the current reading offset for the open document.
        Identical logic to StarApp._save_reading_position."""
        if not self.doc or not self.doc.path or not self.doc.word_map:
            return
        cur = self._qt_current_word_for_nav()
        wm = self.doc.word_map
        if cur < 0 or cur >= len(wm):
            return
        offset = wm[cur].tts_offset
        total_chars = len(self.doc.plain_text or "")
        pct = int(100 * offset / max(1, total_chars))
        positions = dict(self.settings.get("reading_positions", {}))
        positions[self.doc.path] = {
            "offset": offset,
            "pct": pct,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        if len(positions) > 200:
            evict = sorted(positions, key=lambda k: positions[k].get("ts", ""))[:50]
            for k in evict:
                del positions[k]
        self.settings.set("reading_positions", positions)
        # Mirror progress into the library-folder sidecar so it syncs across
        # machines (no-op when the document is not in a library folder).
        record_progress(
            self.settings,
            self.doc.path,
            {"offset": offset, "pct": pct, "ts": positions[self.doc.path]["ts"]},
        )

    def _qt_restore_reading_position(self) -> None:
        """Scroll to the saved position for the current document and
        optionally resume TTS.  Called on the GUI thread via
        _restore_signal after the word map has been built."""
        if not self.doc or not self.doc.path or not self.doc.word_map:
            return
        if not self.settings.get("tts_auto_resume", True):
            return
        saved = self.settings.get("reading_positions", {}).get(self.doc.path)
        # A library-folder document may carry newer progress in its synced
        # sidecar (e.g. read further on another machine) — prefer whichever is
        # most recent by timestamp.
        side = progress_for(self.settings, self.doc.path)
        if side and (not saved or str(side.get("ts", "")) > str(saved.get("ts", ""))):
            saved = side
        if not saved:
            return
        target_offset = int(saved.get("offset", 0))
        pct = int(saved.get("pct", 0))
        ts = str(saved.get("ts", ""))[:10]
        # Find the word-map entry whose tts_offset is at or beyond the
        # saved offset.
        wm = self.doc.word_map
        best = len(wm) - 1
        for i, wp in enumerate(wm):
            if wp.tts_offset >= target_offset:
                best = i
                break
        # Scroll the editor to that position and move the text cursor
        # there.  Moving the cursor is essential: _qt_current_word_for_nav
        # reads the cursor position when TTS is idle, so without this
        # a subsequent _qt_save_reading_position call (e.g. from
        # closeEvent before the user ever starts TTS) would see position 0
        # and overwrite the just-restored offset with the start of the doc.
        # Pagination: page to the saved word first so its offset is rendered.
        if getattr(self, "_paginator", None) is not None:
            self._page_ensure_word_visible(best)
        qwm = self._qt_word_map
        if best < len(qwm) and qwm[best] >= 0:
            cursor = QTextCursor(self.editor.document())
            cursor.setPosition(qwm[best])
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()
        self.statusBar().showMessage(f"Resumed at {pct}%  (saved {ts})", 5000)
