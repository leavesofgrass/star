"""OpenDocument presentations and flat-XML documents → Markdown (stdlib only).

Covers what the odfpy-based ODT loader in :mod:`office` does not:

* ``.odp`` — OpenDocument Presentation (a ZIP with ``content.xml``): one
  section per ``<draw:page>``, its title placeholder as the heading, body
  text/lists as bullets, tables, image alt text, and speaker notes.
* ``.fodp`` / ``.fodt`` — *flat* single-file XML presentations and text
  documents (``<office:document>`` with the body inline, no ZIP).

The same namespace-aware walker also serves as the ODT fallback when odfpy is
absent (it understands headings, paragraphs, lists, tables, notes and inline
spacing elements), replacing the regex tag-stripper for that case.
"""
from .._runtime import *  # noqa: F401,F403

_NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "presentation": "urn:oasis:names:tc:opendocument:xmlns:presentation:1.0",
    "svg": "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0",
    "xlink": "http://www.w3.org/1999/xlink",
    "dc": "http://purl.org/dc/elements/1.1/",
    "meta": "urn:oasis:names:tc:opendocument:xmlns:meta:1.0",
}


def _q(prefix: str, name: str) -> str:
    return f"{{{_NS[prefix]}}}{name}"


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _ns_of(tag: str) -> str:
    return tag[1:].split("}")[0] if tag.startswith("{") else ""


def _odf_inline(elem: ET.Element) -> str:
    """Flatten a ``text:p``/``text:h``/``text:span`` subtree to one string."""
    parts: List[str] = [elem.text or ""]
    for child in elem:
        tag = _local(child.tag)
        if tag == "s":
            parts.append(" " * int(child.get(_q("text", "c")) or 1))
        elif tag == "tab":
            parts.append("\t")
        elif tag == "line-break":
            parts.append("\n")
        elif tag == "note":
            body = child.find(_q("text", "note-body"))
            note = " ".join(
                _odf_inline(p).strip() for p in (body if body is not None else [])
            ).strip()
            parts.append(f" (footnote: {note})" if note else "")
        elif tag == "a":
            inner = _odf_inline(child)
            href = child.get(_q("xlink", "href"), "")
            parts.append(f"[{inner}]({href})" if href and inner.strip() else inner)
        elif tag in ("frame",):
            parts.append(_odf_frame_inline(child))
        elif tag in ("soft-page-break", "bookmark", "bookmark-start", "bookmark-end",
                     "reference-mark", "reference-mark-start", "reference-mark-end",
                     "annotation", "tracked-changes", "change", "change-start",
                     "change-end"):
            pass
        else:
            parts.append(_odf_inline(child))
        parts.append(child.tail or "")
    return "".join(parts)


def _odf_frame_inline(frame: ET.Element) -> str:
    """An image frame → Markdown image with its alt text (``svg:title``/``svg:desc``)."""
    img = frame.find(_q("draw", "image"))
    if img is None:
        return ""
    alt = ""
    for tag in ("title", "desc"):
        t = frame.find(_q("svg", tag))
        if t is not None and (t.text or "").strip():
            alt = t.text.strip()
            break
    href = img.get(_q("xlink", "href"), "")
    return f"![{alt or frame.get(_q('draw', 'name'), '') or 'image'}]({href})"


def _odf_table(table: ET.Element, out: List[str]) -> None:
    rows: List[List[str]] = []
    for row in table.iter(_q("table", "table-row")):
        cells = []
        for cell in row:
            if _local(cell.tag) in ("table-cell", "covered-table-cell"):
                txt = " ".join(
                    _odf_inline(p).strip()
                    for p in cell
                    if _local(p.tag) in ("p", "h")
                ).strip()
                cells.append(txt.replace("|", "\\|").replace("\n", " "))
        if cells:
            rows.append(cells)
    if not rows:
        return
    nc = max(len(r) for r in rows)
    out.append("| " + " | ".join((rows[0] + [""] * nc)[:nc]) + " |")
    out.append("|" + "|".join([" --- "] * nc) + "|")
    for r in rows[1:]:
        out.append("| " + " | ".join((r + [""] * nc)[:nc]) + " |")
    out.append("")


def _odf_walk(node: ET.Element, out: List[str], list_depth: int = 0, ordered: bool = False) -> None:
    """Render ODF text content (``office:text`` subtree, or a draw frame's
    ``draw:text-box``) into Markdown lines."""
    tag = _local(node.tag)
    if tag == "h":
        level = int(node.get(_q("text", "outline-level")) or 1)
        text = _odf_inline(node).strip()
        if text:
            out += [f"{'#' * max(1, min(6, level))} {text}", ""]
    elif tag == "p":
        text = _odf_inline(node).strip()
        if text:
            if list_depth:
                out.append("  " * (list_depth - 1) + ("1. " if ordered else "- ") + text)
            else:
                out += [text, ""]
        elif list_depth == 0:
            # Image-only paragraph (frame as child) already rendered by inline.
            pass
    elif tag == "list":
        style = (node.get(_q("text", "style-name")) or "").lower()
        is_ordered = ordered or "number" in style or "ordered" in style
        for item in node:
            if _local(item.tag) in ("list-item", "list-header"):
                for sub in item:
                    _odf_walk(sub, out, list_depth + 1, is_ordered)
        if list_depth == 0:
            out.append("")
    elif tag == "table":
        _odf_table(node, out)
    elif tag == "frame":
        box = node.find(_q("draw", "text-box"))
        if box is not None:
            for sub in box:
                _odf_walk(sub, out, list_depth, ordered)
        else:
            img = _odf_frame_inline(node)
            if img:
                out += [img, ""]
    elif tag in ("section", "text-box", "custom-shape", "g", "index-body", "table-of-content"):
        for sub in node:
            _odf_walk(sub, out, list_depth, ordered)
    elif tag in ("sequence-decls", "forms", "variable-decls", "user-field-decls",
                 "tracked-changes", "soft-page-break", "index-title"):
        pass
    else:
        for sub in node:
            _odf_walk(sub, out, list_depth, ordered)


def _odf_metadata(root: ET.Element) -> Dict[str, str]:
    meta: Dict[str, str] = {}
    for key, tag in (("title", _q("dc", "title")), ("author", _q("dc", "creator")),
                     ("language", _q("dc", "language")), ("subject", _q("dc", "subject"))):
        e = root.find(f".//{tag}")
        if e is not None and (e.text or "").strip():
            meta[key] = e.text.strip()
    if "author" not in meta:
        e = root.find(f".//{_q('meta', 'initial-creator')}")
        if e is not None and (e.text or "").strip():
            meta["author"] = e.text.strip()
    return meta


def _odf_root(path: str) -> Tuple[ET.Element, Optional[ET.Element]]:
    """``(content_root, meta_root)`` for a zipped or flat OpenDocument file."""
    data = Path(path).read_bytes()
    if data[:2] == b"PK":
        with zipfile.ZipFile(path, "r") as zf:
            content = ET.fromstring(zf.read("content.xml"))
            meta = None
            if "meta.xml" in zf.namelist():
                try:
                    meta = ET.fromstring(zf.read("meta.xml"))
                except ET.ParseError:
                    meta = None
            return content, meta
    root = ET.fromstring(data)
    return root, root


# ── Text documents (ODT via ET, FODT) ───────────────────────────────────────


def _odt_markdown_from_root(content: ET.Element, meta: Optional[ET.Element]) -> str:
    body = content.find(f".//{_q('office', 'text')}")
    if body is None:
        return ""
    out: List[str] = []
    md_meta = _odf_metadata(meta) if meta is not None else {}
    if md_meta.get("title"):
        out += [f"# {md_meta['title']}", ""]
    for child in body:
        _odf_walk(child, out)
    md = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"


def _load_fodt(path: str) -> str:
    """Flat OpenDocument Text (single XML file)."""
    try:
        content, meta = _odf_root(path)
        md = _odt_markdown_from_root(content, meta)
        return md if md.strip() else f"# {Path(path).stem}\n\n*(empty document)*\n"
    except Exception as e:  # noqa: BLE001
        return f"# ODT Error\n\n```\n{e}\n```\n"


def _load_odt_via_xml(path: str) -> str:
    """ODT fallback reader without odfpy: walk ``content.xml`` directly."""
    return _load_fodt(path)


# ── Presentations (ODP, FODP) ───────────────────────────────────────────────


def _odp_markdown_from_root(content: ET.Element, meta: Optional[ET.Element], name: str) -> str:
    pres = content.find(f".//{_q('office', 'presentation')}")
    if pres is None:
        return ""
    out: List[str] = []
    md_meta = _odf_metadata(meta) if meta is not None else {}
    out += [f"# {md_meta.get('title') or name}", ""]
    if md_meta.get("author"):
        out += [f"*{md_meta['author']}*", ""]
    pages = list(pres.iter(_q("draw", "page")))
    for i, page in enumerate(pages, start=1):
        title = ""
        body: List[str] = []
        notes: List[str] = []
        for frame in page:
            ftag = _local(frame.tag)
            if ftag == "notes":
                for nf in frame.iter(_q("draw", "frame")):
                    box = nf.find(_q("draw", "text-box"))
                    if box is not None:
                        tmp: List[str] = []
                        for sub in box:
                            _odf_walk(sub, tmp)
                        notes += [ln for ln in tmp if ln.strip()]
                continue
            if ftag == "frame":
                cls = frame.get(_q("presentation", "class"), "")
                box = frame.find(_q("draw", "text-box"))
                if box is not None:
                    if cls in ("title", "subtitle") and not title:
                        title = " ".join(
                            _odf_inline(p).strip() for p in box if _local(p.tag) in ("p", "h")
                        ).strip()
                        continue
                    tmp = []
                    for sub in box:
                        _odf_walk(sub, tmp)
                    body += tmp
                    continue
                tbl = frame.find(_q("table", "table"))
                if tbl is not None:
                    tmp = []
                    _odf_table(tbl, tmp)
                    body += tmp
                    continue
                img = _odf_frame_inline(frame)
                if img:
                    body += [img, ""]
                continue
            if ftag in ("custom-shape", "g", "rect", "ellipse", "line", "connector"):
                tmp = []
                for sub in frame:
                    _odf_walk(sub, tmp)
                body += tmp
        page_name = page.get(_q("draw", "name"), "") or f"Slide {i}"
        heading = f"## Slide {i}: {title}" if title else f"## {page_name}"
        out += [heading, ""]
        body_lines = [ln for ln in body]
        # Turn bare paragraph lines into bullets, as the PPTX loader does.
        for ln in body_lines:
            if not ln.strip():
                continue
            if ln.startswith(("- ", "1. ", "|", "!", "#", "  ")):
                out.append(ln)
            else:
                out.append(f"- {ln}")
        out.append("")
        if notes:
            out += [f"> Note: {' '.join(n.strip() for n in notes)}", ""]
    md = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"


def _load_odp(path: str) -> str:
    """OpenDocument Presentation (``.odp``) or flat ``.fodp``."""
    try:
        content, meta = _odf_root(path)
        md = _odp_markdown_from_root(content, meta, Path(path).stem)
        return md if md.strip() else f"# {Path(path).stem}\n\n*(empty presentation)*\n"
    except Exception as e:  # noqa: BLE001
        return f"# ODP Error\n\n```\n{e}\n```\n"
