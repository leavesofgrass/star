"""Unix manual pages (roff ``man``/``mdoc`` macros) → Markdown, stdlib only.

Reads ``ls.1``, ``printf.3.gz``, ``foo.man``, ``foo.roff`` and the like: the
``.TH`` header, ``.SH``/``.SS`` headings, ``.PP``/``.TP``/``.IP`` paragraphs,
``.B``/``.I``/``.BR``… font macros, ``.nf``/``.fi`` verbatim blocks, ``.RS``/
``.RE`` indents, ``.UR``/``.UE`` links, ``.TS``/``.TE`` tables (kept verbatim)
and the common inline escapes (``\\fB``, ``\\-``, ``\\(em`` …).  The BSD
``mdoc`` macro set (``.Sh``, ``.Nm``, ``.Fl``, ``.Bl``/``.It``…) is handled
well enough for a readable page.  Pandoc's ``man`` reader is preferred when
installed; this is the zero-dependency path.

Naming: a page is named for its section, not its format — ``ls.1``,
``Tcl_Init.3tcl`` — and installed pages are gzipped on top (``printf.3.gz``).
:func:`is_manual_page_name` mirrors Paperback's rule so those route here.
"""
import gzip

from .._runtime import *  # noqa: F401,F403

_GLYPHS: Dict[str, str] = {
    "em": "—", "en": "–", "hy": "-", "lq": "“", "rq": "”",
    "oq": "‘", "cq": "’", "aq": "'", "dq": '"', "bu": "•",
    "co": "©", "rg": "®", "tm": "™", "ct": "¢", "de": "°",
    "ps": "¶", "sc": "§", "mu": "×", "di": "÷", "pl": "+",
    "mi": "−", "eq": "=", "<=": "≤", ">=": "≥", "!=": "≠",
    "->": "→", "<-": "←", "ua": "↑", "da": "↓", "rs": "\\",
    "sl": "/", "ha": "^", "ti": "~", "at": "@", "sh": "#", "Do": "$", "Eu": "€",
    "12": "½", "14": "¼", "34": "¾", "fm": "′", "dg": "†",
    "dd": "‡", "ss": "ß", "ff": "ff", "fi": "fi", "fl": "fl", "Fi": "ffi",
    "Fl": "ffl", "lB": "[", "rB": "]", "lC": "{", "rC": "}", "la": "<", "ra": ">",
    "ba": "|", "br": "|", "or": "|", "sq": "□", "ci": "○", "OK": "✓",
}


def is_manual_page_name(path: "str | Path") -> bool:
    """True for ``name.N[suffix]`` and ``name.N[suffix].gz`` where N is a digit —
    the way installed manual pages are named."""
    p = Path(path)
    if p.suffix.lower() == ".gz":
        p = Path(p.stem)
    section = p.suffix[1:] if p.suffix else ""
    return bool(section) and section[0].isdigit() and section.isalnum()


def _read_roff(path: str) -> str:
    data = Path(path).read_bytes()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data.decode("utf-8", errors="replace")


def _escapes(text: str, fonts: bool = True) -> str:
    """Resolve roff inline escapes to Markdown / Unicode."""
    out: List[str] = []
    i = 0
    n = len(text)
    bold = italic = False

    def close() -> str:
        nonlocal bold, italic
        s = ""
        if bold:
            s += "**"
        if italic:
            s += "*"
        bold = italic = False
        return s

    while i < n:
        c = text[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        i += 1
        if i >= n:
            break
        c = text[i]
        i += 1
        if c == "f":
            # \fB \fI \fR \fP \f(CW \f[name] \f1..
            if i < n and text[i] == "(":
                name = text[i + 1:i + 3]
                i += 3
            elif i < n and text[i] == "[":
                j = text.find("]", i)
                name = text[i + 1:j] if j > 0 else ""
                i = j + 1 if j > 0 else n
            else:
                name = text[i:i + 1]
                i += 1
            if not fonts:
                continue
            name = name.upper()
            if name in ("B", "3", "BI", "CB"):
                out.append(close())
                bold = True
                out.append("**")
                if name == "BI":
                    italic = True
                    out.append("*")
            elif name in ("I", "2", "CI"):
                out.append(close())
                italic = True
                out.append("*")
            else:  # R, P, 1, CW, CR …
                out.append(close())
        elif c == "(":
            out.append(_GLYPHS.get(text[i:i + 2], ""))
            i += 2
        elif c == "[":
            j = text.find("]", i)
            name = text[i:j] if j > 0 else ""
            i = j + 1 if j > 0 else n
            if name.startswith("u") and len(name) >= 5:
                try:
                    out.append(chr(int(name[1:], 16)))
                    continue
                except ValueError:
                    pass
            out.append(_GLYPHS.get(name, ""))
        elif c == "-":
            out.append("-")
        elif c in ("e", "\\"):
            out.append("\\")
        elif c == "&" or c == ")" or c == ":" or c == "%" or c == "/" or c == ",":
            pass
        elif c == "~" or c == " " or c == "0" or c == "|" or c == "^":
            out.append(" " if c in ("~", " ", "0") else "")
        elif c == '"' or c == "#":
            break  # comment to end of line
        elif c == "*":
            # string interpolation: \*(xx / \*[name] / \*x
            if i < n and text[i] == "(":
                name = text[i + 1:i + 3]
                i += 3
            elif i < n and text[i] == "[":
                j = text.find("]", i)
                name = text[i + 1:j] if j > 0 else ""
                i = j + 1 if j > 0 else n
            else:
                name = text[i:i + 1]
                i += 1
            out.append({"R": "®", "Tm": "™", "lq": "“", "rq": "”"}.get(name, ""))
        elif c == "s" or c == "h" or c == "v" or c == "w" or c == "l" or c == "L" or c == "d" or c == "u":
            # size/motion escapes: \s+2 \s0 \h'…' — drop the argument
            if i < n and text[i] == "'":
                j = text.find("'", i + 1)
                i = j + 1 if j > 0 else n
            else:
                while i < n and (text[i] in "+-" or text[i].isdigit()):
                    i += 1
        elif c == "c":
            pass  # line continuation
        else:
            out.append(c)
    out.append(close())
    return "".join(out)


def _split_args(s: str) -> List[str]:
    """Split macro arguments, honouring double quotes."""
    args: List[str] = []
    i = 0
    n = len(s)
    while i < n:
        while i < n and s[i] == " ":
            i += 1
        if i >= n:
            break
        if s[i] == '"':
            j = i + 1
            buf = []
            while j < n:
                if s[j] == '"':
                    if j + 1 < n and s[j + 1] == '"':
                        buf.append('"')
                        j += 2
                        continue
                    break
                buf.append(s[j])
                j += 1
            args.append("".join(buf))
            i = j + 1
        else:
            j = i
            while j < n and s[j] != " ":
                j += 1
            args.append(s[i:j])
            i = j
    return args


def _alternate(args: List[str], fonts: Tuple[str, str]) -> str:
    """``.BR foo bar`` alternates fonts B, R, B, R … across the arguments."""
    marks = {"B": "**", "I": "*", "R": ""}
    out = []
    for k, a in enumerate(args):
        f = fonts[k % 2]
        m = marks.get(f, "")
        a = _escapes(a, fonts=False)
        out.append(f"{m}{a}{m}" if a and m else a)
    return "".join(out)


def _mdoc_inline(text: str) -> str:
    """Resolve the mdoc inline macros that appear inside ``.Op``/``.It`` arguments."""
    text = re.sub(r"\bFl (\S+)", r"**-\1**", text)
    text = re.sub(r"\bAr (\S+)", r"*\1*", text)
    text = re.sub(r"\b(Cm|Ic|Sy|Nm) (\S+)", r"**\2**", text)
    text = re.sub(r"\bPa (\S+)", r"*\1*", text)
    text = re.sub(r"\b(Ns|Xo|Xc|Oo|Oc)\b ?", "", text)
    return text.strip()


def _roff_to_markdown(src: str) -> str:
    lines = src.replace("\r\n", "\n").split("\n")
    out: List[str] = []
    para: List[str] = []
    verbatim = False
    indent = 0
    pending_tag = False        # next line is a .TP tag
    tag_text = ""
    mdoc = False
    list_stack: List[str] = []
    name = ""

    def flush() -> None:
        nonlocal para
        text = " ".join(p for p in para if p).strip()
        para = []
        if text:
            text = re.sub(r"[ \t]+", " ", text)
            out.append(("  " * indent) + text)
            out.append("")

    def emit_line(text: str) -> None:
        nonlocal tag_text, pending_tag
        text = _escapes(text)
        if pending_tag:
            tag_text = text
            pending_tag = False
            return
        if tag_text:
            tag = tag_text.strip()
            if not tag.startswith(("**", "*", "`")):
                tag = f"**{tag}**"
            para.append(f"{tag}  ")
            tag_text = ""
            flush()
            para.append(("  " * (indent + 1)) + text)
        else:
            para.append(text)

    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        if raw.startswith(("'\\\"", ".\\\"", "\\\"", ".\\#")):
            continue
        if raw.startswith(('\'', ".")) and len(raw) > 1 or raw in (".", "'"):
            body = raw[1:]
            if not body.strip():
                if verbatim:
                    out.append("")
                continue
            parts = body.strip().split(None, 1)
            mac = parts[0]
            rest = parts[1] if len(parts) > 1 else ""
            args = _split_args(rest)
            # ── structure ────────────────────────────────────────────────
            if mac == "TH":
                flush()
                if args:
                    title = _escapes(args[0], fonts=False)
                    sec = f"({args[1]})" if len(args) > 1 else ""
                    out += [f"# {title}{sec}", ""]
                    name = title
            elif mac in ("Dt",):
                flush()
                mdoc = True
                if args:
                    sec = f"({args[1]})" if len(args) > 1 else ""
                    out += [f"# {args[0]}{sec}", ""]
            elif mac in ("Dd", "Os", "Dv"):
                mdoc = True
            elif mac in ("SH", "Sh"):
                flush()
                if verbatim:
                    out += ["```", ""]
                    verbatim = False
                indent = 0
                tag_text = ""
                title = _escapes(rest, fonts=False).strip('"').strip() if rest else ""
                if not title and i < len(lines):
                    title = _escapes(lines[i], fonts=False).strip()
                    i += 1
                if title:
                    out += [f"## {title.title() if title.isupper() else title}", ""]
            elif mac in ("SS", "Ss"):
                flush()
                title = _escapes(rest, fonts=False).strip('"').strip() if rest else ""
                if not title and i < len(lines):
                    title = _escapes(lines[i], fonts=False).strip()
                    i += 1
                if title:
                    out += [f"### {title}", ""]
            elif mac in ("PP", "LP", "P", "Pp", "HP"):
                flush()
                indent = max(0, indent) if list_stack else 0
                tag_text = ""
            elif mac == "TP":
                flush()
                tag_text = ""
                pending_tag = True  # the next output line (text or macro) is the tag
            elif mac == "IP":
                flush()
                tag = _escapes(args[0], fonts=False) if args else ""
                if tag in ("\\(bu", "•", "*", "-", "o", "\\[bu]"):
                    para.append("- ")
                elif tag:
                    para.append(f"**{tag}**  ")
                    flush()
                    para.append("  ")
            elif mac in ("RS", "Bd"):
                flush()
                indent += 1
                if mac == "Bd" and ("-literal" in args or "-unfilled" in args):
                    verbatim = True
                    out.append("```")
            elif mac in ("RE", "Ed"):
                flush()
                if mac == "Ed" and verbatim:
                    out += ["```", ""]
                    verbatim = False
                indent = max(0, indent - 1)
            elif mac == "nf":
                flush()
                verbatim = True
                out.append("```")
            elif mac == "fi":
                if verbatim:
                    out += ["```", ""]
                verbatim = False
            elif mac in ("br",):
                if para:
                    para[-1] = para[-1] + "  \n"
            elif mac in ("sp", "ne", "ns", "rs"):
                flush()
            elif mac == "TS":
                flush()
                out.append("```")
                verbatim = True
            elif mac == "TE":
                out += ["```", ""]
                verbatim = False
            elif mac in ("UR", "MT"):
                flush() if False else None
                url = args[0] if args else ""
                para.append(f"<{url}> " if url else "")
            elif mac in ("UE", "ME"):
                pass
            # ── fonts (man) ──────────────────────────────────────────────
            elif mac == "B":
                if args:
                    emit_line("**" + " ".join(args) + "**")
                else:
                    if i < len(lines):
                        emit_line("**" + lines[i] + "**")
                        i += 1
            elif mac == "I":
                if args:
                    emit_line("*" + " ".join(args) + "*")
                elif i < len(lines):
                    emit_line("*" + lines[i] + "*")
                    i += 1
            elif mac in ("R", "SM", "SB"):
                if args:
                    emit_line(" ".join(args))
            elif mac in ("BI", "IB", "BR", "RB", "IR", "RI"):
                emit_line(_alternate(args, (mac[0], mac[1])))
            # ── mdoc essentials ──────────────────────────────────────────
            elif mac == "Nm":
                if args:
                    name = name or args[0]
                emit_line("**" + (" ".join(args) or name) + "**")
            elif mac == "Nd":
                emit_line("— " + " ".join(args))
            elif mac in ("Fl",):
                emit_line(" ".join("**-" + a + "**" for a in args))
            elif mac in ("Ar", "Fa", "Va", "Vt", "Em", "Pa", "Ev", "Dv", "Cm", "Ic", "Li", "Ql", "Sy", "Fn", "Xr", "Ft", "Ns", "Ap", "Sx", "St", "At", "Bx", "Ux", "Fx", "Nx", "Ox", "Dx"):
                text = " ".join(args)
                if mac in ("Ar", "Em", "Va", "Pa"):
                    emit_line(f"*{text}*" if text else "")
                elif mac in ("Sy", "Cm", "Ic", "Fn", "Ev", "Dv"):
                    emit_line(f"**{text}**" if text else "")
                elif mac == "Li":
                    emit_line(f"`{text}`" if text else "")
                elif mac == "Xr":
                    emit_line(f"{args[0]}({args[1]})" if len(args) > 1 else text)
                else:
                    emit_line(text)
            elif mac in ("Op", "Oo", "Oc"):
                if mac == "Op":
                    emit_line("[" + _mdoc_inline(" ".join(args)) + "]")
            elif mac in ("Bl",):
                flush()
                list_stack.append("bullet" if "-bullet" in args or "-dash" in args else "tag")
            elif mac == "El":
                flush()
                if list_stack:
                    list_stack.pop()
            elif mac == "It":
                flush()
                kind = list_stack[-1] if list_stack else "tag"
                text = _mdoc_inline(" ".join(args))
                if kind == "bullet":
                    para.append("- ")
                elif text:
                    tag = text if text.startswith(("**", "*", "`")) else f"**{text}**"
                    para.append(f"{tag}  ")
                    flush()
                    para.append("  ")
                else:
                    para.append("- ")
            elif mac in ("Pp", "Lp", "Bk", "Ek", "Rs", "Re", "Sm", "Ta", "Tn"):
                if mac in ("Pp", "Lp"):
                    flush()
            elif mac in ("Dq", "Sq", "Qq", "Pq", "Bq", "Brq", "Aq", "Do", "So", "Qo", "Po", "Bo", "Dc", "Sc", "Qc", "Pc", "Bc", "Ao", "Ac"):
                q = {"Dq": ("“", "”"), "Sq": ("‘", "’"), "Qq": ('"', '"'),
                     "Pq": ("(", ")"), "Bq": ("[", "]"), "Brq": ("{", "}"), "Aq": ("<", ">")}.get(mac)
                if q:
                    emit_line(q[0] + " ".join(args) + q[1])
                elif args:
                    emit_line(" ".join(args))
            elif mac in ("%A", "%T", "%B", "%J", "%D", "%R", "%N", "%O", "%P", "%V", "%I", "%Q", "%U", "%C"):
                emit_line(" ".join(args))
            elif mac in ("de", "ig", "am"):
                # skip macro definitions / ignored blocks up to ".."
                while i < len(lines) and lines[i].strip() != "..":
                    i += 1
                i += 1
            elif mac in ("ds", "nr", "if", "ie", "el", "ll", "in", "ti", "ad", "na", "hy", "nh", "ta", "ft", "ps", "vs", "ce", "fam", "so", "mso", "tr", "char", "rr", "rm", "als", "nop", "ie", "return", "pl", "po", "pn", "bp", "ev", "ex", "wh", "ch", "ab", "tm", "ne", "cs", "ss", "ul", "cu", "uf", "BT", "PT", "DT", "PD", "OP", "EX", "EE", "SY", "YS", "TQ", "ft", "ll", "It", "Xo", "Xc"):
                if mac == "EX":
                    flush()
                    verbatim = True
                    out.append("```")
                elif mac == "EE":
                    out += ["```", ""]
                    verbatim = False
                elif mac == "SY":
                    flush()
                    emit_line("**" + " ".join(args) + "** ")
                elif mac == "OP":
                    emit_line("[" + _alternate(args, ("B", "I")) + "]")
                elif mac == "TQ":
                    flush()
                    if i < len(lines) and not lines[i].startswith("."):
                        tag_text = _escapes(lines[i])
                        i += 1
                elif mac == "ce":
                    pass
            else:
                # Unknown macro: keep its arguments as text (better than losing them).
                if args and mac[0].isupper() and not mdoc:
                    emit_line(" ".join(args))
            continue
        # ── text line ────────────────────────────────────────────────────
        if verbatim:
            out.append(_escapes(raw, fonts=False))
            continue
        if not raw.strip():
            flush()
            continue
        emit_line(raw)
    flush()
    if verbatim:
        out.append("```")
    md = "\n".join(out)
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"
    return md


def _load_manpage(path: str) -> str:
    """Load a roff manual page (optionally gzipped) as Markdown."""
    try:
        src = _read_roff(path)
    except Exception as e:  # noqa: BLE001
        return f"# Error\n\n```\n{e}\n```\n"
    if not src.strip():
        return f"# {Path(path).name}\n\n*(empty file)*\n"
    # A .gz that is not roff at all (tarball, other text) — show it as text.
    if not re.search(r"^[.'](TH|Dd|Dt|SH|Sh|PP|nf|B|I|TP)\b", src, re.M):
        body = src if len(src) < 2_000_000 else src[:2_000_000]
        return f"# {Path(path).name}\n\n```\n{body}\n```\n" if "\x00" not in body else (
            f"# {Path(path).name}\n\n*(binary content)*\n"
        )
    try:
        md = _roff_to_markdown(src)
    except Exception as e:  # noqa: BLE001
        return f"# Manual Page Error\n\n```\n{e}\n```\n"
    if not md.lstrip().startswith("#"):
        md = f"# {Path(path).name}\n\n{md}"
    return md
