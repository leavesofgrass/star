"""Text preprocessing for TTS: SSML/DECtalk markup, abbreviation and
pronunciation expansion, number/date normalization, table narration."""
from ._runtime import *  # noqa: F401,F403


def _strip_markdown_for_tts(
    md: str,
    skip_code: bool = True,
    table_mode: str = "structured",
) -> str:
    """Remove markdown syntax to produce clean text suitable for TTS.
    The result should sound natural when read aloud — no asterisks, slashes,
    pound signs, pipe characters, or code fences.

    table_mode is forwarded to _tables_to_narration() and controls how tables
    are rendered for speech (structured / flat / skip).
    """
    text = md

    # Remove fenced code blocks entirely if requested
    if skip_code:
        text = re.sub(r"```[\s\S]*?```", "", text)
        text = re.sub(r"~~~[\s\S]*?~~~", "", text)
        text = re.sub(r"^    .+$", "", text, flags=re.MULTILINE)  # indented code
    else:
        text = re.sub(r"```\w*\n?", "", text)
        text = re.sub(r"```", "", text)

    # Headings — keep text, drop pounds
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Horizontal rules
    text = re.sub(r"^(\*{3,}|-{3,}|_{3,})\s*$", "", text, flags=re.MULTILINE)

    # Links: keep display text
    text = re.sub(r"!\[([^\]]*)\]\([^\)]*\)", r"\1", text)  # images
    text = re.sub(r"\[([^\]]*)\]\([^\)]*\)", r"\1", text)  # links

    # Inline code
    text = re.sub(r"`+(.+?)`+", r"\1", text)

    # Bold / italic
    text = re.sub(r"\*{3}(.+?)\*{3}", r"\1", text)
    text = re.sub(r"_{3}(.+?)_{3}", r"\1", text)
    text = re.sub(r"\*{2}(.+?)\*{2}", r"\1", text)
    text = re.sub(r"_{2}(.+?)_{2}", r"\1", text)
    text = re.sub(r"\*([^*\n]+?)\*", r"\1", text)
    text = re.sub(r"_([^_\n]+?)_", r"\1", text)

    # Blockquotes
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)

    # List markers
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+[.)]\s+", "", text, flags=re.MULTILINE)

    # Table narration — must run before pipes are stripped.
    # _tables_to_narration() is defined later in the file; it operates on the
    # still-raw markdown lines and replaces table blocks with spoken prose.
    text = _tables_to_narration(text, mode=table_mode)

    # Collapse extra blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# =============================================================================
# SSML / prosody helpers
# =============================================================================


def _text_to_ssml(
    text: str,
    backend: str = "pyttsx3",
    sentence_ms: int = 350,
    clause_ms: int = 150,
) -> str:
    """Wrap *text* in SSML markup, inserting pauses at sentence and clause
    boundaries for more natural-sounding speech.

    The output is always wrapped in ``<speak>…</speak>`` tags:

    * eSpeak-NG accepts this directly with its ``-m`` flag.
    * SAPI5 (Windows / pyttsx3) interprets it natively.
    * DECtalk receives its own notation via ``_text_to_dectalk()`` instead.

    If *text* is already SSML (starts with ``<speak>``) it is returned
    unchanged to avoid double-wrapping.
    """
    if text.lstrip().startswith("<speak>"):
        return text  # already wrapped
    if backend == "dectalk":
        return _text_to_dectalk(text, sentence_ms, clause_ms)

    # Escape XML-reserved characters before inserting any tags.
    s = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

    long_ms = sentence_ms * 2

    # Paragraph breaks → long pause
    s = re.sub(r"\n{2,}", f'<break time="{long_ms}ms"/>\n', s)
    # Sentence-ending punctuation → medium pause
    s = re.sub(
        r"([.!?\u2026])(\s+)",
        lambda m: f'{m.group(1)}<break time="{sentence_ms}ms"/>{m.group(2)}',
        s,
    )
    # Clause punctuation (comma, semicolon, colon) → short pause
    s = re.sub(
        r"([,;:])(\s+)",
        lambda m: f'{m.group(1)}<break time="{clause_ms}ms"/>{m.group(2)}',
        s,
    )
    # Em-dash / en-dash → brief pause
    s = re.sub(
        r"[\u2014\u2013]",
        f' <break time="{clause_ms}ms"/> ',
        s,
    )

    return f"<speak>{s}</speak>"


def _text_to_dectalk(
    text: str,
    sentence_ms: int = 350,
    clause_ms: int = 150,
) -> str:
    """Convert plain text to DECtalk phoneme notation for improved prosody.

    DECtalk uses ``[:pau N]`` to insert N milliseconds of silence.
    """
    s = text
    s = re.sub(
        r"([.!?\u2026])(\s+)",
        lambda m: f"{m.group(1)} [:pau {sentence_ms}] ",
        s,
    )
    s = re.sub(
        r"([,;:])(\s+)",
        lambda m: f"{m.group(1)} [:pau {clause_ms}] ",
        s,
    )
    s = re.sub(r"[\u2014\u2013]", f" [:pau {clause_ms}] ", s)
    return s


# =============================================================================
# TTS text preprocessing
# =============================================================================
# Pipeline (applied at speak-time after the plain-text slice is taken):
#   _expand_abbreviations()  ->  _normalize_numbers()  ->  _text_to_ssml()
#
# Table narration mode is baked in at document-load time inside
# _strip_markdown_for_tts() so the word map reflects the spoken structure.
# =============================================================================

# -- Abbreviation table -------------------------------------------------------
# Ordered longest-first so multi-word entries match before their components.

_ABBREV_PAIRS: List[tuple] = [
    # Multi-word Latin phrases
    ("et al.", "and others"),
    ("op. cit.", "op cit"),
    # Single-token Latin / English abbreviations
    ("e.g.,", "for example,"),  # trailing-comma variant must come first
    ("e.g.", "for example"),
    ("i.e.,", "that is,"),
    ("i.e.", "that is"),
    ("etc.", "et cetera"),
    ("cf.", "compare"),
    ("ibid.", "ibid"),
    ("n.d.", "no date"),
    ("ca.", "circa"),
    ("vs.", "versus"),
    ("approx.", "approximately"),
    # Academic / publishing
    ("Fig.", "Figure"),
    ("Figs.", "Figures"),
    ("Eq.", "Equation"),
    ("Eqs.", "Equations"),
    ("Sec.", "Section"),
    ("Chap.", "Chapter"),
    ("Ref.", "Reference"),
    ("Refs.", "References"),
    ("Vol.", "Volume"),
    ("vol.", "volume"),
    ("No.", "Number"),
    ("no.", "number"),
    ("pp.", "pages"),
    ("p.", "page"),
    ("ed.", "edition"),
    ("eds.", "editors"),
    ("Dept.", "Department"),
    ("dept.", "department"),
    ("Assoc.", "Association"),
    ("Univ.", "University"),
    ("univ.", "university"),
    # Titles / honorifics
    ("Dr.", "Doctor"),
    ("Mr.", "Mister"),
    ("Mrs.", "Missus"),
    ("Prof.", "Professor"),
    ("Jr.", "Junior"),
    ("Sr.", "Senior"),
    ("Rev.", "Reverend"),
    ("Gen.", "General"),
    ("Gov.", "Governor"),
    # Units / measurement
    ("hr.", "hour"),
    ("min.", "minutes"),
    ("sec.", "seconds"),
    ("wt.", "weight"),
    ("avg.", "average"),
    ("temp.", "temperature"),
    ("conc.", "concentration"),
    ("est.", "estimated"),
    ("max.", "maximum"),
    # Business / organizations
    ("Inc.", "Incorporated"),
    ("Corp.", "Corporation"),
    ("Ltd.", "Limited"),
]

# Compiled once: word-boundary anchor before each abbreviation token.
# We do NOT add \b after the token because abbreviations end with '.', which is
# not a word-boundary character.
_ABBREV_RE: List[tuple] = [
    (re.compile(r"\b" + re.escape(abbr)), expansion)
    for abbr, expansion in _ABBREV_PAIRS
]


def _expand_abbreviations(text: str, custom: Optional[Dict[str, str]] = None) -> str:
    """Expand common and user-defined abbreviations for natural TTS output.

    Custom expansions (from settings["abbrev_expansions"]) are applied first
    so they take precedence over the built-in list.
    """
    if custom:
        for abbr, exp in sorted(custom.items(), key=lambda x: -len(x[0])):
            text = re.sub(r"\b" + re.escape(abbr), exp, text)
    for pattern, expansion in _ABBREV_RE:
        text = pattern.sub(expansion, text)
    return text


def _apply_pronunciations(text: str, lexicon: Dict[str, str]) -> str:
    """Replace each lexicon *term* with its user-defined spoken form.

    Matching is case-insensitive and whole-word; longer terms are applied
    first so multi-word entries win over their constituent words.  The
    replacement is inserted literally (no regex backreference surprises).
    This lets domain vocabulary — drug names, anatomy, acronyms — be spoken
    correctly and consistently regardless of the TTS engine.
    """
    if not lexicon:
        return text
    for term in sorted(lexicon, key=lambda t: -len(t)):
        spoken = lexicon[term]
        if not term:
            continue
        # Use word boundaries when the term starts/ends with a word char so
        # "CHF" matches the standalone token, not letters inside other words.
        left = r"\b" if term[:1].isalnum() else ""
        right = r"\b" if term[-1:].isalnum() else ""
        try:
            text = re.sub(
                left + re.escape(term) + right,
                lambda _m, s=spoken: s,
                text,
                flags=re.IGNORECASE,
            )
        except re.error:
            continue
    return text


# -- Number normalization helpers --------------------------------------------

_ONES = [
    "",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = [
    "",
    "",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
]

_MONTHS_NUM: Dict[str, str] = {
    "01": "January",
    "02": "February",
    "03": "March",
    "04": "April",
    "05": "May",
    "06": "June",
    "07": "July",
    "08": "August",
    "09": "September",
    "10": "October",
    "11": "November",
    "12": "December",
}


def _int_to_words(n: int) -> str:
    """Convert a non-negative integer to English words."""
    if n == 0:
        return "zero"
    if n < 0:
        return "negative " + _int_to_words(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        t, o = divmod(n, 10)
        return _TENS[t] + ("-" + _ONES[o] if o else "")
    if n < 1000:
        h, r = divmod(n, 100)
        return _ONES[h] + " hundred" + (" " + _int_to_words(r) if r else "")
    for exp, label in [
        (12, "trillion"),
        (9, "billion"),
        (6, "million"),
        (3, "thousand"),
    ]:
        base = 10**exp
        if n >= base:
            q, r = divmod(n, base)
            return (
                _int_to_words(q) + " " + label + (" " + _int_to_words(r) if r else "")
            )
    return str(n)


def _year_to_words(year: int) -> str:
    """Read a 4-digit year naturally.

    1984 -> nineteen eighty-four   2024 -> twenty twenty-four
    1900 -> nineteen hundred       2000 -> two thousand
    """
    if not (100 <= year <= 2999):
        return _int_to_words(year)
    century, decade = divmod(year, 100)
    if decade == 0:
        return _int_to_words(century) + " hundred"
    if decade < 10:
        return _int_to_words(century) + " oh " + _int_to_words(decade)
    return _int_to_words(century) + " " + _int_to_words(decade)


def _ordinal_to_words(n: int) -> str:
    """Convert a positive integer to its ordinal word form.

    1 -> first   21 -> twenty-first   100 -> one hundredth
    Compound ordinals are built by recurring on the last component so that
    21 -> twenty-first (not twenty-onth), 23 -> twenty-third, etc.
    """
    specials = {
        1: "first",
        2: "second",
        3: "third",
        4: "fourth",
        5: "fifth",
        6: "sixth",
        7: "seventh",
        8: "eighth",
        9: "ninth",
        10: "tenth",
        11: "eleventh",
        12: "twelfth",
    }
    if n in specials:
        return specials[n]
    if n < 0:
        return "negative " + _ordinal_to_words(-n)
    # Teens 13-19: thirteenth, fourteenth, …, nineteenth
    if 13 <= n <= 19:
        return _int_to_words(n) + "th"
    # Compound: 21-99 with a non-zero ones digit -> apply ordinal only to ones
    if 20 <= n < 100:
        tens, ones = divmod(n, 10)
        if ones != 0:
            return _int_to_words(tens * 10) + "-" + _ordinal_to_words(ones)
        # Round tens (20, 30, …): twenty -> twentieth
        w = _int_to_words(n)
        return w[:-1] + "ieth"
    # Hundreds: apply ordinal to the remainder if non-zero
    if n < 1_000:
        hundreds, rest = divmod(n, 100)
        if rest != 0:
            return _int_to_words(hundreds * 100) + " " + _ordinal_to_words(rest)
        return _int_to_words(n) + "th"  # e.g. 'one hundredth'
    # Larger numbers: apply ordinal to the remainder, or just append 'th'
    for exp, label in [
        (12, "trillion"),
        (9, "billion"),
        (6, "million"),
        (3, "thousand"),
    ]:
        base = 10**exp
        if n >= base:
            q, r = divmod(n, base)
            if r != 0:
                return _int_to_words(q) + " " + label + " " + _ordinal_to_words(r)
            return _int_to_words(q) + " " + label + "th"
    return _int_to_words(n) + "th"


def _decimal_digits_to_words(digits: str) -> str:
    """Read decimal digits one at a time: "14" -> "one four"."""
    return " ".join(_ONES[int(d)] if d != "0" else "zero" for d in digits)


def _normalize_numbers(text: str) -> str:
    """Expand common numeric patterns to spoken English.

    Processed in specificity order:
      ISO dates     YYYY-MM-DD
      US dates      MM/DD/YYYY
      Times         HH:MM or HH:MM:SS (24-hour converted to 12-hour + AM/PM)
      Currency      dollar sign, pound sign, euro sign
      Percentages   N% or N.N%
      Ordinals      1st 2nd 3rd 4th ...
      Comma integers  1,234,567
      Decimals      N.N
      Plain integers >= 1000 (4-digit treated as years 1000-2099)
    """

    # -- ISO date  YYYY-MM-DD -------------------------------------------------
    def _iso_date(m: re.Match) -> str:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        return f"{_MONTHS_NUM.get(mo, mo)} {_ordinal_to_words(int(d))}, {_year_to_words(int(y))}"

    text = re.sub(r"\b(\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b", _iso_date, text)

    # -- US date  MM/DD/YYYY --------------------------------------------------
    def _us_date(m: re.Match) -> str:
        mo, d, y = m.group(1), m.group(2), m.group(3)
        return f"{_MONTHS_NUM.get(mo.zfill(2), mo)} {_ordinal_to_words(int(d))}, {_year_to_words(int(y))}"

    text = re.sub(
        r"\b(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])/(\d{4})\b", _us_date, text
    )

    # -- Times  HH:MM  (optional explicit AM/PM consumed to avoid duplication) ---
    def _time_val(m: re.Match) -> str:
        h, mi = int(m.group(1)), int(m.group(2))
        explicit = (m.group(3) or "").strip().upper()  # "AM", "PM", or ""
        if h == 0 and mi == 0 and not explicit:
            return "midnight"
        if h == 12 and mi == 0 and not explicit:
            return "noon"
        if explicit == "PM" and h < 12:
            h12 = h  # 3:45 PM -> keep h=3
            period = "PM"
        elif explicit == "AM":
            h12 = h % 12 or 12
            period = "AM"
        else:
            period = "AM" if h < 12 else "PM"
            h12 = h if h <= 12 else h - 12
        if mi == 0:
            return f"{_int_to_words(h12)} {period}"
        return f"{_int_to_words(h12)} {_int_to_words(mi)} {period}"

    text = re.sub(
        r"\b([01]?\d|2[0-3]):([0-5]\d)(?::\d\d)?\s*([AaPp][Mm])?", _time_val, text
    )

    # -- Currency  $  £  € ----------------------------------------------------
    _CURR: Dict[str, tuple] = {
        "$": ("dollar", "cent"),
        "\u00a3": ("pound", "penny"),
        "\u20ac": ("euro", "cent"),
    }

    def _currency_val(m: re.Match) -> str:
        sym = m.group(1)
        whole = m.group(2).replace(",", "")
        frac = (m.group(3) or "00")[:2].ljust(2, "0")
        major, minor = _CURR.get(sym, ("dollar", "cent"))
        parts: List[str] = []
        wi = int(whole)
        if wi:
            parts.append(f"{_int_to_words(wi)} {major}{'s' if wi != 1 else ''}")
        fi = int(frac)
        if fi:
            parts.append(f"{_int_to_words(fi)} {minor}{'s' if fi != 1 else ''}")
        return " and ".join(parts) if parts else f"zero {major}s"

    text = re.sub(r"([$\u00a3\u20ac])(\d[\d,]*)\.?(\d{2})?", _currency_val, text)

    # -- Percentages  75%  3.5% -----------------------------------------------
    def _pct(m: re.Match) -> str:
        num = m.group(1)
        if "." in num:
            whole, frac = num.split(".", 1)
            return f"{_int_to_words(int(whole)) if whole else 'zero'} point {_decimal_digits_to_words(frac)} percent"
        return f"{_int_to_words(int(num))} percent"

    text = re.sub(r"\b(\d+(?:\.\d+)?)%", _pct, text)

    # -- Ordinals  1st  2nd  3rd  4th ... ------------------------------------
    text = re.sub(
        r"\b(\d+)(?:st|nd|rd|th)\b",
        lambda m: _ordinal_to_words(int(m.group(1))),
        text,
        flags=re.IGNORECASE,
    )

    # -- Large integers with comma separators  1,234,567 ----------------------
    text = re.sub(
        r"\b\d{1,3}(?:,\d{3})+\b",
        lambda m: _int_to_words(int(m.group().replace(",", ""))),
        text,
    )

    # -- Decimal numbers  3.14  0.5 -------------------------------------------
    def _decimal(m: re.Match) -> str:
        return f"{_int_to_words(int(m.group(1)))} point {_decimal_digits_to_words(m.group(2))}"

    text = re.sub(r"(?<![\d/\-])\b(\d+)\.(\d+)\b(?![-/\d])", _decimal, text)

    # -- Plain integers >= 1000 (smaller ones TTS handles reliably) -----------
    def _plain_int(m: re.Match) -> str:
        n = int(m.group())
        if 1000 <= n <= 2099:
            return _year_to_words(n)
        return _int_to_words(n)

    text = re.sub(r"(?<!\.)\b(\d{4,})\b(?!\.)", _plain_int, text)

    return text


# -- Table narration ---------------------------------------------------------


def _tables_to_narration(text: str, mode: str = "structured") -> str:
    """Convert markdown table syntax in *text* to TTS-friendly prose.

    mode="structured"  (default)
        Table with 3 columns: Name, Age, City.
        Row 1: Name is Alice, Age is 30, City is New York.
        Row 2: Name is Bob, Age is 25, City is Boston.

    mode="flat"
        Cells joined with period-space (consistent legacy behavior).

    mode="skip"
        Replace entire table with a one-line announcement.

    Must be called on raw markdown BEFORE other stripping so that pipe
    characters and separator rows are still present.
    """
    if mode not in ("structured", "flat", "skip"):
        mode = "structured"

    lines = text.split("\n")
    result: List[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        if "|" not in line or not line.strip().startswith("|"):
            result.append(line)
            i += 1
            continue

        # Gather the full table block.
        block: List[str] = []
        while i < len(lines) and "|" in lines[i] and lines[i].strip().startswith("|"):
            block.append(lines[i])
            i += 1

        if mode == "skip":
            raw = [
                c.strip() for c in block[0].strip().strip("|").split("|") if c.strip()
            ]
            n = len(raw)
            result.append(
                f"Table with {n} column{'s' if n != 1 else ''} \u2014 skipped."
            )
            result.append("")
            continue

        # Parse cells.
        parsed: List[List[str]] = [
            [c.strip() for c in bl.strip().strip("|").split("|")] for bl in block
        ]

        # Separate header from data rows (skip separator lines).
        header: List[str] = []
        data_rows: List[List[str]] = []
        for cells in parsed:
            if bool(cells) and all(re.match(r"^[-:]+$", c) for c in cells if c):
                continue  # separator row
            clean = [c for c in cells if c]
            if not header:
                header = clean
            else:
                data_rows.append(clean)

        if mode == "flat":
            for cells in [header] + data_rows:
                clean = [c for c in cells if c]
                if clean:
                    result.append(".  ".join(clean) + ".")
            result.append("")
            continue

        # structured mode
        ncols = len(header)
        result.append(
            f"Table with {ncols} column{'s' if ncols != 1 else ''}: {', '.join(header)}."
        )
        for ri, data in enumerate(data_rows, 1):
            if header:
                parts = [
                    f"{hdr} is {data[hi]}"
                    for hi, hdr in enumerate(header)
                    if hi < len(data) and data[hi]
                ]
                if parts:
                    result.append(f"Row {ri}: {', '.join(parts)}.")
            else:
                clean = [c for c in data if c]
                if clean:
                    result.append(f"Row {ri}: {', '.join(clean)}.")

        result.append("")

    return "\n".join(result)


def _preprocess_tts_text(text: str, settings: "Settings") -> str:
    """Apply all speak-time text normalizations before SSML wrapping.

    Called in _tts_play_from_word() and _tts_speak_current_line() on the
    plain-text slice.  Each step is gated by its own settings flag so users
    can disable individual normalizations independently.

    Steps:
      1. Pronunciation lexicon    (use_pronunciations)
      2. Abbreviation expansion   (expand_abbreviations)
      3. Number normalization     (normalize_numbers)
    """
    # User pronunciation overrides run first so domain terms are fixed before
    # any other normalization can split or reshape them.
    if settings.get("use_pronunciations", True):
        lexicon = settings.get("pronunciations") or {}
        if lexicon:
            text = _apply_pronunciations(text, lexicon)

    if settings.get("expand_abbreviations", True):
        custom = settings.get("abbrev_expansions") or {}
        text = _expand_abbreviations(text, custom if custom else None)

    if settings.get("normalize_numbers", True):
        text = _normalize_numbers(text)

    if settings.get("normalize_math", True):
        text = _normalize_math_inline(text)

    return text


# ---------------------------------------------------------------------------
# Math expression normalization
# ---------------------------------------------------------------------------


def _normalize_math_inline(text: str) -> str:
    """Convert LaTeX math notation to spoken English for TTS.

    Applied to plain text before it reaches the speech engine.
    Handles the most common patterns in academic/STEM writing.
    """
    # Strip display/inline delimiters (order matters: $$ before $)
    text = re.sub(r"\$\$(.+?)\$\$", r" \1 ", text, flags=re.DOTALL)
    text = re.sub(r"\$(.+?)\$", r" \1 ", text)
    text = re.sub(r"\\\[(.+?)\\\]", r" \1 ", text, flags=re.DOTALL)
    text = re.sub(r"\\\((.+?)\\\)", r" \1 ", text)

    # Statistical accents
    text = re.sub(r"\\bar\{(\w+)\}", r"\1-bar", text)
    text = re.sub(r"\\hat\{(\w+)\}", r"\1-hat", text)
    text = re.sub(r"\\tilde\{(\w+)\}", r"\1-tilde", text)
    text = re.sub(r"\\overline\{([^}]+)\}", r"\1 bar", text)

    # Fractions and roots
    text = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"\1 over \2", text)
    text = re.sub(r"\\sqrt\[([^\]]+)\]\{([^}]+)\}", r"\1-th root of \2", text)
    text = re.sub(r"\\sqrt\{([^}]+)\}", r"square root of \1", text)

    # Superscripts / powers
    text = re.sub(r"\^\{-1\}", " inverse", text)
    text = re.sub(r"\^\{2\}|\^2(?=\W)", " squared", text)
    text = re.sub(r"\^\{3\}|\^3(?=\W)", " cubed", text)
    text = re.sub(r"\^\{([^}]+)\}", r" to the \1", text)
    text = re.sub(r"\^(\w)", r" to the \1", text)

    # Subscripts
    text = re.sub(r"_\{(\w)(\w+)\}", r" sub \1 \2", text)
    text = re.sub(r"_\{(\w+)\}", r" sub \1", text)
    text = re.sub(r"_(\w)", r" sub \1", text)

    # Greek letters
    greek = {
        "alpha": "alpha",
        "beta": "beta",
        "gamma": "gamma",
        "delta": "delta",
        "epsilon": "epsilon",
        "zeta": "zeta",
        "eta": "eta",
        "theta": "theta",
        "lambda": "lambda",
        "mu": "mu",
        "nu": "nu",
        "xi": "xi",
        "pi": "pi",
        "rho": "rho",
        "sigma": "sigma",
        "tau": "tau",
        "phi": "phi",
        "chi": "chi",
        "psi": "psi",
        "omega": "omega",
        "Gamma": "Gamma",
        "Delta": "Delta",
        "Theta": "Theta",
        "Lambda": "Lambda",
        "Pi": "Pi",
        "Sigma": "Sigma",
        "Phi": "Phi",
        "Psi": "Psi",
        "Omega": "Omega",
    }
    for cmd, spoken in greek.items():
        text = text.replace(f"\\{cmd}", f" {spoken} ")

    # Trig and common functions (order: longer names first to avoid partial matches)
    trig = [
        ("arcsin", "arcsine"),
        ("arccos", "arccosine"),
        ("arctan", "arctangent"),
        ("sin", "sine"),
        ("cos", "cosine"),
        ("tan", "tangent"),
        ("cot", "cotangent"),
        ("sec", "secant"),
        ("csc", "cosecant"),
        ("ln", "natural log"),
        ("log", "log"),
        ("exp", "e to the power"),
        ("lim", "limit"),
        ("sum", "sum"),
    ]
    for cmd, spoken in trig:
        text = re.sub(rf"\\{cmd}\b", f" {spoken} ", text)

    # Operators and symbols
    ops = [
        (r"\\times\b", " times "),
        (r"×", " times "),
        (r"\\div\b", " divided by "),
        (r"÷", " divided by "),
        (r"\\pm\b", " plus or minus "),
        (r"\\neq\b", " not equal to "),
        (r"\\leq\b|\\le\b", " less than or equal to "),
        (r"≤", " less than or equal to "),
        (r"\\geq\b|\\ge\b", " greater than or equal to "),
        (r"≥", " greater than or equal to "),
        (r"\\approx\b", " approximately equal to "),
        (r"≈", " approximately equal to "),
        (r"\\infty\b", " infinity "),
        (r"∞", " infinity "),
        (r"\\rightarrow\b|\\to\b", " approaches "),
        (r"→", " approaches "),
        (r"\\leftarrow\b", " from "),
        (r"←", " from "),
        (r"\\nabla\b", " gradient of "),
        (r"\\partial\b", " partial "),
        (r"\\prod\b", " product "),
        (r"\\int\b", " integral "),
    ]
    for pattern, replacement in ops:
        text = re.sub(pattern, replacement, text)

    # Clean up residual LaTeX commands and braces
    text = re.sub(r"\\[a-zA-Z]+", " ", text)
    text = re.sub(r"[{}]", "", text)
    text = re.sub(r"  +", " ", text)
    return text.strip()
