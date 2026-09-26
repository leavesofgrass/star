"""Mobipocket / Kindle e-books (``.mobi``, ``.prc``, ``.azw``, ``.azw3``) → Markdown.

A MOBI file is a Palm Database (PDB) whose record 0 carries the PalmDOC and
MOBI headers plus EXTH metadata, followed by the compressed text records, then
images and index records.  This reader handles, on the standard library alone:

* the **PDB** record table and the **MOBI** header (text encoding, record
  counts, trailing-entry flags, full title);
* **EXTH** metadata (author, title, description, publisher, language);
* **PalmDOC** (LZ77) and **HUFF/CDIC** (Huffman + phrase dictionary)
  decompression — the two schemes Kindle books actually use;
* **KF8** (``.azw3`` and hybrid MOBI/KF8 files): the boundary record from
  EXTH 121, and the FDST flow table so only the text flow (not the embedded
  CSS/SVG flows) becomes the document.

The decompressed text is (X)HTML and goes through the same HTML→Markdown
converter as EPUB chapters, so headings, lists, tables and image alt text
survive.  DRM-protected books cannot be read and say so.  The decompressor
follows the algorithm documented by the MobileRead wiki and KindleUnpack.
"""
import struct

from .._runtime import *  # noqa: F401,F403
from .html import _load_html_str


class MobiError(ValueError):
    pass


def _trailing_size(data: bytes) -> int:
    """Size of a trailing entry, encoded backwards as a variable-length int."""
    size = 0
    shift = 0
    pos = len(data) - 1
    while pos >= 0:
        b = data[pos]
        size |= (b & 0x7F) << shift
        shift += 7
        if b & 0x80 or shift >= 28:
            break
        pos -= 1
    return size


def _strip_trailing(data: bytes, flags: int) -> bytes:
    for bit in range(15, 0, -1):
        if flags & (1 << bit):
            n = _trailing_size(data)
            data = data[:max(0, len(data) - n)]
    if flags & 1 and data:
        n = (data[-1] & 0x3) + 1
        data = data[:max(0, len(data) - n)]
    return data


def _decompress_palmdoc(data: bytes) -> bytes:
    out = bytearray()
    pos = 0
    n = len(data)
    while pos < n:
        c = data[pos]
        pos += 1
        if c == 0 or 0x09 <= c <= 0x7F:
            out.append(c)
        elif 0x01 <= c <= 0x08:
            out += data[pos:pos + c]
            pos += c
        elif 0x80 <= c <= 0xBF:
            if pos >= n:
                break
            token = ((c << 8) | data[pos]) & 0x3FFF
            pos += 1
            distance = token >> 3
            length = (token & 0x7) + 3
            if distance == 0 or distance > len(out):
                continue
            start = len(out) - distance
            for j in range(length):
                out.append(out[start + j])
        else:  # 0xC0–0xFF: space + char
            out.append(0x20)
            out.append(c ^ 0x80)
    return bytes(out)


class _HuffCdic:
    """HUFF/CDIC decoder (MOBI compression type 17480)."""

    def __init__(self, huff: bytes, cdics: List[bytes]) -> None:
        if huff[:4] != b"HUFF":
            raise MobiError("Invalid HUFF record")
        off1, off2 = struct.unpack(">LL", huff[8:16])
        self.dict1: List[Tuple[int, int, int]] = []
        for i in range(256):
            v = struct.unpack(">L", huff[off1 + 4 * i:off1 + 4 * i + 4])[0]
            codelen = v & 0x1F
            term = v & 0x80
            maxcode = v >> 8
            if codelen == 0:
                raise MobiError("Invalid HUFF code length")
            maxcode = ((maxcode + 1) << (32 - codelen)) - 1
            self.dict1.append((codelen, term, maxcode))
        dict2 = struct.unpack(">64L", huff[off2:off2 + 256])
        self.mincode = [0] + [b << (32 - i) for i, b in enumerate(dict2[0::2], start=1)]
        self.maxcode = [0] + [((b + 1) << (32 - i)) - 1 for i, b in enumerate(dict2[1::2], start=1)]
        self.dictionary: List[Optional[Tuple[bytes, int]]] = []
        for cdic in cdics:
            if cdic[:4] != b"CDIC":
                raise MobiError("Invalid CDIC record")
            phrases, bits = struct.unpack(">LL", cdic[8:16])
            n = min(1 << bits, phrases - len(self.dictionary))
            for i in range(n):
                off = struct.unpack(">H", cdic[16 + 2 * i:18 + 2 * i])[0]
                blen = struct.unpack(">H", cdic[16 + off:18 + off])[0]
                phrase = cdic[18 + off:18 + off + (blen & 0x7FFF)]
                self.dictionary.append((phrase, blen & 0x8000))
        self._depth = 0

    def unpack(self, data: bytes) -> bytes:
        self._depth += 1
        if self._depth > 512:
            self._depth -= 1
            raise MobiError("HUFF decode recursion too deep (corrupt data?)")
        try:
            bitsleft = len(data) * 8
            data = data + b"\x00" * 8
            pos = 0
            x = struct.unpack(">Q", data[pos:pos + 8])[0]
            n = 32
            out = bytearray()
            while True:
                if n <= 0:
                    pos += 4
                    x = struct.unpack(">Q", data[pos:pos + 8])[0]
                    n += 32
                code = (x >> n) & 0xFFFFFFFF
                codelen, term, maxcode = self.dict1[code >> 24]
                if not term:
                    while codelen < 33 and code < self.mincode[codelen]:
                        codelen += 1
                    if codelen > 32:
                        break
                    maxcode = self.maxcode[codelen]
                n -= codelen
                bitsleft -= codelen
                if bitsleft < 0:
                    break
                r = (maxcode - code) >> (32 - codelen)
                if r >= len(self.dictionary):
                    break
                entry = self.dictionary[r]
                if entry is None:
                    break  # phrase currently being expanded → corrupt data
                phrase, flag = entry
                if not flag:
                    self.dictionary[r] = None
                    phrase = self.unpack(phrase)
                    self.dictionary[r] = (phrase, 1)
                out += phrase
            return bytes(out)
        finally:
            self._depth -= 1


class _Mobi:
    def __init__(self, data: bytes) -> None:
        self.data = data
        if len(data) < 78 or data[60:68] not in (b"BOOKMOBI", b"TEXtREAd"):
            raise MobiError("Not a Mobipocket/Kindle file (no BOOKMOBI signature)")
        self.num_records = struct.unpack(">H", data[76:78])[0]
        self.offsets: List[int] = []
        for i in range(self.num_records):
            off = struct.unpack(">L", data[78 + 8 * i:82 + 8 * i])[0]
            self.offsets.append(off)
        self.offsets.append(len(data))
        self.title = data[:32].split(b"\x00", 1)[0].decode("cp1252", errors="replace")
        self.meta: Dict[str, str] = {}
        self._parse_header(0)

    def record(self, i: int) -> bytes:
        if i < 0 or i >= self.num_records:
            return b""
        return self.data[self.offsets[i]:self.offsets[i + 1]]

    def _parse_header(self, base_record: int) -> None:
        r0 = self.record(base_record)
        self.base = base_record
        self.compression, _u, self.text_length, self.text_records, self.record_size, self.encryption = (
            struct.unpack(">HHLHHH", r0[:14])
        )
        self.encoding = "cp1252"
        self.extra_flags = 0
        self.huff_offset = self.huff_count = 0
        self.fdst_record = 0
        self.kf8 = False
        self.version = 0
        self.exth: Dict[int, List[bytes]] = {}
        if r0[16:20] != b"MOBI":
            return
        hlen = struct.unpack(">L", r0[20:24])[0]
        codepage = struct.unpack(">L", r0[28:32])[0]
        self.encoding = "utf-8" if codepage == 65001 else ("cp1252" if codepage == 1252 else "utf-8")
        self.version = struct.unpack(">L", r0[36:40])[0]
        name_off, name_len = struct.unpack(">LL", r0[0x54:0x5C])
        if name_off and name_len and name_off + name_len <= len(r0):
            self.title = r0[name_off:name_off + name_len].decode(self.encoding, errors="replace").strip("\x00")
        self.huff_offset, self.huff_count = struct.unpack(">LL", r0[0x70:0x78])
        exth_flags = struct.unpack(">L", r0[0x80:0x84])[0]
        if hlen >= 0xE4 and self.version >= 5:
            self.extra_flags = struct.unpack(">H", r0[0xF2:0xF4])[0]
        if self.version >= 8:
            self.kf8 = True
            self.fdst_record = struct.unpack(">L", r0[0xC0:0xC4])[0]
        if exth_flags & 0x40:
            self._parse_exth(r0, 16 + hlen)

    def _parse_exth(self, r0: bytes, start: int) -> None:
        if r0[start:start + 4] != b"EXTH":
            return
        count = struct.unpack(">L", r0[start + 8:start + 12])[0]
        pos = start + 12
        for _ in range(count):
            if pos + 8 > len(r0):
                break
            rtype, rlen = struct.unpack(">LL", r0[pos:pos + 8])
            if rlen < 8:
                break
            self.exth.setdefault(rtype, []).append(r0[pos + 8:pos + rlen])
            pos += rlen

        def text(t: int) -> str:
            vals = self.exth.get(t)
            return vals[0].decode(self.encoding, errors="replace").strip() if vals else ""

        for key, t in (("author", 100), ("publisher", 101), ("description", 103),
                       ("subject", 105), ("date", 106), ("language", 524), ("isbn", 104)):
            v = text(t)
            if v:
                self.meta[key] = v
        t503 = text(503)
        if t503:
            self.title = t503
        self.meta["title"] = self.title

    def switch_to_kf8(self) -> bool:
        """For a hybrid MOBI/KF8 file, re-read the header at the KF8 boundary."""
        vals = self.exth.get(121)
        if not vals or len(vals[0]) < 4:
            return False
        boundary = struct.unpack(">L", vals[0][:4])[0]
        if boundary <= 0 or boundary >= self.num_records:
            return False
        rec = self.record(boundary)
        if rec[16:20] != b"MOBI":
            return False
        old_meta = dict(self.meta)
        self._parse_header(boundary)
        for k, v in old_meta.items():
            self.meta.setdefault(k, v)
        return True

    def text(self) -> bytes:
        if self.encryption not in (0,):
            raise MobiError("This book is DRM-protected (encrypted); star cannot open it.")
        decoder: Optional[_HuffCdic] = None
        if self.compression == 17480:
            huff = self.record(self.base + self.huff_offset)
            cdics = [self.record(self.base + self.huff_offset + i) for i in range(1, self.huff_count)]
            decoder = _HuffCdic(huff, cdics)
        elif self.compression not in (1, 2):
            raise MobiError(f"Unknown MOBI compression type {self.compression}")
        out = bytearray()
        for i in range(1, self.text_records + 1):
            rec = _strip_trailing(self.record(self.base + i), self.extra_flags)
            if not rec:
                continue
            if self.compression == 2:
                out += _decompress_palmdoc(rec)
            elif decoder is not None:
                out += decoder.unpack(rec)
            else:
                out += rec
        raw = bytes(out)
        if self.kf8 and self.fdst_record and self.fdst_record != 0xFFFFFFFF:
            fd = self.record(self.base + self.fdst_record)
            if fd[:4] == b"FDST":
                nsec = struct.unpack(">L", fd[8:12])[0]
                if nsec >= 1:
                    start, end = struct.unpack(">LL", fd[12:20])
                    if 0 <= start < end <= len(raw):
                        raw = raw[start:end]
        return raw


def _mobi_html_to_md(raw: bytes, encoding: str) -> str:
    html = raw.decode(encoding, errors="replace")
    html = re.sub(r"<mbp:pagebreak\s*/?>", "<hr/>", html, flags=re.I)
    html = re.sub(r"</?mbp:[a-z]+[^>]*>", "", html, flags=re.I)
    html = re.sub(r"<guide>.*?</guide>", "", html, flags=re.I | re.S)
    # Kindle keeps images by record index; keep them as labelled placeholders.
    html = re.sub(r'<img([^>]*?)recindex="?(\d+)"?', r'<img\1 src="image-\2"', html, flags=re.I)
    return _load_html_str(html)


def _load_mobi_full(path: str) -> Tuple[str, Dict[str, str]]:
    try:
        data = Path(path).read_bytes()
        book = _Mobi(data)
        book.switch_to_kf8()
        raw = book.text()
    except MobiError as e:
        return f"# {Path(path).stem}\n\n**{e}**\n", {}
    except Exception as e:  # noqa: BLE001
        return f"# MOBI Error\n\n```\n{e}\n```\n", {}
    md = _mobi_html_to_md(raw, book.encoding)
    author = f"*{book.meta['author']}*" if book.meta.get("author") else ""
    if book.title and not md.lstrip().startswith("# "):
        head = [f"# {book.title}", ""] + ([author, ""] if author else []) + ["---", ""]
        md = "\n".join(head) + md
    elif author:
        first, _, rest = md.lstrip().partition("\n")
        md = f"{first}\n\n{author}\n{rest}"
    if not md.strip():
        md = f"# {book.title or Path(path).stem}\n\n*(empty book)*\n"
    return md.rstrip() + "\n", dict(book.meta)


def _load_mobi(path: str) -> str:
    return _load_mobi_full(path)[0]
