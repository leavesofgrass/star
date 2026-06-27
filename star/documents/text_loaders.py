"""Plain text, Markdown, code, and lightweight-markup loaders."""
from .._runtime import *  # noqa: F401,F403
from ..markup import _asciidoc_to_md, _creole_to_md, _latex_to_md, _mediawiki_to_md, _orgmode_to_md, _pandoc_convert, _rst_to_md, _textile_to_md
from .html import _load_html_str


def _load_plain_text(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"# Error\n\n```\n{e}\n```\n"


def _load_markdown(path: str) -> str:
    return _load_plain_text(path)


def _load_r_code(path: str) -> str:
    """Load R source with fenced code block for syntax highlighting."""
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"# Error\n\n```\n{e}\n```\n"
    return f"# {Path(path).name}\n\n```r\n{src}\n```\n"


def _load_rmarkdown(path: str) -> str:
    """R Markdown: strip YAML front matter and render as markdown."""
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"# Error\n\n```\n{e}\n```\n"
    src = re.sub(r"^---\s*\n.*?\n---\s*\n", "", src, flags=re.S)
    # Code chunks — wrap in fenced blocks with language tag
    src = re.sub(r"```\{r([^}]*)\}", r"```r", src)
    src = re.sub(r"```\{python([^}]*)\}", r"```python", src)
    return src


def _load_notebook(path: str) -> str:
    """Jupyter notebook: extract markdown and code cells."""
    try:
        nb = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
        cells = nb.get("cells", [])
        parts: List[str] = [f"# {Path(path).name}", ""]
        for cell in cells:
            ct = cell.get("cell_type", "")
            src = "".join(cell.get("source", []))
            if ct == "markdown":
                parts.append(src)
                parts.append("")
            elif ct == "code":
                lang = (
                    nb.get("metadata", {})
                    .get("kernelspec", {})
                    .get("language", "python")
                )
                parts.append(f"```{lang}")
                parts.append(src)
                parts.append("```")
                parts.append("")
        return "\n".join(parts)
    except Exception as e:
        return f"# Notebook Error\n\n```\n{e}\n```\n"


def _load_orgmode(path: str) -> str:
    """Load an Org-mode file as Markdown.

    Strategy: Pandoc → orgparse library → built-in _orgmode_to_md().
    """
    # 1. Pandoc (handles the full Org spec including exports, macros, etc.)
    md = _pandoc_convert(path, "org")
    if md:
        return md
    # 2. orgparse (pip install orgparse) — Python-native Org parser
    try:
        import orgparse as _op  # type: ignore[import]

        doc = _op.load(path)
        # Convert the orgparse tree to plain text lines then run through
        # the Markdown converter for any residual markup.
        lines_out: List[str] = []
        for node in doc.children:
            lines_out.extend(str(node).splitlines())
        return _orgmode_to_md("\n".join(lines_out))
    except Exception:
        pass
    # 3. Built-in comprehensive heuristic
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
        return _orgmode_to_md(src)
    except Exception as e:
        return f"# Org-mode Error\n\n```\n{e}\n```\n"


def _load_rst(path: str) -> str:
    """Load a reStructuredText file as Markdown."""
    # 1. Pandoc
    md = _pandoc_convert(path, "rst")
    if md:
        return md
    # 2. docutils (canonical Python RST library)
    try:
        from docutils.core import publish_parts  # type: ignore[import]

        src = Path(path).read_text(encoding="utf-8", errors="replace")
        html = publish_parts(src, writer_name="html")["html_body"]
        return _load_html_str(html)
    except Exception:
        pass
    # 3. Built-in heuristic converter
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
        return _rst_to_md(src)
    except Exception as e:
        return f"# RST Error\n\n```\n{e}\n```\n"


def _load_mediawiki(path: str) -> str:
    """Load a MediaWiki markup file as Markdown."""
    # 1. Pandoc
    md = _pandoc_convert(path, "mediawiki")
    if md:
        return md
    # 2. mwparserfromhell (optional pure-Python MediaWiki parser)
    try:
        import mwparserfromhell as _mwp  # type: ignore[import]

        src = Path(path).read_text(encoding="utf-8", errors="replace")
        wikicode = _mwp.parse(src)
        # Strip templates and extract plain wikitext, then apply basic converter
        plain = wikicode.strip_code(normalize=True, collapse=True)
        return _mediawiki_to_md(plain)
    except Exception:
        pass
    # 3. Built-in heuristic
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
        return _mediawiki_to_md(src)
    except Exception as e:
        return f"# MediaWiki Error\n\n```\n{e}\n```\n"


def _load_asciidoc(path: str) -> str:
    """Load an AsciiDoc file as Markdown."""
    # 1. Pandoc
    md = _pandoc_convert(path, "asciidoc")
    if md:
        return md
    # 2. asciidoctor CLI  (renders to HTML, then convert)
    asciidoctor = shutil.which("asciidoctor") or shutil.which("asciidoc")
    if asciidoctor:
        try:
            r = subprocess.run(
                [asciidoctor, "-b", "html5", "-o", "-", path],
                capture_output=True,
                timeout=30,
            )
            if r.returncode == 0 and r.stdout:
                return _load_html_str(r.stdout.decode("utf-8", errors="replace"))
        except Exception:
            pass
    # 3. Built-in heuristic
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
        return _asciidoc_to_md(src)
    except Exception as e:
        return f"# AsciiDoc Error\n\n```\n{e}\n```\n"


def _load_textile(path: str) -> str:
    """Load a Textile markup file as Markdown."""
    # 1. Pandoc
    md = _pandoc_convert(path, "textile")
    if md:
        return md
    # 2. textile Python library (pip install textile)
    try:
        import textile as _textile_lib  # type: ignore[import]

        src = Path(path).read_text(encoding="utf-8", errors="replace")
        html = _textile_lib.textile(src)
        return _load_html_str(html)
    except Exception:
        pass
    # 3. Built-in heuristic
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
        return _textile_to_md(src)
    except Exception as e:
        return f"# Textile Error\n\n```\n{e}\n```\n"


def _load_creole(path: str) -> str:
    """Load a Wiki Creole 1.0 file as Markdown."""
    # 1. Pandoc
    md = _pandoc_convert(path, "creole")
    if md:
        return md
    # 2. Built-in converter (Creole is simple and self-contained)
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
        return _creole_to_md(src)
    except Exception as e:
        return f"# Creole Error\n\n```\n{e}\n```\n"


def _load_latex(path: str) -> str:
    """Load a LaTeX (.tex / .ltx) file as Markdown.

    Strategy: Pandoc → built-in _latex_to_md() stripper.

    Pandoc produces the best output for well-formed LaTeX (it handles
    cross-references, bibliographies, custom macros from \\newcommand, etc.).
    The built-in fallback covers the 80–90% case for typical academic papers
    and lecture notes without requiring any external tools.
    """
    # 1. Pandoc — also handles BibTeX references if they are inlined
    md = _pandoc_convert(path, "latex")
    if md:
        return md
    # 2. Built-in converter
    try:
        src = Path(path).read_text(encoding="utf-8", errors="replace")
        return _latex_to_md(src)
    except Exception as e:
        return f"# LaTeX Error\n\n```\n{e}\n```\n"
