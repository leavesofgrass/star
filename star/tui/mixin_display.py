"""Theme, table-reading, and footnote display modes.

Methods of StarApp, split out of the former monolithic star/tui.py.
Mixed into StarApp in app.py; calls other groups via ``self``.
"""
from .._runtime import *  # noqa: F401,F403
from .theming import THEMES, THEME_NAMES


class DisplayMixin:

    # ── Footnote mode toggle ──────────────────

    def _set_footnote_mode(self, mode: str) -> None:
        "Set footnote reading mode (inline | deferred | skip) and reload."
        mode = (mode or "").strip().lower()
        if not mode:
            cur = self.settings.get("footnote_mode", "inline")
            self.notify(
                f"Footnote mode: {cur}  —  options: inline  deferred  skip",
                dur=5.0,
            )
            return
        if mode not in ("inline", "deferred", "skip"):
            self.notify(
                f"Unknown footnote mode {mode!r}.  Use: inline, deferred, or skip.",
                error=True,
            )
            return
        self.settings.set("footnote_mode", mode)
        self.notify(f"Footnote mode: {mode}  (reloading document)")
        if self.doc and self.doc.path:
            self._open_async(self.doc.path)

    # ── Table mode helper ─────────────────────────────────────────────────

    def _set_table_mode(self, mode: str) -> None:
        """Set table reading mode.  Valid values: structured | flat | skip.
        Reloads the document so the change takes effect immediately.
        """
        mode = (mode or "").strip().lower()
        if not mode:
            cur = self.settings.get("table_reading_mode", "structured")
            self.notify(
                f"Table mode: {cur}  \u2014  options: structured  flat  skip",
                dur=5.0,
            )
            return
        if mode not in ("structured", "flat", "skip"):
            self.notify(
                f"Unknown table mode {mode!r}.  Use: structured, flat, or skip.",
                error=True,
            )
            return
        self.settings.set("table_reading_mode", mode)
        self.notify(f"Table reading mode: {mode}  (reloading document)")
        if self.doc and self.doc.path:
            self._open_async(self.doc.path)  # reload with new mode baked in

    # ── Theme ─────────────────────────────────────────────────────────────

    def _next_theme(self) -> None:
        idx = (
            THEME_NAMES.index(self.theme_name) if self.theme_name in THEME_NAMES else 0
        )
        self.theme_name = THEME_NAMES[(idx + 1) % len(THEME_NAMES)]
        self.settings["theme"] = self.theme_name
        self._init_colors()
        self.notify(f"Theme: {self.theme_name}")

    def _set_theme(self, name: str) -> None:
        if name in THEMES:
            self.theme_name = name
            self.settings["theme"] = name
            self._init_colors()
            self.notify(f"Theme: {name}")
        else:
            self.notify(
                f"Unknown theme '{name}'.  Available: {', '.join(THEME_NAMES)}",
                error=True,
            )
