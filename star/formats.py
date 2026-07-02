"""Abstract base classes for document format handlers and exporters.

These ABCs define the contracts that built-in and third-party plugins implement.
Concrete handlers are discovered at runtime through the ``star.formats`` and
``star.exporters`` entry-point groups and cached by
:class:`star.plugins.PluginRegistry`.  This module holds only the interfaces —
the registry itself lives in :mod:`star.plugins`.

Plugin API contract
--------------------
:data:`__api_version__` is the version of the plugin ABC surface defined in this
module — the :class:`FormatHandler`, :class:`Exporter`, and
``star.tts.TTSBackend`` method signatures a third-party plugin implements against.
It follows ``MAJOR.MINOR`` semantics:

* **MAJOR** bumps on a breaking change to an ABC (a renamed/removed method, a
  changed required signature).  A plugin built for a different major version may
  fail to load.
* **MINOR** bumps for backward-compatible additions (a new optional method with a
  default, a new keyword argument).

This is deliberately decoupled from the application version (``star.__version__``).
Third-party plugins should pin against the API version — declare a supported
range in your package metadata and check :data:`star.formats.__api_version__` at
import time if you need to fail loudly on an incompatible host — rather than
against the star release number, which changes far more often.  See
``docs/plugins-developing.md`` for the full developer guide.
"""
import abc
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .documents import Document

#: Version of the plugin ABC surface in this module (``MAJOR.MINOR``).
#: See the module docstring for the compatibility contract.  Introspectable via
#: ``star --plugins api``.
__api_version__ = "1.0"


class FormatHandler(abc.ABC):
    """Abstract base for document loaders registered via the ``star.formats`` entry-point group."""

    #: Short identifier matching the entry-point key (e.g. ``"pdf"``).
    name: str = "base"

    #: Lower priority = preferred when multiple handlers claim the same extension.
    priority: int = 50

    @classmethod
    @abc.abstractmethod
    def extensions(cls) -> frozenset[str]:
        """Lowercase extensions including the dot, e.g. ``frozenset({".pdf"})``."""

    @classmethod
    @abc.abstractmethod
    def available(cls) -> bool:
        """Return True if the handler's optional dependencies are present."""

    @abc.abstractmethod
    def load(self, path: Path, **kwargs) -> "Document":
        """Parse *path* and return a Document."""


class Exporter(abc.ABC):
    """Abstract base for export targets registered via the ``star.exporters`` entry-point group."""

    name: str = "base"

    @classmethod
    @abc.abstractmethod
    def extensions(cls) -> frozenset[str]:
        """File extensions this exporter produces, e.g. ``frozenset({".apkg"})``."""

    @classmethod
    @abc.abstractmethod
    def available(cls) -> bool: ...

    @abc.abstractmethod
    def export(self, document: "Document", path: Path, **kwargs) -> None: ...


class UnsupportedFormatError(ValueError):
    """Raised when no FormatHandler is registered and available for a file extension."""

    def __init__(self, ext: str) -> None:
        super().__init__(f"No handler available for {ext!r} files")
        self.ext = ext
