"""HTML → Markdown loading (built-in HTMLParser)."""
from .._runtime import *  # noqa: F401,F403


class _HTML2MD(HTMLParser):
    """Minimal HTML → Markdown converter (no third-party dependencies)."""

    _SKIP = frozenset(
        {
            "script",
            "style",
            "nav",
            "footer",
            "aside",
            "noscript",
            "svg",
            "canvas",
            "meta",
            "link",
            "base",
            "iframe",
            "template",
            "button",
            "form",
        }
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._out: List[str] = []
        self._buf: List[str] = []
        self._skip = 0
        self._pre = 0
        self._bold = 0
        self._italic = 0
        self._code = 0
        self._heading = 0
        self._list: List[Tuple[str, int]] = []
        self._bq = 0
        self._trows: List[List[str]] = []
        self._trow: List[str] = []
        self._tcell: List[str] = []
        self._in_cell = False
        self._link_href = ""
        self._link_buf: List[str] = []
        self._in_link = False
        self._title_buf: List[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        a = dict(attrs)
        if tag in self._SKIP:
            self._skip += 1
            return
        if self._skip:
            return
        if tag == "pre":
            self._emit()
            self._pre += 1
            if self._pre == 1:
                lang = next(
                    (
                        c.split("-", 1)[1]
                        for c in a.get("class", "").split()
                        if c.startswith(("language-", "lang-"))
                    ),
                    "",
                )
                self._out.append(f"```{lang}")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._emit()
            self._heading = int(tag[1])
        elif tag == "title":
            self._in_title = True
        elif tag in ("p", "div", "section", "article", "main", "header"):
            self._emit()
        elif tag in ("b", "strong"):
            self._bold += 1
        elif tag in ("i", "em"):
            self._italic += 1
        elif tag == "code" and not self._pre:
            self._code += 1
        elif tag == "a":
            self._in_link = True
            self._link_href = a.get("href", "")
            self._link_buf = []
        elif tag == "br":
            self._buf.append("\n")
        elif tag == "hr":
            self._emit()
            self._out += ["---", ""]
        elif tag == "ul":
            self._emit()
            self._list.append(("ul", 0))
        elif tag == "ol":
            self._emit()
            self._list.append(("ol", 0))
        elif tag == "li":
            self._emit()
        elif tag == "blockquote":
            self._emit()
            self._bq += 1
        elif tag == "table":
            self._emit()
            self._trows = []
        elif tag == "tr":
            self._trow = []
        elif tag in ("th", "td"):
            self._tcell = []
            self._in_cell = True

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP:
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag == "pre":
            self._pre = max(0, self._pre - 1)
            if self._pre == 0:
                self._out += ["```", ""]
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            t = "".join(self._buf).strip()
            if t:
                self._out += ["#" * self._heading + " " + t, ""]
            self._buf = []
            self._heading = 0
        elif tag == "title":
            self._in_title = False
        elif tag in ("p", "section", "article", "main", "header", "div"):
            self._emit_para()
        elif tag in ("b", "strong"):
            self._bold = max(0, self._bold - 1)
        elif tag in ("i", "em"):
            self._italic = max(0, self._italic - 1)
        elif tag == "code" and not self._pre:
            self._code = max(0, self._code - 1)
        elif tag == "a":
            lt = "".join(self._link_buf).strip()
            frag = f"[{lt}]({self._link_href})" if lt and self._link_href else lt
            (self._tcell if self._in_cell else self._buf).append(frag)
            self._in_link = False
        elif tag == "li":
            t = "".join(self._buf).strip()
            if t and self._list:
                ltype, n = self._list[-1]
                pad = "  " * (len(self._list) - 1)
                if ltype == "ol":
                    n += 1
                    self._list[-1] = ("ol", n)
                    self._out.append(f"{pad}{n}. {t}")
                else:
                    self._out.append(f"{pad}* {t}")
            self._buf = []
        elif tag in ("ul", "ol"):
            if self._list:
                self._list.pop()
            if not self._list:
                self._out.append("")
        elif tag == "blockquote":
            self._emit_para()
            self._bq = max(0, self._bq - 1)
        elif tag in ("th", "td"):
            self._trow.append("".join(self._tcell).strip())
            self._tcell = []
            self._in_cell = False
            self._buf = []
        elif tag == "tr":
            if self._trow:
                self._trows.append(self._trow[:])
        elif tag == "table":
            self._flush_table()

    def handle_data(self, data: str) -> None:
        if self._skip or (not data.strip() and not self._pre):
            return
        t = data if self._pre else re.sub(r"\s+", " ", data.replace("\u00a0", " "))
        if self._pre:
            self._out.append(data.rstrip("\n"))
            return
        if self._code:
            t = f"`{t.strip()}`"
        elif self._bold and self._italic:
            t = f"***{t.strip()}***"
        elif self._bold:
            t = f"**{t.strip()}**"
        elif self._italic:
            t = f"*{t.strip()}*"
        if self._in_title:
            self._title_buf.append(t)
        elif self._in_link:
            self._link_buf.append(t)
        elif self._in_cell:
            self._tcell.append(t)
        else:
            self._buf.append(t)

    def _emit(self) -> None:
        t = "".join(self._buf).strip()
        if t:
            self._out.append(t)
        self._buf = []

    def _emit_para(self) -> None:
        t = "".join(self._buf).strip()
        if t:
            bq = "> " * self._bq
            self._out += [bq + t, ""]
        self._buf = []

    def _flush_table(self) -> None:
        rows = self._trows
        if not rows:
            return
        nc = max(len(r) for r in rows)
        hdr = (rows[0] + [""] * nc)[:nc]
        self._out.append("| " + " | ".join(hdr) + " |")
        self._out.append("|" + "|".join([" --- "] * nc) + "|")
        for row in rows[1:]:
            self._out.append("| " + " | ".join((row + [""] * nc)[:nc]) + " |")
        self._out.append("")
        self._trows = []

    def result(self) -> str:
        self._emit()
        title = "".join(self._title_buf).strip()
        lines = ([f"# {title}", ""] if title else []) + self._out
        out: List[str] = []
        prev_blank = False
        for ln in lines:
            blank = not ln.strip()
            if blank and prev_blank:
                continue
            out.append(ln)
            prev_blank = blank
        return "\n".join(out).strip()


def _load_html(path: str) -> str:
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        p = _HTML2MD()
        p.feed(text)
        p.close()
        return p.result()
    except Exception as e:
        return f"# Error loading HTML\n\n```\n{e}\n```\n"


def _load_html_str(html: str) -> str:
    p = _HTML2MD()
    p.feed(html)
    p.close()
    return p.result()
