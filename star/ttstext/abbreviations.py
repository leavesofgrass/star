"""Abbreviation expansion and user pronunciation-lexicon substitution."""
from .._runtime import *  # noqa: F401,F403


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
