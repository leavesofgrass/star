"""Document exporters registered via the ``star.exporters`` entry-point group.

This module holds the text/markup export targets: Markdown (a direct dump of the
document's rendered markdown) and HTML / EPUB (produced through star's existing
Pandoc integration).  The audio (WAV), video (MP4), and Anki exporters live next
to their respective engines (``star.tts``, ``star.video``, ``star.flashcards``)
so each exporter sits with the code it drives.

All exporters implement :class:`star.formats.Exporter`; they are discovered and
instantiated through :class:`star.plugins.PluginRegistry`.
"""
from ._runtime import *  # noqa: F401,F403
from .formats import Exporter


def _pandoc_write(
    md: str,
    to_fmt: str,
    out_path: str,
    *,
    title: str = "",
    extra_args: Optional[List[str]] = None,
) -> None:
    """Convert *md* (Markdown) to *to_fmt* with Pandoc, writing *out_path*.

    Mirrors :func:`star.markup._pandoc_convert` but on the *output* side: it
    prefers the ``pypandoc`` binding and falls back to the ``pandoc`` binary on
    stdin.  Raises ``RuntimeError`` when Pandoc is unavailable or the conversion
    fails.

    *extra_args* carries the publishing pipeline's flags
    (:func:`star.publish.build_pandoc_args`).  Those already include the
    resolved title, so callers pass either *title* (quick-export path) or
    *extra_args* (publish path) — not both.
    """
    out = str(out_path)
    extra: List[str] = ["--standalone"]
    if title:
        extra += ["--metadata", f"title={title}"]
    if extra_args:
        extra += list(extra_args)
    last_err: Optional[Exception] = None

    if _PYPANDOC:
        try:
            _pypandoc.convert_text(
                md, to_fmt, format="markdown", outputfile=out, extra_args=extra
            )
            return
        except Exception as exc:  # noqa: BLE001
            last_err = exc

    if _PANDOC_BIN:
        try:
            r = subprocess.run(
                [_PANDOC_BIN, "--from", "markdown", "--to", to_fmt, *extra, "-o", out],
                input=md,
                capture_output=True,
                text=True,
                timeout=60, creationflags=_SUBPROCESS_FLAGS)
            if r.returncode == 0:
                return
            last_err = RuntimeError(r.stderr.strip() or "pandoc exited non-zero")
        except Exception as exc:  # noqa: BLE001
            last_err = exc

    hint = f" ({last_err})" if last_err else ""
    raise RuntimeError(
        f"{to_fmt.upper()} export requires Pandoc — install pandoc or "
        f"`pip install pypandoc`{hint}"
    )


class MarkdownExporter(Exporter):
    """Write the document's rendered Markdown verbatim."""

    name = "markdown"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".md", ".markdown"})

    @classmethod
    def available(cls) -> bool:
        return True

    def export(self, document, path, **kwargs) -> None:
        Path(path).write_text(document.markdown or "", encoding="utf-8")


class HTMLExporter(Exporter):
    """Render the document to a standalone HTML file via Pandoc."""

    name = "html"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".html", ".htm"})

    @classmethod
    def available(cls) -> bool:
        from ._runtime import _PANDOC_BIN, _PYPANDOC
        return bool(_PYPANDOC or _PANDOC_BIN)

    def export(self, document, path, *, options=None, **kwargs) -> None:
        if options is not None:
            from .publish import build_pandoc_args

            _pandoc_write(
                document.markdown or "", "html", path,
                extra_args=build_pandoc_args(options, document),
            )
            return
        _pandoc_write(
            document.markdown or "", "html", path, title=getattr(document, "title", "")
        )


class DOCXExporter(Exporter):
    """Render the document to a Word .docx file via Pandoc.

    Registered in 0.1.30 for the publishing arc's phase 2 — the
    submit-your-coursework target.  Appears in the dynamic File ▸ Export
    section as the bare converter; the Publish dialog / ``M-x publish`` route
    through it with a :class:`star.publish.PublishOptions`, where styling
    comes from a ``--reference-doc`` (see
    :func:`star.publish.available_reference_docs`).
    """

    name = "docx"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".docx"})

    @classmethod
    def available(cls) -> bool:
        from ._runtime import _PANDOC_BIN, _PYPANDOC
        return bool(_PYPANDOC or _PANDOC_BIN)

    def export(self, document, path, *, options=None, **kwargs) -> None:
        if options is not None:
            from .publish import build_pandoc_args

            _pandoc_write(
                document.markdown or "", "docx", path,
                extra_args=build_pandoc_args(options, document),
            )
            return
        _pandoc_write(
            document.markdown or "", "docx", path, title=getattr(document, "title", "")
        )


class EPUBExporter(Exporter):
    """Render the document to an EPUB file via Pandoc."""

    name = "epub"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".epub"})

    @classmethod
    def available(cls) -> bool:
        from ._runtime import _PANDOC_BIN, _PYPANDOC
        return bool(_PYPANDOC or _PANDOC_BIN)

    def export(self, document, path, *, options=None, **kwargs) -> None:
        """*options* (a :class:`star.publish.PublishOptions`) selects the full
        publishing pipeline — metadata, stylesheet, cover, TOC; without it this
        stays the bare quick-export the File ▸ Export menu has always offered."""
        if options is not None:
            from .publish import build_pandoc_args

            _pandoc_write(
                document.markdown or "", "epub", path,
                extra_args=build_pandoc_args(options, document),
            )
            return
        _pandoc_write(
            document.markdown or "", "epub", path, title=getattr(document, "title", "")
        )
