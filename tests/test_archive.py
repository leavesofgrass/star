"""Tests for Epic I — archive ingestion (star.archive)."""
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from star.archive import (
    _readable,
    build_index_markdown,
    is_archive,
    is_archive_ref,
    list_members,
    make_ref,
    open_member,
    parse_ref,
)

# =============================================================================
# Pure-logic tests (no archive files needed)
# =============================================================================


def test_is_archive_extensions():
    assert is_archive("book.zip")
    assert is_archive("data.tar.gz")
    assert is_archive("DATA.ZIP")   # case-insensitive
    assert is_archive("book.tgz")
    assert is_archive("book.tar.xz")
    assert not is_archive("paper.pdf")
    assert not is_archive("notes.epub")


def test_is_archive_ref():
    assert is_archive_ref("/abs/book.zip!inner/paper.pdf")
    assert is_archive_ref("C:\\docs\\book.zip!chapter.txt")
    # URLs are not archive refs
    assert not is_archive_ref("https://example.com/!foo")
    assert not is_archive_ref("http://example.com/book.zip!paper.pdf")
    assert not is_archive_ref("just-a-path.pdf")


def test_make_ref():
    ref = make_ref("/abs/book.zip", "inner/paper.pdf")
    assert ref == "/abs/book.zip!inner/paper.pdf"


def test_parse_ref_roundtrip():
    archive, member = "/abs/book.zip", "inner/paper.pdf"
    ref = make_ref(archive, member)
    result = parse_ref(ref)
    assert result == (archive, member)


def test_parse_ref_invalid():
    assert parse_ref("no-bang-here.pdf") is None
    assert parse_ref("") is None
    assert parse_ref("!onlymember") is None  # empty archive path
    assert parse_ref("/path!") is None       # empty member path


def test_readable_filter():
    assert _readable("paper.pdf")
    assert _readable("folder/notes.md")
    assert not _readable("__MACOSX/._paper.pdf")
    assert not _readable(".hidden.md")
    assert not _readable("folder/")           # directory entry
    assert not _readable("folder/.git/config")
    assert not _readable("unknown.xyz")       # unknown extension


def test_build_index_markdown():
    md = build_index_markdown("/abs/book.zip", ["ch1.pdf", "ch2.md"])
    assert "book.zip" in md
    assert "ch1.pdf" in md
    assert "ch2.md" in md


# =============================================================================
# ZIP tests (stdlib — always runs)
# =============================================================================


@pytest.fixture()
def temp_zip(tmp_path):
    """A temp ZIP with a .md and a .txt member."""
    zp = tmp_path / "test.zip"
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr("docs/hello.md", "# Hello\n\nWorld.")
        zf.writestr("docs/readme.txt", "Plain text file.")
        zf.writestr("__MACOSX/._hello.md", "garbage")  # should be filtered
        zf.writestr("hidden/.hidden", "hidden file")   # should be filtered
    return zp


def test_list_members_zip(temp_zip):
    members = list_members(str(temp_zip))
    assert "docs/hello.md" in members
    assert "docs/readme.txt" in members
    assert not any("MACOSX" in m for m in members)
    assert not any(".hidden" in m for m in members)


def test_open_member_zip(temp_zip):
    with open_member(str(temp_zip), "docs/hello.md") as tmp:
        content = Path(tmp).read_text(encoding="utf-8")
        assert "Hello" in content
    # Temp file must be deleted after the context exits
    assert not Path(tmp).exists()


def test_open_member_zip_missing(temp_zip):
    with pytest.raises((KeyError, Exception)):
        with open_member(str(temp_zip), "nonexistent.pdf") as _:
            pass


# =============================================================================
# TAR tests (stdlib — always runs)
# =============================================================================


@pytest.fixture()
def temp_tar_gz(tmp_path):
    """A temp .tar.gz with a .md and a .txt member."""
    tp = tmp_path / "test.tar.gz"
    with tarfile.open(tp, "w:gz") as tf:
        for name, content in [("docs/hello.md", "# Hello"), ("notes.txt", "plain")]:
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return tp


def test_list_members_tar_gz(temp_tar_gz):
    members = list_members(str(temp_tar_gz))
    assert "docs/hello.md" in members
    assert "notes.txt" in members


def test_open_member_tar_gz(temp_tar_gz):
    with open_member(str(temp_tar_gz), "docs/hello.md") as tmp:
        content = Path(tmp).read_text(encoding="utf-8")
        assert "Hello" in content
    assert not Path(tmp).exists()


# =============================================================================
# Integration: load_document on archive ref (requires pdfminer or plain text)
# =============================================================================


def test_load_document_archive_ref(temp_zip):
    """load_document should unwrap an archive ref and return a real Document."""
    from star.documents import load_document
    from star.settings import Settings
    settings = Settings()
    ref = make_ref(str(temp_zip), "docs/hello.md")
    doc = load_document(ref, settings)
    assert doc.path == ref
    assert "Hello" in doc.markdown


def test_load_document_archive_direct(temp_zip):
    """Opening a zip directly should produce an index document."""
    from star.documents import load_document
    from star.settings import Settings
    settings = Settings()
    doc = load_document(str(temp_zip), settings)
    assert "docs/hello.md" in doc.markdown
    assert "docs/readme.txt" in doc.markdown


# =============================================================================
# .7z test — skipped when py7zr is absent
# =============================================================================


@pytest.mark.skipif(
    not __import__("importlib.util", fromlist=["find_spec"]).find_spec("py7zr"),
    reason="py7zr not installed",
)
def test_list_members_7z(tmp_path):
    import py7zr
    sp = tmp_path / "test.7z"
    with py7zr.SevenZipFile(sp, mode="w") as sz:
        content = b"# Hello from 7z"
        sz.writestr({"docs/hello.md": io.BytesIO(content)})
    members = list_members(str(sp))
    assert "docs/hello.md" in members


@pytest.mark.skipif(
    not __import__("importlib.util", fromlist=["find_spec"]).find_spec("py7zr"),
    reason="py7zr not installed",
)
def test_open_member_7z(tmp_path):
    import py7zr
    sp = tmp_path / "test.7z"
    with py7zr.SevenZipFile(sp, mode="w") as sz:
        content = b"# Hello from 7z"
        sz.writestr({"docs/hello.md": io.BytesIO(content)})
    with open_member(str(sp), "docs/hello.md") as tmp:
        data = Path(tmp).read_bytes()
        assert b"Hello" in data
    assert not Path(tmp).exists()
