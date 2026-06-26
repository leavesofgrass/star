"""Abstract base classes for document format handlers and exporters.

These ABCs define the contracts that built-in and third-party plugins implement.
Concrete handlers are discovered at runtime through the ``star.formats`` and
``star.exporters`` entry-point groups and cached by
:class:`star.plugins.PluginRegistry`.  This module holds only the interfaces —
the registry itself lives in :mod:`star.plugins`.
"""
import abc
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .documents import Document


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
