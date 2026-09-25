"""DAISY digital talking books: DAISY 3 packages (``.opf``), DAISY 2.02
(``ncc.html``), NCX navigation files, and zipped books.

star already read DTBook XML (``.xml``/``.daisy``) natively in :mod:`ebook`;
this module adds the *package* forms a DAISY book is actually distributed in:

* **DAISY 3** — an OPF package listing the DTBook XML (text books) and/or the
  SMIL files that align text with audio.  The text is the DTBook; when there is
  none, the spine's XHTML content is used.  Chapters come from the NCX.
* **DAISY 2.02** — ``ncc.html`` (the Navigation Control Center) whose headings
  link to SMIL files, each of which points into the shared content HTML.  A
  text-only 2.02 book links straight to HTML instead.
* **Zip** — a Bookshare/NLS-style download holding either of the above (or a
  bare bundle of audio files, which becomes a track listing).

Everything runs on the standard library.  Audio itself is not played — star is
a text reader — but the chapter/section structure and every word of text are
preserved, which is what a screen-reader user of a DAISY text book needs.
"""
import posixpath

from .._runtime import *  # noqa: F401,F403
from .ebook import _dtbook_to_md
from .html import _load_html_str

_AUDIO_EXTS = frozenset({".mp3", ".mp4", ".m4a", ".m4b", ".wav", ".ogg", ".flac", ".aac", ".wma"})


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _join(base_dir: str, href: str) -> str:
    href = href.split("#")[0]
    if not href:
        return ""
    return posixpath.normpath(posixpath.join(base_dir, href)) if base_dir else posixpath.normpath(href)


class _Source:
    """Uniform access to a book's files: a directory on disk or a ZIP."""

    def __init__(self, path: str):
        self.path = path
        self._zf: Optional[zipfile.ZipFile] = None
        p = Path(path)
        magic = b""
        if p.is_file():
            try:
                with open(path, "rb") as fh:
                    magic = fh.read(2)
            except OSError:
                magic = b""
        if magic == b"PK":
            self._zf = zipfile.ZipFile(path, "r")
            self._names = [n for n in self._zf.namelist() if not n.endswith("/")]
            self._lower = {n.lower(): n for n in self._names}
            self.root = Path(path).parent
        else:
            self.root = p.parent if p.is_file() else p
            self._names = []
            self._lower = {}

    def close(self) -> None:
        if self._zf is not None:
            self._zf.close()

    @property
    def is_zip(self) -> bool:
        return self._zf is not None

    def names(self) -> List[str]:
        if self._zf is not None:
            return list(self._names)
        out: List[str] = []
        for p in sorted(self.root.rglob("*")):
            if p.is_file():
                out.append(p.relative_to(self.root).as_posix())
        return out

    def read(self, name: str) -> Optional[bytes]:
        name = name.replace("\\", "/")
        if self._zf is not None:
            real = self._lower.get(name.lower())
            if real is None:
                # Try matching by basename when the zip nests everything in one folder.
                base = name.rsplit("/", 1)[-1].lower()
                real = next((n for n in self._names if n.rsplit("/", 1)[-1].lower() == base), None)
            if real is None:
                return None
            try:
                return self._zf.read(real)
            except Exception:  # noqa: BLE001
                return None
        fp = self.root / name
        if not fp.is_file():
            cand = next((c for c in self.root.rglob("*") if c.is_file() and c.name.lower() == Path(name).name.lower()), None)
            if cand is None:
                return None
            fp = cand
        try:
            return fp.read_bytes()
        except OSError:
            return None

    def find(self, predicate: "Callable[[str], bool]") -> Optional[str]:
        for n in self.names():
            if predicate(n):
                return n
        return None


def _decode(data: bytes) -> str:
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


# ── SMIL ─────────────────────────────────────────────────────────────────────


def _smil_text_refs(data: bytes) -> List[str]:
    """``src`` of every ``<text>`` element in a SMIL file, in document order."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return re.findall(r"<text[^>]*\ssrc=[\"']([^\"']+)[\"']", _decode(data), flags=re.I)
    return [e.get("src", "") for e in root.iter() if _local(e.tag) == "text" and e.get("src")]


# ── OPF (DAISY 3) ────────────────────────────────────────────────────────────


class _Package:
    def __init__(self) -> None:
        self.title = ""
        self.author = ""
        self.manifest: Dict[str, Tuple[str, str]] = {}   # id → (href, media-type)
        self.spine: List[str] = []
        self.meta: Dict[str, str] = {}


def _parse_opf(data: bytes, opf_dir: str) -> _Package:
    pkg = _Package()
    root = ET.fromstring(data)
    for e in root.iter():
        tag = _local(e.tag).lower()
        if tag == "title" and not pkg.title and (e.text or "").strip():
            pkg.title = e.text.strip()
        elif tag == "creator" and not pkg.author and (e.text or "").strip():
            pkg.author = e.text.strip()
        elif tag == "meta":
            n, c = e.get("name", ""), e.get("content", "")
            if n and c:
                pkg.meta[n.lower()] = c
        elif tag == "item":
            iid, href, mt = e.get("id", ""), e.get("href", ""), e.get("media-type", "")
            if iid and href:
                pkg.manifest[iid] = (_join(opf_dir, href), mt)
        elif tag == "itemref" and e.get("idref"):
            pkg.spine.append(e.get("idref", ""))
    if not pkg.title:
        pkg.title = pkg.meta.get("dc:title", "")
    if not pkg.author:
        pkg.author = pkg.meta.get("dc:creator", "")
    return pkg


def _find_items(pkg: _Package, pred: "Callable[[str, str], bool]") -> List[str]:
    return [href for href, mt in pkg.manifest.values() if pred(href, mt)]


def _ncx_chapters(data: bytes) -> List[Tuple[str, str]]:
    """``(label, content src)`` for every navPoint in an NCX, in reading order."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    out: List[Tuple[str, str]] = []
    for np in root.iter():
        if _local(np.tag) != "navPoint":
            continue
        label = ""
        src = ""
        for c in np:
            ct = _local(c.tag)
            if ct == "navLabel":
                label = " ".join(t.strip() for t in c.itertext() if t.strip())
            elif ct == "content":
                src = c.get("src", "")
        if label:
            out.append((label, src))
    return out


def _load_package(src: _Source, opf_name: str) -> Tuple[str, List[Tuple[str, str]], Dict[str, str]]:
    data = src.read(opf_name)
    if data is None:
        return f"# DAISY Error\n\nCannot read {opf_name}.\n", [], {}
    opf_dir = posixpath.dirname(opf_name)
    try:
        pkg = _parse_opf(data, opf_dir)
    except ET.ParseError as e:
        return f"# DAISY Error\n\n```\n{e}\n```\n", [], {}
    meta = {k: v for k, v in (("title", pkg.title), ("author", pkg.author)) if v}
    parts: List[str] = []
    if pkg.title:
        parts += [f"# {pkg.title}", ""]
    if pkg.author:
        parts += [f"*{pkg.author}*", ""]
    if parts:
        parts += ["---", ""]

    # 1. DTBook text.
    dtbooks = _find_items(pkg, lambda h, mt: "dtbook" in mt.lower() or h.lower().endswith((".xml", ".dtbook")))
    body_done = False
    for href in dtbooks:
        raw = src.read(href)
        if not raw:
            continue
        head = raw[:600].lower()
        if b"dtbook" not in head and b"<book" not in head:
            continue
        md = _dtbook_to_md(raw)
        if md.strip() and not md.startswith("# DTBook Error"):
            parts += [md, ""]
            body_done = True
    # 2. Spine content (XHTML) — DAISY 3 text via SMIL, or an unpacked EPUB-like package.
    if not body_done:
        seen: set = set()
        spine_hrefs = [pkg.manifest[i][0] for i in pkg.spine if i in pkg.manifest]
        smil_hrefs = [h for h in spine_hrefs if h.lower().endswith(".smil")]
        html_hrefs = [h for h in spine_hrefs if h.lower().endswith((".html", ".htm", ".xhtml", ".xml"))]
        if not html_hrefs and not smil_hrefs:
            html_hrefs = _find_items(pkg, lambda h, mt: h.lower().endswith((".html", ".htm", ".xhtml")))
            smil_hrefs = _find_items(pkg, lambda h, mt: h.lower().endswith(".smil"))
        ordered: List[str] = []
        for smil in smil_hrefs:
            sd = src.read(smil)
            if not sd:
                continue
            for ref in _smil_text_refs(sd):
                target = _join(posixpath.dirname(smil), ref)
                if target and target not in seen:
                    seen.add(target)
                    ordered.append(target)
        for h in html_hrefs:
            if h not in seen:
                seen.add(h)
                ordered.append(h)
        for h in ordered:
            raw = src.read(h)
            if not raw:
                continue
            text = _decode(raw)
            if h.lower().endswith(".xml") and "dtbook" in text[:600].lower():
                md = _dtbook_to_md(raw)
            else:
                md = _load_html_str(re.sub(r"<title\b[^>]*>.*?</title>", "", text, flags=re.I | re.S))
            if md.strip():
                parts += [md, "", "---", ""]
                body_done = True
    # 3. Audio-only book: list the tracks.
    if not body_done:
        audio = _find_items(pkg, lambda h, mt: mt.startswith("audio/") or Path(h).suffix.lower() in _AUDIO_EXTS)
        if audio:
            parts += ["## Audio tracks", ""] + [f"- {a}" for a in audio] + [
                "", "*This DAISY book contains audio only (no text layer). Use Tools ▸ "
                "Transcribe Audio on a track to read it.*", ""]
        else:
            parts += ["*No readable text content found in this DAISY package.*", ""]
    # Chapters from the NCX.
    chapters: List[Tuple[str, str]] = []
    ncx = _find_items(pkg, lambda h, mt: "dtbncx" in mt.lower() or h.lower().endswith(".ncx"))
    for href in ncx:
        raw = src.read(href)
        if raw:
            chapters = _ncx_chapters(raw)
            if chapters:
                break
    while parts and parts[-1] in ("", "---"):
        parts.pop()
    md_text = "\n".join(parts) + "\n"
    return re.sub(r"\n{3,}", "\n\n", md_text), chapters, meta


# ── ncc.html (DAISY 2.02) ────────────────────────────────────────────────────


class _NccParser(HTMLParser):
    """Headings (level, text, href) and dc: metadata from ``ncc.html``."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.entries: List[Tuple[int, str, str]] = []
        self.meta: Dict[str, str] = {}
        self._level = 0
        self._href = ""
        self._buf: List[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        a = dict(attrs)
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._level = int(tag[1])
            self._href = ""
            self._buf = []
        elif tag == "a" and self._level:
            self._href = a.get("href", "") or ""
        elif tag == "meta":
            name = (a.get("name") or "").lower()
            content = a.get("content") or ""
            if name and content:
                self.meta[name] = content

    def handle_data(self, data: str) -> None:
        if self._level:
            self._buf.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self._level:
            text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            if text:
                self.entries.append((self._level, text, self._href))
            self._level = 0
            self._buf = []


def _load_ncc(src: _Source, ncc_name: str) -> Tuple[str, List[Tuple[str, str]], Dict[str, str]]:
    data = src.read(ncc_name)
    if data is None:
        return f"# DAISY Error\n\nCannot read {ncc_name}.\n", [], {}
    parser = _NccParser()
    parser.feed(_decode(data))
    parser.close()
    ncc_dir = posixpath.dirname(ncc_name)
    title = parser.meta.get("dc:title", "")
    author = parser.meta.get("dc:creator", "")
    meta = {k: v for k, v in (("title", title), ("author", author)) if v}
    parts: List[str] = []
    if title:
        parts += [f"# {title}", ""]
    if author:
        parts += [f"*{author}*", ""]
    if parts:
        parts += ["---", ""]
    ordered: List[str] = []
    seen: set = set()
    chapters: List[Tuple[str, str]] = []
    for level, text, href in parser.entries:
        target = _join(ncc_dir, href)
        if not target:
            continue
        if target.lower().endswith(".smil"):
            sd = src.read(target)
            refs = _smil_text_refs(sd) if sd else []
            first = ""
            for ref in refs:
                t = _join(posixpath.dirname(target), ref)
                if t and t.lower() != ncc_name.lower():
                    first = first or t
                    if t not in seen:
                        seen.add(t)
                        ordered.append(t)
            chapters.append((text, first or target))
        else:
            if target.lower() != ncc_name.lower() and target not in seen:
                seen.add(target)
                ordered.append(target)
            chapters.append((text, target))
    body: List[str] = []
    for h in ordered:
        raw = src.read(h)
        if not raw:
            continue
        html = re.sub(r"<title\b[^>]*>.*?</title>", "", _decode(raw), flags=re.I | re.S)
        md = _load_html_str(html)
        if md.strip():
            body += [md, "", "---", ""]
    if not body:
        # Audio-only 2.02 book: the NCC headings *are* the readable structure.
        for level, text, _href in parser.entries:
            body.append(f"{'#' * min(6, level)} {text}")
            body.append("")
        if body:
            body += ["*This DAISY 2.02 book has no text content beyond its navigation; "
                     "the audio can be read with Tools ▸ Transcribe Audio.*", ""]
    parts += body
    while parts and parts[-1] in ("", "---"):
        parts.pop()
    return re.sub(r"\n{3,}", "\n\n", "\n".join(parts) + "\n"), chapters, meta


# ── entry points ─────────────────────────────────────────────────────────────


def _is_daisy_zip(path: str) -> bool:
    """True when the ZIP at *path* holds a DAISY book (ncc.html, an OPF, or DTBook)."""
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = [n.lower() for n in zf.namelist()]
            if any(n.rsplit("/", 1)[-1] == "ncc.html" for n in names):
                return True
            if any(n.endswith(".opf") for n in names) and not any(n == "mimetype" for n in names):
                return True
            for n in zf.namelist():
                if n.lower().endswith(".xml") and "book" in n.lower():
                    head = zf.open(n).read(600).lower()
                    if b"dtbook" in head:
                        return True
    except Exception:  # noqa: BLE001
        return False
    return False


def _load_daisy_full(path: str) -> Tuple[str, List[Tuple[str, str]], Dict[str, str]]:
    """``(markdown, chapters, metadata)`` for any DAISY entry file or zip."""
    p = Path(path)
    name = p.name.lower()
    src = _Source(path)
    try:
        if src.is_zip:
            names = src.names()
            ncc = next((n for n in names if n.rsplit("/", 1)[-1].lower() == "ncc.html"), None)
            opf = next((n for n in names if n.lower().endswith(".opf")), None)
            if ncc:
                return _load_ncc(src, ncc)
            if opf:
                return _load_package(src, opf)
            for n in names:
                if n.lower().endswith((".xml", ".dtbook")):
                    raw = src.read(n) or b""
                    if b"dtbook" in raw[:600].lower():
                        return _dtbook_to_md(raw), [], {}
            html = [n for n in names if n.lower().endswith((".html", ".htm", ".xhtml"))]
            if html:
                md = "\n\n---\n\n".join(
                    _load_html_str(_decode(src.read(n) or b"")) for n in sorted(html)
                )
                return md + "\n", [], {}
            audio = [n for n in names if Path(n).suffix.lower() in _AUDIO_EXTS]
            if audio:
                md = (f"# {p.stem}\n\n## Audio tracks\n\n" + "\n".join(f"- {a}" for a in sorted(audio))
                      + "\n\n*This book contains audio only. Use Tools ▸ Transcribe Audio on a track to read it.*\n")
                return md, [], {}
            return "# DAISY Error\n\nNo readable content found in this ZIP.\n", [], {}
        if name == "ncc.html":
            return _load_ncc(src, p.name)
        if name.endswith(".opf"):
            return _load_package(src, p.name)
        if name.endswith(".ncx"):
            # Prefer the package beside it; otherwise follow the NCX's own links.
            sibling_opf = next((c.name for c in p.parent.glob("*.opf")), None)
            if sibling_opf:
                return _load_package(src, sibling_opf)
            if (p.parent / "ncc.html").exists():
                return _load_ncc(src, "ncc.html")
            chapters = _ncx_chapters(p.read_bytes())
            ordered: List[str] = []
            seen: set = set()
            for _label, s in chapters:
                target = _join("", s)
                if target.lower().endswith(".smil"):
                    sd = src.read(target)
                    for ref in (_smil_text_refs(sd) if sd else []):
                        t = _join(posixpath.dirname(target), ref)
                        if t and t not in seen:
                            seen.add(t)
                            ordered.append(t)
                elif target and target not in seen:
                    seen.add(target)
                    ordered.append(target)
            parts: List[str] = []
            for h in ordered:
                raw = src.read(h)
                if not raw:
                    continue
                if h.lower().endswith(".xml"):
                    parts.append(_dtbook_to_md(raw))
                else:
                    parts.append(_load_html_str(_decode(raw)))
            if not parts:
                parts = [f"# {p.stem}", ""] + [f"- {t}" for t, _ in chapters]
            return "\n\n---\n\n".join(x for x in parts if x.strip()) + "\n", chapters, {}
        # .daisy / .xml — DTBook itself.
        return _dtbook_to_md(str(p)), [], {}
    except Exception as e:  # noqa: BLE001
        return f"# DAISY Error\n\n```\n{e}\n```\n", [], {}
    finally:
        src.close()


def _load_daisy(path: str) -> str:
    return _load_daisy_full(path)[0]
