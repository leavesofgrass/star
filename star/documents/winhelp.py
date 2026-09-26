"""WinHelp (``.hlp``) → Markdown on the standard library alone.

A WinHelp file is an archive with its own directory (a B+ tree of internal
file names such as ``|SYSTEM``, ``|TOPIC``, ``|FONT`` and ``|Phrases``).  Topic
text lives in ``|TOPIC`` as a linked list of records spread across fixed-size
blocks that are LZ77 compressed and then compressed *again* against a table of
common phrases; the paragraph structure is a binary command stream, not RTF.
This module walks all of that — WinHelp 3.0 (``HC30``), 3.1 (``HC31``) and
Windows 95 (``HCW 4.00``), both phrase-compression schemes — and turns every
topic into a section with its title as the heading, bold/italic runs, tabs,
line breaks, tables and picture placeholders.  It is a port of Quin
Gillespie's ``libhlp`` (MIT), the reader Paperback uses.

Text is decoded as Windows-1252, the code page of nearly every help file in
the wild.  Hotspot underlines are not reported as emphasis (they are how a
link is drawn), and links are kept as plain text.
"""
import struct

from .._runtime import *  # noqa: F401,F403


class HlpError(ValueError):
    pass


_MAGIC = 0x00035F3F
_TL_DISPLAY30 = 0x01
_TL_TOPICHDR = 0x02
_TL_DISPLAY = 0x20
_TL_TABLE = 0x23
_BLOCK_HEADER_LEN = 12
_LINK_LEN = 21
_TOPIC_HEADER_LEN = 28
_TOPIC_HEADER_LEN_30 = 12
_OFFSET_PER_BLOCK = 0x8000


def _cp1252(b: bytes) -> str:
    return b.decode("cp1252", errors="replace")


def _cstr(b: bytes) -> str:
    end = b.find(b"\x00")
    return _cp1252(b if end < 0 else b[:end])


class _Reader:
    __slots__ = ("buf", "pos")

    def __init__(self, buf: bytes, pos: int = 0) -> None:
        self.buf = buf
        self.pos = pos

    def remaining(self) -> int:
        return max(0, len(self.buf) - self.pos)

    def is_empty(self) -> bool:
        return self.pos >= len(self.buf)

    def take(self, n: int) -> bytes:
        end = self.pos + n
        if end > len(self.buf) or n < 0:
            raise HlpError("truncated")
        out = self.buf[self.pos:end]
        self.pos = end
        return out

    def skip(self, n: int) -> None:
        self.pos += n

    def u8(self) -> int:
        return self.take(1)[0]

    def u16(self) -> int:
        return struct.unpack("<H", self.take(2))[0]

    def i16(self) -> int:
        return struct.unpack("<h", self.take(2))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.take(4))[0]

    def cstr(self) -> bytes:
        if self.pos >= len(self.buf):
            raise HlpError("truncated")
        end = self.buf.find(b"\x00", self.pos)
        if end < 0:
            out = self.buf[self.pos:]
            self.pos = len(self.buf)
            return out
        out = self.buf[self.pos:end]
        self.pos = end + 1
        return out

    def cushort(self) -> int:
        b = self.u8()
        if b % 2 == 0:
            return b // 2
        return (b // 2) + 128 * self.u8()

    def cshort(self) -> int:
        b = self.u8()
        if b % 2 == 0:
            return b // 2 - 64
        return b // 2 + 128 * self.u8() - 16384

    def clong(self) -> int:
        w = self.u16()
        if w % 2 == 0:
            return w // 2 - 0x4000
        hi = self.u16()
        return (w + 0x10000 * hi) // 2 - 0x40000000


# ── LZ77 ─────────────────────────────────────────────────────────────────────


def _lz77(inp: bytes, max_out: int) -> bytes:
    window = bytearray(0x1000)
    cursor = 0
    out = bytearray()
    pos = 0
    n = len(inp)
    while pos < n and len(out) < max_out:
        flags = inp[pos]
        pos += 1
        for bit in range(8):
            if pos >= n:
                break
            if not flags & (1 << bit):
                byte = inp[pos]
                pos += 1
                window[cursor & 0xFFF] = byte
                cursor += 1
                if len(out) < max_out:
                    out.append(byte)
                continue
            if pos + 2 > n:
                pos = n
                break
            pair = inp[pos] | (inp[pos + 1] << 8)
            pos += 2
            length = ((pair >> 12) & 0xF) + 3
            back = (cursor - (pair & 0xFFF) - 1)
            for _ in range(length):
                byte = window[back & 0xFFF]
                back += 1
                window[cursor & 0xFFF] = byte
                cursor += 1
                if len(out) < max_out:
                    out.append(byte)
    return bytes(out)


# ── B+ tree ──────────────────────────────────────────────────────────────────


def _btree_entries(buf: bytes, parse: "Callable[[_Reader], Any]") -> list:
    r = _Reader(buf)
    if r.u16() != 0x293B:
        raise HlpError("bad B+ tree")
    r.skip(2)
    page_size = r.u16()
    r.skip(16 + 2 + 2)
    root_page = r.i16()
    r.skip(2)
    total_pages = r.u16()
    levels = r.u16()
    _total_entries = r.u32()
    if page_size < 8 or levels == 0:
        raise HlpError("bad B+ tree")
    header_len = 38

    def page(n: int) -> bytes:
        if n < 0 or n >= total_pages:
            raise HlpError("bad B+ tree page")
        start = header_len + n * page_size
        return buf[start:start + page_size]

    p = root_page
    for _ in range(1, levels):
        p = struct.unpack("<h", page(p)[4:6])[0]
    out: list = []
    for _ in range(total_pages + 1):
        if p < 0:
            break
        pr = _Reader(page(p))
        pr.skip(2)
        count = pr.i16()
        pr.skip(2)
        nxt = pr.i16()
        for _ in range(max(0, count)):
            out.append(parse(pr))
        p = nxt
    return out


# ── internal files ───────────────────────────────────────────────────────────


def _internal_file(data: bytes, offset: int) -> bytes:
    if offset + 9 > len(data):
        raise HlpError(f"bad internal file header at {offset}")
    used = struct.unpack("<I", data[offset + 4:offset + 8])[0]
    start = offset + 9
    if start + used > len(data):
        raise HlpError(f"bad internal file header at {offset}")
    return data[start:start + used]


class _System:
    def __init__(self, buf: bytes) -> None:
        r = _Reader(buf)
        try:
            magic = r.u16()
        except HlpError:
            raise HlpError("truncated |SYSTEM")
        if magic != 0x036C:
            raise HlpError("bad |SYSTEM magic")
        self.version = r.u16()
        r.skip(2 + 4)
        flags = r.u16()
        self.before31 = self.version < 16
        self.compressed = (not self.before31) and flags in (4, 8)
        self.block_size = 2048 if (self.before31 or flags == 8) else 4096
        self.decompress_size = 2048 if self.before31 else 0x4000
        self.title = ""
        self.copyright = ""
        self.charset: Optional[int] = None
        if self.before31:
            try:
                self.title = _cp1252(r.cstr())
            except HlpError:
                self.title = ""
            return
        while not r.is_empty():
            try:
                kind = r.u16()
                size = r.u16()
                data = r.take(size)
            except HlpError:
                break
            if kind == 1:
                self.title = _cstr(data)
            elif kind == 2:
                self.copyright = _cstr(data)
            elif kind == 11 and len(data) >= 2:
                self.charset = struct.unpack("<H", data[:2])[0]


# ── fonts ────────────────────────────────────────────────────────────────────


class _Fonts:
    def __init__(self, buf: Optional[bytes]) -> None:
        self.formats: List[Tuple[bool, bool, bool]] = []   # (bold, italic, underline)
        if not buf or len(buf) < 8:
            return
        face_count, font_count, faces_off, desc_off = struct.unpack("<HHHH", buf[:8])
        if desc_off < faces_off:
            return
        if faces_off >= 16:
            layout, length = "mvb", 42
        elif faces_off >= 12:
            layout, length = "new", 42
        else:
            layout, length = "old", 11
        for i in range(font_count):
            start = desc_off + i * length
            d = buf[start:start + length]
            if len(d) < length:
                break
            if layout == "old":
                a = d[0]
                self.formats.append((bool(a & 0x01), bool(a & 0x02), bool(a & (0x04 | 0x10))))
            else:
                w, f = (30, 34) if layout == "new" else (28, 32)
                weight = struct.unpack("<h", d[w:w + 2])[0]
                self.formats.append((weight > 500, d[f] != 0, d[f + 1] != 0 or d[f + 3] != 0))

    def format(self, index: int) -> Tuple[bool, bool, bool]:
        if 0 <= index < len(self.formats):
            return self.formats[index]
        return (False, False, False)


# ── phrases ──────────────────────────────────────────────────────────────────


class _Phrases:
    def __init__(self) -> None:
        self.text = b""
        self.offsets: List[int] = []
        self.hall = False

    def phrase(self, n: int) -> bytes:
        if 0 <= n < len(self.offsets) - 1:
            return self.text[self.offsets[n]:self.offsets[n + 1]]
        return b""

    @classmethod
    def parse_phrases(cls, buf: bytes, uncompressed: bool) -> "_Phrases":
        p = cls()
        r = _Reader(buf)
        first = r.u16()
        mvb = first == 0x0800
        count = r.u16() if mvb else first
        if r.u16() != 0x0100:
            raise HlpError("unknown |Phrases layout")
        if count == 0:
            return p
        decompressed = 0 if uncompressed else r.u32()
        if mvb:
            r.skip(30)
        base = (count + 1) * 2
        offsets = []
        for _ in range(count + 1):
            offsets.append(max(0, r.u16() - base))
        rest = r.take(r.remaining())
        p.text = rest if uncompressed else _lz77(rest, decompressed)
        p.offsets = offsets
        return p

    @classmethod
    def parse_hall(cls, index: bytes, image: bytes) -> "_Phrases":
        p = cls()
        p.hall = True
        r = _Reader(index)
        r.skip(4)
        entries = r.u32()
        r.skip(4)
        image_size = r.u32()
        image_comp = r.u32()
        r.skip(4)
        bits = r.u16() & 0xF
        p.text = image if image_size == image_comp else _lz77(image, image_size)
        entries = min(entries, max(1, image_size))
        # bit reader over little-endian u32 words
        pos = 28
        word = 0
        mask = 0

        def bit() -> bool:
            nonlocal pos, word, mask
            mask <<= 1
            if mask == 0 or mask > 0x80000000:
                chunk = index[pos:pos + 4]
                word = struct.unpack("<I", chunk)[0] if len(chunk) == 4 else 0
                pos += 4
                mask = 1
            return bool(word & mask)

        offsets = [0]
        offset = 0
        for _ in range(entries):
            n = 1
            guard = 0
            while bit():
                n += 1 << bits
                guard += 1
                if guard > 100000:
                    break
            if bit():
                n += 1
            for shift in range(1, min(bits, 5)):
                if bit():
                    n += 1 << shift
            offset += n
            offsets.append(offset)
        p.offsets = offsets
        return p

    def expand(self, inp: bytes, expected: int) -> bytes:
        out = bytearray()
        if not self.offsets:
            return bytes(inp[:expected]) if expected else bytes(inp)
        if self.hall:
            i = 0
            n = len(inp)
            while i < n:
                ch = inp[i]
                i += 1
                if ch & 1 == 0:
                    out += self.phrase(ch // 2)
                elif ch & 3 == 1:
                    if i >= n:
                        break
                    nxt = inp[i]
                    i += 1
                    out += self.phrase(128 + (ch // 4) * 256 + nxt)
                elif ch & 7 == 3:
                    take = min(ch // 8 + 1, n - i)
                    out += inp[i:i + take]
                    i += take
                elif ch & 0xF == 7:
                    out += b" " * (ch // 16 + 1)
                else:
                    out += b"\x00" * (ch // 16 + 1)
            return bytes(out)
        i = 0
        n = len(inp)
        while i < n:
            ch = inp[i]
            i += 1
            if not 1 <= ch < 16:
                out.append(ch)
                continue
            if i >= n:
                break
            nxt = inp[i]
            i += 1
            code = 256 * (ch - 1) + nxt
            out += self.phrase(code // 2)
            if code % 2 == 1:
                out.append(0x20)
        return bytes(out)


# ── topic blocks ─────────────────────────────────────────────────────────────


class _Blocks:
    def __init__(self, raw: bytes, block_size: int, decompress_size: int, compressed: bool) -> None:
        self.stride = decompress_size
        step = max(block_size, _BLOCK_HEADER_LEN + 1)
        self.payloads: List[bytes] = []
        for i in range(0, len(raw), step):
            block = raw[i:i + step]
            body = block[_BLOCK_HEADER_LEN:]
            self.payloads.append(_lz77(body, decompress_size) if compressed else body)

    def read(self, pos: int, length: int) -> Optional[Tuple[bytes, int]]:
        out = bytearray()
        left = length
        while True:
            rel = pos - _BLOCK_HEADER_LEN
            if rel < 0 or self.stride == 0:
                return None
            index = rel // self.stride
            offset = rel % self.stride
            if index >= len(self.payloads):
                return None
            payload = self.payloads[index]
            available = max(0, len(payload) - offset)
            if available >= left:
                out += payload[offset:offset + left]
                return bytes(out), pos + left
            out += payload[offset:]
            left -= available
            pos = (index + 1) * self.stride + _BLOCK_HEADER_LEN


class _Paragraph:
    __slots__ = ("runs",)

    def __init__(self) -> None:
        self.runs: List[Tuple[str, Any]] = []   # ("text", (text, bold, italic)) | ("tab",) | ("br",) | ("img",)

    def is_empty(self) -> bool:
        return not self.runs

    def markdown(self) -> str:
        parts: List[str] = []
        for run in self.runs:
            kind = run[0]
            if kind == "text":
                text, bold, italic = run[1]
                core = text.strip()
                if core and (bold or italic):
                    lead = text[: len(text) - len(text.lstrip())]
                    trail = text[len(text.rstrip()):]
                    mark = "***" if bold and italic else ("**" if bold else "*")
                    parts.append(f"{lead}{mark}{core}{mark}{trail}")
                else:
                    parts.append(text)
            elif kind == "tab":
                parts.append("\t")
            elif kind == "br":
                parts.append("  \n")
            elif kind == "img":
                parts.append("![Image]()")
        text = "".join(parts)
        text = re.sub(r"[ \t]+", " ", text)
        return "\n".join(ln.strip() for ln in text.split("\n")).strip()


class _Collector:
    def __init__(self, fonts: _Fonts) -> None:
        self.fonts = fonts
        self.done: List[_Paragraph] = []
        self.current = _Paragraph()
        self.in_link = False
        self.fmt = (False, False, False)

    def push_text(self, b: bytes) -> None:
        if not b:
            return
        bold, italic, _u = self.fmt
        self.current.runs.append(("text", (_cp1252(b), bold, italic)))

    def push(self, kind: str) -> None:
        self.current.runs.append((kind,))

    def end_paragraph(self) -> None:
        self.in_link = False
        self.done.append(self.current)
        self.current = _Paragraph()

    def take(self) -> List[_Paragraph]:
        if not self.current.is_empty():
            self.done.append(self.current)
            self.current = _Paragraph()
        self.in_link = False
        self.fmt = (False, False, False)
        out, self.done = self.done, []
        return out

    def finish(self) -> List[_Paragraph]:
        if not self.current.is_empty():
            self.done.append(self.current)
        return self.done


def _skip_settings(cmds: _Reader) -> bool:
    try:
        cmds.skip(4)
        bits = cmds.u16()
        if bits & 0x0001:
            cmds.clong()
        for bit in (0x0002, 0x0004, 0x0008, 0x0010, 0x0020, 0x0040):
            if bits & bit:
                cmds.cshort()
        if bits & 0x0100:
            cmds.skip(3)
        if bits & 0x0200:
            count = cmds.cshort()
            for _ in range(max(0, count)):
                stop = cmds.cushort()
                if stop & 0x4000:
                    cmds.cushort()
        return True
    except HlpError:
        return False


def _counted_body(cmds: _Reader) -> Optional[bytes]:
    start = cmds.pos
    try:
        ln = cmds.i16()
        total = ln + 3
        if total < 3:
            return None
        body = cmds.take(total - 3)
    except HlpError:
        return None
    cmds.pos = start - 1 + total
    return body


def _skip_picture(cmds: _Reader, out: _Collector) -> bool:
    try:
        kind = cmds.u8()
        size = max(0, cmds.clong())
        if kind == 0x22:
            cmds.cushort()
        cmds.take(size)
    except HlpError:
        return False
    if kind in (0x03, 0x22):
        out.push("img")
    return True


def _read_commands(cmds: _Reader, strings: _Reader, out: _Collector) -> bool:
    while True:
        try:
            out.push_text(strings.cstr())
            cmd = cmds.u8()
        except HlpError:
            return False
        try:
            if cmd == 0xFF:
                return True
            if cmd == 0x20:
                cmds.skip(4)
            elif cmd == 0x21:
                cmds.skip(2)
            elif cmd == 0x80:
                out.fmt = out.fonts.format(cmds.u16())
            elif cmd == 0x81:
                out.push("br")
            elif cmd == 0x82:
                out.end_paragraph()
            elif cmd == 0x83:
                out.push("tab")
            elif 0x86 <= cmd <= 0x88:
                if not _skip_picture(cmds, out):
                    return False
            elif cmd == 0x89:
                out.in_link = False
            elif cmd in (0xC8, 0xCC):
                if _counted_body(cmds) is None:
                    return False
                out.in_link = True
            elif cmd in (0xE0, 0xE1):
                cmds.u32()
                out.in_link = True
            elif cmd in (0xE2, 0xE3, 0xE6, 0xE7):
                cmds.u32()
                out.in_link = True
            elif cmd in (0xEA, 0xEB, 0xEE, 0xEF):
                if _counted_body(cmds) is None:
                    return False
                out.in_link = True
        except HlpError:
            return False


def _parse_record(record_type: int, data1: bytes, data2: bytes, fonts: _Fonts) -> Tuple[List[Any], int]:
    """``(blocks, topic_length)`` where a block is ``("p", _Paragraph)`` or ``("table", rows)``."""
    cmds = _Reader(data1)
    strings = _Reader(data2)
    out = _Collector(fonts)
    try:
        cmds.clong()
        topic_length = cmds.cushort() if record_type in (_TL_DISPLAY, _TL_TABLE) else 0
    except HlpError:
        return [], 0
    if record_type != _TL_TABLE:
        if cmds.pos < len(data1) and _skip_settings(cmds):
            _read_commands(cmds, strings, out)
        return [("p", p) for p in out.finish()], topic_length
    rows: List[List[List[_Paragraph]]] = []
    row: List[List[_Paragraph]] = []
    last_col: Optional[int] = None
    try:
        columns = cmds.u8()
        table_type = cmds.u8()
        if table_type in (0, 2):
            cmds.i16()
        cmds.skip(4 * columns)
    except HlpError:
        return [], topic_length
    while True:
        if cmds.pos + 2 > len(data1):
            break
        column = struct.unpack("<h", data1[cmds.pos:cmds.pos + 2])[0]
        if column == -1:
            break
        cmds.skip(5)
        if cmds.pos >= len(data1) or not _skip_settings(cmds):
            break
        ok = _read_commands(cmds, strings, out)
        cell = out.take()
        if last_col is not None and column <= last_col:
            if any(p.markdown() for c in row for p in c):
                rows.append(row)
            row = []
        last_col = column
        row.append(cell)
        if not ok:
            break
    if row and any(p.markdown() for c in row for p in c):
        rows.append(row)
    return ([("table", rows)] if rows else []), topic_length


class _Topic:
    def __init__(self, number: int, offset: int, title: str) -> None:
        self.number = number
        self.offset = offset
        self.title = title
        self.blocks: List[Any] = []


def _walk(blocks: _Blocks, phrases: _Phrases, fonts: _Fonts, before31: bool) -> List[_Topic]:
    header_len = _TOPIC_HEADER_LEN_30 if before31 else _TOPIC_HEADER_LEN
    topics: List[_Topic] = []
    current: Optional[_Topic] = None
    pos = _BLOCK_HEADER_LEN
    offset = 0
    number = 16
    for _ in range(1 << 22):
        got = blocks.read(pos, _LINK_LEN)
        if got is None:
            break
        header, after_header = got
        try:
            block_size, data_len2, _prev, nxt, data_len1, record_type = struct.unpack("<IIIIIB", header)
        except struct.error:
            break
        if nxt == 0 or nxt == 0xFFFFFFFF:
            break
        nxt = pos + nxt if before31 else nxt
        if nxt <= pos:
            break
        len1 = max(0, data_len1 - _LINK_LEN)
        r1 = blocks.read(after_header, len1) if len1 else (b"", after_header)
        if r1 is None:
            break
        data1, after_data1 = r1
        stored2 = max(0, block_size - data_len1)
        r2 = blocks.read(after_data1, stored2) if stored2 else (b"", after_data1)
        if r2 is None:
            break
        raw2 = r2[0]
        data2 = phrases.expand(raw2, data_len2) if data_len2 > stored2 else raw2[:data_len2]
        if record_type == _TL_TOPICHDR and len(data1) >= header_len:
            if current is not None:
                topics.append(current)
            current = _Topic(number, offset, _cstr(data2))
            number += 1
        elif record_type in (_TL_DISPLAY30, _TL_DISPLAY, _TL_TABLE):
            rec_blocks, topic_length = _parse_record(record_type, data1, data2, fonts)
            offset += topic_length
            if current is not None:
                for kind, payload in rec_blocks:
                    if kind == "table" and current.blocks and current.blocks[-1][0] == "table":
                        current.blocks[-1][1].extend(payload)
                    else:
                        current.blocks.append((kind, payload))
        # offset bookkeeping across blocks
        stride = blocks.stride
        if pos >= _BLOCK_HEADER_LEN and nxt >= _BLOCK_HEADER_LEN and stride:
            frm = (pos - _BLOCK_HEADER_LEN) // stride
            to = (nxt - _BLOCK_HEADER_LEN) // stride
            if frm != to:
                offset = to * _OFFSET_PER_BLOCK
        pos = nxt
    if current is not None:
        topics.append(current)
    return topics


# ── file ─────────────────────────────────────────────────────────────────────


class HlpFile:
    def __init__(self, data: bytes) -> None:
        if len(data) < 16:
            raise HlpError("truncated file")
        magic, dir_start, _free, size = struct.unpack("<IIII", data[:16])
        if magic != _MAGIC:
            raise HlpError("Not a WinHelp file (Borland/QuickHelp .hlp files are a different format)")
        if len(data) < size:
            raise HlpError("truncated file")
        self.data = data
        dir_buf = _internal_file(data, dir_start)

        def entry(r: _Reader) -> Tuple[str, int]:
            name = _cp1252(r.cstr())
            return name, r.u32()

        self.directory: Dict[str, int] = dict(_btree_entries(dir_buf, entry))
        if "|SYSTEM" not in self.directory:
            raise HlpError("no |SYSTEM file")
        self.system = _System(_internal_file(data, self.directory["|SYSTEM"]))

    def read_file(self, name: str) -> Optional[bytes]:
        off = self.directory.get(name)
        if off is None:
            return None
        try:
            return _internal_file(self.data, off)
        except HlpError:
            return None

    def phrases(self) -> _Phrases:
        index = self.read_file("|PhrIndex")
        image = self.read_file("|PhrImage")
        if index is not None and image is not None:
            try:
                return _Phrases.parse_hall(index, image)
            except (HlpError, struct.error):
                return _Phrases()
        buf = self.read_file("|Phrases")
        if buf is not None:
            try:
                return _Phrases.parse_phrases(buf, self.system.before31)
            except (HlpError, struct.error):
                return _Phrases()
        return _Phrases()

    def titles(self) -> Dict[int, str]:
        buf = self.read_file("|TTLBTREE")
        if buf is None:
            return {}
        try:
            return dict(_btree_entries(buf, lambda r: (r.u32(), _cp1252(r.cstr()))))
        except (HlpError, struct.error):
            return {}

    def topics(self) -> List[_Topic]:
        raw = self.read_file("|TOPIC")
        if raw is None:
            raise HlpError("no |TOPIC file (no help text)")
        s = self.system
        blocks = _Blocks(raw, s.block_size, s.decompress_size, s.compressed)
        topics = _walk(blocks, self.phrases(), _Fonts(self.read_file("|FONT")), s.before31)
        titles = self.titles()
        for t in topics:
            if not t.title and t.offset in titles:
                t.title = titles[t.offset]
        return topics


def _topic_markdown(topic: _Topic) -> List[str]:
    out: List[str] = []
    title = topic.title.strip()
    heading = title or f"Topic {topic.number}"
    out += [f"## {heading}", ""]
    first_text = True
    for kind, payload in topic.blocks:
        if kind == "p":
            md = payload.markdown()
            if not md:
                continue
            if first_text and title and md.strip("*").strip().lower() == title.lower():
                first_text = False
                continue  # the topic repeats its title as its first line
            first_text = False
            out += [md, ""]
        else:
            rows = payload
            cells_md = [[" ".join(p.markdown() for p in cell).replace("|", "\\|").replace("\n", " ") for cell in row] for row in rows]
            if not cells_md:
                continue
            nc = max(len(r) for r in cells_md)
            out.append("| " + " | ".join((cells_md[0] + [""] * nc)[:nc]) + " |")
            out.append("|" + "|".join([" --- "] * nc) + "|")
            for r in cells_md[1:]:
                out.append("| " + " | ".join((r + [""] * nc)[:nc]) + " |")
            out.append("")
    return out


def _load_winhelp_full(path: str) -> Tuple[str, List[Tuple[str, str]], Dict[str, str]]:
    """``(markdown, chapters, metadata)`` for a WinHelp file."""
    try:
        hlp = HlpFile(Path(path).read_bytes())
        topics = hlp.topics()
    except HlpError as e:
        return f"# {Path(path).stem}\n\n**{e}**\n", [], {}
    except Exception as e:  # noqa: BLE001
        return f"# WinHelp Error\n\n```\n{e}\n```\n", [], {}
    title = hlp.system.title or Path(path).stem
    meta = {"title": title}
    if hlp.system.copyright:
        meta["copyright"] = hlp.system.copyright
    parts: List[str] = [f"# {title}", ""]
    if hlp.system.copyright:
        parts += [f"*{hlp.system.copyright}*", ""]
    if not topics:
        parts += ["*This help file contains no topics.*", ""]
    for t in topics:
        parts += _topic_markdown(t)
        parts += ["---", ""]
    while parts and parts[-1] in ("", "---"):
        parts.pop()
    chapters = [(t.title, f"topicnum{t.number}") for t in topics if t.title.strip()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(parts)) + "\n", chapters, meta


def _load_winhelp(path: str) -> str:
    return _load_winhelp_full(path)[0]
