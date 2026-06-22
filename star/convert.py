"""Batch conversion core and the shared export-format registry.

Both batch conversion (the ``batch-convert`` command / Qt menu) and hot-folder
watching (``star --watch``) drive the *existing* single-file
``load_document`` -> export pipeline through this one module.  That keeps the
set of output formats, the file-naming / collision rules, and the failure
handling identical across every entry point, and means neither feature
re-implements document loading or export.

Output formats here are the headless, text-producing exports the interactive
commands already offer: Markdown (``doc.markdown``), plain text
(``doc.plain_text``), and Braille/BRF (``braille._export_braille``).  Audio and
subtitle export are intentionally excluded — they require speech *synthesis*
(a heavy, separate pipeline), which is not what unattended document conversion
is for; the interactive ``export-audio`` / ``export-subtitles`` commands remain
the way to produce those.  The registry is structured so another format can be
added in one place if that ever changes.
"""

from ._runtime import *  # noqa: F401,F403
from .braille import _export_braille
from .documents import Document, load_document
from .settings import Settings

# =============================================================================
# Export-format registry (single source of truth for both features)
# =============================================================================


def _to_markdown(doc: "Document", settings: Settings) -> str:
    return doc.markdown


def _to_text(doc: "Document", settings: Settings) -> str:
    return doc.plain_text


def _to_braille(doc: "Document", settings: Settings) -> str:
    return _export_braille(
        doc.plain_text,
        str(settings.get("braille_table", "en-ueb-g2.ctb")),
        use_liblouis=bool(settings.get("braille_grade2", False)),
    )


# canonical name -> (file extension, converter(doc, settings) -> str, label)
EXPORT_FORMATS: "Dict[str, Tuple[str, Callable[..., str], str]]" = {
    "markdown": (".md", _to_markdown, "Markdown"),
    "text": (".txt", _to_text, "Plain text"),
    "braille": (".brf", _to_braille, "Braille (BRF)"),
}

# Accepted spellings / extensions that map onto a canonical format name.
_FORMAT_ALIASES: "Dict[str, str]" = {
    "markdown": "markdown",
    "md": "markdown",
    "text": "text",
    "txt": "text",
    "plain": "text",
    "braille": "braille",
    "brf": "braille",
}


def supported_formats() -> "List[str]":
    """Canonical export-format names, in display order."""
    return list(EXPORT_FORMATS.keys())


def resolve_format(name: str) -> str:
    """Return the canonical format name for *name* or raise ``ValueError``.

    This is the one validation used by the batch command, the watcher, and the
    ``--watch`` CLI flag, so the accepted set can never drift between them.
    """
    key = (name or "").strip().lower().lstrip(".")
    canon = _FORMAT_ALIASES.get(key)
    if canon is None:
        raise ValueError(
            f"Unsupported format {name!r}. Choose one of: "
            + ", ".join(supported_formats())
        )
    return canon


# =============================================================================
# Single-file conversion (the core both features call into)
# =============================================================================


@dataclass
class ConversionResult:
    """Outcome of converting one file."""

    source: str
    output: str = ""  # path written (empty on failure)
    ok: bool = False
    error: str = ""  # human-readable reason on failure


def _unique_path(path: Path) -> Path:
    """Return *path*, or a disambiguated sibling if it already exists.

    Appends `` (2)``, `` (3)`` … before the extension rather than silently
    overwriting an existing file.
    """
    if not path.exists():
        return path
    stem, suffix, parent = path.stem, path.suffix, path.parent
    n = 2
    while True:
        candidate = parent / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def convert_file(
    path: "str | Path",
    out_dir: "str | Path",
    fmt: str,
    settings: Settings,
    *,
    overwrite: bool = False,
) -> ConversionResult:
    """Convert one file through the existing ``load_document`` -> export path.

    Returns a :class:`ConversionResult`; it never raises for a per-file problem
    (corrupt, password-protected, or unreadable input, or a write error) so a
    single bad file can't abort a batch — the reason is captured in the result.
    A bad *fmt* (a caller error, not a per-file error) still raises ``ValueError``.
    """
    src = str(path)
    canon = resolve_format(fmt)  # caller error if invalid; validate before the try
    ext, converter, _label = EXPORT_FORMATS[canon]
    try:
        doc = load_document(src, settings)
        # Some loaders fail soft, returning a Document tagged as an error rather
        # than raising; treat that as a failure too.
        if getattr(doc, "format", "") == "error":
            raise RuntimeError(doc.plain_text or "could not load document")
        data = converter(doc, settings)
        if data is None:
            raise RuntimeError("converter produced no output")
        out_dir_p = Path(out_dir)
        out_dir_p.mkdir(parents=True, exist_ok=True)
        dest = out_dir_p / (Path(src).stem + ext)
        if not overwrite:
            dest = _unique_path(dest)
        dest.write_text(data, encoding="utf-8")
        return ConversionResult(source=src, output=str(dest), ok=True)
    except Exception as exc:  # noqa: BLE001 — failure isolation is the point
        return ConversionResult(
            source=src, output="", ok=False, error=f"{type(exc).__name__}: {exc}"
        )


# =============================================================================
# Batch conversion
# =============================================================================


def expand_inputs(
    paths: "List[str | Path]", *, recursive: bool = False
) -> "List[Path]":
    """Expand a mix of files and directories into a deterministic file list.

    A directory contributes the files directly inside it (or, with *recursive*,
    its whole tree).  Results are de-duplicated and sorted so batch logs are
    reproducible.
    """
    found: "List[Path]" = []
    for p in paths:
        pp = Path(p)
        if pp.is_dir():
            it = pp.rglob("*") if recursive else pp.iterdir()
            found.extend(child for child in it if child.is_file())
        elif pp.is_file():
            found.append(pp)
    seen: "set[str]" = set()
    uniq: "List[Path]" = []
    for f in sorted(found, key=lambda x: str(x).lower()):
        rp = str(f.resolve())
        if rp not in seen:
            seen.add(rp)
            uniq.append(f)
    return uniq


@dataclass
class BatchSummary:
    """Aggregate outcome of a batch run."""

    out_dir: str
    fmt: str
    results: "List[ConversionResult]" = field(default_factory=list)
    log_path: str = ""

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def succeeded(self) -> "List[ConversionResult]":
        return [r for r in self.results if r.ok]

    @property
    def failed(self) -> "List[ConversionResult]":
        return [r for r in self.results if not r.ok]


def write_summary_log(out_dir: "str | Path", summary: BatchSummary) -> str:
    """Write a timestamped batch summary alongside the outputs; return its path.

    A persisted report matters because batches can be too large to scroll back
    through in the UI.  Returns "" if the log could not be written.
    """
    out = Path(out_dir)
    try:
        out.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        log_path = out / f"star-batch-{stamp}.log"
        lines = [
            f"star batch conversion — {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"format : {summary.fmt}",
            f"output : {out}",
            f"total  : {summary.total}    ok: {len(summary.succeeded)}    "
            f"failed: {len(summary.failed)}",
            "",
        ]
        for r in summary.results:
            if r.ok:
                lines.append(f"OK    {r.source}  ->  {r.output}")
            else:
                lines.append(f"FAIL  {r.source}  ::  {r.error}")
        log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(log_path)
    except OSError:
        return ""


def run_batch(
    paths: "List[str | Path]",
    out_dir: "str | Path",
    fmt: str,
    settings: Settings,
    *,
    progress: "Optional[Callable[[int, int, ConversionResult], None]]" = None,
    stop: "Optional[threading.Event]" = None,
    recursive: bool = False,
    overwrite: bool = False,
) -> BatchSummary:
    """Convert many files (failure-isolated) and write a summary log.

    *progress(done, total, result)* — if given — is called after each file so a
    UI can report ``done/total``, the current filename, and running counts.
    *stop* — an optional :class:`threading.Event` — is checked between files for
    cooperative cancellation.  Returns a :class:`BatchSummary`; the summary log
    is always written (even for an empty or cancelled run).
    """
    canon = resolve_format(fmt)  # validate once, up front
    files = expand_inputs(paths, recursive=recursive)
    summary = BatchSummary(out_dir=str(out_dir), fmt=canon)
    total = len(files)
    for i, f in enumerate(files, 1):
        if stop is not None and stop.is_set():
            break
        result = convert_file(f, out_dir, canon, settings, overwrite=overwrite)
        summary.results.append(result)
        if progress is not None:
            try:
                progress(i, total, result)
            except Exception:
                pass  # a progress-callback failure must never abort the batch
    summary.log_path = write_summary_log(out_dir, summary)
    return summary
