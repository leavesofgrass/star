"""Office formats: DOCX/DOC, PPTX, XLSX, CSV/TSV, ODT."""
from .._runtime import *  # noqa: F401,F403
from .pandoc import _load_via_pandoc


def _load_csv_tsv(path: str, delim: str = ",") -> str:
    """Render CSV or TSV as a Markdown table."""
    try:
        rows: List[List[str]] = []
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            reader = csv.reader(fh, delimiter=delim)
            for row in reader:
                rows.append(row)
        if not rows:
            return "*(empty file)*\n"
        nc = max(len(r) for r in rows)
        out: List[str] = [f"# {Path(path).name}", ""]
        hdr = (rows[0] + [""] * nc)[:nc]
        out.append("| " + " | ".join(h.replace("|", "\\|") for h in hdr) + " |")
        out.append("|" + "|".join([" --- "] * nc) + "|")
        for row in rows[1:]:
            cells = (row + [""] * nc)[:nc]
            out.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
        return "\n".join(out)
    except Exception as e:
        return f"# Error loading {Path(path).suffix.upper()}\n\n```\n{e}\n```\n"


def _load_xlsx(path: str) -> str:
    """Render XLSX spreadsheet as Markdown tables, one per sheet."""
    if not _XLSX:
        return (
            "# XLSX support not available\n\n"
            "Install openpyxl:  `pip install openpyxl`\n"
        )
    try:
        wb = _load_openpyxl().load_workbook(path, read_only=True, data_only=True)
        parts: List[str] = [f"# {Path(path).name}", ""]
        for ws in wb.worksheets:
            parts.append(f"## {ws.title}")
            parts.append("")
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                parts.append("*(empty sheet)*")
                parts.append("")
                continue
            nc = max(len(r) for r in rows)

            def _cell(v: Any) -> str:
                return str(v) if v is not None else ""

            hdr = [_cell(c) for c in (rows[0] + (None,) * nc)[:nc]]
            parts.append("| " + " | ".join(hdr) + " |")
            parts.append("|" + "|".join([" --- "] * nc) + "|")
            for row in rows[1:]:
                cells = [_cell(c) for c in (list(row) + [None] * nc)[:nc]]
                parts.append("| " + " | ".join(cells) + " |")
            parts.append("")
        return "\n".join(parts)
    except Exception as e:
        return f"# XLSX Error\n\n```\n{e}\n```\n"


def _load_docx(path: str) -> str:
    if not _DOCX:
        return (
            "# DOCX support not available\n\n"
            "Install python-docx:  `pip install python-docx`\n"
        )
    try:
        doc = _load_docx().Document(path)
        out: List[str] = []
        for para in doc.paragraphs:
            sn = para.style.name.lower()
            txt = para.text
            if not txt.strip():
                out.append("")
                continue
            if "heading 1" in sn:
                out.append(f"# {txt}")
            elif "heading 2" in sn:
                out.append(f"## {txt}")
            elif "heading 3" in sn:
                out.append(f"### {txt}")
            elif "heading 4" in sn:
                out.append(f"#### {txt}")
            elif "heading" in sn:
                out.append(f"##### {txt}")
            elif "list" in sn:
                out.append(f"* {txt}")
            elif "code" in sn or "preformat" in sn:
                out.append(f"    {txt}")
            else:
                rich = ""
                for run in para.runs:
                    rt = run.text
                    if not rt:
                        continue
                    if run.bold and run.italic:
                        rt = f"***{rt}***"
                    elif run.bold:
                        rt = f"**{rt}**"
                    elif run.italic:
                        rt = f"*{rt}*"
                    rich += rt
                out.append(rich)
        for tbl in doc.tables:
            out.append("")
            for ri, row in enumerate(tbl.rows):
                cells = [c.text.replace("\n", " ").strip() for c in row.cells]
                out.append("| " + " | ".join(cells) + " |")
                if ri == 0:
                    out.append("|" + "|".join([" --- "] * len(cells)) + "|")
            out.append("")
        return "\n".join(out)
    except Exception as e:
        return f"# DOCX Error\n\n```\n{e}\n```\n"


def _load_doc(path: str) -> str:
    """Load a legacy binary Word (.doc / .dot) file as Markdown.

    Tries four approaches in order of preference:

    1. **python-docx** — works when the file is actually OOXML saved with a
       .doc extension (common with modern versions of Word on Windows).
    2. **antiword** subprocess — the lightweight dedicated converter for the
       true binary Word 97-2003 format.  Free binary available for Windows at
       https://www.winfield.demon.nl/  — add to PATH to enable.
    3. **LibreOffice headless** — converts .doc → .docx in a temp directory,
       then loads with python-docx.  Works if LibreOffice is installed.
    4. **Pandoc** — delegates to the existing _load_via_pandoc() helper.

    If none of these succeed a human-readable error with install instructions
    is returned.
    """
    title = Path(path).stem

    # ── 1. python-docx (file may be OOXML despite the .doc extension) ───────
    if _DOCX:
        try:
            md = _load_docx(path)
            if not md.startswith(("# DOCX Error", "# DOCX support")):
                return md
        except Exception:
            pass

    # ── 2. antiword ───────────────────────────────────────────────────
    antiword_bin = shutil.which("antiword") or shutil.which("antiword.exe")
    if antiword_bin:
        try:
            result = subprocess.run(
                [antiword_bin, "-w", "0", path],
                capture_output=True,
                timeout=30,
            )
            if result.returncode == 0:
                text = result.stdout.decode("utf-8", errors="replace").strip()
                if text:
                    return f"# {title}\n\n{text}\n"
        except Exception:
            pass

    # ── 3. LibreOffice headless (doc → docx → python-docx) ─────────────────
    lo_candidates: List[str] = ["soffice", "libreoffice"]
    if sys.platform == "win32":
        lo_candidates += [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
    lo_bin = next(
        (b for b in lo_candidates if shutil.which(b) or Path(b).exists()),
        None,
    )
    if lo_bin and _DOCX:
        try:
            import tempfile as _tmpmod

            with _tmpmod.TemporaryDirectory() as tmpdir:
                result = subprocess.run(
                    [
                        lo_bin,
                        "--headless",
                        "--convert-to",
                        "docx",
                        "--outdir",
                        tmpdir,
                        path,
                    ],
                    capture_output=True,
                    timeout=60,
                )
                if result.returncode == 0:
                    docx_path = Path(tmpdir) / (Path(path).stem + ".docx")
                    if docx_path.exists():
                        md = _load_docx(str(docx_path))
                        if not md.startswith(("# DOCX Error", "# DOCX support")):
                            return md
        except Exception:
            pass

    # ── 4. Pandoc ──────────────────────────────────────────────────────
    pandoc_md = _load_via_pandoc(path)
    if pandoc_md:
        return pandoc_md

    # ── Nothing worked ──────────────────────────────────────────────────
    return (
        f"# {title}\n\n"
        "**Could not load this binary Word (.doc) file.**\n\n"
        "Install one of the following to add .doc support:\n\n"
        "- **antiword** (lightest option): "
        "download the Windows binary from https://www.winfield.demon.nl/ "
        "and add it to your PATH\n"
        "- **LibreOffice** (also enables ODT/ODP/ODS conversion): "
        "https://www.libreoffice.org/\n"
        "- **Pandoc** + LibreOffice: `pip install pypandoc` then install "
        "Pandoc from https://pandoc.org/\n"
    )


def _load_pptx(path: str) -> str:
    """Load a PowerPoint .pptx file as Markdown.

    Each slide becomes a section with its title as a heading.
    Body text, bullet points, and speaker notes are included.
    Requires: pip install python-pptx
    """
    if not _PPTX:
        return (
            "Could not load PowerPoint file: python-pptx is not installed.\n"
            "Install it with: pip install python-pptx"
        )

    prs = _load_pptx().Presentation(path)
    sections = []

    for slide_num, slide in enumerate(prs.slides, start=1):
        title_text = ""
        body_parts = []

        for shape in slide.shapes:
            # Images (MSO_SHAPE_TYPE.PICTURE == 13)
            if shape.shape_type == 13:
                alt = getattr(shape, "name", f"slide {slide_num} image")
                body_parts.append(f"[Image: {alt}]")
                continue

            # Tables
            if hasattr(shape, "table"):
                tbl = shape.table
                md_rows = []
                for row_idx, row in enumerate(tbl.rows):
                    cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                    md_rows.append("| " + " | ".join(cells) + " |")
                    if row_idx == 0:
                        md_rows.append("| " + " | ".join(["---"] * len(cells)) + " |")
                body_parts.append("\n".join(md_rows))
                continue

            if not shape.has_text_frame:
                continue

            is_title = (
                hasattr(shape, "placeholder_format")
                and shape.placeholder_format is not None
                and shape.placeholder_format.idx == 0
            )

            if is_title:
                title_text = shape.text_frame.text.strip()
            else:
                for para in shape.text_frame.paragraphs:
                    txt = para.text.strip()
                    if not txt:
                        continue
                    indent = "  " * para.level if para.level else ""
                    body_parts.append(f"{indent}- {txt}")

        heading = (
            f"## Slide {slide_num}: {title_text}"
            if title_text
            else f"## Slide {slide_num}"
        )
        slide_md = [heading]
        if body_parts:
            slide_md.append("")
            slide_md.extend(body_parts)

        if slide.has_notes_slide:
            notes_text = slide.notes_slide.notes_text_frame.text.strip()
            if notes_text:
                slide_md.append("")
                slide_md.append(f"> Note: {notes_text}")

        sections.append("\n".join(slide_md))

    return "\n\n".join(sections)


def _load_odt_v2(path: str) -> str:
    """Load an ODT (OpenDocument Text) file to Markdown.

    Uses odfpy if available for full fidelity; otherwise falls back to
    Pandoc (if installed) or raw XML extraction.
    Supports headings, paragraphs, lists, tables, footnotes.
    """
    if _ODT:
        return _load_odt_via_odfpy(path)

    # Pandoc fallback (prefer the bundled binary, then PATH)
    try:
        import subprocess

        result = subprocess.run(
            [_PANDOC_BIN or "pandoc", "-f", "odt", "-t", "markdown", path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except (FileNotFoundError, OSError):
        pass

    return _load_odt_raw_xml(path)


def _load_odt_via_odfpy(path: str) -> str:
    """Parse an ODT document via the odfpy library, converting to Markdown."""
    from odf.element import Element  # type: ignore  # noqa: F401
    from odf.opendocument import load as odf_load  # type: ignore

    doc = odf_load(path)
    lines: list = []
    footnotes: dict = {}
    fn_counter = [0]

    def get_text(elem) -> str:
        if not hasattr(elem, "childNodes"):
            return getattr(elem, "data", "")
        tag = elem.qname[1] if hasattr(elem, "qname") else ""
        if tag == "s":
            return " " * int(elem.getAttribute("text:c") or 1)
        if tag == "tab":
            return "\t"
        if tag == "line-break":
            return "\n"
        return "".join(get_text(c) for c in elem.childNodes)

    def walk(node, list_depth: int = 0):
        if not hasattr(node, "qname"):
            return
        tag = node.qname[1]

        if tag == "h":
            level = int(node.getAttribute("text:outline-level") or 1)
            lines.append("#" * level + " " + get_text(node).strip())
            lines.append("")

        elif tag == "p":
            txt = get_text(node).strip()
            if txt:
                if list_depth:
                    lines.append("  " * (list_depth - 1) + "- " + txt)
                else:
                    lines.append(txt)
                    lines.append("")

        elif tag == "list":
            for child in node.childNodes:
                if hasattr(child, "qname") and child.qname[1] == "list-item":
                    for sub in child.childNodes:
                        walk(sub, list_depth + 1)

        elif tag == "table":
            _odt_table_to_md(node, lines, get_text)

        elif tag == "note":
            fn_counter[0] += 1
            label = str(fn_counter[0])
            body_text = ""
            for child in node.childNodes:
                if hasattr(child, "qname") and child.qname[1] == "note-body":
                    body_text = get_text(child).strip()
            footnotes[label] = body_text
            if lines:
                lines[-1] = lines[-1] + f"[^{label}]"

        else:
            for child in node.childNodes:
                walk(child, list_depth)

    for child in doc.text.childNodes:
        walk(child)

    if footnotes:
        lines += ["", "## Footnotes", ""]
        for label, note_text in footnotes.items():
            lines.append(f"[^{label}]: {note_text}")

    return "\n".join(lines)


def _odt_table_to_md(table_node, lines: list, get_text_fn) -> None:
    """Convert an ODF table element to Markdown table rows, appended to lines."""
    rows = []
    for child in table_node.childNodes:
        if not hasattr(child, "qname"):
            continue
        if child.qname[1] == "table-row":
            cells = []
            for cell in child.childNodes:
                if hasattr(cell, "qname") and cell.qname[1] in (
                    "table-cell",
                    "covered-table-cell",
                ):
                    cells.append(get_text_fn(cell).strip().replace("\n", " "))
            rows.append(cells)

    if not rows:
        return
    col_count = max(len(r) for r in rows)
    lines.append("")
    for i, row in enumerate(rows):
        padded = row + [""] * (col_count - len(row))
        lines.append("| " + " | ".join(padded) + " |")
        if i == 0:
            lines.append("| " + " | ".join(["---"] * col_count) + " |")
    lines.append("")


def _load_odt_raw_xml(path: str) -> str:
    """Fallback ODT reader: extract text via raw ZIP + regex XML stripping."""
    import zipfile

    try:
        with zipfile.ZipFile(path, "r") as zf:
            content = zf.read("content.xml").decode("utf-8", errors="replace")
    except (KeyError, zipfile.BadZipFile) as exc:
        return f"[Could not read ODT file: {exc}]"

    text = re.sub(
        r"<text:h[^>]*>(.*?)</text:h[^>]*>", r"\n\n\1\n", content, flags=re.DOTALL
    )
    text = re.sub(r"<text:p[^>]*/>", "\n", text)
    text = re.sub(r"<text:p[^>]*>(.*?)</text:p>", r"\1\n", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
