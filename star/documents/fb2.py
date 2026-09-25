"""FictionBook 2 (``.fb2``) → Markdown, on the standard library alone.

FB2 is a plain XML e-book format popular in Russian-language libraries.  The
document is ``<FictionBook>`` → ``<description>`` (metadata) + one or more
``<body>`` elements holding nested ``<section>``s of ``<p>`` paragraphs, with
``<title>``/``<subtitle>`` headings, ``<epigraph>``/``<cite>`` block quotes,
``<poem>`` stanzas, ``<table>``s, ``<image>`` references and inline
``<emphasis>``/``<strong>``/``<a>`` markup.  A second ``<body name="notes">``
holds footnotes that in-text ``<a type="note">`` links point at.

Pandoc reads FB2 too and is preferred when installed (``prefer_pandoc``); this
loader is the zero-dependency fallback and the path when Pandoc is absent.  A
``.fb2.zip`` bundle is handled by the archive/zip sniffing in ``dispatch``.
"""
from .._runtime import *  # noqa: F401,F403

_XLINK = "{http://www.w3.org/1999/xlink}"


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _inline(elem: ET.Element) -> str:
    """Flatten an inline container (``<p>``, ``<v>``, ``<td>`` …) to Markdown text."""
    parts: List[str] = [elem.text or ""]
    for child in elem:
        tag = _local(child.tag)
        inner = _inline(child)
        if tag == "emphasis":
            parts.append(f"*{inner}*" if inner.strip() else inner)
        elif tag == "strong":
            parts.append(f"**{inner}**" if inner.strip() else inner)
        elif tag == "strikethrough":
            parts.append(f"~~{inner}~~" if inner.strip() else inner)
        elif tag == "code":
            parts.append(f"`{inner}`" if inner.strip() else inner)
        elif tag in ("sup", "sub"):
            parts.append(inner)
        elif tag == "a":
            href = child.get(f"{_XLINK}href", "") or child.get("href", "")
            if child.get("type") == "note" and href.startswith("#"):
                parts.append(f"[^{href[1:]}]")
            elif href and not href.startswith("#"):
                parts.append(f"[{inner}]({href})" if inner.strip() else href)
            else:
                parts.append(inner)
        elif tag == "image":
            alt = child.get("alt") or child.get("title") or "image"
            parts.append(f"![{alt}]({child.get(f'{_XLINK}href', '')})")
        else:
            parts.append(inner)
        parts.append(child.tail or "")
    return re.sub(r"[ \t\r\n]+", " ", "".join(parts))


def _title_text(elem: ET.Element) -> str:
    """A ``<title>`` holds ``<p>`` lines (and ``<empty-line/>``s); join them."""
    lines = [_inline(p).strip() for p in elem if _local(p.tag) == "p"]
    lines = [ln for ln in lines if ln]
    if not lines:
        t = _inline(elem).strip()
        return t
    return " ".join(lines)


def _walk(elem: ET.Element, out: List[str], depth: int, quote: int = 0) -> None:
    """Render a block-level FB2 element into *out* (Markdown lines)."""
    q = "> " * quote
    tag = _local(elem.tag)
    if tag == "section":
        for child in elem:
            _walk(child, out, depth + 1, quote)
        return
    if tag == "title":
        text = _title_text(elem)
        if text:
            level = max(1, min(6, depth))
            out += [f"{q}{'#' * level} {text}", ""]
        return
    if tag == "subtitle":
        text = _inline(elem).strip()
        if text:
            out += [f"{q}**{text}**", ""]
        return
    if tag == "p":
        text = _inline(elem).strip()
        if text:
            out += [f"{q}{text}", ""]
        return
    if tag == "empty-line":
        out.append("")
        return
    if tag in ("epigraph", "cite", "annotation"):
        for child in elem:
            ct = _local(child.tag)
            if ct == "text-author":
                text = _inline(child).strip()
                if text:
                    out += [f"{q}> — {text}", ""]
            else:
                _walk(child, out, depth, quote + 1)
        return
    if tag == "poem":
        for child in elem:
            ct = _local(child.tag)
            if ct == "title":
                text = _title_text(child)
                if text:
                    out += [f"{q}**{text}**", ""]
            elif ct == "stanza":
                verses = [_inline(v).strip() for v in child if _local(v.tag) == "v"]
                verses = [v for v in verses if v]
                if verses:
                    # Two trailing spaces keep the line breaks inside the stanza.
                    out += [f"{q}{v}  " for v in verses] + [""]
            elif ct == "text-author":
                text = _inline(child).strip()
                if text:
                    out += [f"{q}— {text}", ""]
            elif ct == "date":
                text = _inline(child).strip()
                if text:
                    out += [f"{q}*{text}*", ""]
        return
    if tag == "table":
        rows: List[List[str]] = []
        for tr in elem:
            if _local(tr.tag) != "tr":
                continue
            rows.append(
                [
                    _inline(td).strip().replace("|", "\\|")
                    for td in tr
                    if _local(td.tag) in ("td", "th")
                ]
            )
        rows = [r for r in rows if r]
        if rows:
            nc = max(len(r) for r in rows)
            out.append(f"{q}| " + " | ".join((rows[0] + [""] * nc)[:nc]) + " |")
            out.append(f"{q}|" + "|".join([" --- "] * nc) + "|")
            for r in rows[1:]:
                out.append(f"{q}| " + " | ".join((r + [""] * nc)[:nc]) + " |")
            out.append("")
        return
    if tag == "image":
        alt = elem.get("alt") or elem.get("title") or "image"
        out += [f"{q}![{alt}]({elem.get(f'{_XLINK}href', '')})", ""]
        return
    if tag in ("text-author", "date"):
        text = _inline(elem).strip()
        if text:
            out += [f"{q}*{text}*", ""]
        return
    if tag == "v":
        text = _inline(elem).strip()
        if text:
            out += [f"{q}{text}  "]
        return
    # Unknown container: descend.
    for child in elem:
        _walk(child, out, depth, quote)


def _fb2_metadata(root: ET.Element) -> Dict[str, str]:
    meta: Dict[str, str] = {}
    for e in root.iter():
        tag = _local(e.tag)
        if tag == "title-info":
            for c in e.iter():
                ct = _local(c.tag)
                if ct == "book-title" and c.text and "title" not in meta:
                    meta["title"] = c.text.strip()
                elif ct == "author" and "author" not in meta:
                    names = [
                        (n.text or "").strip()
                        for n in c
                        if _local(n.tag) in ("first-name", "middle-name", "last-name")
                    ]
                    nick = next(
                        ((n.text or "").strip() for n in c if _local(n.tag) == "nickname"),
                        "",
                    )
                    author = " ".join(n for n in names if n) or nick
                    if author:
                        meta["author"] = author
                elif ct == "lang" and c.text and "language" not in meta:
                    meta["language"] = c.text.strip()
                elif ct == "genre" and c.text and "genre" not in meta:
                    meta["genre"] = c.text.strip()
            break
    return meta


def _fb2_to_markdown(root: ET.Element) -> Tuple[str, Dict[str, str]]:
    meta = _fb2_metadata(root)
    out: List[str] = []
    if meta.get("title"):
        out += [f"# {meta['title']}", ""]
    if meta.get("author"):
        out += [f"*{meta['author']}*", ""]
    # Annotation (blurb) from the description block.
    for e in root.iter():
        if _local(e.tag) == "annotation":
            before = len(out)
            _walk(e, out, 1, 0)
            if len(out) > before:
                out += ["---", ""]
            break
    footnotes: List[str] = []
    for body in root:
        if _local(body.tag) != "body":
            continue
        if (body.get("name") or "").lower() in ("notes", "footnotes", "comments"):
            for sec in body:
                if _local(sec.tag) != "section":
                    continue
                sid = sec.get("id", "")
                text_lines: List[str] = []
                for child in sec:
                    if _local(child.tag) == "title":
                        continue
                    _walk(child, text_lines, 2, 0)
                text = " ".join(ln.strip() for ln in text_lines if ln.strip())
                if sid and text:
                    footnotes.append(f"[^{sid}]: {text}")
            continue
        if out and out[-1] != "":
            out.append("")
        for child in body:
            # A body-level <title> is the book/part title; sections nest below.
            # Skip it when it merely repeats the metadata title already emitted.
            if _local(child.tag) == "title" and meta.get("title") and \
                    _title_text(child).strip().lower() == meta["title"].strip().lower():
                continue
            _walk(child, out, 1, 0)
    if footnotes:
        out += ["", *footnotes]
    md = "\n".join(out)
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"
    return md, meta


def _load_fb2(path: str) -> str:
    """Load a FictionBook 2 file (plain XML, or the same inside a ``.fb2.zip``)."""
    try:
        data = Path(path).read_bytes()
        if data[:2] == b"PK":
            with zipfile.ZipFile(path, "r") as zf:
                inner = next(
                    (n for n in zf.namelist() if n.lower().endswith(".fb2")), None
                )
                if inner is None:
                    return "# FB2 Error\n\nNo .fb2 file inside this ZIP.\n"
                data = zf.read(inner)
        root = ET.fromstring(data)
        if _local(root.tag) != "FictionBook":
            return "# FB2 Error\n\nNot a FictionBook document.\n"
        md, _meta = _fb2_to_markdown(root)
        return md
    except ET.ParseError as e:
        return f"# FB2 Error\n\n```\n{e}\n```\n"
    except Exception as e:  # noqa: BLE001 — loader must never raise into the UI
        return f"# FB2 Error\n\n```\n{e}\n```\n"


def _fb2_chapters(path: str) -> "List[Tuple[str, str]]":
    """``(title, anchor)`` pairs for every titled top-level section, for the
    chapter navigation list."""
    try:
        data = Path(path).read_bytes()
        if data[:2] == b"PK":
            with zipfile.ZipFile(path, "r") as zf:
                inner = next((n for n in zf.namelist() if n.lower().endswith(".fb2")), None)
                if inner is None:
                    return []
                data = zf.read(inner)
        root = ET.fromstring(data)
    except Exception:  # noqa: BLE001
        return []
    chapters: List[Tuple[str, str]] = []
    for body in root:
        if _local(body.tag) != "body" or body.get("name"):
            continue
        for sec in body:
            if _local(sec.tag) != "section":
                continue
            title = next(
                (_title_text(c) for c in sec if _local(c.tag) == "title"), ""
            )
            if title:
                chapters.append((title, sec.get("id", "") or title))
    return chapters
