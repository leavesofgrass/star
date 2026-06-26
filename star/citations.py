"""Citation parsing/formatting (BibTeX, RIS, CSL-JSON) and DOI lookup."""
from ._runtime import *  # noqa: F401,F403


# =============================================================================
# Citation manager
# =============================================================================


def _citation_label(c: Dict[str, Any]) -> str:
    """Human-readable one-line label for a citation dict."""
    author = str(c.get("author", "")).split(" and ")[0].split(",")[0].strip()
    year = str(c.get("year", "")).strip()
    title = str(c.get("title", "")).strip()
    cid = str(c.get("id", "")).strip()
    head = " ".join(p for p in (author, f"({year})" if year else "") if p).strip()
    label = f"{head}  {title}" if head else title
    return f"[{cid}] {label}".strip() if cid else label or "(untitled)"


def _parse_bibtex(text: str) -> List[Dict[str, Any]]:
    """Parse a (subset of) BibTeX into a list of citation dicts.

    Uses brace-counting to find each entry's body so it works whether the
    closing brace is on its own line or inline, and tolerates nested braces.
    """
    items: List[Dict[str, Any]] = []
    n = len(text)
    mapping = {
        "title": "title",
        "author": "author",
        "year": "year",
        "journal": "journal",
        "booktitle": "journal",
        "doi": "doi",
        "url": "url",
        "publisher": "publisher",
    }
    for m in re.finditer(r"@(\w+)\s*\{", text):
        ctype = m.group(1).lower()
        depth, j = 1, m.end()
        while j < n and depth > 0:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        body = text[m.end() : j - 1]
        key, _sep, rest = body.partition(",")
        fields: Dict[str, Any] = {"id": key.strip(), "type": ctype}
        for fm in re.finditer(
            r"(\w+)\s*=\s*(\{(?:[^{}]|\{[^{}]*\})*\}|\"[^\"]*\"|[^,\n]+)",
            rest,
        ):
            name = fm.group(1).lower()
            val = fm.group(2).strip().strip("{}").strip('"').strip()
            if name in mapping:
                fields[mapping[name]] = val
        items.append(fields)
    return items


def _parse_ris(text: str) -> List[Dict[str, Any]]:
    """Parse RIS records into a list of citation dicts."""
    items: List[Dict[str, Any]] = []
    cur: Dict[str, Any] = {}
    authors: List[str] = []
    tag_map = {
        "TI": "title",
        "T1": "title",
        "PY": "year",
        "Y1": "year",
        "JO": "journal",
        "JF": "journal",
        "T2": "journal",
        "DO": "doi",
        "UR": "url",
        "PB": "publisher",
        "ID": "id",
    }
    for line in text.splitlines():
        # The value after "  - " may be empty (notably the "ER  - " end-of-record
        # tag, whose trailing space rstrip() removes), so the space is optional.
        mm = re.match(r"^([A-Z][A-Z0-9])  - ?(.*)$", line.rstrip())
        if not mm:
            continue
        tag, val = mm.group(1), mm.group(2).strip()
        if tag == "TY":
            cur = {"type": val.lower()}
            authors = []
        elif tag in ("AU", "A1"):
            authors.append(val)
        elif tag == "ER":
            if authors:
                cur["author"] = " and ".join(authors)
            if "year" in cur:
                cur["year"] = str(cur["year"])[:4]
            if not cur.get("id"):
                a0 = (authors[0].split(",")[0] if authors else "ref").strip()
                cur["id"] = re.sub(r"\W+", "", a0 + str(cur.get("year", ""))) or "ref"
            items.append(cur)
            cur = {}
        elif tag in tag_map:
            cur[tag_map[tag]] = val
    return items


def _parse_csl_json(text: str) -> List[Dict[str, Any]]:
    """Parse CSL-JSON into a list of citation dicts."""
    data = json.loads(text)
    if isinstance(data, dict):
        data = [data]
    items: List[Dict[str, Any]] = []
    for c in data:
        authors = []
        for a in c.get("author", []) or []:
            fam = a.get("family", "")
            given = a.get("given", "")
            authors.append(f"{fam}, {given}".strip(", ") if fam else given)
        issued = c.get("issued", {}) or {}
        year = ""
        if isinstance(issued, dict):
            parts = issued.get("date-parts") or [[""]]
            year = str(parts[0][0]) if parts and parts[0] else ""
        items.append(
            {
                "id": str(c.get("id", "")),
                "type": str(c.get("type", "article")),
                "title": str(c.get("title", "")),
                "author": " and ".join(authors),
                "year": year,
                "journal": str(c.get("container-title", "")),
                "doi": str(c.get("DOI", "")),
                "url": str(c.get("URL", "")),
                "publisher": str(c.get("publisher", "")),
            }
        )
    return items


def _import_citations(path: str) -> List[Dict[str, Any]]:
    """Read citations from a .bib / .ris / .json file (format by extension)."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    ext = Path(path).suffix.lower()
    if ext == ".bib":
        return _parse_bibtex(text)
    if ext == ".ris":
        return _parse_ris(text)
    if ext in (".json", ".csl"):
        return _parse_csl_json(text)
    # Heuristic fallback by content.
    if text.lstrip().startswith("@"):
        return _parse_bibtex(text)
    if re.search(r"^TY  - ", text, re.MULTILINE):
        return _parse_ris(text)
    return _parse_csl_json(text)


def _format_citations(items: List[Dict[str, Any]], ext: str) -> str:
    """Serialize citations to BibTeX (.bib), RIS (.ris), or CSL-JSON (.json)."""
    if ext == ".ris":
        out: List[str] = []
        for c in items:
            out.append(f"TY  - {str(c.get('type', 'GEN')).upper()}")
            if c.get("title"):
                out.append(f"TI  - {c['title']}")
            for au in str(c.get("author", "")).split(" and "):
                if au.strip():
                    out.append(f"AU  - {au.strip()}")
            if c.get("year"):
                out.append(f"PY  - {c['year']}")
            if c.get("journal"):
                out.append(f"JO  - {c['journal']}")
            if c.get("doi"):
                out.append(f"DO  - {c['doi']}")
            if c.get("url"):
                out.append(f"UR  - {c['url']}")
            out.append("ER  - ")
            out.append("")
        return "\r\n".join(out)
    if ext in (".json", ".csl"):
        csl = []
        for c in items:
            authors = []
            for au in str(c.get("author", "")).split(" and "):
                au = au.strip()
                if not au:
                    continue
                if "," in au:
                    fam, given = au.split(",", 1)
                    authors.append({"family": fam.strip(), "given": given.strip()})
                else:
                    authors.append({"family": au})
            entry: Dict[str, Any] = {
                "id": c.get("id", ""),
                "type": c.get("type", "article"),
                "title": c.get("title", ""),
            }
            if authors:
                entry["author"] = authors
            if c.get("year"):
                entry["issued"] = {"date-parts": [[str(c["year"])]]}
            if c.get("journal"):
                entry["container-title"] = c["journal"]
            if c.get("doi"):
                entry["DOI"] = c["doi"]
            if c.get("url"):
                entry["URL"] = c["url"]
            csl.append(entry)
        return json.dumps(csl, indent=2, ensure_ascii=False)
    # Default: BibTeX
    out = []
    for c in items:
        cid = (
            c.get("id") or re.sub(r"\W+", "", str(c.get("title", "ref"))[:20]) or "ref"
        )
        out.append(f"@{c.get('type', 'article')}{{{cid},")
        for fld, key in (
            ("title", "title"),
            ("author", "author"),
            ("year", "year"),
            ("journal", "journal"),
            ("doi", "doi"),
            ("url", "url"),
            ("publisher", "publisher"),
        ):
            if c.get(fld):
                out.append(f"  {key} = {{{c[fld]}}},")
        out.append("}")
        out.append("")
    return "\n".join(out)


def _valid_isbn(s: str) -> bool:
    """Return True when *s* is a checksum-valid ISBN-10 or ISBN-13.

    Hyphens and whitespace are stripped before validation.
    """
    isbn = re.sub(r"[\s\-]", "", s.upper())
    if len(isbn) == 10:
        if not re.match(r"^\d{9}[\dX]$", isbn):
            return False
        total = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(isbn))
        return total % 11 == 0
    if len(isbn) == 13:
        if not re.match(r"^\d{13}$", isbn):
            return False
        total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(isbn))
        return total % 10 == 0
    return False


def _fetch_metadata_by_isbn(isbn: str) -> Tuple[Dict[str, Any], str]:
    """Look up a book by ISBN via the OpenLibrary Books API.

    Returns ``(metadata_dict, message)``.  On success the message is ``""``;
    on failure the dict is ``{}`` and the message explains why.  No API key
    is required.  Network call — invoke from a background thread in the GUI.
    """
    isbn_clean = re.sub(r"[\s\-]", "", isbn)
    url = (
        "https://openlibrary.org/api/books"
        f"?bibkeys=ISBN:{isbn_clean}&format=json&jscmd=data"
    )
    req = urllib.request.Request(
        url, headers={"User-Agent": f"star/{APP_VERSION} (metadata lookup)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        key = f"ISBN:{isbn_clean}"
        book = data.get(key) or {}
        if not book:
            return {}, f"ISBN {isbn_clean!r} not found on OpenLibrary"
        title = str(book.get("title", "")).strip()
        authors = [str(a.get("name", "")).strip() for a in (book.get("authors") or [])]
        year = ""
        pub_date = str(book.get("publish_date") or "")
        m = re.search(r"\d{4}", pub_date)
        if m:
            year = m.group()
        publishers = [str(p.get("name", "")).strip() for p in (book.get("publishers") or [])]
        publisher = ", ".join(p for p in publishers if p)
        meta: Dict[str, Any] = {
            "title": title,
            "author": " and ".join(a for a in authors if a),
            "year": year,
            "publisher": publisher,
            "isbn": isbn_clean,
        }
        return meta, ""
    except urllib.error.URLError as e:
        return {}, f"OpenLibrary lookup unavailable: {e}"
    except Exception as e:
        return {}, f"OpenLibrary lookup failed: {e}"


def _fetch_citation_by_doi(doi: str) -> Dict[str, Any]:
    """Look up a DOI via the Crossref REST API and return a citation dict.

    Network call (blocking) — call from a background thread in the GUI.
    Raises on network/parse errors so callers can report them.
    """
    doi = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix) :]
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi)
    req = urllib.request.Request(
        url, headers={"User-Agent": f"star/{APP_VERSION} (citation lookup)"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    msg = data.get("message", {}) or {}
    authors = []
    for a in msg.get("author", []) or []:
        fam = a.get("family", "")
        given = a.get("given", "")
        authors.append(f"{fam}, {given}".strip(", ") if fam else given)
    year = ""
    parts = (msg.get("issued", {}) or {}).get("date-parts", [[None]])
    if parts and parts[0] and parts[0][0]:
        year = str(parts[0][0])
    title = (msg.get("title") or [""])[0]
    journal = (msg.get("container-title") or [""])[0]
    fam0 = authors[0].split(",")[0] if authors else "ref"
    cid = re.sub(r"\W+", "", fam0 + year) or "ref"
    return {
        "id": cid,
        "type": str(msg.get("type", "article")),
        "title": title,
        "author": " and ".join(authors),
        "year": year,
        "journal": journal,
        "doi": doi,
        "url": str(msg.get("URL", "")),
    }
