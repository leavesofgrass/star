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


# A note type ("model") needs an id that is stable across exports so Anki
# updates the same type on re-import instead of creating duplicates.  genanki
# asks for a random-but-persistent integer; this one is fixed for star.
_STAR_MODEL_ID = 1607392319
_STAR_MODEL = None  # built lazily, only once genanki is importable


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


def _deck_id(title: str) -> int:
    """Derive a stable deck id from *title* so re-exports update one deck."""
    digest = hashlib.md5(title.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def export_anki_deck(annotations: List[Dict[str, Any]], title: str, path: str) -> None:
    """Write *annotations* to an Anki deck file at *path* (an ``.apkg``).

    *annotations* is a list of dicts with ``anchor`` (the highlighted passage,
    used as the card front) and ``note`` (the user's note, used as the card
    back); empty cards are skipped.  *title* names the deck.

    Raises ``RuntimeError`` with install guidance when genanki is unavailable,
    and ``ValueError`` when no annotation has any content to export.
    """
    if not _GENANKI:
        raise RuntimeError("Anki export requires genanki:\n    pip install genanki")
    import genanki  # deferred from startup

    title = (title or "star Deck").strip() or "star Deck"
    deck = genanki.Deck(_deck_id(title), title)
    model = _model()
    count = 0
    for ann in annotations or []:
        front = str((ann or {}).get("anchor", "") or "").strip()
        back = str((ann or {}).get("note", "") or "").strip()
        if not (front or back):
            continue
        deck.add_note(genanki.Note(model=model, fields=[front, back]))
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
