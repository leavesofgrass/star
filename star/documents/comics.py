"""Comic book archives (``.cbz`` ZIP, ``.cbr`` RAR) → Markdown.

A comic archive is a bag of page images and no text at all.  Pages are listed
in natural (numeric-aware) order — ``page10.jpg`` after ``page2.jpg`` — and,
when OCR is installed (pytesseract + Pillow, the ``[ocr]`` extra), every page
is run through it so speech bubbles and captions can be read aloud, exactly as
a scanned PDF is.  Without OCR the document is a page index with the image
references and a one-line install hint, so the file still opens.

Comic archives get renamed between .cbz and .cbr by people sorting their
shelves, so the container is sniffed by magic bytes rather than trusted by
extension (a "``.cbr``" that is really a ZIP opens without ``rarfile``).
"""
from .._runtime import *  # noqa: F401,F403

_PAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".avif", ".tif", ".tiff"})


def _natural_key(name: str) -> list:
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def _is_page(name: str) -> bool:
    n = name.replace("\\", "/")
    base = n.rsplit("/", 1)[-1]
    if base.startswith(".") or "__MACOSX" in n or n.endswith("/"):
        return False
    return Path(base).suffix.lower() in _PAGE_EXTS


def _container_kind(path: str) -> str:
    """``"zip"``, ``"rar"`` or ``""`` from the magic bytes (extension as a fallback)."""
    try:
        with open(path, "rb") as fh:
            magic = fh.read(8)
    except OSError:
        return ""
    if magic[:2] == b"PK":
        return "zip"
    if magic[:4] == b"Rar!":
        return "rar"
    if magic[:6] == b"7z\xbc\xaf\x27\x1c":
        return "7z"
    ext = Path(path).suffix.lower()
    return {"cbz": "zip", "cbr": "rar", "cb7": "7z"}.get(ext[1:], "")


def _comic_pages(path: str) -> "Tuple[str, List[str], Callable[[str], bytes]]":
    """``(kind, ordered page names, reader)`` for the archive at *path*.

    Raises ``RuntimeError`` with an install hint when the RAR/7z reader is absent.
    """
    kind = _container_kind(path)
    if kind == "zip":
        zf = zipfile.ZipFile(path, "r")
        names = sorted((n for n in zf.namelist() if _is_page(n)), key=_natural_key)
        return kind, names, zf.read
    if kind == "rar":
        try:
            import rarfile  # type: ignore[import]
        except ImportError:
            raise RuntimeError(
                "rarfile is required to open .cbr comic archives.\n"
                'Install: pip install rarfile  or  pip install "star-reader[archive]"'
            )
        rf = rarfile.RarFile(path)
        names = sorted((n for n in rf.namelist() if _is_page(n)), key=_natural_key)
        return kind, names, rf.read
    if kind == "7z":
        try:
            import py7zr  # type: ignore[import]
        except ImportError:
            raise RuntimeError(
                "py7zr is required to open .cb7 comic archives.\n"
                'Install: pip install py7zr  or  pip install "star-reader[archive]"'
            )
        sz = py7zr.SevenZipFile(path, mode="r")
        names = sorted((n for n in sz.getnames() if _is_page(n)), key=_natural_key)

        def _read(member: str) -> bytes:
            with tempfile.TemporaryDirectory() as td:
                sz.extract(path=td, targets=[member])
                return (Path(td) / member).read_bytes()

        return kind, names, _read
    raise ValueError("Not a ZIP or RAR comic archive")


def _ocr_page(data: bytes, lang: str) -> str:
    """OCR one page image; empty string when OCR is unavailable or fails."""
    if not _OCR:
        return ""
    try:
        import io

        pytesseract, Image = _load_ocr()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        return pytesseract.image_to_string(img, lang=lang or "eng").strip()
    except Exception:  # noqa: BLE001
        return ""


def _load_comic(path: str, lang: str = "eng", ocr: "Optional[bool]" = None) -> str:
    """Load a comic archive as one section per page (OCR text when available)."""
    try:
        kind, names, read = _comic_pages(path)
    except RuntimeError as e:
        return f"# {Path(path).stem}\n\n**{e}**\n"
    except Exception as e:  # noqa: BLE001
        return f"# Comic Error\n\n```\n{e}\n```\n"
    title = Path(path).stem
    if not names:
        return f"# {title}\n\n*This comic archive contains no page images.*\n"
    use_ocr = bool(_OCR) if ocr is None else bool(ocr and _OCR)
    out: List[str] = [f"# {title}", "", f"*{len(names)} pages*", ""]
    if not use_ocr:
        out += [
            "> Comic pages are images. Install OCR (`pip install \"star-reader[ocr]\"` "
            "plus the Tesseract engine) and reopen to read the text on each page.",
            "",
        ]
    for i, name in enumerate(names, start=1):
        out += [f"## Page {i}", ""]
        out.append(f"![Page {i}]({name})")
        if use_ocr:
            try:
                text = _ocr_page(read(name), lang)
            except Exception:  # noqa: BLE001
                text = ""
            if text:
                out += ["", text]
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def _comic_page_names(path: str) -> List[str]:
    """Ordered page names (for tests and the chapter list); empty on any failure."""
    try:
        return _comic_pages(path)[1]
    except Exception:  # noqa: BLE001
        return []
