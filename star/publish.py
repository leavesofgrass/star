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
    for src in sorted(_BUNDLED_STYLES_DIR.glob("*.css")):
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
        css = available_templates().get(options.template)
        if css is not None:
            args += ["--css", str(css)]

    if options.toc:
        args += ["--toc", f"--toc-depth={int(options.toc_depth)}"]

    if options.fmt == "epub":
        if options.cover_image:
            args += ["--epub-cover-image", options.cover_image]
        flag = "--split-level" if _pandoc_major() >= 3 else "--epub-chapter-level"
        args += [f"{flag}={int(options.split_level)}"]

    return args
