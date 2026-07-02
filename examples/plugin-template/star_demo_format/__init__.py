"""A minimal third-party *star* format-handler plugin.

This is a complete, working example of extending `star`_ with support for a new
document format via the ``star.formats`` entry-point group.  It teaches a made-up
``.demo`` extension: a plain-text file whose first line is treated as the title
and whose remaining lines are the body.

The package ships one class, :class:`DemoHandler`, and declares it in
``pyproject.toml`` as::

    [project.entry-points."star.formats"]
    demo = "star_demo_format:DemoHandler"

Install it (``pip install .`` from this directory) alongside ``star`` and it is
discovered automatically — ``star --plugins list`` will show it under the
``star.formats`` group, and opening any ``file.demo`` routes through it.

.. _star: https://pypi.org/project/star-reader/
"""
from __future__ import annotations

from pathlib import Path

# `star.formats` holds ONLY the abstract base classes and the plugin-API version.
# Importing it does not pull in the GUI/TUI or the document loaders, so a plugin
# stays cheap to import and safe to declare as an entry-point.
from star.formats import FormatHandler

#: The minimum plugin-API version this handler was written against.  Compare it
#: to ``star.formats.__api_version__`` on the host if you want to fail loudly on
#: an incompatible star (see the developer guide); here we only record intent.
REQUIRES_STAR_API = "1.0"


class DemoHandler(FormatHandler):
    """Loader for the toy ``.demo`` format (first line = title, rest = body)."""

    #: Must match the entry-point key declared in pyproject.toml.
    name = "demo"

    #: Lower = preferred when several handlers claim the same extension.  Built-in
    #: star handlers use 10-50; third-party handlers should use >= 100 unless they
    #: intend to override a built-in for a shared extension.
    priority = 100

    @classmethod
    def extensions(cls) -> frozenset[str]:
        """Lowercase extensions this handler claims, each including the dot."""
        return frozenset({".demo"})

    @classmethod
    def available(cls) -> bool:
        """True when the handler's dependencies are present.

        This toy handler needs nothing beyond the standard library, so it is
        always available.  A real handler would probe its optional dependency
        here (e.g. ``return importlib.util.find_spec("mylib") is not None``) so
        that ``star --plugins list`` can show it as unavailable rather than
        crashing when the file is opened.
        """
        return True

    def load(self, path: Path, **kwargs) -> "object":
        """Parse *path* and return a ``star.documents.Document``.

        ``Document`` is imported lazily inside ``load`` (not at module import
        time) so merely *declaring* the plugin stays cheap — the heavy document
        machinery is only touched when a ``.demo`` file is actually opened.
        """
        from star.documents import Document

        text = Path(path).read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        title = lines[0].strip() if lines else Path(path).stem
        body = "\n".join(lines[1:]).strip()

        doc = Document()
        doc.path = str(path)
        doc.title = title
        doc.format = "demo"
        # `markdown` feeds the on-screen view; `plain_text` feeds TTS.  For this
        # toy format they are the same body text.
        doc.markdown = f"# {title}\n\n{body}\n"
        doc.plain_text = f"{title}. {body}"
        return doc
