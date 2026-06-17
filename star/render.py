"""Markdown -> styled terminal lines rendering and code lexers."""
from ._runtime import *  # noqa: F401,F403


# =============================================================================
# Markdown renderer (for curses TUI)
# =============================================================================

# Segment type: (text, role)
Seg = Tuple[str, str]
Line = List[Seg]

_INLINE_RE = re.compile(
    r"(`+)(.*?)\1"
    r"|\*{3}(.+?)\*{3}|_{3}(.+?)_{3}"
    r"|\*{2}(.+?)\*{2}|_{2}(.+?)_{2}"
    r"|\*([^*\n]+?)\*|_([^_\n]+?)_"
    r"|!\[([^\]]*)\]\([^)]*\)"
    r"|\[([^\]]*)\]\(([^)]*)\)",
    re.DOTALL,
)

_SYNTAX_PY_KW = set(
    "False None True and as assert async await break class continue def del "
    "elif else except finally for from global if import in is lambda nonlocal "
    "not or pass raise return try while with yield".split()
)
_SYNTAX_R_KW = set(
    "if else while for repeat in next break function NULL NA TRUE FALSE "
    "Inf NaN NA_integer_ NA_real_ NA_complex_ NA_character_".split()
)


def _parse_inline(text: str) -> List[Seg]:
    out: List[Seg] = []
    last = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > last:
            out.append((text[last : m.start()], "normal"))
        if m.group(1):
            out.append((m.group(2), "code"))
        elif m.group(3) or m.group(4):
            out.append((m.group(3) or m.group(4), "bolditalic"))
        elif m.group(5) or m.group(6):
            out.append((m.group(5) or m.group(6), "bold"))
        elif m.group(7) or m.group(8):
            out.append((m.group(7) or m.group(8), "italic"))
        elif m.group(9) is not None:
            out.append((f"[img: {m.group(9)}]", "image"))
        elif m.group(10):
            out.append((m.group(10), "link"))
        last = m.end()
    if last < len(text):
        out.append((text[last:], "normal"))
    return out or [(text, "normal")]


def _wrap_segs(segs: List[Seg], width: int) -> List[Line]:
    if width <= 0:
        return [list(segs)]
    result: List[Line] = []
    line: Line = []
    col = 0
    for text, role in segs:
        for tok in re.split(r"(\s+)", text):
            if not tok:
                continue
            is_ws = not tok.strip()
            tlen = len(tok)
            if is_ws:
                if col == 0:
                    continue
                if col + tlen <= width:
                    line.append((tok, role))
                    col += tlen
            else:
                if tlen >= width:
                    while tok:
                        chunk = tok[:width]
                        tok = tok[width:]
                        if line:
                            result.append(line)
                        line = [(chunk, role)]
                        col = len(chunk)
                elif col == 0:
                    line.append((tok, role))
                    col = tlen
                elif col + tlen <= width:
                    line.append((tok, role))
                    col += tlen
                else:
                    if line:
                        result.append(line)
                    line = [(tok, role)]
                    col = tlen
    if line:
        result.append(line)
    return result or [[]]


def render_markdown(
    md: str, width: int, tab_width: int = 4, syntax: bool = True
) -> List[Line]:
    """Convert a markdown string to a list of display lines (lists of Seg)."""
    width = max(10, width)
    lines: List[Line] = []
    src = md.splitlines()
    i = 0
    n = len(src)

    while i < n:
        ln = src[i]

        # Fenced code block
        fm = re.match(r"^(`{3,}|~{3,})\s*(\S*)", ln)
        if fm:
            fence, lang = fm.group(1), fm.group(2).lower()
            i += 1
            code_lines: List[str] = []
            while i < n and not src[i].startswith(fence[:3]):
                code_lines.append(src[i])
                i += 1
            i += 1  # closing fence
            lbl = f" {lang} " if lang else " "
            top = "┌" + lbl + "─" * max(0, width - 2 - len(lbl)) + "┐"
            lines.append([(top, "codeblock")])
            full_code = "\n".join(code_lines)
            for cl in code_lines:
                cl_exp = cl.replace("\t", " " * tab_width)
                if syntax and lang in ("python", "py"):
                    lines.append([("│ ", "codeblock")] + _lex_python_line(cl_exp))
                elif syntax and lang in ("r",):
                    lines.append([("│ ", "codeblock")] + _lex_r_line(cl_exp))
                else:
                    lines.append([("│ ", "codeblock"), (cl_exp, "codeblock")])
            bot = "└" + "─" * (width - 2) + "┘"
            lines.append([(bot, "codeblock")])
            lines.append([])
            continue

        # Setext headings
        if i + 1 < n and re.match(r"^=+\s*$", src[i + 1]) and ln.strip():
            lines.append([("# " + ln.strip(), "h1")])
            lines.append([("═" * min(len(ln) + 2, width), "h1")])
            lines.append([])
            i += 2
            continue
        if i + 1 < n and re.match(r"^-+\s*$", src[i + 1]) and ln.strip():
            lines.append([("## " + ln.strip(), "h2")])
            lines.append([("─" * min(len(ln) + 3, width), "h2")])
            lines.append([])
            i += 2
            continue

        # ATX heading
        hm = re.match(r"^(#{1,6})\s+(.*?)(?:\s+#+\s*)?$", ln)
        if hm:
            lv = min(len(hm.group(1)), 4)
            role = f"h{lv}"
            txt = hm.group(2).strip()
            prefix = {"h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### "}[role]
            segs = [(prefix, role)] + [(s, role) for s, _ in _parse_inline(txt)]
            lines.append(segs)
            if lv == 1:
                lines.append([("═" * min(len(prefix + txt), width), "h1")])
            elif lv == 2:
                lines.append([("─" * min(len(prefix + txt), width), "h2")])
            lines.append([])
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^(\*{3,}|-{3,}|_{3,})\s*$", ln.strip()):
            lines.append([("─" * width, "hr")])
            i += 1
            continue

        # Blockquote
        if ln.startswith(">"):
            qls: List[str] = []
            while i < n and (src[i].startswith(">") or (qls and not src[i].strip())):
                qls.append(src[i][1:].lstrip() if src[i].startswith(">") else "")
                i += 1
            text = " ".join(l for l in qls if l)
            pfx: Line = [("▌ ", "quote")]
            for wl in _wrap_segs(_parse_inline(text), width - 2):
                lines.append(pfx + wl)
            lines.append([])
            continue

        # Unordered list
        if re.match(r"^\s*[-*+]\s+\S", ln):
            while i < n and re.match(r"^\s*[-*+]\s+\S", src[i]):
                m2 = re.match(r"^\s*[-*+]\s+(.*)", src[i])
                item = m2.group(1) if m2 else ""
                rows = _wrap_segs(_parse_inline(item), width - 3)
                for k, row in enumerate(rows):
                    pfx_seg = [("  • ", "bullet")] if k == 0 else [("    ", "normal")]
                    lines.append(pfx_seg + row)
                i += 1
            lines.append([])
            continue

        # Ordered list
        if re.match(r"^\s*\d+[.)]\s+\S", ln):
            counter = 1
            while i < n and re.match(r"^\s*\d+[.)]\s+\S", src[i]):
                m2 = re.match(r"^\s*\d+[.)]\s+(.*)", src[i])
                item = m2.group(1) if m2 else ""
                pfx_str = f"  {counter}. "
                rows = _wrap_segs(_parse_inline(item), width - len(pfx_str))
                for k, row in enumerate(rows):
                    p = (
                        [(pfx_str, "ordinal")]
                        if k == 0
                        else [(" " * len(pfx_str), "normal")]
                    )
                    lines.append(p + row)
                counter += 1
                i += 1
            lines.append([])
            continue

        # Table
        if "|" in ln and i + 1 < n and re.match(r"^\|?[\s\-:|]+\|", src[i + 1]):
            tls: List[str] = []
            while i < n and "|" in src[i]:
                tls.append(src[i])
                i += 1
            for tl in tls:
                if re.match(r"^\|?[\s\-:|]+\|", tl):
                    cells = [c.strip() for c in tl.strip("|").split("|")]
                    sep = "┼".join("─" * (len(c) + 2) for c in cells)
                    lines.append([("├" + sep + "┤", "table")])
                else:
                    cells = [c.strip() for c in tl.strip("|").split("|")]
                    row_line: Line = [("│", "table")]
                    for j, cell in enumerate(cells):
                        if j:
                            row_line.append(("│", "table"))
                        row_line.append((" ", "normal"))
                        row_line.extend(_parse_inline(cell))
                        row_line.append((" ", "normal"))
                    row_line.append(("│", "table"))
                    lines.append(row_line)
            lines.append([])
            continue

        # Blank line
        if not ln.strip():
            lines.append([])
            i += 1
            continue

        # Paragraph
        pls: List[str] = [ln]
        i += 1
        while (
            i < n
            and src[i].strip()
            and not re.match(r"^(#{1,6}\s|[-*+]\s|\d+[.)]\s|>|`{3,}|~{3,})", src[i])
        ):
            pls.append(src[i])
            i += 1
        text = " ".join(l.rstrip() for l in pls)
        for wl in _wrap_segs(_parse_inline(text), width):
            lines.append(wl)
        lines.append([])

    return lines


def _lex_python_line(line: str) -> List[Seg]:
    """Tokenize a Python source line into (text, role) segments."""
    out: List[Seg] = []
    rest = line
    while rest:
        if rest.startswith("#"):
            out.append((rest, "comment"))
            break
        m = re.match(r'"[^"]*"|\'[^\']*\'', rest)
        if m:
            out.append((m.group(), "string"))
            rest = rest[m.end() :]
            continue
        m = re.match(r"[A-Za-z_]\w*", rest)
        if m:
            w = m.group()
            role = "keyword" if w in _SYNTAX_PY_KW else "code_normal"
            out.append((w, role))
            rest = rest[m.end() :]
            continue
        m = re.match(r"\d+\.?\d*", rest)
        if m:
            out.append((m.group(), "number"))
            rest = rest[m.end() :]
            continue
        out.append((rest[0], "code_normal"))
        rest = rest[1:]
    return out


def _lex_r_line(line: str) -> List[Seg]:
    """Tokenize an R source line into (text, role) segments."""
    out: List[Seg] = []
    rest = line
    while rest:
        if rest.startswith("#"):
            out.append((rest, "comment"))
            break
        m = re.match(r'"[^"]*"|\'[^\']*\'', rest)
        if m:
            out.append((m.group(), "string"))
            rest = rest[m.end() :]
            continue
        m = re.match(r"[A-Za-z_.][A-Za-z0-9_.]*", rest)
        if m:
            w = m.group()
            role = "keyword" if w in _SYNTAX_R_KW else "code_normal"
            out.append((w, role))
            rest = rest[m.end() :]
            continue
        m = re.match(r"\d+\.?\d*", rest)
        if m:
            out.append((m.group(), "number"))
            rest = rest[m.end() :]
            continue
        out.append((rest[0], "code_normal"))
        rest = rest[1:]
    return out


def lines_to_plain(rendered: List[Line]) -> str:
    """Convert rendered lines back to plain text (strip roles)."""
    return "\n".join("".join(t for t, _ in line) for line in rendered)
