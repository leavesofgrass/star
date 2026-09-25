"""Office Open XML (DOCX/DOCM, PPTX/PPTM) → Markdown with the standard library.

python-docx / python-pptx (the base dependencies) refuse the *macro-enabled*
variants — ``.docm`` / ``.pptm`` carry a different main-part content type — and
are not present on a stdlib-only install.  This module walks the package XML
directly with :mod:`zipfile` + :mod:`xml.etree`, so those files open, and it is
the fallback when the libraries are absent or reject a file.

Word: headings from ``Heading N``/``Title`` paragraph styles, bold/italic runs,
numbered/bulleted paragraphs (``w:numPr``), tables, tabs and breaks, image
alt text (``wp:docPr``), footnotes inline.  PowerPoint: one section per slide
in ``presentation.xml`` order, the title placeholder as the heading, body
paragraphs as bullets, tables, picture alt text, and speaker notes.
"""
from .._runtime import *  # noqa: F401,F403

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
_PIC = "{http://schemas.openxmlformats.org/drawingml/2006/picture}"
_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _rels(zf: zipfile.ZipFile, part: str) -> Dict[str, str]:
    """``rId → target path`` for *part* (``word/document.xml`` → ``word/_rels/document.xml.rels``)."""
    d, _, base = part.rpartition("/")
    rel_path = f"{d}/_rels/{base}.rels" if d else f"_rels/{base}.rels"
    out: Dict[str, str] = {}
    if rel_path not in zf.namelist():
        return out
    try:
        root = ET.fromstring(zf.read(rel_path))
    except ET.ParseError:
        return out
    for r in root.iter(f"{_REL}Relationship"):
        target = r.get("Target", "")
        if r.get("TargetMode") == "External":
            continue
        if target.startswith("/"):
            path = target.lstrip("/")
        else:
            import posixpath
            path = posixpath.normpath(f"{d}/{target}" if d else target)
        out[r.get("Id", "")] = path
    return out


def _main_part(zf: zipfile.ZipFile, kind: str) -> str:
    """Path of the main document/presentation part (via ``_rels/.rels``, with the
    conventional path as fallback)."""
    conventional = "word/document.xml" if kind == "word" else "ppt/presentation.xml"
    for rid, target in _rels(zf, "").items():
        if kind == "word" and target.startswith("word/") and target.endswith(".xml") and "document" in target:
            return target
        if kind == "ppt" and target.startswith("ppt/") and target.endswith("presentation.xml"):
            return target
    return conventional


# ── Word ─────────────────────────────────────────────────────────────────────


def _w_run_text(r: ET.Element) -> str:
    parts: List[str] = []
    for child in r:
        tag = child.tag
        if tag == f"{_W}t":
            parts.append(child.text or "")
        elif tag == f"{_W}tab":
            parts.append("\t")
        elif tag in (f"{_W}br", f"{_W}cr"):
            parts.append("\n")
        elif tag == f"{_W}sym":
            parts.append("\u2022")
        elif tag == f"{_W}noBreakHyphen":
            parts.append("\u2011")
        elif tag == f"{_W}softHyphen":
            pass
        elif tag == f"{_W}footnoteReference":
            parts.append(f"[^{child.get(f'{_W}id', '')}]")
        elif tag in (f"{_W}drawing", f"{_W}pict"):
            for dp in child.iter(f"{_WP}docPr"):
                alt = (dp.get("descr") or dp.get("title") or dp.get("name") or "image").strip()
                parts.append(f"![{alt}]()")
    return "".join(parts)


def _w_para_md(p: ET.Element, styles: Dict[str, str], fig: List[int]) -> str:
    ppr = p.find(f"{_W}pPr")
    style_id = ""
    numbered = False
    ilvl = 0
    if ppr is not None:
        ps = ppr.find(f"{_W}pStyle")
        if ps is not None:
            style_id = ps.get(f"{_W}val", "")
        numpr = ppr.find(f"{_W}numPr")
        if numpr is not None:
            numbered = True
            lvl = numpr.find(f"{_W}ilvl")
            if lvl is not None:
                try:
                    ilvl = int(lvl.get(f"{_W}val", "0"))
                except ValueError:
                    ilvl = 0
    style_name = styles.get(style_id, style_id).lower()
    pieces: List[str] = []
    for node in p.iter():
        if node.tag == f"{_W}r":
            rpr = node.find(f"{_W}rPr")
            bold = italic = False
            if rpr is not None:
                b = rpr.find(f"{_W}b")
                i = rpr.find(f"{_W}i")
                bold = b is not None and b.get(f"{_W}val", "true") not in ("0", "false")
                italic = i is not None and i.get(f"{_W}val", "true") not in ("0", "false")
            t = _w_run_text(node)
            if not t:
                continue
            core = t.strip()
            if core and (bold or italic):
                lead = t[: len(t) - len(t.lstrip())]
                trail = t[len(t.rstrip()):]
                mark = "***" if bold and italic else ("**" if bold else "*")
                t = f"{lead}{mark}{core}{mark}{trail}"
            pieces.append(t)
    text = "".join(pieces)
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        return ""
    m = re.match(r"heading\s*(\d)", style_name)
    if m:
        return f"{'#' * max(1, min(6, int(m.group(1))))} {text}"
    if style_name == "title":
        return f"# {text}"
    if style_name == "subtitle":
        return f"**{text}**"
    if numbered or "list" in style_name:
        return "  " * ilvl + f"- {text}"
    if "code" in style_name or "preformat" in style_name:
        return f"    {text}"
    if "quote" in style_name:
        return f"> {text}"
    return text


def _w_table_md(tbl: ET.Element, styles: Dict[str, str], fig: List[int]) -> List[str]:
    rows: List[List[str]] = []
    for tr in tbl.findall(f"{_W}tr"):
        cells: List[str] = []
        for tc in tr.findall(f"{_W}tc"):
            paras = [_w_para_md(p, styles, fig) for p in tc.findall(f"{_W}p")]
            cells.append(" ".join(x for x in paras if x).replace("|", "\\|").replace("\n", " "))
        if cells:
            rows.append(cells)
    if not rows:
        return []
    nc = max(len(r) for r in rows)
    out = ["| " + " | ".join((rows[0] + [""] * nc)[:nc]) + " |",
           "|" + "|".join([" --- "] * nc) + "|"]
    for r in rows[1:]:
        out.append("| " + " | ".join((r + [""] * nc)[:nc]) + " |")
    out.append("")
    return out


def _w_styles(zf: zipfile.ZipFile) -> Dict[str, str]:
    """``styleId → style name`` from ``word/styles.xml`` (lower-cased names)."""
    out: Dict[str, str] = {}
    if "word/styles.xml" not in zf.namelist():
        return out
    try:
        root = ET.fromstring(zf.read("word/styles.xml"))
    except ET.ParseError:
        return out
    for st in root.iter(f"{_W}style"):
        sid = st.get(f"{_W}styleId", "")
        name = st.find(f"{_W}name")
        if sid and name is not None:
            out[sid] = (name.get(f"{_W}val") or "").lower()
    return out


def _w_footnotes(zf: zipfile.ZipFile, styles: Dict[str, str]) -> List[str]:
    if "word/footnotes.xml" not in zf.namelist():
        return []
    try:
        root = ET.fromstring(zf.read("word/footnotes.xml"))
    except ET.ParseError:
        return []
    out: List[str] = []
    for fn in root.findall(f"{_W}footnote"):
        fid = fn.get(f"{_W}id", "")
        if fn.get(f"{_W}type") in ("separator", "continuationSeparator"):
            continue
        text = " ".join(
            x for x in (_w_para_md(p, styles, [0]) for p in fn.findall(f"{_W}p")) if x
        )
        if fid and text:
            out.append(f"[^{fid}]: {text}")
    return out


def _load_docx_native(path: str) -> str:
    """DOCX/DOCM → Markdown via the package XML (no python-docx)."""
    try:
        with zipfile.ZipFile(path, "r") as zf:
            main = _main_part(zf, "word")
            if main not in zf.namelist():
                return "# DOCX Error\n\nNo document part found in the package.\n"
            root = ET.fromstring(zf.read(main))
            styles = _w_styles(zf)
            body = root.find(f"{_W}body")
            if body is None:
                return "# DOCX Error\n\nNo document body.\n"
            out: List[str] = []
            fig = [0]
            for child in body:
                if child.tag == f"{_W}p":
                    md = _w_para_md(child, styles, fig)
                    if md:
                        if md.startswith("- ") or md.startswith("  "):
                            out.append(md)
                        else:
                            out += [md, ""]
                    elif out and out[-1] != "":
                        out.append("")
                elif child.tag == f"{_W}tbl":
                    if out and out[-1] != "":
                        out.append("")
                    out += _w_table_md(child, styles, fig)
                elif child.tag == f"{_W}sdt":
                    content = child.find(f"{_W}sdtContent")
                    if content is not None:
                        for p in content.iter(f"{_W}p"):
                            md = _w_para_md(p, styles, fig)
                            if md:
                                out += [md, ""]
            notes = _w_footnotes(zf, styles)
            if notes:
                out += ["", *notes]
            md_text = "\n".join(out)
            md_text = re.sub(r"\n{3,}", "\n\n", md_text).strip()
            return (md_text + "\n") if md_text else f"# {Path(path).stem}\n\n*(empty document)*\n"
    except zipfile.BadZipFile:
        return "# DOCX Error\n\nNot a valid Office Open XML package (ZIP).\n"
    except Exception as e:  # noqa: BLE001
        return f"# DOCX Error\n\n```\n{e}\n```\n"


# ── PowerPoint ───────────────────────────────────────────────────────────────


def _a_para_text(p: ET.Element) -> str:
    parts: List[str] = []
    for child in p:
        if child.tag == f"{_A}r":
            t = child.find(f"{_A}t")
            parts.append(t.text or "" if t is not None else "")
        elif child.tag == f"{_A}br":
            parts.append("\n")
        elif child.tag == f"{_A}fld":
            t = child.find(f"{_A}t")
            parts.append(t.text or "" if t is not None else "")
    return re.sub(r"[ \t]+", " ", "".join(parts)).strip()


def _a_para_level(p: ET.Element) -> int:
    ppr = p.find(f"{_A}pPr")
    if ppr is None:
        return 0
    try:
        return int(ppr.get("lvl", "0"))
    except ValueError:
        return 0


def _slide_paths(zf: zipfile.ZipFile) -> List[str]:
    main = _main_part(zf, "ppt")
    if main not in zf.namelist():
        return []
    try:
        root = ET.fromstring(zf.read(main))
    except ET.ParseError:
        return []
    rels = _rels(zf, main)
    paths: List[str] = []
    for sid in root.iter(f"{_P}sldId"):
        rid = sid.get(f"{_R}id", "")
        target = rels.get(rid)
        if target and target in zf.namelist():
            paths.append(target)
    if not paths:
        # Fall back to numeric order of ppt/slides/slideN.xml.
        cands = [n for n in zf.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)]
        paths = sorted(cands, key=lambda n: int(re.search(r"(\d+)", n).group(1)))
    return paths


def _slide_md(zf: zipfile.ZipFile, slide_path: str, index: int) -> str:
    root = ET.fromstring(zf.read(slide_path))
    title = ""
    body: List[str] = []
    spTree = root.find(f".//{_P}cSld/{_P}spTree")
    if spTree is None:
        spTree = root
    for shape in spTree:
        tag = shape.tag
        if tag == f"{_P}sp":
            ph = shape.find(f".//{_P}nvPr/{_P}ph")
            ph_type = ph.get("type", "body") if ph is not None else ""
            paras = [(_a_para_text(p), _a_para_level(p)) for p in shape.iter(f"{_A}p")]
            paras = [(t, lvl) for t, lvl in paras if t]
            if ph_type in ("title", "ctrTitle") and not title:
                title = " ".join(t for t, _ in paras)
                continue
            for t, lvl in paras:
                body.append(f"{'  ' * lvl}- {t}")
        elif tag == f"{_P}pic":
            cnv = shape.find(f".//{_P}cNvPr")
            descr = (cnv.get("descr") or cnv.get("title") or "").strip() if cnv is not None else ""
            name = (cnv.get("name") or "").strip() if cnv is not None else ""
            body.append(f"![{descr or name or f'slide {index} image'}]()")
            if descr:
                body.append(f"*{descr}*")
        elif tag == f"{_P}graphicFrame":
            tbl = shape.find(f".//{_A}tbl")
            if tbl is not None:
                rows: List[List[str]] = []
                for tr in tbl.findall(f"{_A}tr"):
                    cells = []
                    for tc in tr.findall(f"{_A}tc"):
                        cells.append(" ".join(_a_para_text(p) for p in tc.iter(f"{_A}p")).strip().replace("|", "\\|"))
                    rows.append(cells)
                if rows:
                    nc = max(len(r) for r in rows)
                    body.append("| " + " | ".join((rows[0] + [""] * nc)[:nc]) + " |")
                    body.append("| " + " | ".join(["---"] * nc) + " |")
                    for r in rows[1:]:
                        body.append("| " + " | ".join((r + [""] * nc)[:nc]) + " |")
        elif tag == f"{_P}grpSp":
            for sp in shape.iter(f"{_P}sp"):
                for p in sp.iter(f"{_A}p"):
                    t = _a_para_text(p)
                    if t:
                        body.append(f"- {t}")
    heading = f"## Slide {index}: {title}" if title else f"## Slide {index}"
    lines = [heading]
    if body:
        lines += ["", *body]
    # Speaker notes via the slide's notesSlide relationship.
    for rid, target in _rels(zf, slide_path).items():
        if "notesSlide" in target and target in zf.namelist():
            try:
                nroot = ET.fromstring(zf.read(target))
            except ET.ParseError:
                continue
            notes: List[str] = []
            for sp in nroot.iter(f"{_P}sp"):
                ph = sp.find(f".//{_P}nvPr/{_P}ph")
                if ph is not None and ph.get("type") in ("sldNum", "hdr", "ftr", "dt", "sldImg"):
                    continue
                for p in sp.iter(f"{_A}p"):
                    t = _a_para_text(p)
                    if t:
                        notes.append(t)
            if notes:
                lines += ["", f"> Note: {' '.join(notes)}"]
            break
    return "\n".join(lines)


def _load_pptx_native(path: str) -> str:
    """PPTX/PPTM → Markdown via the package XML (no python-pptx)."""
    try:
        with zipfile.ZipFile(path, "r") as zf:
            slides = _slide_paths(zf)
            if not slides:
                return f"# {Path(path).stem}\n\n*(no slides found)*\n"
            sections = [_slide_md(zf, sp, i) for i, sp in enumerate(slides, start=1)]
            return "\n\n".join(sections) + "\n"
    except zipfile.BadZipFile:
        return "# PPTX Error\n\nNot a valid Office Open XML package (ZIP).\n"
    except Exception as e:  # noqa: BLE001
        return f"# PPTX Error\n\n```\n{e}\n```\n"


def _ooxml_kind(path: str) -> str:
    """``"word"``, ``"ppt"``, ``"xl"`` or ``""`` by sniffing the package — used to
    open a ``.zip`` that is really an Office file."""
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = set(zf.namelist())
    except Exception:  # noqa: BLE001
        return ""
    if "[Content_Types].xml" not in names:
        return ""
    if any(n.startswith("word/") for n in names):
        return "word"
    if any(n.startswith("ppt/") for n in names):
        return "ppt"
    if any(n.startswith("xl/") for n in names):
        return "xl"
    return ""
