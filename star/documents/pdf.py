"""PDF loading + column/reading-order reconstruction."""
from .._runtime import *  # noqa: F401,F403
from ..ttstext import _strip_markdown_for_tts


@dataclass(frozen=True)
class _PdfBox:
    """A laid-out text box in pdfminer coordinates (origin bottom-left, y up)."""

    text: str
    x0: float  # left
    y0: float  # bottom
    x1: float  # right
    y1: float  # top


# A bare/decorated page number in a margin: "12", "Page 12", "12 of 340", "iv".
_PDF_PAGENUM_RE = re.compile(
    r"^(?:page\s+)?\d{1,4}(?:\s*(?:/|of)\s*\d{1,4})?$|^[ivxlcdm]{1,7}$",
    re.IGNORECASE,
)

# A figure / table caption line: "Figure 3. …", "Fig. 3: …", "Table 2 …".
# Used to tag captions so they render distinctly (emphasised) from body text.
_PDF_CAPTION_RE = re.compile(
    r"^\s*(?:figure|fig\.?|table|tbl\.?|scheme|plate|chart|exhibit)\s+"
    r"\d+[.:)]?\s+\S",
    re.IGNORECASE,
)


def _pdf_mark_captions(text: str) -> str:
    """Italicise standalone figure/table caption lines in extracted PDF text.

    Detects lines that begin with a figure/table label and a number (e.g.
    ``Figure 3. Foo``) and wraps them in ``*…*`` so the display render shows
    them as captions.  Already-emphasised or blank lines are left untouched.
    This is a display-fidelity nicety only; the TTS strip removes the emphasis
    markers so speech is unaffected.
    """
    out: List[str] = []
    for ln in text.split("\n"):
        s = ln.strip()
        if s and not s.startswith("*") and _PDF_CAPTION_RE.match(s):
            out.append(f"*{s}*")
        else:
            out.append(ln)
    return "\n".join(out)


def _pdf_norm_margin(text: str) -> str:
    """Normalize a margin line so it matches across pages: lowercased,
    whitespace collapsed, digit runs → '#' (so 'Page 3' == 'Page 4')."""
    t = re.sub(r"\s+", " ", text.strip().lower())
    return re.sub(r"\d+", "#", t)


def _pdf_running_heads_feet(pages: List[List["_PdfBox"]], page_height: float) -> set:
    """Normalized text that recurs in the top/bottom margin across pages —
    i.e. running headers/footers worth suppressing."""
    if page_height <= 0 or len(pages) < 3:
        return set()
    top, bot = 0.90 * page_height, 0.10 * page_height
    counts: Dict[str, int] = {}
    for boxes in pages:
        seen = set()
        for b in boxes:
            if b.y0 >= top or b.y1 <= bot:
                key = _pdf_norm_margin(b.text)
                if key and key not in seen:
                    counts[key] = counts.get(key, 0) + 1
                    seen.add(key)
    threshold = max(3, (len(pages) + 1) // 2)
    return {k for k, c in counts.items() if c >= threshold}


def _pdf_is_running(box: "_PdfBox", page_height: float, repeating: set) -> bool:
    """True if `box` sits in a margin and is a running head/foot or page number."""
    if page_height <= 0:
        return False
    if not (box.y0 >= 0.90 * page_height or box.y1 <= 0.10 * page_height):
        return False
    if _PDF_PAGENUM_RE.match(box.text.strip()):
        return True
    return _pdf_norm_margin(box.text) in repeating


def _pdf_detect_columns(boxes: List["_PdfBox"], page_width: float) -> List[tuple]:
    """The page's column x-ranges, left→right, from a vertical projection of
    box x-extents.  A single range means single-column."""
    if not boxes or page_width <= 0:
        return [(0.0, page_width)]
    n = 200
    binw = page_width / n
    covered = [False] * n
    for b in boxes:
        lo = max(0, min(n - 1, int(b.x0 / binw)))
        hi = max(0, min(n - 1, int(b.x1 / binw)))
        for i in range(lo, hi + 1):
            covered[i] = True
    regions: List[list] = []
    i = 0
    while i < n:
        if covered[i]:
            j = i
            while j < n and covered[j]:
                j += 1
            regions.append([i * binw, j * binw])
            i = j
        else:
            i += 1
    if not regions:
        return [(0.0, page_width)]
    gutter = 0.04 * page_width  # a real column gutter is at least this wide
    merged = [regions[0]]
    for lo, hi in regions[1:]:
        if lo - merged[-1][1] < gutter:
            merged[-1][1] = hi
        else:
            merged.append([lo, hi])
    return [(lo, hi) for lo, hi in merged]


def _pdf_order_boxes(boxes: List["_PdfBox"], page_width: float) -> List["_PdfBox"]:
    """Reading order for one page: column-by-column, top-to-bottom.  Full-width
    boxes (titles, spanning figures) act as band dividers that interrupt the
    column flow at their vertical position."""
    boxes = [b for b in boxes if b.text.strip()]
    if len(boxes) <= 1:
        return sorted(boxes, key=lambda b: (-b.y1, b.x0))
    full_w = 0.55 * page_width if page_width > 0 else float("inf")
    full = [b for b in boxes if (b.x1 - b.x0) >= full_w]
    cols = [b for b in boxes if (b.x1 - b.x0) < full_w]
    ranges = _pdf_detect_columns(cols, page_width)
    if len(ranges) <= 1:
        return sorted(boxes, key=lambda b: (-b.y1, b.x0))  # single column
    centers = [(lo + hi) / 2 for lo, hi in ranges]

    def col_index(b: "_PdfBox") -> int:
        cx = (b.x0 + b.x1) / 2
        for i, (lo, hi) in enumerate(ranges):
            if lo <= cx <= hi:
                return i
        return min(range(len(ranges)), key=lambda i: abs(cx - centers[i]))

    div_centers = sorted(((b.y0 + b.y1) / 2 for b in full), reverse=True)

    def band(b: "_PdfBox") -> int:
        cy = (b.y0 + b.y1) / 2
        return sum(1 for dc in div_centers if dc > cy)

    full_ids = {id(b) for b in full}

    def key(b: "_PdfBox") -> tuple:
        is_div = id(b) in full_ids
        # (band, dividers-after-their-band's-columns, column, top→bottom, left→right)
        return (band(b), 1 if is_div else 0, 0 if is_div else col_index(b), -b.y1, b.x0)

    return sorted(boxes, key=key)


def _load_pdf(path: str, reconstruct: bool = True, ocr_lang: str = "eng") -> str:
    if not _PDF and not (_OCR and _PYMUPDF):
        return (
            "# PDF support not available\n\n"
            "Install pdfminer.six:  `pip install pdfminer.six`\n"
            "For image/scanned PDFs also install:  `pip install pytesseract pymupdf`\n"
        )
    try:
        if _PDF == "layout":
            extract_pages, LTTextBoxHorizontal = _load_pdf_pages()
            # First pass: collect each page's boxes (+ OCR text for image pages).
            collected: List[dict] = []
            for pnum, page in enumerate(extract_pages(path), 1):
                boxes = [
                    _PdfBox(
                        el.get_text().strip(),
                        float(el.x0), float(el.y0), float(el.x1), float(el.y1),
                    )
                    for el in page
                    if isinstance(el, LTTextBoxHorizontal) and el.get_text().strip()
                ]
                ocr_text = None
                if not boxes and _OCR and _PYMUPDF:
                    fitz = _load_fitz()
                    pytesseract, Image = _load_ocr()
                    doc = fitz.open(path)
                    pix = doc[pnum - 1].get_pixmap(matrix=fitz.Matrix(2, 2))
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    doc.close()
                    ocr_text = pytesseract.image_to_string(
                        img, lang=ocr_lang or "eng"
                    ).strip()
                collected.append({
                    "pnum": pnum,
                    "boxes": boxes,
                    "w": float(getattr(page, "width", 0) or 0),
                    "h": float(getattr(page, "height", 0) or 0),
                    "ocr": ocr_text,
                })
            heights = [c["h"] for c in collected if c["h"] > 0]
            rep_h = max(heights) if heights else 0.0
            repeating = (
                _pdf_running_heads_feet([c["boxes"] for c in collected], rep_h)
                if reconstruct else set()
            )
            # Second pass: assemble text.  reconstruct → column-aware order with
            # running heads/feet stripped; raw → pdfminer's native box order.
            parts: List[str] = []
            for c in collected:
                parts.append(f"\n---\n*Page {c['pnum']}*\n")
                if c["ocr"] is not None:
                    parts.append(c["ocr"])
                    continue
                page_boxes = c["boxes"]
                if reconstruct:
                    h = c["h"] or rep_h
                    page_boxes = [
                        b for b in page_boxes if not _pdf_is_running(b, h, repeating)
                    ]
                    page_boxes = _pdf_order_boxes(page_boxes, c["w"])
                parts.extend(b.text for b in page_boxes)
            assembled = "\n".join(parts)
            return _pdf_mark_captions(assembled) if reconstruct else assembled
        elif _PDF == "simple":
            extract_text = _load_pdf_text()
            return _strip_markdown_for_tts(extract_text(path) or "")
        elif _OCR and _PYMUPDF:
            fitz = _load_fitz()
            pytesseract, Image = _load_ocr()
            doc = fitz.open(path)
            parts = []
            for pnum, page in enumerate(doc, 1):
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                parts.append(
                    f"\n---\n*Page {pnum}*\n\n"
                    + pytesseract.image_to_string(img, lang=ocr_lang or "eng").strip()
                )
            doc.close()
            return "\n".join(parts)
    except Exception as e:
        return f"# PDF Error\n\n```\n{e}\n```\n"
    return "# PDF Error\n\nUnknown failure.\n"
