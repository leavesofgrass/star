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
