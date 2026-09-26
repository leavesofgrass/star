"""OLE2 compound files: legacy binary PowerPoint (``.ppt``) and Word (``.doc``).

A minimal Compound File Binary (CFB) reader — header, FAT/DIFAT, mini-FAT,
directory — is all that is needed to pull the named streams out of the
Office 97–2003 containers, so both formats open on the standard library:

* **PowerPoint 97–2003** — the ``PowerPoint Document`` stream is a tree of
  records; every ``TextCharsAtom`` (UTF-16) and ``TextBytesAtom`` (8-bit)
  holds a text run, and ``SlidePersistAtom``/``Slide`` containers mark the
  slide boundaries.  Slide titles are the ``TextHeaderAtom`` runs typed
  *title*/*center title*.
* **Word 97–2003** — the ``WordDocument`` stream's FIB points at the piece
  table (``CLX``) in the ``0Table``/``1Table`` stream; each piece is either
  8-bit (cp1252, compressed) or UTF-16 text.  Word 6/95 keeps its text
  inline between ``fcMin`` and ``fcMac``.  This is the last native fallback
  after python-docx (OOXML-in-disguise), antiword, LibreOffice and Pandoc.

Encrypted documents are reported, not decrypted.
"""
import struct

from .._runtime import *  # noqa: F401,F403

_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_ENDOFCHAIN = 0xFFFFFFFE
_FREESECT = 0xFFFFFFFF


class OleError(ValueError):
    pass


class OleFile:
    """Read-only CFB container: ``streams()`` lists names, ``read(name)`` returns bytes."""

    def __init__(self, data: bytes) -> None:
        if data[:8] != _OLE_MAGIC:
            raise OleError("Not an OLE2 compound file")
        self.data = data
        (self.sector_shift, self.mini_shift) = struct.unpack("<HH", data[30:34])
        self.sector_size = 1 << self.sector_shift
        self.mini_size = 1 << self.mini_shift
        (num_fat, first_dir, _tx, self.mini_cutoff, first_minifat, num_minifat,
         first_difat, num_difat) = struct.unpack("<IIIIIIII", data[44:76])
        # FAT sector list: 109 entries in the header, then DIFAT chain.
        fat_sectors = list(struct.unpack("<109I", data[76:512]))
        sect = first_difat
        for _ in range(num_difat):
            if sect in (_ENDOFCHAIN, _FREESECT) or sect >= (len(data) // self.sector_size):
                break
            start = (sect + 1) * self.sector_size
            chunk = data[start:start + self.sector_size]
            n = self.sector_size // 4 - 1
            fat_sectors += list(struct.unpack(f"<{n}I", chunk[:n * 4]))
            sect = struct.unpack("<I", chunk[n * 4:n * 4 + 4])[0]
        self.fat: List[int] = []
        per = self.sector_size // 4
        for s in fat_sectors[:num_fat]:
            if s in (_ENDOFCHAIN, _FREESECT):
                continue
            start = (s + 1) * self.sector_size
            chunk = data[start:start + self.sector_size]
            if len(chunk) < self.sector_size:
                chunk = chunk + b"\xff" * (self.sector_size - len(chunk))
            self.fat += list(struct.unpack(f"<{per}I", chunk))
        # Directory.
        dir_bytes = self._chain(first_dir)
        self.entries: List[Dict[str, Any]] = []
        for i in range(0, len(dir_bytes) - 127, 128):
            e = dir_bytes[i:i + 128]
            name_len = struct.unpack("<H", e[64:66])[0]
            name = e[:max(0, min(name_len - 2, 62))].decode("utf-16-le", errors="replace")
            typ = e[66]
            start, size = struct.unpack("<II", e[116:124])
            if typ == 0:
                continue
            self.entries.append({"name": name, "type": typ, "start": start, "size": size})
        # Mini stream (root entry's stream) + mini FAT.
        root = next((e for e in self.entries if e["type"] == 5), None)
        self._mini_stream = self._chain(root["start"], root["size"]) if root else b""
        mini_bytes = self._chain(first_minifat) if num_minifat else b""
        n = len(mini_bytes) // 4
        self.minifat: List[int] = list(struct.unpack(f"<{n}I", mini_bytes[:n * 4])) if n else []

    def _chain(self, start: int, size: Optional[int] = None) -> bytes:
        out = bytearray()
        sect = start
        seen: set = set()
        while sect not in (_ENDOFCHAIN, _FREESECT) and sect not in seen and sect < len(self.fat) + 1:
            seen.add(sect)
            off = (sect + 1) * self.sector_size
            out += self.data[off:off + self.sector_size]
            if sect >= len(self.fat):
                break
            sect = self.fat[sect]
            if size is not None and len(out) >= size:
                break
        return bytes(out[:size]) if size is not None else bytes(out)

    def _mini_chain(self, start: int, size: int) -> bytes:
        out = bytearray()
        sect = start
        seen: set = set()
        while sect not in (_ENDOFCHAIN, _FREESECT) and sect not in seen and sect < len(self.minifat):
            seen.add(sect)
            off = sect * self.mini_size
            out += self._mini_stream[off:off + self.mini_size]
            sect = self.minifat[sect]
            if len(out) >= size:
                break
        return bytes(out[:size])

    def streams(self) -> List[str]:
        return [e["name"] for e in self.entries if e["type"] == 2]

    def read(self, name: str) -> bytes:
        for e in self.entries:
            if e["type"] == 2 and e["name"].lstrip("/").lower() == name.lstrip("/").lower():
                if e["size"] < self.mini_cutoff:
                    return self._mini_chain(e["start"], e["size"])
                return self._chain(e["start"], e["size"])
        raise KeyError(name)


def is_ole(path: str) -> bool:
    try:
        with open(path, "rb") as fh:
            return fh.read(8) == _OLE_MAGIC
    except OSError:
        return False


# ── PowerPoint 97–2003 ───────────────────────────────────────────────────────

_RT_SLIDE = 0x03EE
_RT_TEXT_HEADER = 0x0F9F
_RT_TEXT_CHARS = 0x0FA0
_RT_TEXT_BYTES = 0x0FA8
_RT_CSTRING = 0x0FBA
_RT_NOTES = 0x03F0
_RT_MAIN_MASTER = 0x03F8
_RT_DOCUMENT = 0x03E8
_RT_SLIDE_LIST_WITH_TEXT = 0x0FF0
_RT_SLIDE_PERSIST_ATOM = 0x03F3


def _ppt_records(data: bytes, start: int, end: int):
    """Yield ``(rec_type, rec_instance, is_container, body_start, body_end)``."""
    pos = start
    while pos + 8 <= end:
        ver_inst, rtype, length = struct.unpack("<HHI", data[pos:pos + 8])
        version = ver_inst & 0x0F
        instance = ver_inst >> 4
        body = pos + 8
        body_end = min(body + length, end)
        yield rtype, instance, version == 0xF, body, body_end
        if length == 0 and version != 0xF:
            pos = body
        else:
            pos = body_end
        if body_end <= pos - 1 and length == 0:
            break


def _ppt_text_from_range(data: bytes, start: int, end: int) -> List[Tuple[int, str]]:
    """``(text_type, text)`` runs found (recursively) in a record range.
    text_type is the TextHeaderAtom type (0 title, 6 center title, 1 body …), -1 if unknown."""
    out: List[Tuple[int, str]] = []
    current_type = -1
    for rtype, inst, is_cont, bs, be in _ppt_records(data, start, end):
        if is_cont:
            out += _ppt_text_from_range(data, bs, be)
        elif rtype == _RT_TEXT_HEADER and be - bs >= 4:
            current_type = struct.unpack("<I", data[bs:bs + 4])[0]
        elif rtype == _RT_TEXT_CHARS:
            text = data[bs:be].decode("utf-16-le", errors="replace")
            out.append((current_type, text))
            current_type = -1
        elif rtype == _RT_TEXT_BYTES:
            text = data[bs:be].decode("cp1252", errors="replace")
            out.append((current_type, text))
            current_type = -1
    return out


def _ppt_clean(text: str) -> List[str]:
    text = text.replace("\r", "\n").replace("\x0b", "\n").replace("\x00", "")
    return [ln.strip() for ln in text.split("\n") if ln.strip()]


def _ppt_markdown(stream: bytes, name: str) -> str:
    """Markdown from the ``PowerPoint Document`` stream."""
    slides: List[Tuple[str, List[str], List[str]]] = []   # (title, body lines, notes)
    # Walk the top-level containers: each Slide (0x03EE) container is one slide.
    # Text for slides can also live in the Document's SlideListWithText; handle both.
    doc_slwt: List[List[Tuple[int, str]]] = []
    for rtype, inst, is_cont, bs, be in _ppt_records(stream, 0, len(stream)):
        if rtype == _RT_DOCUMENT and is_cont:
            for r2, i2, c2, b2, e2 in _ppt_records(stream, bs, be):
                if r2 == _RT_SLIDE_LIST_WITH_TEXT and c2 and i2 == 0:
                    # Split by SlidePersistAtom into per-slide text groups.
                    groups: List[List[Tuple[int, str]]] = []
                    cur_type = -1
                    for r3, i3, c3, b3, e3 in _ppt_records(stream, b2, e2):
                        if r3 == _RT_SLIDE_PERSIST_ATOM:
                            groups.append([])
                        elif r3 == _RT_TEXT_HEADER and e3 - b3 >= 4:
                            cur_type = struct.unpack("<I", stream[b3:b3 + 4])[0]
                        elif r3 in (_RT_TEXT_CHARS, _RT_TEXT_BYTES):
                            text = (stream[b3:e3].decode("utf-16-le", errors="replace")
                                    if r3 == _RT_TEXT_CHARS else stream[b3:e3].decode("cp1252", errors="replace"))
                            if groups:
                                groups[-1].append((cur_type, text))
                            cur_type = -1
                    doc_slwt = groups
        elif rtype == _RT_SLIDE and is_cont:
            runs = _ppt_text_from_range(stream, bs, be)
            title = ""
            body: List[str] = []
            for ttype, text in runs:
                lines = _ppt_clean(text)
                if not lines:
                    continue
                if ttype in (0, 6) and not title:
                    title = " ".join(lines)
                else:
                    body += lines
            slides.append((title, body, []))
        elif rtype == _RT_NOTES and is_cont:
            runs = _ppt_text_from_range(stream, bs, be)
            notes = [ln for _t, text in runs for ln in _ppt_clean(text)]
            if notes and slides:
                slides[-1][2].extend(notes)
    # Slides whose text lives only in the SlideListWithText (common in files
    # saved by older PowerPoint versions): merge by position.
    if doc_slwt and (not slides or all(not t and not b for t, b, _n in slides)):
        slides = []
        for group in doc_slwt:
            title = ""
            body = []
            for ttype, text in group:
                lines = _ppt_clean(text)
                if not lines:
                    continue
                if ttype in (0, 6) and not title:
                    title = " ".join(lines)
                else:
                    body += lines
            slides.append((title, body, []))
    if not slides:
        return f"# {name}\n\n*(no slide text found)*\n"
    sections: List[str] = []
    for i, (title, body, notes) in enumerate(slides, start=1):
        heading = f"## Slide {i}: {title}" if title else f"## Slide {i}"
        lines = [heading]
        if body:
            lines += [""] + [f"- {b}" for b in body]
        if notes:
            lines += ["", f"> Note: {' '.join(notes)}"]
        sections.append("\n".join(lines))
    return "\n\n".join(sections) + "\n"


def _load_ppt_native(path: str) -> str:
    """Legacy binary PowerPoint → Markdown (stdlib)."""
    try:
        ole = OleFile(Path(path).read_bytes())
    except OleError:
        return "# PPT Error\n\nNot an OLE2 compound file (not a PowerPoint 97–2003 presentation).\n"
    except Exception as e:  # noqa: BLE001
        return f"# PPT Error\n\n```\n{e}\n```\n"
    try:
        stream = ole.read("PowerPoint Document")
    except KeyError:
        if any(n.lower().startswith("encrypted") for n in ole.streams()):
            return f"# {Path(path).stem}\n\n**This presentation is password-protected; star cannot open encrypted files.**\n"
        return "# PPT Error\n\nNo 'PowerPoint Document' stream in this file.\n"
    try:
        return _ppt_markdown(stream, Path(path).stem)
    except Exception as e:  # noqa: BLE001
        return f"# PPT Error\n\n```\n{e}\n```\n"


# ── Word 97–2003 ─────────────────────────────────────────────────────────────

_FIB_MAGIC = (0xA5EC, 0xA5DC)
_FIB_NFIB_WORD97 = 0x00C1


def _doc_text_word6(word_doc: bytes) -> str:
    fc_min, fc_mac = struct.unpack("<II", word_doc[0x18:0x20])
    if fc_min >= fc_mac or fc_mac > len(word_doc):
        return ""
    return word_doc[fc_min:fc_mac].decode("cp1252", errors="replace")


def _doc_text_piece_table(word_doc: bytes, table: bytes) -> Optional[str]:
    fc_clx, lcb_clx = struct.unpack("<II", word_doc[0x1A2:0x1AA])
    if lcb_clx == 0 or fc_clx + lcb_clx > len(table):
        return None
    clx = table[fc_clx:fc_clx + lcb_clx]
    pos = 0
    while pos < len(clx):
        kind = clx[pos]
        pos += 1
        if kind == 0x01:            # Prc (property data) — skip
            if pos + 2 > len(clx):
                return None
            size = struct.unpack("<H", clx[pos:pos + 2])[0]
            pos += 2 + size
            continue
        if kind != 0x02:
            return None
        if pos + 4 > len(clx):
            return None
        size = struct.unpack("<I", clx[pos:pos + 4])[0]
        pos += 4
        plc = clx[pos:pos + size]
        n = (len(plc) - 4) // 12
        if n <= 0:
            return None
        cps = struct.unpack(f"<{n + 1}I", plc[:(n + 1) * 4])
        parts: List[str] = []
        base = (n + 1) * 4
        for i in range(n):
            pcd = plc[base + i * 8: base + i * 8 + 8]
            fc = struct.unpack("<I", pcd[2:6])[0]
            count = cps[i + 1] - cps[i]
            if fc & 0x40000000:
                start = (fc & 0x3FFFFFFF) // 2
                parts.append(word_doc[start:start + count].decode("cp1252", errors="replace"))
            else:
                parts.append(word_doc[fc:fc + count * 2].decode("utf-16-le", errors="replace"))
        return "".join(parts)
    return None


def _doc_normalize(text: str) -> str:
    text = text.replace("\r", "\n").replace("\x0b", "\n").replace("\x0c", "\n\n---\n\n")
    text = text.replace("\x07", " | ")          # cell / row marks
    text = re.sub(r"[\x00-\x08\x0e-\x1f]", "", text)
    text = re.sub(r"\x13[^\x14\x15]*\x14?", "", text)   # field codes {…}
    text = text.replace("\x15", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    paras = [p.strip() for p in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n\n".join(p for p in paras if p)).strip()


def _load_doc_native(path: str) -> Optional[str]:
    """Legacy binary Word → Markdown; None when the file is not a Word OLE file."""
    try:
        ole = OleFile(Path(path).read_bytes())
    except OleError:
        return None
    except Exception:  # noqa: BLE001
        return None
    try:
        wd = ole.read("WordDocument")
    except KeyError:
        return None
    if len(wd) < 0x1AA:
        return None
    magic = struct.unpack("<H", wd[0:2])[0]
    if magic not in _FIB_MAGIC:
        return None
    nfib = struct.unpack("<H", wd[2:4])[0]
    flags = struct.unpack("<H", wd[0x0A:0x0C])[0]
    if flags & 0x0100:
        return f"# {Path(path).stem}\n\n**This document is password-protected; star cannot open encrypted files.**\n"
    text: Optional[str] = None
    if nfib >= _FIB_NFIB_WORD97:
        table_name = "1Table" if flags & 0x0200 else "0Table"
        try:
            table = ole.read(table_name)
        except KeyError:
            table = b""
        if table:
            text = _doc_text_piece_table(wd, table)
    if not text or not text.strip():
        text = _doc_text_word6(wd)
    md = _doc_normalize(text or "")
    if not md:
        return None
    return f"# {Path(path).stem}\n\n{md}\n"
