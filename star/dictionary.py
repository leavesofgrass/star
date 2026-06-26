"""Offline dictionary / definition lookup.

Closes the loop the difficult-word overlay (:mod:`star.vocab`) opens: vocab tints
*which* words are hard; this module says what they *mean* — fully offline, which
matters for dense terminology with no network.

Optional feature, guarded like every other: when nltk is absent the module still
imports cleanly with ``_NLTK = False`` and the UI shows an install hint instead
of failing.  Backends, in priority order:

1. A user-supplied **custom dictionary file** (JSON), pointed at by the
   ``dictionary_file`` setting — checked first so a reader can layer their own
   medical/domain glossary over the defaults.
2. **WordNet** via nltk (``pip install "star-reader[dictionary]"`` then a one-time
   ``python -m nltk.downloader wordnet omw-1.4 cmudict``) — definitions grouped by
   part of speech, with examples and synonyms.
3. **CMUdict** (also nltk) supplies an ARPAbet pronunciation when its corpus is
   present.

The nltk *package* is detected at import; the WordNet/CMUdict *corpora* are
detected lazily inside the lookup functions (a ``LookupError`` from nltk means
"package installed, corpus not downloaded").
"""
from ._runtime import *  # noqa: F401,F403

# Detected cheaply at import (mirrors vocab._WORDFREQ); the heavy corpus loads
# are deferred to the lookup functions so this stays off the startup path.
_NLTK = _module_available("nltk")

# WordNet part-of-speech codes → readable names.  "s" is an adjective satellite.
_POS_NAMES = {"n": "noun", "v": "verb", "a": "adjective", "s": "adjective", "r": "adverb"}
_POS_ORDER = ["noun", "verb", "adjective", "adverb"]

# Custom-dictionary file cache, keyed by (path, mtime) so edits are picked up.
_custom_cache: "Dict[Tuple[str, float], Dict[str, Any]]" = {}


@dataclass
class Sense:
    """One sense of a word: a definition plus optional examples/synonyms."""

    definition: str
    examples: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)


@dataclass
class POSGroup:
    """All senses for one part of speech (``pos`` may be "" for custom entries)."""

    pos: str
    senses: List[Sense] = field(default_factory=list)


@dataclass
class DefinitionResult:
    """A full lookup result for one word."""

    word: str
    pronunciation: str = ""  # ARPAbet (from CMUdict) or a custom-supplied string
    groups: List[POSGroup] = field(default_factory=list)
    source: str = "wordnet"  # "custom" | "wordnet"


def _normalize(word: str) -> str:
    """Lowercase and strip surrounding punctuation from a selected token."""
    return re.sub(r"^\W+|\W+$", "", word or "", flags=re.UNICODE).strip().lower()


def _load_custom_dictionary(path: str) -> "Dict[str, Any]":
    """Load + cache a custom JSON dictionary.  Returns ``{}`` on any problem."""
    if not path:
        return {}
    try:
        mtime = Path(path).stat().st_mtime
    except OSError:
        return {}
    key = (path, mtime)
    if key in _custom_cache:
        return _custom_cache[key]
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
        result = {str(k).lower(): v for k, v in data.items()} if isinstance(data, dict) else {}
    except Exception:
        result = {}
    _custom_cache[key] = result
    return result


def _wordnet():
    """Return the WordNet corpus module, or ``None`` if pkg/corpus unavailable."""
    if not _NLTK:
        return None
    try:
        from nltk.corpus import wordnet as wn

        wn.ensure_loaded()  # raises LookupError when the corpus isn't downloaded
        return wn
    except Exception:
        return None


def _pronounce(word: str) -> str:
    """ARPAbet pronunciation from CMUdict, or "" when unavailable."""
    if not _NLTK:
        return ""
    try:
        from nltk.corpus import cmudict

        prons = cmudict.dict().get(word.lower())
        return " ".join(prons[0]) if prons else ""
    except Exception:
        return ""


def availability(settings: Any = None) -> "Tuple[bool, str]":
    """Return ``(ok, hint)``.  ``ok`` is True when *some* backend can answer; the
    hint explains how to enable lookups when it cannot."""
    if settings is not None:
        path = str(settings.get("dictionary_file", "") or "")
        if path and _load_custom_dictionary(path):
            return True, ""
    if not _NLTK:
        return False, (
            "Offline definitions need nltk:\n"
            '    pip install "star-reader[dictionary]"'
        )
    if _wordnet() is None:
        return False, (
            "nltk is installed but the WordNet corpus isn't downloaded:\n"
            "    python -m nltk.downloader wordnet omw-1.4 cmudict"
        )
    return True, ""


def _result_from_custom(word: str, entry: Any) -> DefinitionResult:
    """Build a result from a custom-dictionary entry (a string or an object)."""
    if isinstance(entry, dict):
        sense = Sense(
            definition=str(entry.get("definition", "")),
            examples=[str(e) for e in (entry.get("examples") or [])],
            synonyms=[str(s) for s in (entry.get("synonyms") or [])],
        )
        return DefinitionResult(
            word=word,
            pronunciation=str(entry.get("pronunciation", "")),
            groups=[POSGroup(pos=str(entry.get("pos", "")), senses=[sense])],
            source="custom",
        )
    return DefinitionResult(
        word=word,
        groups=[POSGroup(pos="", senses=[Sense(definition=str(entry))])],
        source="custom",
    )


def define(word: str, settings: Any = None) -> "Optional[DefinitionResult]":
    """Look up *word*; return a :class:`DefinitionResult` or ``None`` if not found.

    Tries the custom dictionary first, then WordNet.  Pronunciation is filled
    from CMUdict when available.
    """
    w = _normalize(word)
    if not w:
        return None

    if settings is not None:
        custom = _load_custom_dictionary(str(settings.get("dictionary_file", "") or ""))
        if w in custom:
            result = _result_from_custom(w, custom[w])
            if not result.pronunciation:
                result.pronunciation = _pronounce(w)
            return result

    wn = _wordnet()
    if wn is None:
        return None
    synsets = wn.synsets(w)
    if not synsets:
        return None

    groups: "Dict[str, POSGroup]" = {}
    for syn in synsets:
        pos = _POS_NAMES.get(syn.pos(), syn.pos())
        group = groups.setdefault(pos, POSGroup(pos=pos))
        group.senses.append(
            Sense(
                definition=syn.definition(),
                examples=list(syn.examples()),
                synonyms=[
                    lemma.name().replace("_", " ")
                    for lemma in syn.lemmas()
                    if lemma.name().lower() != w
                ][:6],
            )
        )

    ordered = [groups[p] for p in _POS_ORDER if p in groups]
    ordered += [g for p, g in groups.items() if p not in _POS_ORDER]
    return DefinitionResult(
        word=w, pronunciation=_pronounce(w), groups=ordered, source="wordnet"
    )


def format_definition_markdown(result: "Optional[DefinitionResult]") -> str:
    """Render a result as Markdown (used by the TUI pager, the Qt panel, notes)."""
    if result is None:
        return ""
    lines = [f"# {result.word}"]
    if result.pronunciation:
        lines.append(f"*/{result.pronunciation}/*")
    lines.append("")
    for group in result.groups:
        if group.pos:
            lines.append(f"## {group.pos}")
        for i, sense in enumerate(group.senses, 1):
            lines.append(f"{i}. {sense.definition}")
            for ex in sense.examples:
                lines.append(f"   > {ex}")
            if sense.synonyms:
                lines.append(f"   *Synonyms: {', '.join(sense.synonyms)}*")
        lines.append("")
    lines.append(f"_Source: {'custom dictionary' if result.source == 'custom' else 'WordNet'}_")
    return "\n".join(lines).strip() + "\n"
