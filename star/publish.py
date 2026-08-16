"""Publishing pipeline — options, stylesheet templates, and Pandoc arguments.

The engine side of the publishing arc (design: pandoc-first).  This module is
deliberately UI-free: the GUI Publish dialog and the TUI ``M-x publish`` both
assemble a :class:`PublishOptions` and hand it to an exporter
(:mod:`star.export`), which turns it into Pandoc flags through
:func:`build_pandoc_args`.  Keeping the flag assembly a pure function of the
options means the whole mapping is unit-testable without Pandoc installed.

Templates are plain CSS files shared by the EPUB and HTML targets.  Bundled
stylesheets ship in ``star/publish_styles/`` and are seeded into the user's
``publish-styles`` config folder on first discovery — the same
copy-once-never-overwrite model the theme folder uses
(:func:`star.themes._seed_default_css_themes`), so a hand-edited template is
never clobbered and any ``*.css`` dropped into the folder simply appears.
"""
from ._runtime import *  # noqa: F401,F403
from ._runtime import PUBLISH_STYLES_DIR

#: Bundled stylesheet directory (package data; may be absent in a trimmed
#: install — every consumer treats a missing directory as "no bundled styles").
_BUNDLED_STYLES_DIR = Path(__file__).resolve().parent / "publish_styles"


@dataclass
class PublishOptions:
    """Everything the Publish dialog (or ``M-x publish``) can choose.

    ``template`` is a stylesheet *name* (file stem) resolved through
    :func:`available_templates`; ``""`` means Pandoc's default styling.  The
    metadata fields are *overrides* — blank values fall through to the
    document's own metadata (see :func:`resolve_metadata`).
    """

    fmt: str = "epub"
    template: str = ""
    title: str = ""
    author: str = ""
    language: str = ""
    date: str = ""
    cover_image: str = ""
    toc: bool = True
    toc_depth: int = 3
    # Heading level that starts a new chapter/file inside the EPUB.  Named
    # --split-level in pandoc >= 3, --epub-chapter-level before.
    split_level: int = 1
    # Citation processing (0.1.30): a CSL style name from
    # :func:`available_citation_styles` switches on pandoc's citeproc, and
    # ``bibliography`` names the references file — callers leave it "" to have
    # the front-end fill it from star's citation library
    # (:func:`export_bibliography`), or set an explicit .json/.bib/.ris path.
    citation_style: str = ""
    bibliography: str = ""


def _seed_user_styles() -> None:
    """Copy each bundled stylesheet into the user folder if absent.

    Existing files are never overwritten, so a user's edits survive upgrades;
    a bundled style they deleted does reappear (matching theme behavior).
    """
    if not _BUNDLED_STYLES_DIR.is_dir():
        return
    try:
        PUBLISH_STYLES_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    for pattern in ("*.css", "*.csl"):
        for src in sorted(_BUNDLED_STYLES_DIR.glob(pattern)):
            dest = PUBLISH_STYLES_DIR / src.name
            if dest.exists():
                continue
            try:
                dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            except OSError:
                pass


def available_templates() -> Dict[str, Path]:
    """Map template name (file stem) → CSS path, seeding the user folder first.

    The user folder wins on a name clash so an edited copy of a bundled style
    is the one that ships inside the export.
    """
    _seed_user_styles()
    result: Dict[str, Path] = {}
    for root in (_BUNDLED_STYLES_DIR, PUBLISH_STYLES_DIR):
        try:
            entries = sorted(root.glob("*.css"))
        except OSError:
            continue
        for css in entries:
            result[css.stem] = css
    return result


def available_citation_styles() -> Dict[str, Path]:
    """Map citation-style name (file stem) → .csl path.

    star bundles APA 7th (``apa`` — the nursing-education standard), AMA 11th
    (``american-medical-association``), and NLM/Vancouver (``vancouver``) from
    the Citation Style Language project (CC-BY-SA; each file carries its own
    license metadata).  They seed into the user ``publish-styles`` folder like
    the CSS templates, and any ``*.csl`` dropped there — the CSL repository
    has ten thousand more — appears; the user copy wins on a name clash.
    """
    _seed_user_styles()
    result: Dict[str, Path] = {}
    for root in (_BUNDLED_STYLES_DIR, PUBLISH_STYLES_DIR):
        try:
            entries = sorted(root.glob("*.csl"))
        except OSError:
            continue
        for csl in entries:
            result[csl.stem] = csl
    return result


def export_bibliography(settings: Any) -> Optional[str]:
    """Write star's citation library as CSL-JSON for ``--bibliography``.

    The automatic half of the publish bibliography: when a citation style is
    chosen and no explicit file was picked, the front-ends call this to turn
    the Study-menu citation library (``settings["citations"]``) into the
    references file pandoc consumes.  Returns the written path, or ``None``
    when the library is empty or unreadable (publishing proceeds without a
    bibliography rather than failing).
    """
    try:
        from .citations import _format_citations

        items = list(settings.get("citations", []) or [])
        if not items:
            return None
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        dest = CACHE_DIR / "publish-bibliography.json"
        dest.write_text(_format_citations(items, ".json"), encoding="utf-8")
        return str(dest)
    except Exception:  # noqa: BLE001 — bibliography is best-effort, never fatal
        return None


def _generate_reference_doc(kind: str, dest: Path) -> bool:
    """Generate an accessibility ``--reference-doc`` .docx at *dest*.

    DOCX styling can't use CSS — Pandoc styles its output by copying the
    styles of a reference document.  Rather than shipping binary .docx blobs,
    the two accessibility references are *generated* from python-docx's stock
    template (a base dependency) the first time discovery runs:

    - ``large-print``: 18 pt Normal, 1.5 line spacing, sans-serif, bumped
      headings — the large-print-edition conventions.
    - ``dyslexia-friendly``: OpenDyslexic (Word substitutes its default when
      the font is absent), 14 pt, 1.5 spacing, extra paragraph gap.

    Pandoc's docx writer puts body paragraphs in ``Body Text`` (and the first
    paragraph after a heading in ``First Paragraph``) — python-docx's template
    defines neither, so both are added based on Normal; without them the
    tuned Normal style would never actually cascade to the output text.
    Returns False (and writes nothing) when python-docx is unavailable.
    """
    try:
        import docx as _docx
        from docx.enum.style import WD_STYLE_TYPE
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Inches, Pt
    except ImportError:
        return False
    try:
        d = _docx.Document()
        normal = d.styles["Normal"]
        hanging_bibliography = False
        if kind == "large-print":
            normal.font.name = "Arial"
            normal.font.size = Pt(18)
            normal.paragraph_format.line_spacing = 1.5
            normal.paragraph_format.space_after = Pt(12)
            for name, size in (("Heading 1", 26), ("Heading 2", 22), ("Heading 3", 20)):
                st = d.styles[name]
                st.font.size = Pt(size)
        elif kind == "dyslexia-friendly":
            normal.font.name = "OpenDyslexic"
            normal.font.size = Pt(14)
            normal.paragraph_format.line_spacing = 1.5
            normal.paragraph_format.space_after = Pt(14)
        elif kind == "apa-student-paper":
            # APA 7 student-paper conventions: Times New Roman 12, double
            # spacing throughout, 0.5" first-line paragraph indents, headings
            # the same size as body text (Level 1 centered bold), and a
            # hanging-indent double-spaced reference list.
            normal.font.name = "Times New Roman"
            normal.font.size = Pt(12)
            normal.paragraph_format.line_spacing = 2.0
            normal.paragraph_format.space_after = Pt(0)
            for name in ("Heading 1", "Heading 2", "Heading 3"):
                st = d.styles[name]
                st.font.name = "Times New Roman"
                st.font.size = Pt(12)
                st.font.bold = True
                st.font.color.rgb = None  # body-colored, not theme blue
            d.styles["Heading 1"].paragraph_format.alignment = (
                WD_ALIGN_PARAGRAPH.CENTER
            )
            hanging_bibliography = True
        elif kind == "ama-manuscript":
            # AMA-style manuscript: Times New Roman 12, double-spaced; the
            # numeric (superscript) citation format comes from the CSL style,
            # so the reference list stays flush (no hanging indent).
            normal.font.name = "Times New Roman"
            normal.font.size = Pt(12)
            normal.paragraph_format.line_spacing = 2.0
            normal.paragraph_format.space_after = Pt(0)
            for name in ("Heading 1", "Heading 2", "Heading 3"):
                st = d.styles[name]
                st.font.name = "Times New Roman"
                st.font.color.rgb = None
        else:
            return False
        # Pandoc's docx writer assigns these styles; python-docx's template
        # defines none of them, and a missing style would break the cascade.
        # "Bibliography" is what citeproc's reference list lands in.
        for pandoc_style in ("Body Text", "First Paragraph", "Bibliography"):
            if pandoc_style not in [s.name for s in d.styles]:
                st = d.styles.add_style(pandoc_style, WD_STYLE_TYPE.PARAGRAPH)
                st.base_style = d.styles["Normal"]
        if hanging_bibliography:
            bib = d.styles["Bibliography"].paragraph_format
            bib.left_indent = Inches(0.5)
            bib.first_line_indent = Inches(-0.5)
        if kind == "apa-student-paper":
            # First-line indent on body paragraphs only — after the reference
            # list style is derived, so References keep the hanging indent.
            for name in ("Body Text", "First Paragraph"):
                d.styles[name].paragraph_format.first_line_indent = Inches(0.5)
        d.save(str(dest))
        return True
    except Exception:  # noqa: BLE001 — a failed generate must not break discovery
        return False


def available_reference_docs() -> Dict[str, Path]:
    """Map reference-doc name (file stem) → .docx path for the DOCX target.

    Mirrors :func:`available_templates` for the ``--reference-doc`` world:
    the two generated accessibility references are seeded into the user
    folder once (never regenerated over an edited file), any ``*.docx`` the
    user drops there appears, and the user copy wins on a name clash.
    """
    try:
        PUBLISH_STYLES_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return {}
    for kind in (
        "large-print",
        "dyslexia-friendly",
        "apa-student-paper",
        "ama-manuscript",
    ):
        dest = PUBLISH_STYLES_DIR / f"{kind}.docx"
        if not dest.exists():
            _generate_reference_doc(kind, dest)
    result: Dict[str, Path] = {}
    try:
        for ref in sorted(PUBLISH_STYLES_DIR.glob("*.docx")):
            result[ref.stem] = ref
    except OSError:
        pass
    return result


def resolve_metadata(document: Any, options: "PublishOptions") -> Dict[str, str]:
    """Resolve title/author/language/date: options → doc.metadata → doc fields.

    ``doc.metadata`` keys are matched case-insensitively, with the common
    aliases loaders actually produce (``creator`` for author — the EPUB OPF
    term — and ``lang`` for language).
    """
    meta_raw = getattr(document, "metadata", None) or {}
    meta = {str(k).lower(): str(v) for k, v in meta_raw.items() if v}

    def from_doc(*keys: str) -> str:
        for k in keys:
            if meta.get(k):
                return meta[k]
        return ""

    return {
        "title": options.title
        or from_doc("title")
        or str(getattr(document, "title", "") or ""),
        "author": options.author or from_doc("author", "creator"),
        "language": options.language or from_doc("language", "lang"),
        "date": options.date or from_doc("date"),
    }


# Cached major version of the Pandoc that will do the conversion; probed once.
_pandoc_major_cache: Optional[int] = None


def _pandoc_major() -> int:
    """Major version of the active Pandoc (pypandoc first, then the binary).

    Defaults to 3 when no probe works — matching the vendored/current Pandoc —
    so flag selection degrades to the modern spelling rather than crashing.
    """
    global _pandoc_major_cache
    if _pandoc_major_cache is not None:
        return _pandoc_major_cache
    ver = ""
    if _PYPANDOC:
        try:
            ver = str(_pypandoc.get_pandoc_version())
        except Exception:  # noqa: BLE001
            ver = ""
    if not ver and _PANDOC_BIN:
        try:
            out = subprocess.run(
                [_PANDOC_BIN, "--version"],
                capture_output=True,
                text=True,
                timeout=15, creationflags=_SUBPROCESS_FLAGS)
            # First line: "pandoc 3.9" (possibly with more dotted components).
            ver = (out.stdout or "").split()[1] if out.stdout else ""
        except Exception:  # noqa: BLE001
            ver = ""
    try:
        _pandoc_major_cache = int(str(ver).split(".", 1)[0])
    except (ValueError, IndexError):
        _pandoc_major_cache = 3
    return _pandoc_major_cache


def build_pandoc_args(
    options: "PublishOptions", document: Any = None
) -> List[str]:
    """Translate *options* into Pandoc command-line flags (pure, testable).

    The returned list is passed to :func:`star.export._pandoc_write` as
    ``extra_args`` — it intentionally does NOT include ``--standalone`` (the
    writer always adds that) and carries the title itself, so callers must not
    also pass ``title=`` (doubled ``--metadata title=`` would be ambiguous).
    """
    args: List[str] = []
    meta = resolve_metadata(document, options)
    if meta["title"]:
        args += ["--metadata", f"title={meta['title']}"]
    if meta["author"]:
        args += ["--metadata", f"author={meta['author']}"]
    if meta["language"]:
        # "lang" drives both the OPF dc:language and xml:lang on the content.
        args += ["--metadata", f"lang={meta['language']}"]
    if meta["date"]:
        args += ["--metadata", f"date={meta['date']}"]

    if options.template:
        if options.fmt == "docx":
            # DOCX has no CSS — styling comes from a reference document.
            ref = available_reference_docs().get(options.template)
            if ref is not None:
                args += ["--reference-doc", str(ref)]
        else:
            css = available_templates().get(options.template)
            if css is not None:
                args += ["--css", str(css)]

    if options.citation_style:
        csl = available_citation_styles().get(options.citation_style)
        if csl is not None:
            args += ["--citeproc", "--csl", str(csl)]
            if options.bibliography:
                args += ["--bibliography", options.bibliography]
            # Clickable in-text citations in HTML/EPUB; inert in DOCX.
            args += ["--metadata", "link-citations=true"]

    if options.toc:
        args += ["--toc", f"--toc-depth={int(options.toc_depth)}"]

    if options.fmt == "epub":
        if options.cover_image:
            args += ["--epub-cover-image", options.cover_image]
        flag = "--split-level" if _pandoc_major() >= 3 else "--epub-chapter-level"
        args += [f"{flag}={int(options.split_level)}"]

    if options.fmt == "html":
        # Publish means ONE portable file: the template CSS and any images
        # embed as data URIs (the quick File ▸ Export ▸ HTML stays bare).
        args += [
            "--embed-resources"
            if _pandoc_major() >= 3
            else "--self-contained"
        ]

    return args
