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

    def _find_dyslexia_font(self) -> str:
        """Return the first installed dyslexia-friendly family, or "".

        QFontDatabase.families() is a static method in PyQt6 but an
        instance method in PyQt5, so both call styles are attempted.
        """
        try:
            fams = QFontDatabase.families()  # PyQt6 (static)
        except TypeError:
            fams = QFontDatabase().families()  # PyQt5 (instance)
        except Exception:
            return ""
        available = {str(f).lower() for f in fams}
        for cand in self._DYSLEXIA_FONTS:
            if cand.lower() in available:
                return cand
        return ""

    def _effective_font_family(self) -> str:
        """The display family, honoring the dyslexia-font preference.

        When 'qt_dyslexia_font' is on and a dyslexia-friendly family is
        installed it wins; otherwise the user's chosen family is used.
        """
        if self.settings.get("qt_dyslexia_font", False):
            fam = self._find_dyslexia_font()
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

