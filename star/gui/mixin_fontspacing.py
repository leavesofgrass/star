"""FontSpacingMixin — methods extracted from StarWindow (main_window.py).

Mixed into StarWindow via ``class StarWindow(FontSpacingMixin, ...)``; operates
on StarWindow instance state and other methods via ``self``, holding no
state of its own.  IMPORT SAFETY: references Qt at module scope — imported
lazily by main_window.py (itself imported by runner.py after the _QT guard).
"""
from .._runtime import *  # noqa: F401,F403
from ._qtcompat import _DOC_SELECTION, _PCT_SPACING, _PROPORTIONAL, _SINGLE_UNDERLINE, _WAVE_UNDERLINE


class FontSpacingMixin:
    # ── Reading accessibility: fonts, spacing & reading aids ──────────

    # Candidate dyslexia-friendly families, in order of preference.
    # OpenDyslexic is purpose-built; the others are widely available
    # fallbacks with the high legibility traits dyslexic readers benefit
    # from (open apertures, distinct letterforms, generous spacing).
    _DYSLEXIA_FONTS = (
        "OpenDyslexic",
        "OpenDyslexic3",
        "OpenDyslexicAlta",
        "Atkinson Hyperlegible",
        "Lexend",
        "Lexend Deca",
        "Comic Sans MS",
        "Comic Neue",
    )

    # Reading-font chooser keys → the QFont family each provides.  "default"
    # means "no override" (the user's chosen family / theme font wins).  Kept in
    # sync with star.fonts.FONTS; the dyslexia toggle maps onto "opendyslexic".
    _READING_FONTS = {
        "default": "",
        "opendyslexic": "OpenDyslexic",
        "atkinson": "Atkinson Hyperlegible",
        "lexend": "Lexend",
    }

    def _register_dyslexia_font(self, paths=None) -> None:
        """Register any fetched reading-font files with Qt (idempotent).

        Makes the on-demand-fetched fonts (OpenDyslexic / Atkinson Hyperlegible /
        Lexend, ``.otf`` and ``.ttf``) visible to QFontDatabase.families()
        without a system-wide install, so the family lookups pick them up."""
        from .. import fonts as _fontmod

        try:
            paths = _fontmod.fetched_paths() if paths is None else paths
            for p in paths:
                QFontDatabase.addApplicationFont(str(p))
        except Exception:
            pass  # best-effort; falls back to system fonts / the chosen family

    def _reading_font_key(self) -> str:
        """The active reading-font chooser key, honoring the legacy toggle.

        The pre-0.1.21 ``qt_dyslexia_font`` boolean is treated as an alias for
        selecting OpenDyslexic, so the old Dyslexia-Friendly Font accelerator and
        any saved profiles keep working alongside the new chooser."""
        key = str(self.settings.get("qt_reading_font", "default"))
        if key not in self._READING_FONTS:
            key = "default"
        if key == "default" and self.settings.get("qt_dyslexia_font", False):
            return "opendyslexic"
        return key

    def _maybe_prefetch_dyslexia_font(self) -> None:
        """Download OpenDyslexic in the background if it isn't available yet.

        Runs like the other optional dependencies: best-effort, off the GUI
        thread, honoring the auto_install setting and STAR_NO_AUTOINSTALL. When
        the download finishes, _font_ready_signal fires _on_dyslexia_font_ready on
        the GUI thread to register + (re)apply. A no-op when the font is already
        fetched, already installed, or auto-install is disabled."""
        import os
        import threading

        from .. import fonts as _fontmod

        if os.environ.get("STAR_NO_AUTOINSTALL") or not self.settings.get(
            "auto_install", True
        ):
            return
        # Prefetch whichever reading font is currently selected (OpenDyslexic by
        # default so the classic behavior is unchanged); a no-op once it's on
        # disk or a matching system family is already installed.
        key = self._reading_font_key()
        font_key = key if key in _fontmod.FONTS else "opendyslexic"
        if _fontmod.is_font_fetched(font_key) or self._find_dyslexia_font():
            return

        def _work() -> None:
            try:
                _fontmod.fetch_font(font_key)
            except Exception:
                return
            try:
                self._font_ready_signal.emit()   # register/apply on the GUI thread
            except Exception:
                pass

        threading.Thread(target=_work, name="star-font-fetch", daemon=True).start()

    def _on_dyslexia_font_ready(self) -> None:
        """GUI-thread slot: register the freshly-fetched reading font and, if a
        reading font is selected, apply it across the UI now that it's available."""
        self._register_dyslexia_font()
        self._dyslexia_registered = True
        if self._reading_font_key() != "default":
            self._apply_dyslexia_font(True, fetch=False)
        else:
            self.statusBar().showMessage("Reading font ready", 4000)

    def _available_families(self) -> "set[str]":
        """Lower-cased set of every family Qt can resolve, or empty on failure.

        Registers any fetched reading fonts first so they're visible.
        QFontDatabase.families() is static in PyQt6 but an instance method in
        PyQt5, so both call styles are attempted."""
        if not getattr(self, "_dyslexia_registered", False):
            self._register_dyslexia_font()
            self._dyslexia_registered = True
        try:
            fams = QFontDatabase.families()  # PyQt6 (static)
        except TypeError:
            fams = QFontDatabase().families()  # PyQt5 (instance)
        except Exception:
            return set()
        return {str(f).lower() for f in fams}

    def _find_dyslexia_font(self, prefer: str = "") -> str:
        """Return an available reading-aid family, or "".

        When *prefer* (a family name) is installed/fetched it wins; otherwise the
        first available family from _DYSLEXIA_FONTS is used (preserving the
        original OpenDyslexic-first fallback order).
        """
        available = self._available_families()
        if not available:
            return ""
        if prefer and prefer.lower() in available:
            return prefer
        for cand in self._DYSLEXIA_FONTS:
            if cand.lower() in available:
                return cand
        return ""

    def _apply_dyslexia_font(self, on: bool, *, fetch: bool = True) -> str:
        """Apply (or remove) the selected reading font across the WHOLE UI.

        When *on*, resolves the chosen reading font (OpenDyslexic / Atkinson
        Hyperlegible / Lexend, honoring the legacy dyslexia toggle); if it isn't
        installed and *fetch* is true, downloads it on demand from GitHub
        (best-effort, no pip). The family is applied to the QApplication (menus,
        toolbar, dialogs, docks, labels) as well as the document editor, then the
        view is re-rendered.  Returns the family applied (\"\" if none / when
        turning off)."""
        app = QApplication.instance()
        if not on:
            if app is not None:
                # Restore the captured default font. A default-constructed QFont()
                # has no resolve mask and would NOT revert widgets (menus, docks)
                # already resolved to the reading font, so restore the snapshot.
                default = getattr(self, "_default_app_font", None)
                app.setFont(default if default is not None else QFont())
            self.editor.setFont(self._make_editor_font())
            self._apply_qt_theme(str(self.settings.get("theme", "dark")))
            return ""
        from .. import fonts as _fontmod

        key = self._reading_font_key()
        prefer = self._READING_FONTS.get(key, "")
        fam = self._find_dyslexia_font(prefer)
        # Fetch the specific selected family (not just OpenDyslexic) if it isn't
        # available yet and we're allowed to.
        if (not fam or (prefer and fam != prefer)) and fetch:
            font_key = key if key in _fontmod.FONTS else "opendyslexic"
            paths = _fontmod.fetch_font(font_key)
            if paths:
                self._register_dyslexia_font(paths)
                fam = self._find_dyslexia_font(prefer)
        if fam and app is not None:
            base = int(self.settings.get("qt_font_size", 14)) or 14
            app.setFont(QFont(fam, base))     # chrome: menus, toolbar, dialogs, labels
        # The editor family flows from _effective_font_family (honors the setting).
        self.editor.setFont(self._make_editor_font())
        self._apply_qt_theme(str(self.settings.get("theme", "dark")))
        return fam

    def _effective_font_family(self) -> str:
        """The display family, honoring the reading-font preference.

        When a reading font is selected (via the chooser or the legacy dyslexia
        toggle) and an appropriate family is installed/fetched it wins; otherwise
        the user's chosen family is used.
        """
        key = self._reading_font_key()
        if key != "default":
            fam = self._find_dyslexia_font(self._READING_FONTS.get(key, ""))
            if fam:
                return fam
        return str(self.settings.get("qt_font_family", "Georgia"))

    def _make_editor_font(self) -> "QFont":
        """Construct the editor's base QFont from family, size, and the
        letter/word-spacing accessibility settings.

        Letter and word spacing are applied through QFont (Qt's rich-text
        CSS subset does not support letter-spacing/word-spacing), while
        line height is applied separately via _apply_block_spacing.
        """
        fam = self._effective_font_family()
        size = int(self.settings.get("font_size", 0)) or int(
            self.settings.get("qt_font_size", 14)
        )
        f = QFont(fam, max(6, size))
        ls = float(self.settings.get("qt_letter_spacing", 0.0))
        # PercentageSpacing: 100 == normal; we store *extra* percent.
        f.setLetterSpacing(_PCT_SPACING, 100.0 + ls)
        ws = float(self.settings.get("qt_word_spacing", 0.0))
        f.setWordSpacing(ws)
        return f

    def _apply_block_spacing(self) -> None:
        """Apply the line-height multiplier to every block in the document.

        Run after each setHtml() because block formats are per-document
        and are reset whenever the HTML is replaced.
        """
        try:
            mult = float(self.settings.get("qt_line_height", 1.5))
        except (TypeError, ValueError):
            mult = 1.5
        pct = max(100.0, mult * 100.0)
        cur = QTextCursor(self.editor.document())
        cur.select(_DOC_SELECTION)
        bf = QTextBlockFormat()
        # setLineHeight's second arg is an int height-type.  PyQt5 enums
        # are plain ints; PyQt6 enums expose the int via .value.
        ht = getattr(_PROPORTIONAL, "value", _PROPORTIONAL)
        bf.setLineHeight(pct, int(ht))
        cur.mergeBlockFormat(bf)

    def _apply_text_spacing(self) -> None:
        """Re-apply font (letter/word spacing) and block (line-height)
        spacing to the live document, then refresh."""
        self.editor.setFont(self._make_editor_font())
        self._apply_block_spacing()

    def _bionic_word(self, m: "re.Match") -> str:
        """Embolden the leading ~40% of a single word for bionic reading."""
        w = m.group(0)
        if len(w) <= 1:
            return f"<b>{w}</b>"
        n = max(1, round(len(w) * 0.4))
        return f"<b>{w[:n]}</b>{w[n:]}"

    def _bionic_html(self, html: str) -> str:
        """Apply bionic-reading emphasis to the text runs of an HTML body.

        Splits on tags and HTML entities so markup and entities are left
        intact; text inside <code> spans is skipped (code stays verbatim).
        """
        parts = re.split(r"(<[^>]+>|&[a-zA-Z]+;|&#\d+;)", html)
        in_code = False
        out: List[str] = []
        word_re = re.compile(r"[^\W\d_]{2,}", re.UNICODE)
        for p in parts:
            if not p:
                continue
            if p.startswith("<"):
                low = p.lower()
                if low.startswith("<code"):
                    in_code = True
                elif low.startswith("</code"):
                    in_code = False
                out.append(p)
            elif p.startswith("&"):
                out.append(p)  # HTML entity — leave untouched
            elif in_code:
                out.append(p)
            else:
                out.append(word_re.sub(self._bionic_word, p))
        return "".join(out)

    def _rebuild_hl_fmt(self) -> None:
        """Rebuild the spoken-word highlight format from the user's
        'highlight_style' and 'highlight_color' settings.

        Styles: background (filled), underline, box (wavy underline),
        bold (colored bold text), color (colored text).
        """
        style = str(self.settings.get("highlight_style", "background"))
        color = QColor(str(self.settings.get("highlight_color", "cyan")))
        if not color.isValid():
            color = QColor("#06b6d4")  # cyan-500 fallback
        fmt = QTextCharFormat()
        if style == "underline":
            fmt.setFontUnderline(True)
            fmt.setUnderlineColor(color)
            fmt.setUnderlineStyle(_SINGLE_UNDERLINE)
            fmt.setFontWeight(700)
        elif style == "box":
            fmt.setUnderlineColor(color)
            fmt.setUnderlineStyle(_WAVE_UNDERLINE)
            fmt.setFontWeight(700)
        elif style == "bold":
            fmt.setForeground(color)
            fmt.setFontWeight(900)
        elif style == "color":
            fmt.setForeground(color)
            fmt.setFontWeight(700)
        else:  # "background" (default)
            fmt.setBackground(color)
            # Pick a readable foreground based on the fill's luminance.
            lum = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
            fmt.setForeground(QColor("#000000" if lum > 140 else "#ffffff"))
            fmt.setFontWeight(700)
        self._hl_fmt = fmt

