"""Loaders added for format parity with Paperback (https://github.com/trypsynth/paperback).

Every format Paperback opens now opens in star, on the standard library alone:
FictionBook (FB2), RTF, Windows Write, OpenDocument presentations and flat XML,
macro-enabled Office (DOCM/PPTM), legacy binary PowerPoint and Word (OLE),
MOBI/AZW, CHM (ITSF + LZX), WinHelp, DAISY 3 packages and DAISY 2.02 books,
comic archives, M4B/MP3 audiobooks, manual pages (incl. gzipped and numbered
sections), gzipped documents, and the extra Markdown/log/xhtml spellings.

The binary containers (CHM, WinHelp, OLE, MOBI, MP4, ID3) are exercised on
**synthetic fixtures built here** — no binary blobs in the repository — using
small writers that follow the same specifications the readers do.  The LZX
fixture uses the format's *uncompressed* block type, which drives the block
header, reset-table and frame plumbing; the Huffman paths are covered by the
decoder's structural checks only.
"""
import gzip
import struct
import zipfile
from pathlib import Path

import pytest

from star.documents import (
    ChmFile,
    HlpFile,
    OleFile,
    _detect_format,
    _fb2_chapters,
    _load_audiobook_full,
    _load_chm_full,
    _load_comic,
    _load_daisy_full,
    _load_doc_native,
    _load_docx_native,
    _load_fb2,
    _load_fodt,
    _load_manpage,
    _load_mobi_full,
    _load_odp,
    _load_ppt_native,
    _load_pptx_native,
    _load_rtf,
    _load_winhelp_full,
    _load_wri,
    _sniff_zip,
    is_manual_page_name,
    load_document,
    looks_like_rtf,
    supported_extensions,
)
from star.settings import Settings


@pytest.fixture
def settings():
    s = Settings()
    s["prefer_pandoc"] = False  # exercise the native loaders (tmp settings file)
    return s


# ═══════════════════════════════════════════════════════════════════════════
# Fixture builders (synthetic binary containers)
# ═══════════════════════════════════════════════════════════════════════════

# ── CHM ─────────────────────────────────────────────────────────────────────


def _cword(n: int) -> bytes:
    """A CHM directory integer: big-endian base-128 with continuation bits."""
    parts = []
    while True:
        parts.append(n & 0x7F)
        n >>= 7
        if not n:
            break
    parts.reverse()
    return bytes(p | (0x80 if i < len(parts) - 1 else 0) for i, p in enumerate(parts))


def _lzx_uncompressed_stream(data: bytes, block_len: int = 0x8000) -> list:
    """One LZX frame per *block_len* chunk, each an 'uncompressed' block (type 3)."""
    frames = []
    first = True
    for i in range(0, len(data), block_len):
        chunk = data[i:i + block_len]
        bits: list = []

        def put(v: int, n: int) -> None:
            for k in range(n - 1, -1, -1):
                bits.append((v >> k) & 1)

        if first:
            put(0, 1)  # no Intel E8 file size
            first = False
        put(3, 3)
        put(len(chunk) >> 8, 16)
        put(len(chunk) & 0xFF, 8)
        while len(bits) % 16:
            bits.append(0)
        out = bytearray()
        for j in range(0, len(bits), 16):
            w = 0
            for b in bits[j:j + 16]:
                w = (w << 1) | b
            out += struct.pack("<H", w)
        out += struct.pack("<III", 1, 1, 1)  # R0 R1 R2
        out += chunk
        if len(chunk) & 1:
            out += b"\x00"
        frames.append(bytes(out))
    return frames


def build_chm(files: dict, compressed: bool = False) -> bytes:
    """An ITSF v3 container with one PMGL block; content in section 0, or in an
    LZX 'MSCompressed' section built from uncompressed-type blocks."""
    entries = []  # (path, space, start, length)
    content = bytearray()
    if compressed:
        space = bytearray()
        for path, data in files.items():
            entries.append((path, 1, len(space), len(data)))
            space += data
        block_len = 0x8000
        frames = _lzx_uncompressed_stream(bytes(space), block_len)
        comp = b"".join(frames)
        offsets = []
        acc = 0
        for f in frames:
            offsets.append(acc)
            acc += len(f)
        content_start = len(content)
        content += comp
        rt = struct.pack("<IIIIQQQ", 2, len(frames), 8, 0x28, len(space), len(comp), block_len)
        rt += b"".join(struct.pack("<Q", o) for o in offsets)
        rt_start = len(content)
        content += rt
        # LZXC v2: reset interval and window in 0x8000 units → 0x10000 each.
        ctl = struct.pack("<I", 6) + b"LZXC" + struct.pack("<IIIII", 2, 2, 2, 1, 0)
        ctl_start = len(content)
        content += ctl
        prefix = "::DataSpace/Storage/MSCompressed/"
        entries.append((prefix + "Content", 0, content_start, len(comp)))
        entries.append((prefix + "Transform/{7FC28940-9D31-11D0-9B27-00A0C91E9C7C}/InstanceData/ResetTable", 0, rt_start, len(rt)))
        entries.append((prefix + "ControlData", 0, ctl_start, len(ctl)))
    else:
        for path, data in files.items():
            entries.append((path, 0, len(content), len(data)))
            content += data
    entries.sort(key=lambda e: e[0].lower())
    body = bytearray()
    for path, sp, st, ln in entries:
        pb = path.encode()
        body += _cword(len(pb)) + pb + _cword(sp) + _cword(st) + _cword(ln)
    block_len = 0x1000
    free = block_len - 0x14 - len(body)
    pmgl = b"PMGL" + struct.pack("<IIii", free, 0, -1, -1) + bytes(body) + b"\x00" * free
    itsp = b"ITSP" + struct.pack("<IIIIIiiiIIII", 1, 0x54, 0x0A, block_len, 2, 1, -1, 0, 0, 1, 1, 0)
    itsp += b"\x00" * (0x54 - len(itsp))
    dir_offset = 0x60 + 0x18
    directory = itsp + pmgl
    data_offset = dir_offset + len(directory)
    itsf = b"ITSF" + struct.pack("<III", 3, 0x60, 1) + struct.pack("<II", 0, 0x0409) + b"\x00" * 32
    itsf += struct.pack("<QQQQ", 0x60, 0x18, dir_offset, len(directory))
    itsf += struct.pack("<Q", data_offset)
    assert len(itsf) == 0x60
    return bytes(itsf + b"\x00" * 0x18 + directory + content)


# ── WinHelp ─────────────────────────────────────────────────────────────────

_HLP_LINK_LEN = 21


def _hlp_internal_file(content: bytes) -> bytes:
    return struct.pack("<IIB", len(content) + 9, len(content), 4) + content


def _hlp_btree(entries: list, page_size: int = 1024) -> bytes:
    """A single-leaf B+ tree over already-encoded *entries*."""
    page = struct.pack("<Hh", 0, len(entries)) + struct.pack("<hh", -1, -1) + b"".join(entries)
    page = page.ljust(page_size, b"\x00")
    hdr = struct.pack("<HHH", 0x293B, 0x0402, page_size) + b"\x00" * 16
    hdr += struct.pack("<hhhhHHI", 0, 0, 0, -1, 1, 1, len(entries))
    assert len(hdr) == 38
    return hdr + page


def _hlp_record(rtype: int, nxt: int, data1: bytes, data2: bytes) -> bytes:
    data_len1 = _HLP_LINK_LEN + len(data1)
    block_size = data_len1 + len(data2)
    return struct.pack("<IIIIIB", block_size, len(data2), 0, nxt, data_len1, rtype) + data1 + data2


def _hlp_display(paras: list, font: int = 1) -> tuple:
    """A 3.1 display record: font change, first paragraph, end-of-paragraph, second."""
    d1 = struct.pack("<H", 0x8000) + b"\x00" + b"\x00\x00\x00\x00" + struct.pack("<H", 0)
    strings = []
    d1 += b"\x80" + struct.pack("<H", font)
    strings.append(b"")
    d1 += b"\x82"
    strings.append(paras[0].encode("cp1252"))
    d1 += b"\xff"
    strings.append(paras[1].encode("cp1252") if len(paras) > 1 else b"")
    return d1, b"".join(s + b"\x00" for s in strings)


def build_hlp(title: str, topics: list) -> bytes:
    """A WinHelp 3.1 file (uncompressed 4k blocks): |SYSTEM, |TOPIC, |FONT, directory."""
    parts = []
    for topic_title, paras in topics:
        parts.append((2, b"\x00" * 28, topic_title.encode("cp1252") + b"\x00"))
        d1, d2 = _hlp_display(paras)
        parts.append((0x20, d1, d2))
    pos = 12
    starts = []
    for _kind, d1, d2 in parts:
        starts.append(pos)
        pos += _HLP_LINK_LEN + len(d1) + len(d2)
    payload = b""
    for i, (kind, d1, d2) in enumerate(parts):
        nxt = starts[i + 1] if i + 1 < len(starts) else pos
        payload += _hlp_record(kind, nxt, d1, d2)
    payload += _hlp_record(0, 0, b"", b"")
    topic_file = (b"\x00" * 12 + payload).ljust(4096, b"\x00")
    system = struct.pack("<HHHIH", 0x036C, 21, 1, 0, 0)
    system += struct.pack("<HH", 1, len(title) + 1) + title.encode() + b"\x00"
    faces = b"Arial".ljust(20, b"\x00")
    font = struct.pack("<HHHH", 1, 2, 8, 8 + 20) + faces
    for attrs in (0, 1):  # font 0 plain, font 1 bold
        font += bytes([attrs, 20, 3]) + struct.pack("<H", 0) + b"\x00" * 6
    files = {
        b"|SYSTEM": _hlp_internal_file(system),
        b"|TOPIC": _hlp_internal_file(topic_file),
        b"|FONT": _hlp_internal_file(font),
    }
    out = bytearray(b"\x00" * 16)
    offsets = {}
    for name, blob in files.items():
        offsets[name] = len(out)
        out += blob
    entries = [name + b"\x00" + struct.pack("<I", offsets[name]) for name in sorted(files)]
    dir_start = len(out)
    out += _hlp_internal_file(_hlp_btree(entries))
    struct.pack_into("<IIII", out, 0, 0x00035F3F, dir_start, 0xFFFFFFFF, len(out))
    return bytes(out)


# ── OLE (CFB) ───────────────────────────────────────────────────────────────

_SEC = 512
_MINI = 64
_CUTOFF = 4096
_END, _FREE, _FATSECT = 0xFFFFFFFE, 0xFFFFFFFF, 0xFFFFFFFD


def build_cfb(streams: dict) -> bytes:
    """A compound file with 512-byte sectors; streams under 4096 bytes go to the
    mini stream, exactly as Office writes them."""
    fat = [_FATSECT, _END]  # sector 0 = FAT, sector 1 = directory
    data_sectors: list = []

    def add_chain(blob: bytes) -> int:
        chunks = [blob[i:i + _SEC] for i in range(0, len(blob), _SEC)] or [b""]
        start = 2 + len(data_sectors)
        for i, c in enumerate(chunks):
            data_sectors.append(c.ljust(_SEC, b"\x00"))
            fat.append(start + i + 1 if i + 1 < len(chunks) else _END)
        return start

    mini_blob = bytearray()
    minifat: list = []
    mini_starts = {}
    big_starts = {}
    for name, data in streams.items():
        if len(data) < _CUTOFF:
            chunks = [data[i:i + _MINI] for i in range(0, len(data), _MINI)] or [b""]
            start = len(minifat)
            mini_starts[name] = start
            for i, c in enumerate(chunks):
                mini_blob += c.ljust(_MINI, b"\x00")
                minifat.append(start + i + 1 if i + 1 < len(chunks) else _END)
        else:
            big_starts[name] = add_chain(data)
    mini_start = add_chain(bytes(mini_blob)) if mini_blob else _END
    while len(minifat) % (_SEC // 4):
        minifat.append(_FREE)
    minifat_bytes = b"".join(struct.pack("<I", x) for x in minifat)
    minifat_start = add_chain(minifat_bytes) if minifat_bytes else _END
    num_minifat = (len(minifat_bytes) + _SEC - 1) // _SEC
    while len(fat) < _SEC // 4:
        fat.append(_FREE)
    fat_bytes = struct.pack("<128I", *fat[:128])

    def dirent(name: str, typ: int, start: int, size: int, right: int = -1, child: int = -1) -> bytes:
        nm = name.encode("utf-16-le") + b"\x00\x00"
        e = nm.ljust(64, b"\x00") + struct.pack("<H", len(nm)) + bytes([typ, 1])
        e += struct.pack("<iii", -1, right, child) + b"\x00" * 16 + struct.pack("<I", 0) + b"\x00" * 16
        e += struct.pack("<II", start & 0xFFFFFFFF, size) + b"\x00" * 4
        assert len(e) == 128
        return e

    names = list(streams)
    entries = [dirent("Root Entry", 5, mini_start, len(mini_blob), child=1)]
    for i, name in enumerate(names):
        start = mini_starts.get(name, big_starts.get(name))
        entries.append(dirent(name, 2, start, len(streams[name]), right=(i + 2 if i + 1 < len(names) else -1)))
    dir_bytes = b"".join(entries).ljust(_SEC, b"\x00")
    header = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 16 + struct.pack(
        "<HHHHH6sIIIIIIIII", 0x3E, 3, 0xFFFE, 9, 6, b"\x00" * 6, 0, 1, 1, 0, _CUTOFF,
        minifat_start, num_minifat, _END, 0)
    assert len(header) == 76
    header += struct.pack("<109I", 0, *([_FREE] * 108))
    return header + fat_bytes + dir_bytes + b"".join(data_sectors)


def ppt_stream(slides: list) -> bytes:
    """A ``PowerPoint Document`` stream: one Slide container per slide with a
    TextHeaderAtom + TextCharsAtom title and a TextHeaderAtom + TextBytesAtom body."""

    def rec(rtype: int, body: bytes, container: bool = False, instance: int = 0) -> bytes:
        ver = 0xF if container else 0
        return struct.pack("<HHI", (instance << 4) | ver, rtype, len(body)) + body

    out = b""
    for title, body in slides:
        inner = rec(0x0F9F, struct.pack("<I", 0)) + rec(0x0FA0, title.encode("utf-16-le"))
        inner += rec(0x0F9F, struct.pack("<I", 1)) + rec(0x0FA8, "\r".join(body).encode("cp1252"))
        out += rec(0x03EE, inner, container=True)
    return out


def doc_streams(text: str) -> tuple:
    """Word 97 ``WordDocument`` + ``0Table`` with a one-piece (8-bit) piece table."""
    wd = bytearray(0x400)
    struct.pack_into("<H", wd, 0, 0xA5EC)
    struct.pack_into("<H", wd, 2, 0x00C1)
    struct.pack_into("<H", wd, 0x0A, 0)
    text_bytes = text.encode("cp1252")
    fc = 0x400
    wd += text_bytes
    struct.pack_into("<II", wd, 0x18, fc, fc + len(text_bytes))
    plc = struct.pack("<II", 0, len(text_bytes)) + b"\x00\x00" + struct.pack("<I", (fc * 2) | 0x40000000) + b"\x00\x00"
    clx = b"\x02" + struct.pack("<I", len(plc)) + plc
    table = b"\x00" * 16 + clx
    struct.pack_into("<II", wd, 0x1A2, 16, len(clx))
    return bytes(wd), table


# ── MOBI / PDB ───────────────────────────────────────────────────────────────


def _palmdoc_literal_compress(data: bytes) -> bytes:
    """A valid PalmDOC stream that uses only literal codes (no back-references)."""
    out = bytearray()
    i = 0
    while i < len(data):
        c = data[i]
        if c == 0 or 9 <= c <= 0x7F:
            out.append(c)
            i += 1
        else:
            run = data[i:i + 8]
            out.append(len(run))
            out += run
            i += len(run)
    return bytes(out)


def build_mobi(html: bytes, title: str = "Synthetic Mobi", author: str = "Author M",
               compression: int = 2, huff: bool = False) -> bytes:
    text_rec = _palmdoc_literal_compress(html) if compression == 2 else html
    r0 = bytearray(struct.pack(">HHIHHHH", compression, 0, len(html), 1, 4096, 0, 0))
    hdr = bytearray(b"MOBI" + struct.pack(">III", 0xE8, 2, 65001) + b"\x00" * (0xE8 - 16))
    hdr[0x24:0x28] = struct.pack(">I", 6)          # file version
    hdr[0x70:0x74] = struct.pack(">I", 0x40)       # EXTH flags
    exth_rec = struct.pack(">II", 100, 8 + len(author)) + author.encode()
    exth = b"EXTH" + struct.pack(">II", 12 + len(exth_rec), 1) + exth_rec
    r0 += hdr + exth
    name = title.encode()
    r0[0x54:0x58] = struct.pack(">I", len(r0))
    r0[0x58:0x5C] = struct.pack(">I", len(name))
    r0 += name + b"\x00" * 4
    records = [bytes(r0), text_rec]
    pdb = bytearray(b"synthetic".ljust(32, b"\x00") + struct.pack(">HHIIIIII", 0, 0, 0, 0, 0, 0, 0, 0)
                    + b"BOOKMOBI" + struct.pack(">IIH", 0, 0, len(records)))
    off = len(pdb) + 8 * len(records) + 2
    for i, r in enumerate(records):
        pdb += struct.pack(">I", off) + bytes([0]) + i.to_bytes(3, "big")
        off += len(r)
    pdb += b"\x00\x00"
    for r in records:
        pdb += r
    return bytes(pdb)


# ── MP3 (ID3v2.3) and M4B (MP4 atoms) ───────────────────────────────────────


def _id3_frame(fid: str, payload: bytes) -> bytes:
    return fid.encode() + struct.pack(">I", len(payload)) + b"\x00\x00" + payload


def _id3_text(fid: str, text: str) -> bytes:
    return _id3_frame(fid, b"\x03" + text.encode() + b"\x00")


def _id3_chap(eid: str, start_ms: int, title: str) -> bytes:
    body = eid.encode() + b"\x00" + struct.pack(">IIII", start_ms, start_ms + 1000, 0xFFFFFFFF, 0xFFFFFFFF)
    return _id3_frame("CHAP", body + _id3_text("TIT2", title))


def build_mp3(title="My Audiobook", artist="Narrator N", album="Album", chapters=(("ch1", 0, "Intro"), ("ch2", 60000, "Middle"))) -> bytes:
    body = _id3_text("TIT2", title) + _id3_text("TPE1", artist) + _id3_text("TALB", album)
    for eid, start, ctitle in chapters:
        body += _id3_chap(eid, start, ctitle)
    ids = b"".join(e.encode() + b"\x00" for e, _s, _t in chapters)
    body += _id3_frame("CTOC", b"toc\x00\x03" + bytes([len(chapters)]) + ids)
    size = len(body)
    ss = bytes([(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F])
    # One MPEG-1 Layer III frame header (128 kbps, 44.1 kHz) then silence.
    return b"ID3\x03\x00\x00" + ss + body + b"\xff\xfb\x90\x00" + b"\x00" * 4000


def _atom(t: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", 8 + len(payload)) + t + payload


def build_m4b(title="The M4B", artist="Author A", duration_ms=90000,
              chapters=((0, "Start"), (30000, "End"))) -> bytes:
    def data_atom(text: str) -> bytes:
        return _atom(b"data", struct.pack(">II", 1, 0) + text.encode())
    ilst = _atom(b"ilst", _atom(b"\xa9nam", data_atom(title)) + _atom(b"\xa9ART", data_atom(artist)))
    meta = _atom(b"meta", b"\x00\x00\x00\x00" + ilst)
    chpl = b"\x01\x00\x00\x00" + b"\x00\x00\x00\x00" + struct.pack(">I", len(chapters))
    for start_ms, ctitle in chapters:
        chpl += struct.pack(">Q", start_ms * 10_000) + bytes([len(ctitle)]) + ctitle.encode()
    udta = _atom(b"udta", meta + _atom(b"chpl", chpl))
    mvhd = _atom(b"mvhd", b"\x00" * 12 + struct.pack(">II", 1000, duration_ms) + b"\x00" * 80)
    moov = _atom(b"moov", mvhd + udta)
    return _atom(b"ftyp", b"M4B \x00\x00\x00\x00") + moov + _atom(b"mdat", b"\x00" * 100)


# ═══════════════════════════════════════════════════════════════════════════
# Detection & registry
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "name,fmt",
    [
        ("a.mdx", "markdown"), ("a.mdwn", "markdown"), ("a.mkd", "markdown"), ("a.ronn", "markdown"),
        ("x.log", "text"), ("page.xhtml", "html"),
        ("a.docm", "docx"), ("a.pptm", "pptx"), ("a.ppt", "ppt"), ("a.pps", "ppt"),
        ("a.odp", "odp"), ("a.fodp", "odp"), ("a.fodt", "fodt"),
        ("a.rtf", "rtf"), ("a.wri", "wri"), ("a.fb2", "fb2"),
        ("a.mobi", "mobi"), ("a.azw", "mobi"), ("a.azw3", "mobi"), ("a.prc", "mobi"),
        ("a.chm", "chm"), ("a.hlp", "winhelp"),
        ("a.cbz", "comic"), ("a.cbr", "comic"),
        ("a.m4b", "audiobook"), ("a.mp3", "audiobook"),
        ("a.man", "man"), ("a.roff", "man"), ("ls.1", "man"), ("Tcl_Init.3tcl", "man"),
        ("printf.3.gz", "man"), ("notes.txt.gz", "gz"),
        ("ncc.html", "daisy"), ("NCC.HTML", "daisy"), ("book.opf", "daisy"), ("nav.ncx", "daisy"),
    ],
)
def test_paperback_extensions_detect(name, fmt):
    assert _detect_format(name) == fmt


def test_every_paperback_extension_is_supported():
    paperback = {
        "cbr", "cbz", "chm", "hlp", "opf", "zip", "docx", "docm", "doc", "epub", "fb2",
        "htm", "html", "xhtml", "pdf", "man", "roff", "gz", "1", "2", "3", "4", "5", "6",
        "7", "8", "9", "md", "markdown", "mdx", "mdown", "mdwn", "mkd", "mkdn", "mkdown",
        "ronn", "m4b", "mp3", "mobi", "azw", "azw3", "fodp", "odp", "fodt", "odt", "pptx",
        "pptm", "ppt", "rst", "rest", "rtf", "txt", "log", "wri",
    }
    exts = supported_extensions()
    missing = {e for e in paperback if f".{e}" not in exts and e != "zip"}
    assert not missing, f"Paperback formats star cannot open: {sorted(missing)}"


def test_manual_page_names():
    assert is_manual_page_name("ls.1")
    assert is_manual_page_name("printf.3.gz")
    assert is_manual_page_name("Tcl_Init.3tcl")
    assert not is_manual_page_name("notes.txt")
    assert not is_manual_page_name("archive.tar.gz")
    assert not is_manual_page_name("file")


def test_handlers_registered_for_new_formats():
    from star.plugins import PluginRegistry

    reg = PluginRegistry.get()
    expected = {
        ".rtf": "RTFHandler", ".fb2": "FB2Handler", ".chm": "CHMHandler", ".hlp": "WinHelpHandler",
        ".mobi": "MobiHandler", ".cbz": "ComicHandler", ".m4b": "AudiobookHandler",
        ".opf": "DAISYHandler", ".odp": "ODPHandler", ".fodt": "FODTHandler",
        ".wri": "WriHandler", ".ppt": "PPTHandler", ".doc": "DocHandler", ".man": "ManPageHandler",
    }
    for ext, cls in expected.items():
        h = reg.handler_for(Path("x" + ext))
        assert h is not None and type(h).__name__ == cls, (ext, h)


def test_archive_member_filter_follows_dispatcher():
    from star.archive import _DOC_EXTS, _readable

    assert ".rtf" in _DOC_EXTS and ".mobi" in _DOC_EXTS and ".chm" in _DOC_EXTS
    assert _readable("book.fb2")
    assert _readable("dir/help.chm")
    assert not _readable("__MACOSX/x.rtf")


# ═══════════════════════════════════════════════════════════════════════════
# Text-ish formats
# ═══════════════════════════════════════════════════════════════════════════

_RTF = (b"{\\rtf1\\ansi\\ansicpg1252\\deff0{\\fonttbl{\\f0 Times;}}"
        b"{\\stylesheet{\\s0 Normal;}{\\s1 heading 1;}}{\\info{\\title Skip me}}"
        b"\\pard\\s1 Big Heading\\par"
        b"\\pard\\plain Hello \\b bold\\b0  and \\i italic\\i0  caf\\'e9 \\u8212? dash.\\par"
        b"{\\pntext\\'b7\\tab}First bullet\\par{\\pntext\\'b7\\tab}Second\\par"
        b"\\trowd\\cellx1000\\cellx2000 \\intbl A\\cell B\\cell\\row"
        b"\\trowd\\cellx1000\\cellx2000 \\intbl 1\\cell 2\\cell\\row"
        b"\\pard After table.\\page Next page.\\par}")


def test_rtf_native(tmp_path, settings):
    p = tmp_path / "memo.rtf"
    p.write_bytes(_RTF)
    assert looks_like_rtf(_RTF)
    md = _load_rtf(str(p))
    assert md.startswith("# Big Heading")
    assert "Hello **bold** and *italic* café — dash." in md
    assert "- First bullet\n- Second" in md
    assert "| A | B |\n| --- | --- |\n| 1 | 2 |" in md
    assert md.index("| 1 | 2 |") < md.index("After table.")
    assert "Skip me" not in md
    assert "\n---\n" in md  # page break
    doc = load_document(str(p), settings)
    assert doc.format == "rtf" and doc.title == "Big Heading"
    assert "bold" in doc.plain_text


def test_rtf_non_rtf_bytes_read_as_text(tmp_path):
    p = tmp_path / "plain.rtf"
    p.write_text("just text")
    assert _load_rtf(str(p)) == "just text"


def test_wri_routes_rtf_binary_and_text(tmp_path, settings):
    rtf = tmp_path / "a.wri"
    rtf.write_bytes(b"{\\rtf1 RTF in disguise\\par}")
    assert "RTF in disguise" in _load_wri(str(rtf))
    hdr = bytearray(128)
    hdr[0:2] = (0x31BE).to_bytes(2, "little")
    text = b"Hello from Write.\r\nSecond para.\r\n"
    hdr[0x0E:0x12] = (128 + len(text)).to_bytes(4, "little")
    wri = tmp_path / "b.wri"
    wri.write_bytes(bytes(hdr) + text + b"\x00" * 20)
    md = _load_wri(str(wri))
    assert "Hello from Write." in md and "Second para." in md
    txt = tmp_path / "c.wri"
    txt.write_text("plain write file")
    assert _load_wri(str(txt)) == "plain write file"
    assert load_document(str(wri), settings).format == "wri"


_FB2 = """<?xml version="1.0"?><FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0" xmlns:l="http://www.w3.org/1999/xlink">
<description><title-info><author><first-name>Ann</first-name><last-name>Smith</last-name></author><book-title>The Book</book-title></title-info></description>
<body><title><p>The Book</p></title>
<section id="c1"><title><p>Chapter One</p></title><p>It was <emphasis>dark</emphasis>.<a l:href="#n1" type="note">1</a></p>
<poem><stanza><v>line a</v><v>line b</v></stanza></poem><table><tr><td>x</td><td>y</td></tr></table></section>
<section><title><p>Chapter Two</p></title><p>More.</p></section></body>
<body name="notes"><section id="n1"><title><p>1</p></title><p>A note.</p></section></body></FictionBook>"""


def test_fb2_native(tmp_path, settings):
    p = tmp_path / "book.fb2"
    p.write_text(_FB2, encoding="utf-8")
    md = _load_fb2(str(p))
    assert md.startswith("# The Book\n\n*Ann Smith*")
    assert md.count("# The Book") == 1  # body-level title not repeated
    assert "## Chapter One" in md and "## Chapter Two" in md
    assert "It was *dark*.[^n1]" in md and "[^n1]: A note." in md
    assert "line a  \nline b" in md
    assert "| x | y |" in md
    assert _fb2_chapters(str(p)) == [("Chapter One", "c1"), ("Chapter Two", "Chapter Two")]
    doc = load_document(str(p), settings)
    assert doc.format == "fb2" and doc.title == "The Book"
    assert [c[0] for c in doc.chapters] == ["Chapter One", "Chapter Two"]
    assert doc.chapters[1][2] > doc.chapters[0][2] > 0  # resolved word indices


def test_fb2_zip_bundle(tmp_path, settings):
    z = tmp_path / "book.fb2.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("book.fb2", _FB2)
    assert _sniff_zip(str(z)) == "fb2"
    doc = load_document(str(z), settings)
    assert doc.format == "fb2" and "Chapter One" in doc.markdown


_ODP_CONTENT = """<?xml version="1.0"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" xmlns:presentation="urn:oasis:names:tc:opendocument:xmlns:presentation:1.0"><office:body><office:presentation>
<draw:page draw:name="page1"><draw:frame presentation:class="title"><draw:text-box><text:p>Welcome</text:p></draw:text-box></draw:frame>
<draw:frame presentation:class="outline"><draw:text-box><text:list><text:list-item><text:p>Point one</text:p></text:list-item><text:list-item><text:p>Point two</text:p></text:list-item></text:list></draw:text-box></draw:frame>
<presentation:notes><draw:frame><draw:text-box><text:p>Say hi.</text:p></draw:text-box></draw:frame></presentation:notes></draw:page>
<draw:page draw:name="page2"><draw:frame><draw:text-box><text:p>Plain body</text:p></draw:text-box></draw:frame></draw:page>
</office:presentation></office:body></office:document-content>"""


def test_odp_and_fodp(tmp_path, settings):
    odp = tmp_path / "deck.odp"
    with zipfile.ZipFile(odp, "w") as zf:
        zf.writestr("mimetype", "application/vnd.oasis.opendocument.presentation")
        zf.writestr("content.xml", _ODP_CONTENT)
    md = _load_odp(str(odp))
    assert "## Slide 1: Welcome" in md and "- Point one\n- Point two" in md
    assert "> Note: Say hi." in md and "## page2" in md and "- Plain body" in md
    fodp = tmp_path / "deck.fodp"
    fodp.write_text(_ODP_CONTENT.replace("office:document-content", "office:document"))
    assert _load_odp(str(fodp)) == md
    assert load_document(str(odp), settings).format == "odp"


def test_fodt(tmp_path, settings):
    fodt = tmp_path / "doc.fodt"
    fodt.write_text("""<?xml version="1.0"?><office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"><office:body><office:text><text:h text:outline-level="1">Title</text:h><text:p>Para with<text:s text:c="2"/>spaces.</text:p><text:list><text:list-item><text:p>item</text:p></text:list-item></text:list><table:table><table:table-row><table:table-cell><text:p>a</text:p></table:table-cell><table:table-cell><text:p>b</text:p></table:table-cell></table:table-row></table:table></office:text></office:body></office:document>""")
    md = _load_fodt(str(fodt))
    assert md.startswith("# Title") and "Para with  spaces." in md and "- item" in md and "| a | b |" in md
    assert load_document(str(fodt), settings).format == "fodt"


_MAN = """.\\" comment
.TH LS 1 "2024" "coreutils" "User Commands"
.SH NAME
ls \\- list directory contents
.SH SYNOPSIS
.B ls
[\\fIOPTION\\fR]... [\\fIFILE\\fR]...
.SH DESCRIPTION
List information about the FILEs.
.TP
.BR \\-a ", " \\-\\-all
do not ignore entries starting with .
.TP
\\fB\\-l\\fR
use a long listing format
.SS Exit status
.nf
0  if OK
1  minor problems
.fi
.SH SEE ALSO
.UR https://example.com
Full docs
.UE
"""


def test_manpage_native_and_gzipped(tmp_path, settings):
    p = tmp_path / "ls.1"
    p.write_text(_MAN)
    md = _load_manpage(str(p))
    assert md.startswith("# LS(1)")
    assert "## Name\n\nls - list directory contents" in md
    assert "**ls** [*OPTION*]... [*FILE*]..." in md
    assert "**-a**, **--all**\n\ndo not ignore" in md
    assert "**-l**\n\nuse a long listing format" in md
    assert "```\n0  if OK\n1  minor problems\n```" in md
    assert "<https://example.com>" in md
    doc = load_document(str(p), settings)
    assert doc.format == "man" and doc.title == "LS(1)"
    gz = tmp_path / "printf.3.gz"
    with gzip.open(gz, "wb") as fh:
        fh.write(_MAN.replace("LS 1", "PRINTF 3").encode())
    doc = load_document(str(gz), settings)
    assert doc.format == "man" and doc.title == "PRINTF(3)"


def test_mdoc_manpage(tmp_path):
    p = tmp_path / "cat.1"
    p.write_text(".Dd Jan 1\n.Dt CAT 1\n.Sh NAME\n.Nm cat\n.Nd concatenate files\n.Sh SYNOPSIS\n.Nm\n.Op Fl u\n.Sh DESCRIPTION\nReads files.\n.Bl -tag\n.It Fl u\nUnbuffered.\n.El\n")
    md = _load_manpage(str(p))
    assert md.startswith("# CAT(1)") and "## Name" in md and "**cat**" in md
    assert "**cat** [**-u**]" in md and "**-u**\n\nUnbuffered." in md


def test_gzipped_document_unpacks_by_inner_extension(tmp_path, settings):
    gz = tmp_path / "notes.txt.gz"
    with gzip.open(gz, "wb") as fh:
        fh.write(b"Just some gzipped notes.\n")
    doc = load_document(str(gz), settings)
    assert doc.format == "text" and "gzipped notes" in doc.markdown and doc.path == str(gz)
    html_gz = tmp_path / "page.html.gz"
    with gzip.open(html_gz, "wb") as fh:
        fh.write(b"<html><body><h1>Gz Page</h1><p>Body.</p></body></html>")
    doc = load_document(str(html_gz), settings)
    assert doc.format == "html" and doc.title == "Gz Page"


# ═══════════════════════════════════════════════════════════════════════════
# Office
# ═══════════════════════════════════════════════════════════════════════════

_CT = """<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/word/document.xml" ContentType="application/vnd.ms-word.document.macroEnabled.main+xml"/></Types>"""
_DOCM = """<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Macro Doc</w:t></w:r></w:p><w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Bold</w:t></w:r><w:r><w:t xml:space="preserve"> and plain.</w:t></w:r></w:p><w:p><w:pPr><w:numPr><w:ilvl w:val="0"/></w:numPr></w:pPr><w:r><w:t>Item</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>h1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>h2</w:t></w:r></w:p></w:tc></w:tr><w:tr><w:tc><w:p><w:r><w:t>c1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>c2</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>"""
_STYLES = """<?xml version="1.0"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:style w:styleId="Heading1"><w:name w:val="heading 1"/></w:style></w:styles>"""


def _write_docm(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", _CT)
        zf.writestr("word/document.xml", _DOCM)
        zf.writestr("word/styles.xml", _STYLES)


def test_docm_native_ooxml(tmp_path, settings):
    p = tmp_path / "macro.docm"
    _write_docm(p)
    md = _load_docx_native(str(p))
    assert md.startswith("# Macro Doc") and "**Bold** and plain." in md and "- Item" in md
    assert "| h1 | h2 |\n| --- | --- |\n| c1 | c2 |" in md
    doc = load_document(str(p), settings)
    assert doc.format == "docx" and doc.title == "Macro Doc" and "Bold" in doc.plain_text


def test_docx_in_zip_clothing(tmp_path, settings):
    p = tmp_path / "renamed.zip"
    _write_docm(p)
    assert _sniff_zip(str(p)) == "docx"
    doc = load_document(str(p), settings)
    assert doc.format == "docx" and "Macro Doc" in doc.markdown


_PRES = """<?xml version="1.0"?><p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst><p:sldId id="256" r:id="rId2"/></p:sldIdLst></p:presentation>"""
_PRELS = """<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId2" Type="x" Target="slides/slide1.xml"/></Relationships>"""
_SLIDE = """<?xml version="1.0"?><p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree><p:sp><p:nvSpPr><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr><p:txBody><a:p><a:r><a:t>Slide Title</a:t></a:r></a:p></p:txBody></p:sp><p:sp><p:nvSpPr><p:nvPr><p:ph type="body"/></p:nvPr></p:nvSpPr><p:txBody><a:p><a:r><a:t>Bullet A</a:t></a:r></a:p><a:p><a:pPr lvl="1"/><a:r><a:t>Sub</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>"""


def test_pptm_native_ooxml(tmp_path, settings):
    p = tmp_path / "macro.pptm"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("[Content_Types].xml", _CT.replace("word/document.xml", "ppt/presentation.xml"))
        zf.writestr("ppt/presentation.xml", _PRES)
        zf.writestr("ppt/_rels/presentation.xml.rels", _PRELS)
        zf.writestr("ppt/slides/slide1.xml", _SLIDE)
    md = _load_pptx_native(str(p))
    assert md.startswith("## Slide 1: Slide Title") and "- Bullet A\n  - Sub" in md
    doc = load_document(str(p), settings)
    assert doc.format == "pptx" and "Bullet A" in doc.plain_text


def test_legacy_ppt_native_ole(tmp_path, settings, monkeypatch):
    monkeypatch.setenv("STAR_NO_LIBREOFFICE", "1")
    data = build_cfb({"PowerPoint Document": ppt_stream([("First Slide", ["Point A", "Point B"]), ("Second", ["Only"])])})
    p = tmp_path / "legacy.ppt"
    p.write_bytes(data)
    assert OleFile(data).streams() == ["PowerPoint Document"]
    md = _load_ppt_native(str(p))
    assert "## Slide 1: First Slide\n\n- Point A\n- Point B" in md and "## Slide 2: Second" in md
    doc = load_document(str(p), settings)
    assert doc.format == "ppt" and "Point A" in doc.plain_text


def test_legacy_doc_native_ole(tmp_path):
    wd, tbl = doc_streams("Hello legacy Word.\rSecond paragraph.\r")
    small = tmp_path / "legacy.doc"
    small.write_bytes(build_cfb({"WordDocument": wd, "0Table": tbl}))
    md = _load_doc_native(str(small))
    assert md and "Hello legacy Word.\n\nSecond paragraph." in md
    # A stream past the mini-stream cutoff exercises the regular FAT chain too.
    big = tmp_path / "legacy_big.doc"
    big.write_bytes(build_cfb({"WordDocument": wd + b"\x00" * 5000, "0Table": tbl}))
    assert "Second paragraph." in (_load_doc_native(str(big)) or "")
    assert _load_doc_native(str(small.with_suffix(".missing"))) is None


def test_ole_rejects_non_ole():
    with pytest.raises(ValueError):
        OleFile(b"not an ole file at all" * 10)


# ═══════════════════════════════════════════════════════════════════════════
# E-books & help files
# ═══════════════════════════════════════════════════════════════════════════

_MOBI_HTML = (b"<html><body><h1>Mobi Title</h1><p>Hello mobi world. Hello mobi world again.</p>"
              b"<mbp:pagebreak/><h2>Two</h2><p>End.</p></body></html>")


@pytest.mark.parametrize("compression", [1, 2])
def test_mobi_native(tmp_path, settings, compression):
    p = tmp_path / "book.mobi"
    p.write_bytes(build_mobi(_MOBI_HTML, compression=compression))
    md, meta = _load_mobi_full(str(p))
    assert md.startswith("# Mobi Title\n\n*Author M*")
    assert "Hello mobi world. Hello mobi world again." in md and "## Two" in md
    assert meta["author"] == "Author M" and meta["title"] == "Synthetic Mobi"
    doc = load_document(str(p), settings)
    assert doc.format == "mobi" and doc.metadata["author"] == "Author M"


def test_mobi_palmdoc_backreferences():
    from star.documents.mobi import _decompress_palmdoc

    # "abcabc": literals then a 3-byte copy from distance 3 (token = dist<<3 | len-3).
    token = 0x8000 | (3 << 3) | 0
    assert _decompress_palmdoc(b"abc" + token.to_bytes(2, "big")) == b"abcabc"
    assert _decompress_palmdoc(b"\xc1") == b" A"  # 0xC0–0xFF: space + char


def test_mobi_drm_reported(tmp_path):
    data = bytearray(build_mobi(_MOBI_HTML))
    # encryption type lives at record-0 offset 12 (after the 78-byte PDB header + record list)
    rec0 = struct.unpack(">I", data[78:82])[0]
    struct.pack_into(">H", data, rec0 + 12, 2)
    p = tmp_path / "drm.azw"
    p.write_bytes(bytes(data))
    md, _ = _load_mobi_full(str(p))
    assert "DRM" in md


_CHM_FILES = {
    "/index.html": b"<html><head><title>Welcome</title></head><body><h1>Welcome</h1><p>Hello CHM world.</p></body></html>",
    "/page2.html": b"<html><body><h2>Second</h2><ul><li>one</li><li>two</li></ul></body></html>",
    "/toc.hhc": b'<html><body><ul><li><object type="text/sitemap"><param name="Name" value="Welcome"><param name="Local" value="index.html"></object><li><object type="text/sitemap"><param name="Name" value="Second"><param name="Local" value="page2.html"></object></ul></body></html>',
    "/#SYSTEM": (b"\x03\x00\x00\x00" + struct.pack("<HH", 3, 8) + b"MyHelp\x00\x00"
                 + struct.pack("<HH", 0, 10) + b"toc.hhc\x00\x00\x00" + struct.pack("<HH", 2, 11) + b"index.html\x00"),
}


@pytest.mark.parametrize("compressed", [False, True])
def test_chm_native(tmp_path, settings, compressed):
    data = build_chm(_CHM_FILES, compressed=compressed)
    p = tmp_path / "help.chm"
    p.write_bytes(data)
    chm = ChmFile(data)
    assert chm.has_compression() is compressed
    assert chm.files() == ["/index.html", "/page2.html", "/toc.hhc"]
    assert chm.read("/index.html") == _CHM_FILES["/index.html"]
    assert chm.read("/PAGE2.HTML") == _CHM_FILES["/page2.html"]  # case-insensitive paths
    md, chapters, meta = _load_chm_full(str(p))
    assert md.startswith("# MyHelp\n\n## Contents\n\n- Welcome\n- Second")
    assert md.count("# Welcome") == 1 and "Hello CHM world." in md
    assert md.index("Hello CHM world.") < md.index("* one")  # TOC order
    assert chapters == [("Welcome", "/index.html"), ("Second", "/page2.html")]
    doc = load_document(str(p), settings)
    assert doc.format == "chm" and doc.title == "MyHelp" and [c[0] for c in doc.chapters] == ["Welcome", "Second"]


def test_chm_rejects_garbage(tmp_path):
    p = tmp_path / "bad.chm"
    p.write_bytes(b"ITSFxxxx" + b"\x00" * 200)
    md, _, _ = _load_chm_full(str(p))
    assert md.startswith("# bad") and "**" in md


def test_lzx_decode_table_rejects_oversubscribed_lengths():
    from star.documents.chm import ChmError, _make_decode_table

    with pytest.raises(ChmError):
        _make_decode_table(3, 4, [1, 1, 1], [0] * 64)
    table = [0] * ((1 << 7) + 8 * 2)
    _make_decode_table(8, 7, [1, 1] + [0] * 70, table)
    assert table[0] == 0 and table[1 << 6] == 1


def test_winhelp_native(tmp_path, settings):
    data = build_hlp("Test Help", [("Intro", ["Intro", "Welcome to the help."]), ("Usage", ["Usage", "Press F1 for help."])])
    p = tmp_path / "test.hlp"
    p.write_bytes(data)
    hlp = HlpFile(data)
    assert hlp.system.title == "Test Help" and sorted(hlp.directory) == ["|FONT", "|SYSTEM", "|TOPIC"]
    topics = hlp.topics()
    assert [t.title for t in topics] == ["Intro", "Usage"]
    md, chapters, meta = _load_winhelp_full(str(p))
    assert md.startswith("# Test Help\n\n## Intro\n\n**Welcome to the help.**")
    assert "## Usage" in md and "Press F1 for help." in md
    assert chapters == [("Intro", "topicnum16"), ("Usage", "topicnum17")]
    doc = load_document(str(p), settings)
    assert doc.format == "winhelp" and doc.title == "Test Help" and doc.chapters[1][2] > doc.chapters[0][2]


def test_winhelp_lz77_and_phrases():
    from star.documents.winhelp import _Phrases, _lz77

    # literals "abc" then copy 3 from distance 3 (stored distance 2, length 3 → 0x2002)
    assert _lz77(bytes([0b1000, ord("a"), ord("b"), ord("c"), 0x02, 0x00]), 64) == b"abcabc"
    assert _lz77(bytes([0b10, ord("x"), 0x00, 0x20]), 64) == b"xxxxxx"  # overlapping run
    buf = struct.pack("<HH", 2, 0x0100) + struct.pack("<HHH", 6, 11, 16) + b"helloworld"
    p = _Phrases.parse_phrases(buf, uncompressed=True)
    assert p.phrase(0) == b"hello" and p.phrase(1) == b"world"
    assert p.expand(b">" + bytes([1, 1]) + bytes([1, 2]) + b"!", 32) == b">hello world!"


def test_winhelp_rejects_foreign_hlp(tmp_path):
    p = tmp_path / "borland.hlp"
    p.write_bytes(b"\x4c\x4e\x02\x00" + b"\x00" * 64)
    md, _, _ = _load_winhelp_full(str(p))
    assert "Not a WinHelp file" in md


# ═══════════════════════════════════════════════════════════════════════════
# DAISY
# ═══════════════════════════════════════════════════════════════════════════


def test_daisy_202_ncc(tmp_path, settings):
    d = tmp_path / "d2"
    d.mkdir()
    (d / "ncc.html").write_text('<html><head><meta name="dc:title" content="Talking Book"/><meta name="dc:creator" content="Reader R"/></head><body><h1 id="a"><a href="s1.smil#t1">Chapter 1</a></h1><h2 id="b"><a href="s2.smil#t2">Chapter 2</a></h2></body></html>')
    (d / "s1.smil").write_text('<smil><body><seq><par id="t1"><text src="content.html#p1"/><audio src="a.mp3"/></par></seq></body></smil>')
    (d / "s2.smil").write_text('<smil><body><seq><par id="t2"><text src="content.html#p2"/></par></seq></body></smil>')
    (d / "content.html").write_text('<html><body><h1 id="p1">Chapter 1</h1><p>First chapter text.</p><h1 id="p2">Chapter 2</h1><p>Second chapter text.</p></body></html>')
    md, chapters, meta = _load_daisy_full(str(d / "ncc.html"))
    assert md.startswith("# Talking Book\n\n*Reader R*")
    assert "First chapter text." in md and "Second chapter text." in md
    assert chapters == [("Chapter 1", "content.html"), ("Chapter 2", "content.html")]
    doc = load_document(str(d / "ncc.html"), settings)
    assert doc.format == "daisy" and doc.title == "Talking Book"
    assert doc.chapters[1][2] > doc.chapters[0][2]


_OPF = """<package xmlns="http://openebook.org/namespaces/oeb-package/1.0/"><metadata><dc-metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:Title>Zipped DAISY</dc:Title><dc:Creator>Z Author</dc:Creator></dc-metadata></metadata><manifest><item id="txt" href="book.xml" media-type="application/x-dtbook+xml"/><item id="ncx" href="nav.ncx" media-type="application/x-dtbncx+xml"/></manifest><spine><itemref idref="txt"/></spine></package>"""
_DTBOOK = """<dtbook xmlns="http://www.daisy.org/z3986/2005/dtbook/"><book><bodymatter><level1><h1>Intro</h1><p>Body text.</p></level1><level1><h1>Next</h1><p>More.</p></level1></bodymatter></book></dtbook>"""
_NCX = """<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/"><navMap><navPoint><navLabel><text>Intro</text></navLabel><content src="s.smil#x"/></navPoint><navPoint><navLabel><text>Next</text></navLabel><content src="s.smil#y"/></navPoint></navMap></ncx>"""


def test_daisy3_zip_and_loose_opf(tmp_path, settings):
    z = tmp_path / "d3.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("book/book.opf", _OPF)
        zf.writestr("book/book.xml", _DTBOOK)
        zf.writestr("book/nav.ncx", _NCX)
    assert _sniff_zip(str(z)) == "daisy"
    doc = load_document(str(z), settings)
    assert doc.format == "daisy" and doc.title == "Zipped DAISY"
    assert "*Z Author*" in doc.markdown and "Body text." in doc.markdown and "More." in doc.markdown
    assert [c[0] for c in doc.chapters] == ["Intro", "Next"]
    d = tmp_path / "loose"
    d.mkdir()
    (d / "book.opf").write_text(_OPF)
    (d / "book.xml").write_text(_DTBOOK)
    (d / "nav.ncx").write_text(_NCX)
    doc = load_document(str(d / "book.opf"), settings)
    assert doc.format == "daisy" and "Body text." in doc.markdown
    # An NCX beside its package opens the package.
    doc = load_document(str(d / "nav.ncx"), settings)
    assert "Body text." in doc.markdown and doc.chapters


def test_daisy_zip_audio_only_lists_tracks(tmp_path, settings):
    z = tmp_path / "audio.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("ncc.html", '<html><body><h1><a href="a.smil#x">Only Heading</a></h1></body></html>')
        zf.writestr("a.smil", '<smil><body><seq><par><audio src="a.mp3"/></par></seq></body></smil>')
        zf.writestr("a.mp3", b"\x00" * 10)
    doc = load_document(str(z), settings)
    assert doc.format == "daisy" and "Only Heading" in doc.markdown and "Transcribe" in doc.markdown


# ═══════════════════════════════════════════════════════════════════════════
# Comics & audiobooks
# ═══════════════════════════════════════════════════════════════════════════

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 30


def test_comic_cbz_pages_in_natural_order(tmp_path, settings):
    p = tmp_path / "comic.cbz"
    with zipfile.ZipFile(p, "w") as zf:
        for n in ["p10.png", "p2.png", "p1.png", "ComicInfo.xml", "__MACOSX/._p1.png"]:
            zf.writestr(n, _PNG if n.endswith("png") else "<x/>")
    md = _load_comic(str(p), ocr=False)
    assert "*3 pages*" in md
    assert md.index("(p1.png)") < md.index("(p2.png)") < md.index("(p10.png)")
    assert "## Page 3" in md and "OCR" in md
    doc = load_document(str(p), settings)
    assert doc.format == "comic"


def test_comic_zip_of_images_sniffed(tmp_path, settings):
    p = tmp_path / "pages.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("a/p2.jpg", _PNG)
        zf.writestr("a/p1.jpg", _PNG)
    assert _sniff_zip(str(p)) == "comic"
    assert load_document(str(p), settings).format == "comic"


def test_comic_cbr_needs_rarfile_or_is_zip(tmp_path):
    p = tmp_path / "renamed.cbr"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("p1.png", _PNG)
    assert "*1 pages*" in _load_comic(str(p), ocr=False)
    real_rar = tmp_path / "real.cbr"
    real_rar.write_bytes(b"Rar!\x1a\x07\x00" + b"\x00" * 64)
    md = _load_comic(str(real_rar), ocr=False)
    assert "rarfile" in md or "Page" in md  # guidance when rarfile is absent, pages when present


def test_mp3_id3_chapters(tmp_path, settings):
    p = tmp_path / "book.mp3"
    p.write_bytes(build_mp3())
    md, chapters, meta = _load_audiobook_full(str(p))
    assert md.startswith("# My Audiobook\n\n*Narrator N*")
    assert "| **Album** | Album |" in md
    assert "### 1. Intro" in md and "### 2. Middle" in md and "00:01:00" in md
    assert chapters == [("1. Intro", "t=0"), ("2. Middle", "t=60000")]
    assert meta["title"] == "My Audiobook"
    doc = load_document(str(p), settings)
    assert doc.format == "audiobook" and doc.title == "My Audiobook" and doc.chapters[1][2] > doc.chapters[0][2]
    assert "Transcribe Audio" in doc.markdown


def test_m4b_atoms_chapters(tmp_path, settings):
    p = tmp_path / "book.m4b"
    p.write_bytes(build_m4b())
    md, chapters, meta = _load_audiobook_full(str(p))
    assert md.startswith("# The M4B\n\n*Author A*")
    assert "| **Duration** | 00:01:30 |" in md
    assert "### 1. Start" in md and "00:00:00 – 00:00:30 (00:00:30)" in md
    assert "### 2. End" in md and "00:00:30 – 00:01:30" in md
    assert chapters == [("1. Start", "t=0"), ("2. End", "t=30000")]
    assert load_document(str(p), settings).format == "audiobook"


def test_audiobook_without_tags_still_opens(tmp_path):
    p = tmp_path / "bare.mp3"
    p.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 2000)
    md, chapters, meta = _load_audiobook_full(str(p))
    assert md.startswith("# bare") and "### 1. bare" in md and chapters == []
