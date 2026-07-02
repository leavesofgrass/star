"""Annotation formatting, tag parsing, and search matching."""
from ._runtime import *  # noqa: F401,F403


def _format_annotations(
    items: List[Dict[str, Any]],
    ext: str,
    title: str,
    author: str,
    source: str,
) -> str:
    """Serialize document annotations to the format implied by *ext*.

    Supported extensions: ``.json``, ``.bib`` (BibTeX), ``.ris`` (RIS),
    ``.txt``, and ``.md`` (Markdown — the default for anything else).  BibTeX
    and RIS emit a single reference for the source document with the notes
    attached, which is the standard reference-manager convention.
    """
    date = time.strftime("%Y-%m-%d")
    year = time.strftime("%Y")

    if ext == ".json":
        return json.dumps(
            {
                "title": title,
                "author": author,
                "source": source,
                "exported": date,
                "annotations": items,
            },
            indent=2,
            ensure_ascii=False,
        )

    if ext == ".bib":
        key = (
            re.sub(r"\W+", "", (Path(source).stem or title or "notes"))[:40] or "notes"
        )
        notes_blob = "; ".join(
            f"[{a.get('anchor', '')}] {a.get('note', '')}".strip() for a in items
        )
        lines = [f"@misc{{{key},", f"  title = {{{title}}},"]
        if author:
            lines.append(f"  author = {{{author}}},")
        if source:
            lines.append(f"  howpublished = {{{source}}},")
        lines.append(f"  year = {{{year}}},")
        lines.append(f"  annote = {{{notes_blob}}}")
        lines.append("}")
        return "\n".join(lines) + "\n"

    if ext == ".ris":
        lines = ["TY  - GEN", f"TI  - {title}"]
        if author:
            lines.append(f"AU  - {author}")
        for a in items:
            anchor = str(a.get("anchor", "")).strip()
            note = str(a.get("note", "")).strip()
            combined = f"“{anchor}” — {note}" if anchor else note
            lines.append(f"N1  - {combined}")
        if source:
            lines.append(f"UR  - {source}")
        lines.append(f"PY  - {year}")
        lines.append("ER  - ")
        return "\r\n".join(lines) + "\r\n"

    if ext == ".txt":
        out = [f"Notes — {title}"]
        if author:
            out.append(f"Author: {author}")
        if source:
            out.append(f"Source: {source}")
        out.append(f"Exported: {date}")
        out.append("")
        for i, a in enumerate(items, 1):
            anchor = str(a.get("anchor", "")).strip()
            note = str(a.get("note", "")).strip()
            ts = str(a.get("ts", ""))
            out.append(f"{i}. {note}")
            if anchor:
                out.append(f"   context: “{anchor}”")
            if ts:
                out.append(f"   {ts}")
            out.append("")
        return "\n".join(out)

    # Default: Markdown
    md = [f"# Notes — {title}", ""]
    if author:
        md.append(f"- **Author:** {author}")
    if source:
        md.append(f"- **Source:** `{source}`")
    md.append(f"- **Exported:** {date}")
    md.append(f"- **Count:** {len(items)}")
    md.append("")
    md.append("---")
    md.append("")
    for i, a in enumerate(items, 1):
        anchor = str(a.get("anchor", "")).strip()
        note = str(a.get("note", "")).strip()
        ts = str(a.get("ts", ""))
        md.append(f"## Note {i}")
        if anchor:
            md.append("")
            md.append(f"> {anchor}")
        md.append("")
        md.append(note)
        if ts:
            md.append("")
            md.append(f"*{ts}*")
        md.append("")
    return "\n".join(md)


def _annotation_matches(a: Dict[str, Any], query: str) -> bool:
    """Return True if annotation *a* matches the free-text *query*.

    The query supports space-separated terms (all must match — AND) over the
    note body, anchor quote, and tags.  A term beginning with ``#`` is a tag
    filter (matches against the note's tags only).  An empty query matches all.
    Shared by the Qt Notes panel and the curses TUI notes list.
    """
    q = (query or "").strip().lower()
    if not q:
        return True
    note = str(a.get("note", "")).lower()
    anchor = str(a.get("anchor", "")).lower()
    tags = [str(t).lower() for t in a.get("tags", []) or []]
    for term in q.split():
        if term.startswith("#") and len(term) > 1:
            if not any(term[1:] in t for t in tags):
                return False
        else:
            if (
                term not in note
                and term not in anchor
                and not any(term in t for t in tags)
            ):
                return False
    return True


def _parse_tags(raw: str) -> List[str]:
    """Split a comma/space/`#`-separated tag string into a clean tag list."""
    parts = re.split(r"[,\s]+", (raw or "").strip())
    return [p.lstrip("#").strip() for p in parts if p.strip().lstrip("#")]


# =============================================================================
# Knowledge-graph relations between annotations
# =============================================================================

RELATION_TYPES = [
    "CONFLICTS_WITH",
    "SUPPORTS",
    "IS_EXAMPLE_OF",
    "CITES",
    "CONTRADICTS",
    "DEFINES",
    "EXTENDS",
    "SEE_ALSO",
    "PRECEDES",
    "FOLLOWS",
]


def _save_settings(settings: Any) -> None:
    # The helpers accept either a Settings instance or a plain dict (tests), so
    # only persist when the object actually supports it.
    save = getattr(settings, "save", None)
    if callable(save):
        save()


def _ensure_id(ann: Dict[str, Any]) -> str:
    """Return *ann*'s stable id, assigning a fresh one in place if absent."""
    aid = ann.get("id")
    if not aid:
        aid = uuid.uuid4().hex[:8]
        ann["id"] = aid
    return aid


def get_annotation_by_id(
    settings: Any, doc_path: str, ann_id: str
) -> "Optional[Dict[str, Any]]":
    """Return the annotation with *ann_id* in *doc_path*, or None."""
    for ann in settings["annotations"].get(doc_path, []) or []:
        if _ensure_id(ann) == ann_id:
            return ann
    return None


def add_relation(
    settings: Any,
    src_doc: str,
    src_id: str,
    rel_type: str,
    tgt_doc: str,
    tgt_id: str,
    note: str = "",
) -> bool:
    """Append a directed relation edge from one annotation to another."""
    src = get_annotation_by_id(settings, src_doc, src_id)
    if src is None:
        return False
    src.setdefault("relations", []).append(
        {
            "rel_type": rel_type,
            "target_doc": tgt_doc,
            "target_id": tgt_id,
            "note": note or "",
        }
    )
    _save_settings(settings)
    return True


def remove_relation(settings: Any, src_doc: str, src_id: str, rel_index: int) -> bool:
    """Delete the relation at *rel_index* on the given source annotation."""
    src = get_annotation_by_id(settings, src_doc, src_id)
    if src is None:
        return False
    rels = src.get("relations") or []
    if 0 <= rel_index < len(rels):
        rels.pop(rel_index)
        _save_settings(settings)
        return True
    return False


def all_relations(settings: Any):
    """Yield ``(src_doc, annotation, relation)`` for every edge across all docs."""
    for doc, anns in (settings["annotations"] or {}).items():
        for ann in anns or []:
            _ensure_id(ann)
            for rel in ann.get("relations") or []:
                yield doc, ann, rel


def get_related(settings: Any, doc_path: str, ann_id: str):
    """Return ``[(relation, target_annotation_or_None), ...]`` for one annotation."""
    src = get_annotation_by_id(settings, doc_path, ann_id)
    if src is None:
        return []
    out = []
    for rel in src.get("relations") or []:
        tgt = get_annotation_by_id(
            settings, rel.get("target_doc", ""), rel.get("target_id", "")
        )
        out.append((rel, tgt))
    return out


# =============================================================================
# Spaced-repetition state on annotations (see star/sr.py)
# =============================================================================
#
# Each reviewable annotation carries an ``sr_state`` sub-dict — the scheduler's
# per-card memory (next_review / interval / stability / difficulty / reps /
# lapses).  A note is *reviewable* when it has content to test: a highlighted
# passage (``anchor``) and/or a note body.  These helpers keep the persistence
# concerns (per-doc storage, save-on-write) out of the pure sr.py math.


def is_reviewable(ann: Dict[str, Any]) -> bool:
    """True when *ann* has enough content to become a review card.

    A card needs a front and a back.  The front is the highlighted passage
    (``anchor``); the back is the note.  Either alone is enough to review (a
    bare highlight becomes a "recall the note" prompt once one exists, and a
    bare note is a free-recall prompt), so the card is reviewable when *either*
    is present.
    """
    return bool(str(ann.get("anchor", "") or "").strip()
                or str(ann.get("note", "") or "").strip())


def get_sr_state(ann: Dict[str, Any]) -> "Optional[Dict[str, Any]]":
    """Return the annotation's ``sr_state`` sub-dict, or ``None`` if unscheduled."""
    st = ann.get("sr_state")
    return st if isinstance(st, dict) else None


def set_sr_state(
    settings: Any, doc_path: str, ann_id: str, state: Dict[str, Any]
) -> bool:
    """Write *state* as the annotation's ``sr_state`` and persist.

    Returns True when the annotation was found and updated, False otherwise.
    """
    ann = get_annotation_by_id(settings, doc_path, ann_id)
    if ann is None:
        return False
    ann["sr_state"] = dict(state)
    _save_settings(settings)
    return True


def ensure_sr_state(
    settings: Any, doc_path: str, ann_id: str, today: Any = None
) -> "Optional[Dict[str, Any]]":
    """Return the annotation's ``sr_state``, creating a fresh one if absent.

    A newly-created state is due immediately (``today``).  ``today`` is injected
    (a ``datetime.date``) so callers/tests stay deterministic.  Returns ``None``
    only when the annotation id does not exist.
    """
    from . import sr

    ann = get_annotation_by_id(settings, doc_path, ann_id)
    if ann is None:
        return None
    st = get_sr_state(ann)
    if st is None:
        st = sr.new_state(today)
        ann["sr_state"] = st
        _save_settings(settings)
    return st


def review_annotation(
    settings: Any, doc_path: str, ann_id: str, grade: Any, today: Any = None
) -> "Optional[Dict[str, Any]]":
    """Grade an annotation's review card and persist the new ``sr_state``.

    Thin persistence wrapper around :func:`star.sr.review`.  Returns the new
    state, or ``None`` when the annotation id does not exist.
    """
    from . import sr

    ann = get_annotation_by_id(settings, doc_path, ann_id)
    if ann is None:
        return None
    new = sr.review(get_sr_state(ann), grade, today)
    ann["sr_state"] = new
    _save_settings(settings)
    return new


def iter_review_cards(settings: Any):
    """Yield ``(doc_path, annotation)`` for every reviewable annotation.

    Assigns a stable id to any annotation that lacks one (so review state can be
    written back), and skips notes with no content to test.
    """
    for doc, anns in (settings["annotations"] or {}).items():
        for ann in anns or []:
            if not is_reviewable(ann):
                continue
            _ensure_id(ann)
            yield doc, ann


def due_cards(settings: Any, today: Any = None):
    """Return ``[(doc_path, annotation), ...]`` for all cards due on/before *today*.

    A card with no ``sr_state`` is treated as due (it needs a first review).
    Ordered most-overdue first, then by document, so the review session starts
    with the cards that have waited longest.  ``today`` is injected for
    determinism (a ``datetime.date``; defaults to the real today).
    """
    from . import sr

    out = []
    for doc, ann in iter_review_cards(settings):
        st = get_sr_state(ann)
        if sr.is_due(st, today):
            out.append((doc, ann))
    out.sort(key=lambda pair: (sr.days_until_due(get_sr_state(pair[1]), today), pair[0]))
    return out


def review_summary(settings: Any, today: Any = None) -> Dict[str, Any]:
    """Return aggregate review stats: total/due/new counts and mean retention.

    ``retention`` is the mean estimated recall probability across all *reviewed*
    cards (0.0 when none have been reviewed yet) — the headline "% remembered"
    figure shown on the dashboard.
    """
    from . import sr

    total = due = new = 0
    ret_sum = 0.0
    ret_n = 0
    for _doc, ann in iter_review_cards(settings):
        total += 1
        st = get_sr_state(ann)
        if sr.is_due(st, today):
            due += 1
        if sr.is_new(st):
            new += 1
        else:
            ret_sum += sr.retention_estimate(st, today)
            ret_n += 1
    retention = round(ret_sum / ret_n, 4) if ret_n else 0.0
    return {
        "total": total,
        "due": due,
        "new": new,
        "reviewed": ret_n,
        "retention": retention,
    }
