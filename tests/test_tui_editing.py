"""Tests for the TUI's edit-in-$EDITOR flow (GUI edit-mode parity).

Follows the tests/test_tui_mixins.py pattern: the REAL TuiEditingMixin over a
tiny fake app.  The curses suspend/resume half (_run_editor) is stubbed — what
is under test is the pure logic around it: editor resolution, the in-place vs
Markdown-draft split, the Save-As commit, and the never-lose-work paths.
"""
import importlib.util
import os

import pytest

from star.documents import Document

pytestmark = pytest.mark.skipif(
    not (importlib.util.find_spec("curses") or importlib.util.find_spec("_curses")),
    reason="curses not available",
)

from star.tui.mixin_editing import TuiEditingMixin  # noqa: E402
from star.tui.text import MX_COMMANDS  # noqa: E402


class _App(TuiEditingMixin):
    def __init__(self, doc=None, editor_ok=True):
        self.doc = doc
        self.notices = []
        self.opened = []
        self.minibuffer = None
        self.tts_stopped = 0
        self._editor_ok = editor_ok
        self.edited_paths = []

    def notify(self, msg, dur=4.0, error=False):
        self.notices.append((msg, error))

    def _tts_stop(self):
        self.tts_stopped += 1

    def _open_async(self, path):
        self.opened.append(path)

    def _enter_minibuffer(self, prompt, initial="", on_commit=None,
                          completions=None, **kw):
        self.minibuffer = (prompt, initial, on_commit, completions)

    def _run_editor(self, path):  # overridden per-test when edits are simulated
        self.edited_paths.append(path)
        return self._editor_ok


def _md_doc(path):
    return Document(path=str(path), title="T", markdown="# T\n\nbody",
                    plain_text="body")


# ── Editor resolution ────────────────────────────────────────────────────────


def test_editor_command_visual_wins_and_is_split(monkeypatch):
    monkeypatch.setenv("VISUAL", "code -w")
    monkeypatch.setenv("EDITOR", "vim")
    app = _App()
    assert TuiEditingMixin._editor_command(app) == ["code", "-w"]


def test_editor_command_falls_back_to_editor_var(monkeypatch):
    monkeypatch.delenv("VISUAL", raising=False)
    monkeypatch.setenv("EDITOR", "vim")
    app = _App()
    assert TuiEditingMixin._editor_command(app) == ["vim"]


def test_editor_command_platform_fallback(monkeypatch):
    monkeypatch.delenv("VISUAL", raising=False)
    monkeypatch.delenv("EDITOR", raising=False)
    app = _App()
    cmd = TuiEditingMixin._editor_command(app)
    if os.name == "nt":
        assert cmd == ["notepad"]
    else:
        assert cmd in (["nano"], ["vi"], [])


# ── Ctrl+E / M-x edit ────────────────────────────────────────────────────────


def test_edit_requires_a_document():
    app = _App(doc=None)
    app._edit_cmd()
    assert app.notices[-1] == ("No document to edit", True)


def test_edit_text_file_in_place_and_reload(tmp_path):
    src = tmp_path / "notes.md"
    src.write_text("# T\n\nbody", encoding="utf-8")
    app = _App(doc=_md_doc(src))
    app._edit_cmd()
    assert app.tts_stopped == 1
    assert app.edited_paths == [str(src)]
    assert app.opened == [str(src)]          # reloaded after the editor exits
    assert app.minibuffer is None            # no Save-As for text formats


def test_edit_text_file_editor_failure_skips_reload(tmp_path):
    src = tmp_path / "notes.md"
    src.write_text("x", encoding="utf-8")
    app = _App(doc=_md_doc(src), editor_ok=False)
    app._edit_cmd()
    assert app.opened == []


def test_edit_binary_doc_roundtrips_through_draft(tmp_path):
    """A PDF-backed doc: the Markdown conversion is edited as a draft, then
    Save-As writes it where the user says and opens the result."""
    doc = Document(path=str(tmp_path / "paper.pdf"), title="Paper",
                   markdown="# Paper\n\noriginal", plain_text="original")
    app = _App(doc=doc)

    def _fake_editor(path):  # the user edits the draft
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n\nEDITED")
        return True

    app._run_editor = _fake_editor
    app._edit_cmd()
    prompt, initial, on_commit, completions = app.minibuffer
    assert initial.endswith("paper.md")       # Save-As default next to the source
    dest = tmp_path / "out" / "paper.md"
    on_commit(str(dest))
    assert dest.read_text(encoding="utf-8").endswith("EDITED")
    assert app.opened == [str(dest)]


def test_edit_binary_doc_unchanged_draft_is_a_noop(tmp_path):
    doc = Document(path=str(tmp_path / "paper.pdf"), title="Paper",
                   markdown="# Paper", plain_text="Paper")
    app = _App(doc=doc)
    drafts = []

    def _fake_editor(path):  # the user quits without editing
        drafts.append(path)
        return True

    app._run_editor = _fake_editor
    app._edit_cmd()
    assert app.notices[-1] == ("No changes made", False)
    assert app.minibuffer is None
    assert not os.path.exists(drafts[0])      # draft cleaned up


def test_edit_binary_doc_empty_dest_keeps_the_draft(tmp_path):
    doc = Document(path=str(tmp_path / "paper.pdf"), title="Paper",
                   markdown="# Paper", plain_text="Paper")
    app = _App(doc=doc)

    def _fake_editor(path):
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n\nEDITED")
        return True

    app._run_editor = _fake_editor
    app._edit_cmd()
    _prompt, _initial, on_commit, _completions = app.minibuffer
    on_commit("")                              # user commits an empty path
    msg, is_error = app.notices[-1]
    assert is_error and "draft kept" in msg
    draft = msg.rsplit(" ", 1)[-1]
    assert os.path.exists(draft)               # edits are never lost
    os.unlink(draft)


def test_edit_registered_in_mx_commands():
    assert "edit" in MX_COMMANDS


# ── Ctrl+N / M-x new-document ────────────────────────────────────────────────


def test_new_document_creates_seeds_and_opens(tmp_path):
    app = _App()
    dest = tmp_path / "ideas.md"
    app._new_document_cmd(str(dest))
    assert dest.read_text(encoding="utf-8") == "# ideas\n\n"
    assert app.edited_paths == [str(dest)]     # handed to $EDITOR
    assert app.opened == [str(dest)]           # loaded afterwards


def test_new_document_appends_md_suffix(tmp_path):
    app = _App()
    app._new_document_cmd(str(tmp_path / "plain"))
    assert (tmp_path / "plain.md").is_file()


def test_new_document_refuses_to_overwrite(tmp_path):
    existing = tmp_path / "have.md"
    existing.write_text("precious", encoding="utf-8")
    app = _App()
    app._new_document_cmd(str(existing))
    assert existing.read_text(encoding="utf-8") == "precious"
    msg, is_error = app.notices[-1]
    assert is_error and "already exists" in msg
    assert app.opened == []


def test_new_document_no_arg_prompts_with_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = _App()
    app._new_document_cmd()
    prompt, initial, on_commit, _completions = app.minibuffer
    assert initial.endswith("untitled.md")
    on_commit("")                              # Esc-equivalent: empty commit
    assert app.notices[-1] == ("New document cancelled", False)
    assert app.opened == []


def test_new_document_registered_in_mx_commands():
    assert "new-document" in MX_COMMANDS
