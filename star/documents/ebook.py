"""EPUB / DAISY-DTBook loading and chapter extraction."""
from .._runtime import *  # noqa: F401,F403
from .html import _load_html_str


def _load_epub(path: str) -> str:
    """Load EPUB via zipfile + HTML converter (no third-party package needed)."""
    import posixpath
    from urllib.parse import unquote

    _HTML_MT = frozenset({"application/xhtml+xml", "text/html"})

    def _local(elem: ET.Element) -> str:
        t = elem.tag
        return t.split("}")[-1] if "}" in t else t

    try:
        with zipfile.ZipFile(path, "r") as zf:
            try:
                container = ET.fromstring(zf.read("META-INF/container.xml"))
            except (KeyError, ET.ParseError) as e:
                return f"# EPUB Error\n\n```\n{e}\n```\n"

            opf_path = next(
                (
                    e.get("full-path")
                    for e in container.iter()
                    if _local(e) == "rootfile"
                ),
                None,
            )
            if not opf_path:
                return "# EPUB Error\n\nCould not locate OPF rootfile.\n"

            opf_root = ET.fromstring(zf.read(opf_path))
            opf_dir = (opf_path.rsplit("/", 1)[0] + "/") if "/" in opf_path else ""

            title = author = ""
            for e in opf_root.iter():
                tl = _local(e)
                if tl == "title" and not title and e.text:
                    title = e.text.strip()
                elif tl == "creator" and not author and e.text:
                    author = e.text.strip()

            manifest: Dict[str, Tuple[str, str, str]] = {}
            for e in opf_root.iter():
                if _local(e) == "item":
                    iid = e.get("id", "")
                    href = unquote(e.get("href", ""))
                    mt = e.get("media-type", "")
                    props = e.get("properties", "")
                    if iid and href:
                        manifest[iid] = (href, mt, props)

            spine = [
                e.get("idref", "")
                for e in opf_root.iter()
                if _local(e) == "itemref" and e.get("idref")
            ]

            znames = {n.lower(): n for n in zf.namelist()}

            def read_item(item_path: str) -> Optional[bytes]:
                try:
                    return zf.read(item_path)
                except KeyError:
                    canon = znames.get(item_path.lower())
                    return zf.read(canon) if canon else None

            parts: List[str] = []
            if title:
                parts += [f"# {title}", ""]
            if author:
                parts += [f"*{author}*", ""]
            if title or author:
                parts += ["---", ""]

            seen: set = set()
            for idref in spine:
                if idref not in manifest:
                    continue
                href, mt, props = manifest[idref]
                if mt not in _HTML_MT:
                    continue
                if "nav" in props.split():
                    continue
                href = href.split("#")[0]
                if not href:
                    continue
                raw = href if href.startswith("/") else opf_dir + href
                item_path = posixpath.normpath(raw).lstrip("/")
                if item_path in seen:
                    continue
                seen.add(item_path)
                data = read_item(item_path)
                if not data:
                    continue
                html_text = re.sub(
                    r"<title\b[^>]*>.*?</title>",
                    "",
                    data.decode("utf-8", "replace"),
                    flags=re.I | re.S,
                )
                ch = _load_html_str(html_text).strip()
                if ch:
                    parts += [ch, "", "---", ""]

            while parts and parts[-1] in ("", "---"):
                parts.pop()
            return (
                "\n".join(parts) + "\n"
                if parts
                else f"# {Path(path).name}\n\n*(empty EPUB)*\n"
            )
    except zipfile.BadZipFile:
        return "# EPUB Error\n\nNot a valid ZIP/EPUB file.\n"
    except Exception as e:
        return f"# EPUB Error\n\n```\n{e}\n```\n"


def _load_dtbook(path: str) -> str:
    """Load DTBook XML (DAISY digital talking book) into markdown.
    Supports DTBook 2005-3 and DAISY 3 NCX navigation."""
    _NS = {
        "dtb": "http://www.daisy.org/z3986/2005/dtbook/",
        "ncx": "http://www.daisy.org/z3986/2005/ncx/",
    }

    def _text(elem: ET.Element) -> str:
        return "".join(elem.itertext()).strip()

    def _walk(elem: ET.Element, depth: int = 0) -> List[str]:
        out: List[str] = []
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        if tag in (
            "dtbook",
            "book",
            "frontmatter",
            "bodymatter",
            "rearmatter",
            "pagenum",
        ):
            for child in elem:
                out.extend(_walk(child, depth))
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            out.append("#" * level + " " + _text(elem))
            out.append("")
        elif tag in ("p",):
            t = _text(elem)
            if t:
                out.append(t)
                out.append("")
        elif tag in ("list",):
            for li in elem:
                li_tag = li.tag.split("}")[-1] if "}" in li.tag else li.tag
                if li_tag == "li":
                    out.append("* " + _text(li))
            out.append("")
        elif tag in ("imggroup",):
            for child in elem:
                ct = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if ct == "caption":
                    out.append(f"*{_text(child)}*")
                elif ct == "img":
                    alt = child.get("alt", "")
                    out.append(f"![{alt}]({child.get('src', '')})")
            out.append("")
        elif tag in ("sidebar", "prodnote", "annotation"):
            out.append("> " + _text(elem).replace("\n", "\n> "))
            out.append("")
        elif tag in ("level", "level1", "level2", "level3", "level4", "section", "div"):
            for child in elem:
                out.extend(_walk(child, depth + 1))
        elif tag in ("note", "footnote"):
            out.append(f"[^note]: {_text(elem)}")
        else:
            for child in elem:
                out.extend(_walk(child, depth))
        return out

    try:
        tree = ET.parse(path)
        root = tree.getroot()
        lines = _walk(root)
        # Collapse runs of blank lines
        result: List[str] = []
        blank = 0
        for ln in lines:
            if not ln.strip():
                blank += 1
                if blank <= 1:
                    result.append("")
            else:
                blank = 0
                result.append(ln)
        return "\n".join(result).strip()
    except Exception as e:
        return f"# DTBook Error\n\n```\n{e}\n```\n"


def _load_daisy_zip(path: str) -> str:
    """Load a DAISY book from a ZIP archive (Bookshare format).
    Tries DTBook XML first, then EPUB-style HTML chapters."""
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            # Priority: DTBook XML
            for n in names:
                if n.lower().endswith((".xml", ".dtbook")) and "book" in n.lower():
                    tmp = CACHE_DIR / ("daisy_" + Path(n).name)
                    tmp.parent.mkdir(parents=True, exist_ok=True)
                    tmp.write_bytes(zf.read(n))
                    return _load_dtbook(str(tmp))
            # Fall back: any .html / .xhtml
            html_parts = []
            for n in sorted(names):
                if n.lower().endswith((".html", ".xhtml", ".htm")):
                    html_parts.append(
                        _load_html_str(zf.read(n).decode("utf-8", "replace"))
                    )
            if html_parts:
                return "\n\n---\n\n".join(html_parts)
            return "# DAISY Error\n\nNo readable content found in this ZIP.\n"
    except zipfile.BadZipFile:
        return "# DAISY Error\n\nNot a valid ZIP file.\n"
    except Exception as e:
        return f"# DAISY Error\n\n```\n{e}\n```\n"


def _epub_extract_chapters(path: str) -> "List[Tuple[str, str]]":
    """Extract chapter/navigation data from an EPUB file.

    Reads the NCX (EPUB 2) or NAV document (EPUB 3) to return an ordered
    list of (chapter_title, href) pairs representing the book\'s structure.
    Returns an empty list if the EPUB has no navigation data.
    """
    import zipfile
    from xml.etree import ElementTree as ET

    OPF = "http://www.idpf.org/2007/opf"
    NCX = "http://www.daisy.org/z3986/2005/ncx/"
    EPUB = "http://www.idpf.org/2007/ops"
    XHTML = "http://www.w3.org/1999/xhtml"

    try:
        zf = zipfile.ZipFile(path, "r")
    except zipfile.BadZipFile:
        return []

    with zf:
        try:
            container = zf.read("META-INF/container.xml")
        except KeyError:
            return []

        cont_root = ET.fromstring(container)
        rf = cont_root.find(
            ".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile"
        )
        if rf is None:
            return []
        opf_path = rf.get("full-path", "")
        opf_dir = opf_path.rsplit("/", 1)[0] + "/" if "/" in opf_path else ""

        try:
            opf_tree = ET.fromstring(zf.read(opf_path))
        except (KeyError, ET.ParseError):
            return []

        # Build manifest: id -> (href, media-type, properties)
        manifest = {
            item.get("id", ""): (
                item.get("href", ""),
                item.get("media-type", ""),
                item.get("properties", ""),
            )
            for item in opf_tree.findall(f"{{{OPF}}}manifest/{{{OPF}}}item")
        }

        chapters: list = []

        # --- EPUB3 NAV ---
        nav_id = next(
            (k for k, (h, t, p) in manifest.items() if "nav" in p.split()), None
        )
        if nav_id:
            try:
                nav_tree = ET.fromstring(zf.read(opf_dir + manifest[nav_id][0]))
                for nav_elem in nav_tree.iter(f"{{{XHTML}}}nav"):
                    if "toc" in nav_elem.get(f"{{{EPUB}}}type", ""):
                        for li in nav_elem.iter(f"{{{XHTML}}}li"):
                            a = li.find(f"{{{XHTML}}}a")
                            if a is not None:
                                title = "".join(a.itertext()).strip()
                                href = a.get("href", "").split("#")[0]
                                if title and href:
                                    chapters.append((title, opf_dir + href))
                        break
            except (KeyError, ET.ParseError):
                pass

        # --- NCX (EPUB2 fallback) ---
        if not chapters:
            spine = opf_tree.find(f"{{{OPF}}}spine")
            toc_id = (spine.get("toc", "") if spine is not None else "") or next(
                (
                    k
                    for k, (h, t, p) in manifest.items()
                    if t == "application/x-dtbncx+xml"
                ),
                "",
            )
            if toc_id and toc_id in manifest:
                try:
                    ncx_tree = ET.fromstring(zf.read(opf_dir + manifest[toc_id][0]))
                    for np in ncx_tree.iter(f"{{{NCX}}}navPoint"):
                        label = np.find(f"{{{NCX}}}navLabel/{{{NCX}}}text")
                        content = np.find(f"{{{NCX}}}content")
                        if label is not None and content is not None:
                            title = (label.text or "").strip()
                            href = content.get("src", "").split("#")[0]
                            if title and href:
                                chapters.append((title, opf_dir + href))
                except (KeyError, ET.ParseError):
                    pass

    # Deduplicate by href, preserving first occurrence
    seen: set = set()
    unique: list = []
    for title, href in chapters:
        if href not in seen:
            seen.add(href)
            unique.append((title, href))
    return unique
