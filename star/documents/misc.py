"""Image/OCR, URL fetch, footnote processing, archive bookkeeping."""
from .._runtime import *  # noqa: F401,F403
from .html import _load_html_str
from .pdf import _load_pdf


def _load_image_ocr(path: str) -> str:
    if not _OCR:
        return (
            "# OCR support not available\n\n"
            "Install pytesseract:  `pip install pytesseract`\n"
            "Also install Tesseract binary: https://github.com/tesseract-ocr/tesseract\n"
        )
    try:
        pytesseract, Image = _load_ocr()
        img = Image.open(path).convert("RGB")
        text = pytesseract.image_to_string(img)
        return f"# {Path(path).name}\n\n{text.strip()}\n"
    except Exception as e:
        return f"# OCR Error\n\n```\n{e}\n```\n"


def _load_url(url: str) -> str:
    """Fetch a URL and convert to markdown."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": f"star/{APP_VERSION} (text reader; {sys.platform})"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            ct = resp.headers.get("Content-Type", "text/html")
            raw = resp.read()
            encoding = "utf-8"
            enc_m = re.search(r"charset=([^\s;]+)", ct)
            if enc_m:
                encoding = enc_m.group(1).strip("\"'")
            text = raw.decode(encoding, errors="replace")

        if "text/html" in ct or "xhtml" in ct:
            return _load_html_str(text)
        elif "text/plain" in ct or "markdown" in ct:
            return text
        elif "application/pdf" in ct:
            tmp = CACHE_DIR / "download.pdf"
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(raw)
            return _load_pdf(str(tmp))
        else:
            return text
    except urllib.error.URLError as e:
        return f"# URL Error\n\n```\n{e}\n```\n"
    except Exception as e:
        return f"# Fetch Error\n\n```\n{e}\n```\n"


def _process_footnotes(md: str, mode: str = "inline") -> str:
    """Handle Pandoc/GitHub-style Markdown footnotes for TTS.

    mode="inline":   insert footnote text at point of reference
    mode="deferred": collect footnotes and append at end of document
    mode="skip":     remove all footnote markers and content silently

    Supported syntax:
      Definitions:  [^1]: footnote text here
      References:   word[^1]  or  word[^label]
      Multi-line:   [^label]: First line
                        continuation
    """
    definitions: dict = {}

    def _strip_definitions(text: str) -> str:
        def _replace(m):
            definitions[m.group(1)] = m.group(2).strip()
            return ""

        return re.sub(r"^\[\^([^\]]+)\]:\s*(.+)$", _replace, text, flags=re.MULTILINE)

    md = _strip_definitions(md)

    if mode == "skip":
        return re.sub(r"\[\^[^\]]+\]", "", md).strip()

    if mode == "inline":

        def _inline_sub(m):
            note = definitions.get(m.group(1), "")
            return f" (footnote: {note})" if note else ""

        return re.sub(r"\[\^([^\]]+)\]", _inline_sub, md).strip()

    if mode == "deferred":
        md = re.sub(r"\[\^[^\]]+\]", "", md).strip()
        if definitions:
            # Emit the collected notes as a plain numbered list, NOT as bare
            # "[^label]:" definitions — with every in-text reference stripped
            # above, Pandoc treats reference-less definitions as unused and
            # silently DROPS them, so HTML/EPUB exports shipped an empty
            # "Footnotes" heading with no footnote bodies.
            md += "\n\n## Footnotes\n\n"
            for i, (label, text) in enumerate(definitions.items(), start=1):
                marker = label if label.isdigit() else f"{i} ({label})"
                md += f"{marker}. {text}\n"
        return md

    return md


def _record_archive_members(archive_path: str, members: List[str], settings: Any) -> None:
    """Register archive members in the library under their ref keys."""
    from ..archive import make_ref
    from .dispatch import _detect_format
    try:
        library: Dict[str, Any] = settings.get("library") or {}
        changed = False
        for member in members:
            ref = make_ref(archive_path, member)
            if ref not in library:
                library[ref] = {
                    "title": Path(member).name,
                    "format": _detect_format(member),
                    "added": str(Path(archive_path).stat().st_mtime),
                    "last_opened": "",
                    "source": f"archive:{archive_path}",
                }
                changed = True
        if changed:
            settings.set("library", library)
    except Exception:
        pass
