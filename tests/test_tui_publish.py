"""TUI ``M-x publish`` — the minibuffer chain, guards, and shared persistence.

Same harness style as test_tui_editing.py: a minimal mixin-host with stub
``notify`` / ``_enter_minibuffer`` capture, no curses required.  The worker
thread is run inline so assertions see the export synchronously.
"""
import queue

import star.tui.mixin_export as tui_export
from star.documents.model import Document
from star.publish import PublishOptions
from star.tui.mixin_export import ExportMixin


class _Settings:
    def __init__(self):
        self._d = {}

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


class _App(ExportMixin):
    def __init__(self, doc=None):
        self.doc = doc
        self.settings = _Settings()
        self._bg_queue = queue.Queue()
        self.notices = []
        self.prompts = []  # (prompt, initial, completions, on_commit)

    def notify(self, msg, dur=4.0, error=False):
        self.notices.append((msg, error))

    def _enter_minibuffer(self, prompt="", initial="", on_commit=None,
                          mode="mx", completions=None):
        self.prompts.append((prompt, initial, completions, on_commit))

    def _annot_key(self):
        if not self.doc:
            return ""
        return self.doc.path or self.doc.title or ""


class _InlineThread:
    """threading.Thread stand-in that runs the target synchronously."""

    def __init__(self, target=None, daemon=None):
        self._target = target

    def start(self):
        self._target()


class _FakeExporter:
    name = "epub"
    calls = []

    @classmethod
    def available(cls):
        return True

    @classmethod
    def extensions(cls):
        return frozenset({".epub"})

    def export(self, document, path, *, options=None, **kw):
        _FakeExporter.calls.append((document, path, options))


def _doc(path="D:/tmp/notes.md"):
    d = Document()
    d.path = path
    d.title = "Notes"
    return d


def test_publish_requires_a_document():
    app = _App(doc=None)
    app._publish_cmd()
    assert app.notices and app.notices[0][1] is True
    assert "No document" in app.notices[0][0]


def test_publish_requires_pandoc(monkeypatch):
    from star.export import EPUBExporter

    monkeypatch.setattr(EPUBExporter, "available", classmethod(lambda cls: False))
    app = _App(doc=_doc())
    app._publish_cmd()
    assert any("Pandoc" in m for m, _e in app.notices)


def test_publish_chain_prompts_and_runs(monkeypatch):
    from star.export import EPUBExporter

    monkeypatch.setattr(EPUBExporter, "available", classmethod(lambda cls: True))
    monkeypatch.setattr(
        tui_export, "threading",
        type("T", (), {"Thread": _InlineThread}),
    )

    class _Reg:
        exporters = [_FakeExporter]

    import star.plugins as plugins

    monkeypatch.setattr(plugins.PluginRegistry, "get", classmethod(lambda cls: _Reg))

    _FakeExporter.calls.clear()
    app = _App(doc=_doc())
    # The GUI dialog previously saved metadata for this document — the TUI
    # must merge into that entry, not clobber it.
    app.settings.set(
        "publish_options", {app._annot_key(): {"author": "Saved Author"}}
    )

    app._publish_cmd()
    prompt, initial, completions, commit = app.prompts[-1]
    assert "format" in prompt.lower()
    assert completions == ["epub", "html", "docx"]
    commit("epub")

    prompt, initial, completions, commit = app.prompts[-1]
    assert "template" in prompt.lower()
    assert completions[0] == "none"
    assert "large-print" in completions  # bundled templates discovered
    commit("large-print")

    prompt, initial, completions, commit = app.prompts[-1]
    assert "citation" in prompt.lower()
    assert completions[0] == "none"
    assert "apa" in completions  # bundled CSL styles discovered
    commit("none")

    prompt, initial, completions, commit = app.prompts[-1]
    assert initial.endswith("notes.epub")
    commit(initial)

    # Export ran inline with the pipeline options.
    assert len(_FakeExporter.calls) == 1
    _docv, dest, options = _FakeExporter.calls[0]
    assert dest.endswith("notes.epub")
    assert options == PublishOptions(fmt="epub", template="large-print")
    # Success notice was queued for the curses loop.
    app._bg_queue.get_nowait()()
    assert any("Published EPUB" in m for m, _e in app.notices)
    # Persistence merged with (not clobbered) the GUI-saved entry.
    entry = app.settings.get("publish_options")[app._annot_key()]
    assert entry["fmt"] == "epub" and entry["template"] == "large-print"
    assert entry["author"] == "Saved Author"


def test_publish_rejects_unknown_format(monkeypatch):
    from star.export import EPUBExporter

    monkeypatch.setattr(EPUBExporter, "available", classmethod(lambda cls: True))
    app = _App(doc=_doc())
    app._publish_fmt_cb("pdf")
    assert any("epub, html, or docx" in m for m, _e in app.notices)


def test_publish_docx_offers_reference_docs(monkeypatch, tmp_path):
    """The docx branch completes over --reference-doc names, not CSS, and the
    destination default carries the .docx extension."""
    import star.publish as publish
    from star.export import EPUBExporter

    monkeypatch.setattr(EPUBExporter, "available", classmethod(lambda cls: True))
    ref = tmp_path / "large-print.docx"
    ref.write_bytes(b"stub")
    monkeypatch.setattr(
        publish, "available_reference_docs", lambda: {"large-print": ref}
    )
    monkeypatch.setattr(
        publish, "available_templates", lambda: {"css-only": tmp_path}
    )

    app = _App(doc=_doc())
    app._publish_fmt_cb("docx")
    _p, _i, completions, commit = app.prompts[-1]
    assert completions == ["none", "large-print"]  # reference docs, no CSS
    commit("large-print")
    _p, _i, _c, commit = app.prompts[-1]  # citation-style prompt
    commit("none")
    _p, initial, _c, _commit = app.prompts[-1]
    assert initial.endswith("notes.docx")
