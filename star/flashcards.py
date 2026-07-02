"""Anki flashcard (.apkg) export from a document's notes via genanki.

Optional feature: requires the ``genanki`` package (``pip install genanki``).
Gated behind ``_GENANKI`` so star imports cleanly without it.

Each annotation becomes one card: the highlighted passage (``anchor``) is the
front and the user's note (``note``) is the back.  The result is a standard
``.apkg`` file importable by Anki.
"""

from ._runtime import *  # noqa: F401,F403
from .formats import Exporter

# Detected cheaply; genanki is imported lazily by the functions below the first
# time an Anki deck is exported.
_GENANKI = _module_available("genanki")

# ── Auto-cloze generation ────────────────────────────────────────────────────
# A cloze card blanks out a key term in a sentence ("The capital of France is
# {{c1::Paris}}") and asks the reader to recall it.  We pick the terms to blank
# with a stdlib-only heuristic so the feature is fully offline and has no hard
# dependency: proper-noun phrases (runs of Capitalized words), numbers/years,
# and — when the optional wordfreq database is present — the rarest content
# words.  This deliberately errs toward *fewer, higher-value* blanks.

_CLOZE_TOKEN_RE = re.compile(r"[^\W\d_]+(?:[-'][^\W\d_]+)*|\d[\d,.]*", re.UNICODE)
# A run of Capitalized words = a candidate proper-noun phrase / named entity.
_PROPER_PHRASE_RE = re.compile(
    r"\b([A-Z][\w'-]*(?:\s+(?:of|the|and|de|von|van)\s+)?"
    r"(?:[A-Z][\w'-]*)?(?:\s+[A-Z][\w'-]*)*)\b"
)
# A number, optionally a 4-digit year or a quantity, is usually a fact worth testing.
_NUMBER_RE = re.compile(r"\b\d[\d,]*(?:\.\d+)?%?\b")

# Sentence-initial function words that begin a Capitalized run only because they
# start the sentence — never worth clozing on their own.
_STOP_CAPS = frozenset({
    "The", "A", "An", "This", "That", "These", "Those", "It", "He", "She",
    "They", "We", "You", "I", "In", "On", "At", "For", "And", "But", "Or",
    "As", "If", "So", "To", "Of", "By", "When", "While", "Because", "There",
    "Here", "Then", "Thus", "However", "Therefore",
})


def _split_sentences(text: str) -> "List[str]":
    """Split *text* into sentences using the runtime's shared sentence splitter."""
    parts = _SENTENCE_SPLIT_RE.split(text or "")
    return [p.strip() for p in parts if p and p.strip()]


def _cloze_candidates(sentence: str, max_terms: int = 3) -> "List[str]":
    """Return up to *max_terms* key terms to blank out of *sentence*.

    Priority: proper-noun phrases (named entities) and numbers first, then the
    rarest content words (only when wordfreq is available).  Terms are returned
    in the order they appear so overlapping blanks stay left-to-right.
    """
    if not sentence:
        return []
    picks: "List[Tuple[int, str]]" = []  # (position, term)
    seen: "set[str]" = set()

    def _add(term: str, pos: int) -> None:
        t = term.strip()
        key = t.lower()
        if t and key not in seen and len(t) > 1:
            seen.add(key)
            picks.append((pos, t))

    # 1) Proper-noun phrases (skip a sentence-initial lone stopword-cap).
    for m in _PROPER_PHRASE_RE.finditer(sentence):
        phrase = m.group(1).strip()
        words = phrase.split()
        if len(words) == 1 and words[0] in _STOP_CAPS:
            continue
        # Drop a leading sentence-start stopword ("The Nile" at pos 0 → "Nile"
        # only if the rest is still a proper noun; otherwise keep the phrase).
        if len(words) > 1 and words[0] in _STOP_CAPS and words[1][:1].isupper():
            phrase = " ".join(words[1:])
            _add(phrase, sentence.find(phrase))
        else:
            _add(phrase, m.start())

    # 2) Numbers / years / percentages.
    for m in _NUMBER_RE.finditer(sentence):
        _add(m.group(0), m.start())

    # 3) Rarest content words (optional; needs wordfreq).  Only used to top up
    #    when the entity/number pass found too few terms.
    if len(picks) < max_terms:
        from .vocab import _WORDFREQ  # cheap flag, no heavy import
        if _WORDFREQ:
            from wordfreq import zipf_frequency  # deferred: loads DB lazily
            scored: "List[Tuple[float, int, str]]" = []
            for m in _CLOZE_TOKEN_RE.finditer(sentence):
                tok = m.group(0)
                low = tok.lower()
                if len(tok) < 4 or low in seen or not tok[0].isalpha():
                    continue
                z = zipf_frequency(low, "en")
                if z and z < 4.5:
                    scored.append((z, m.start(), tok))
            for _z, pos, tok in sorted(scored)[: max_terms - len(picks)]:
                _add(tok, pos)

    picks.sort(key=lambda p: p[0])
    return [t for _pos, t in picks[:max_terms]]


def _blank_term(sentence: str, term: str, marker: str = "____") -> str:
    """Replace the first whole occurrence of *term* in *sentence* with *marker*."""
    pattern = re.compile(r"\b" + re.escape(term) + r"\b")
    return pattern.sub(marker, sentence, count=1)


def make_cloze_cards(
    text: str, note: str = "", max_terms: int = 3, anki_syntax: bool = False
) -> "List[Dict[str, str]]":
    """Generate cloze (fill-in-the-blank) cards from *text* (a highlight/sentence).

    Each returned card is a dict with:

    * ``front`` — the sentence with the key term(s) blanked out;
    * ``back``  — the original sentence (the answer), plus *note* if given;
    * ``cloze`` — Anki cloze-deletion markup (``{{c1::term}}``) when
      *anki_syntax* is True, else the plain blanked text.
    * ``terms`` — the list of blanked terms.

    One card is produced per sentence that yields at least one key term.  When
    no term can be identified (e.g. a sentence of only common words), that
    sentence is skipped.  Fully offline; no network, no hard dependency.
    """
    cards: "List[Dict[str, str]]" = []
    for sent in _split_sentences(text) or ([text.strip()] if text and text.strip() else []):
        terms = _cloze_candidates(sent, max_terms=max_terms)
        if not terms:
            continue
        front = sent
        for t in terms:
            front = _blank_term(front, t, "____")
        if front == sent:  # nothing actually blanked (term not word-bounded)
            continue
        if anki_syntax:
            cloze = sent
            for i, t in enumerate(terms, 1):
                cloze = _blank_term(cloze, t, "{{c%d::%s}}" % (i, t))
        else:
            cloze = front
        back = sent + (("\n\n" + note.strip()) if note and note.strip() else "")
        cards.append(
            {"front": front, "back": back, "cloze": cloze, "terms": terms}
        )
    return cards


# A note type ("model") needs an id that is stable across exports so Anki
# updates the same type on re-import instead of creating duplicates.  genanki
# asks for a random-but-persistent integer; this one is fixed for star.
_STAR_MODEL_ID = 1607392319
# A separate, fixed id for star's cloze note type (distinct from the basic one
# so Anki keeps them as two different models on import).
_STAR_CLOZE_MODEL_ID = 1607392320
_STAR_MODEL = None  # built lazily, only once genanki is importable
_STAR_CLOZE_MODEL = None


def _model() -> "genanki.Model":
    """Return star's shared Anki note type, building it on first use."""
    global _STAR_MODEL
    if _STAR_MODEL is None:
        import genanki  # deferred from startup

        _STAR_MODEL = genanki.Model(
            _STAR_MODEL_ID,
            "star Annotation",
            fields=[{"name": "Front"}, {"name": "Back"}],
            templates=[
                {
                    "name": "Card 1",
                    "qfmt": "{{Front}}",
                    "afmt": '{{FrontSide}}<hr id="answer">{{Back}}',
                }
            ],
        )
    return _STAR_MODEL


def _cloze_model() -> "genanki.Model":
    """Return star's cloze note type (Anki's built-in cloze card kind)."""
    global _STAR_CLOZE_MODEL
    if _STAR_CLOZE_MODEL is None:
        import genanki  # deferred from startup

        _STAR_CLOZE_MODEL = genanki.Model(
            _STAR_CLOZE_MODEL_ID,
            "star Cloze",
            fields=[{"name": "Text"}, {"name": "Extra"}],
            templates=[
                {
                    "name": "Cloze",
                    "qfmt": "{{cloze:Text}}",
                    "afmt": "{{cloze:Text}}<br>{{Extra}}",
                }
            ],
            model_type=genanki.Model.CLOZE,
        )
    return _STAR_CLOZE_MODEL


def _deck_id(title: str) -> int:
    """Derive a stable deck id from *title* so re-exports update one deck."""
    digest = hashlib.md5(title.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def export_anki_deck(
    annotations: List[Dict[str, Any]],
    title: str,
    path: str,
    *,
    cloze: bool = False,
) -> None:
    """Write *annotations* to an Anki deck file at *path* (an ``.apkg``).

    *annotations* is a list of dicts with ``anchor`` (the highlighted passage,
    used as the card front) and ``note`` (the user's note, used as the card
    back); empty cards are skipped.  *title* names the deck.

    When *cloze* is True, auto-generated fill-in-the-blank cards are emitted
    **alongside** the basic cards: for each annotation, key terms in the
    highlighted passage (or, lacking one, the note) are blanked out into Anki
    cloze-deletion cards.  This is best-effort — an annotation that yields no
    clozable term still contributes its basic card.

    Raises ``RuntimeError`` with install guidance when genanki is unavailable,
    and ``ValueError`` when no annotation has any content to export.
    """
    if not _GENANKI:
        raise RuntimeError("Anki export requires genanki:\n    pip install genanki")
    import genanki  # deferred from startup

    title = (title or "star Deck").strip() or "star Deck"
    deck = genanki.Deck(_deck_id(title), title)
    model = _model()
    cloze_model = _cloze_model() if cloze else None
    count = 0
    for ann in annotations or []:
        front = str((ann or {}).get("anchor", "") or "").strip()
        back = str((ann or {}).get("note", "") or "").strip()
        if not (front or back):
            continue
        deck.add_note(genanki.Note(model=model, fields=[front, back]))
        count += 1
        if cloze:
            # Blank key terms from the highlighted passage (preferred, since it
            # is verbatim source text); fall back to the note body.
            source = front or back
            for card in make_cloze_cards(source, note=back, anki_syntax=True):
                deck.add_note(
                    genanki.Note(model=cloze_model, fields=[card["cloze"], back])
                )
                count += 1
    if count == 0:
        raise ValueError("No annotations with content to export.")
    genanki.Package(deck).write_to_file(path)


class AnkiExporter(Exporter):
    """Export a document's annotations as an Anki deck (``.apkg``).

    The cards come from the document's *annotations* (passed via ``kwargs`` —
    each a dict with ``anchor``/``note``), not the document body, since an Anki
    deck is built from the reader's highlights and notes.  The deck title
    defaults to the document title.
    """

    name = "anki"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".apkg"})

    @classmethod
    def available(cls) -> bool:
        return bool(_GENANKI)

    def export(self, document, path, **kwargs) -> None:
        annotations = kwargs.get("annotations") or []
        title = kwargs.get("title") or getattr(document, "title", "") or "star Deck"
        export_anki_deck(annotations, title, str(path))
