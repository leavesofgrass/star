"""Number, date, time, currency, and ordinal normalization for TTS."""
from .._runtime import *  # noqa: F401,F403


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
        # Round millennia read as "<n> thousand" (2000 → two thousand, 1000 →
        # one thousand); other round centuries stay "<century> hundred"
        # (1900 → nineteen hundred).
        if year % 1000 == 0:
            return _int_to_words(year)
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
