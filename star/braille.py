"""Built-in Grade 1 BRF translation and Braille export."""
from ._runtime import *  # noqa: F401,F403


# North American Braille ASCII (a.k.a. NABCC / Braille-ASCII) lookup, indexed
# by the 6-dot cell value (bit0=dot1, bit1=dot2 … bit5=dot6).  Each braille
# cell maps to exactly one ASCII byte; this is the character set BRF embossers
# expect.  This table is the canonical Unicode-braille (U+2800..U+283F) order.
_BRAILLE_ASCII = " A1B'K2L@CIF/MSP\"E3H9O6R^DJG>NTQ,*5<-U8V.%[$+X!&;:4\\0Z7(_?W]#Y)="

# Print character -> braille dot-cell value, for uncontracted (Grade 1) English.
_BRL_LETTER = {
    chr(ord("a") + i): v
    for i, v in enumerate(
        # a  b  c   d   e   f   g   h   i   j   k  l  m   n   o   p   q   r   s
        [
            1,
            3,
            9,
            25,
            17,
            11,
            27,
            19,
            10,
            26,
            5,
            7,
            13,
            29,
            21,
            15,
            31,
            23,
            14,
            # t   u   v   w   x   y   z
            30,
            37,
            39,
            58,
            45,
            61,
            53,
        ]
    )
}
_BRL_DIGIT = {
    "1": 1,
    "2": 3,
    "3": 9,
    "4": 25,
    "5": 17,
    "6": 11,
    "7": 27,
    "8": 19,
    "9": 10,
    "0": 26,
}
_BRL_PUNCT = {
    ".": 50,
    ",": 2,
    ";": 6,
    ":": 18,
    "?": 38,
    "!": 22,
    "'": 4,
    "-": 36,
    "(": 54,
    ")": 54,
    "/": 12,
    '"': 38,
}
_BRL_NUMBER_SIGN = 60  # dots 3-4-5-6
_BRL_CAPITAL_SIGN = 32  # dot 6
_BRL_LETTER_SIGN = 48  # dots 5-6 — grade-1 indicator terminating number mode


def _text_to_braille_grade1(text: str) -> str:
    """Translate plain text to uncontracted (Grade 1) Braille-ASCII.

    Pure-Python, dependency-free, and incapable of crashing the process — the
    reliable default for BRF export.  Handles letters, digits (with number
    sign), capital signs, common punctuation, and whitespace.  Unknown
    characters are dropped so the output stays valid Braille-ASCII.
    """
    import unicodedata

    out: List[str] = []
    in_number = False
    for ch in text:
        if ch == "\n":
            out.append("\n")
            in_number = False
            continue
        if ch == "\t" or ch == " ":
            out.append(" ")
            in_number = False
            continue
        if ch.lower() not in _BRL_LETTER and ch not in _BRL_DIGIT and ch not in _BRL_PUNCT:
            # Fold accented Latin letters to their base letter instead of
            # silently dropping them ("café" embossed as "caf").
            folded = "".join(
                c
                for c in unicodedata.normalize("NFKD", ch)
                if unicodedata.category(c) != "Mn"
            )
            if len(folded) == 1 and folded.lower() in _BRL_LETTER:
                ch = folded
        low = ch.lower()
        if low in _BRL_LETTER:
            # A letter a-j immediately after a number shares its cell with the
            # digit 1-0, so it MUST be preceded by the letter sign (dots 5-6)
            # — without it "3a" embosses as "31", silent content corruption.
            # (Letters k-z use cells outside the digit range; UEB still calls
            # for the terminator on a-j, which is the ambiguous set.)
            if in_number and low in "abcdefghij":
                out.append(_BRAILLE_ASCII[_BRL_LETTER_SIGN])
            if ch.isupper():
                out.append(_BRAILLE_ASCII[_BRL_CAPITAL_SIGN])
            in_number = False
            out.append(_BRAILLE_ASCII[_BRL_LETTER[low]])
        elif ch in _BRL_DIGIT:
            if not in_number:
                out.append(_BRAILLE_ASCII[_BRL_NUMBER_SIGN])
                in_number = True
            out.append(_BRAILLE_ASCII[_BRL_DIGIT[ch]])
        elif ch in _BRL_PUNCT:
            in_number = False
            out.append(_BRAILLE_ASCII[_BRL_PUNCT[ch]])
        # else: unsupported glyph -> skip (keeps output valid Braille-ASCII)
    return "".join(out)


def _format_brf(braille: str, cells: int = 40, lines_per_page: int = 25) -> str:
    """Wrap a Braille-ASCII string into standard BRF page geometry.

    Word-wraps at *cells* columns (default 40), groups output into pages of
    *lines_per_page* lines separated by a form feed, and uses CRLF line
    endings as embossers expect.
    """
    lines: List[str] = []
    for para in braille.split("\n"):
        if not para:
            lines.append("")
            continue
        cur = ""
        for word in para.split(" "):
            if not cur:
                cur = word
            elif len(cur) + 1 + len(word) <= cells:
                cur += " " + word
            else:
                lines.append(cur)
                cur = word
            # A single word longer than a line: hard-split it.
            while len(cur) > cells:
                lines.append(cur[:cells])
                cur = cur[cells:]
        lines.append(cur)
    # Paginate.
    pages: List[str] = []
    for i in range(0, len(lines), lines_per_page):
        pages.append("\r\n".join(lines[i : i + lines_per_page]))
    return "\f".join(pages) + "\r\n"


def _export_braille(
    text: str, table: str = "en-ueb-g2.ctb", use_liblouis: bool = False
) -> str:
    """Convert text to BRF (Braille Ready Format).

    By default this uses the built-in pure-Python Grade 1 translator, which is
    always available and can never crash the host process.  This fixes the
    long-standing bug where a missing liblouis translation table caused
    liblouis to call ``exit()`` at the C level, abruptly closing the window.

    Set *use_liblouis* (``braille_grade2`` setting) to opt in to contracted
    Grade 2 translation via liblouis when it is installed and the requested
    table resolves; any failure falls back to the built-in translator.
    """
    if use_liblouis and _LOUIS:
        try:
            # With the bundled liblouis, resolve the table to its absolute
            # path (the bundled engine does not honor a search path env var
            # the way a system install does).
            bundled = _LIBLOUIS_TABLES / table
            tbl = str(bundled) if bundled.is_file() else table
            brl = _louis.translateString([tbl], text, None, 0)
            if brl:
                return _format_brf(brl)
        except Exception:
            pass  # fall through to the dependency-free translator
    return _format_brf(_text_to_braille_grade1(text))
