"""Compiled HTML Help (``.chm``) → Markdown, on the standard library alone.

A CHM file is an ITSS container: an ``ITSF`` header, an ``ITSP`` directory of
``PMGL`` leaf blocks (with ``PMGI`` index blocks above them) listing every
entry's path, section and offset, and two content sections — the small
*uncompressed* one and ``MSCompressed``, an LZX stream cut into blocks whose
compressed offsets live in a reset table so any block can be reached by
replaying from the previous reset point.

This module carries a full **LZX decompressor** (the CHM dialect: verbatim,
aligned-offset and uncompressed blocks, delta-coded canonical Huffman trees,
the three recent-offset registers, and the Intel E8 call transform), a port of
Quin Gillespie's ``libchm`` (MIT) — the same reader Paperback uses — into
Python.  On top of it, the ``.hhc`` table of contents becomes the chapter
list, and the topics are converted HTML→Markdown in TOC order (falling back
to every ``.htm``/``.html`` entry in directory order).

Whole-file reads are used throughout: help files are a few megabytes at most,
and the LZX stream has to be replayed sequentially anyway.
"""
import struct

from .._runtime import *  # noqa: F401,F403
from .html import _load_html_str


class ChmError(ValueError):
    pass


# ── LZX ──────────────────────────────────────────────────────────────────────

_LZX_MIN_MATCH = 2
_NUM_CHARS = 256
_PRETREE_NUM = 20
_ALIGNED_NUM = 8
_NUM_PRIMARY_LENGTHS = 7
_NUM_SECONDARY_LENGTHS = 249
_PRETREE_TABLEBITS = 6
_MAINTREE_MAXSYMBOLS = _NUM_CHARS + 50 * 8
_MAINTREE_TABLEBITS = 12
_LENGTH_MAXSYMBOLS = _NUM_SECONDARY_LENGTHS + 1
_LENGTH_TABLEBITS = 12
_ALIGNED_TABLEBITS = 7
_LENTABLE_SAFETY = 64

_BT_INVALID, _BT_VERBATIM, _BT_ALIGNED, _BT_UNCOMPRESSED = 0, 1, 2, 3
_MAX_E8_FRAMES = 32768
_E8_TAIL = 10

_EXTRA_BITS = [
    0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13,
    14, 14, 15, 15, 16, 16, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17, 17,
]
_POSITION_BASE = [
    0, 1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256, 384, 512, 768, 1024, 1536,
    2048, 3072, 4096, 6144, 8192, 12288, 16384, 24576, 32768, 49152, 65536, 98304, 131072,
    196608, 262144, 393216, 524288, 655360, 786432, 917504, 1048576, 1179648, 1310720,
    1441792, 1572864, 1703936, 1835008, 1966080, 2097152,
]


class _Bits:
    """MSB-first bit reader over 16-bit little-endian words (LZX convention)."""

    __slots__ = ("buf", "left", "src", "pos")

    def __init__(self, src: bytes) -> None:
        self.buf = 0
        self.left = 0
        self.src = src
        self.pos = 0

    def reinit(self) -> None:
        self.buf = 0
        self.left = 0

    def ensure(self, n: int) -> None:
        src = self.src
        while self.left < n:
            if self.pos + 1 >= len(src):
                if self.pos >= len(src):
                    self.left += 16
                    continue
                w = src[self.pos]
                self.buf = (self.buf | (w << max(0, 16 - self.left))) & 0xFFFFFFFF
                self.left += 8
                self.pos += 1
                continue
            w = src[self.pos] | (src[self.pos + 1] << 8)
            self.buf = (self.buf | (w << max(0, 16 - self.left))) & 0xFFFFFFFF
            self.left += 16
            self.pos += 2

    def peek(self, n: int) -> int:
        return self.buf >> (32 - n)

    def remove(self, n: int) -> None:
        self.buf = (self.buf << n) & 0xFFFFFFFF
        self.left -= n

    def read(self, n: int) -> int:
        self.ensure(n)
        v = self.buf >> (32 - n)
        self.buf = (self.buf << n) & 0xFFFFFFFF
        self.left -= n
        return v

    def read_huffsym(self, table: List[int], lens: List[int], tablebits: int, maxsymbols: int) -> int:
        self.ensure(16)
        i = table[self.buf >> (32 - tablebits)]
        if i >= maxsymbols:
            j = 1 << (32 - tablebits - 1)
            while True:
                i <<= 1
                if self.buf & j:
                    i |= 1
                j >>= 1
                if j == 0:
                    raise ChmError("LZX: illegal data (huffman tree)")
                if i >= len(table):
                    raise ChmError("LZX: illegal data (huffman index)")
                i = table[i]
                if i < maxsymbols:
                    break
        self.remove(lens[i])
        return i


def _make_decode_table(nsyms: int, nbits: int, lengths: List[int], table: List[int]) -> None:
    table_mask = 1 << nbits
    bit_mask = table_mask >> 1
    next_symbol = bit_mask
    pos = 0
    bit_num = 1
    while bit_num <= nbits:
        for sym in range(nsyms):
            if lengths[sym] == bit_num:
                leaf = pos
                pos += bit_mask
                if pos > table_mask:
                    raise ChmError("LZX: illegal data (table overrun)")
                for k in range(leaf, leaf + bit_mask):
                    table[k] = sym
        bit_mask >>= 1
        bit_num += 1
    if pos != table_mask:
        for k in range(pos, table_mask):
            table[k] = 0
        pos32 = pos << 16
        table_mask32 = table_mask << 16
        bit_mask = 1 << 15
        while bit_num <= 16:
            for sym in range(nsyms):
                if lengths[sym] == bit_num:
                    leaf = pos32 >> 16
                    for fill in range(bit_num - nbits):
                        if table[leaf] == 0:
                            ns2 = next_symbol << 1
                            if ns2 + 1 >= len(table):
                                raise ChmError("LZX: illegal data (tree overflow)")
                            table[ns2] = 0
                            table[ns2 + 1] = 0
                            table[leaf] = next_symbol
                            next_symbol += 1
                        leaf = table[leaf] << 1
                        if (pos32 >> (15 - fill)) & 1:
                            leaf += 1
                    table[leaf] = sym
                    pos32 += bit_mask
                    if pos32 > table_mask32:
                        raise ChmError("LZX: illegal data (long code overrun)")
            bit_mask >>= 1
            bit_num += 1
        if pos32 != table_mask32:
            for sym in range(nsyms):
                if lengths[sym] != 0:
                    raise ChmError("LZX: illegal data (incomplete table)")


def _read_lens(bits: _Bits, pretree_len: List[int], pretree_table: List[int],
               lens: List[int], first: int, last: int) -> None:
    for i in range(_PRETREE_NUM):
        pretree_len[i] = bits.read(4)
    _make_decode_table(_PRETREE_NUM, _PRETREE_TABLEBITS, pretree_len, pretree_table)
    x = first
    while x < last:
        z = bits.read_huffsym(pretree_table, pretree_len, _PRETREE_TABLEBITS, _PRETREE_NUM)
        if z == 17:
            run = bits.read(4) + 4
            end = min(x + run, last)
            for k in range(x, end):
                lens[k] = 0
            x = end
        elif z == 18:
            run = bits.read(5) + 20
            end = min(x + run, last)
            for k in range(x, end):
                lens[k] = 0
            x = end
        elif z == 19:
            run = bits.read(1) + 4
            sym = bits.read_huffsym(pretree_table, pretree_len, _PRETREE_TABLEBITS, _PRETREE_NUM)
            val = (lens[x] - sym) % 17
            end = min(x + run, last)
            for k in range(x, end):
                lens[k] = val
            x = end
        else:
            lens[x] = (lens[x] - z) % 17
            x += 1


class LzxDecoder:
    """Stateful LZX decoder; ``decompress`` yields one frame per call."""

    def __init__(self, window_bits: int) -> None:
        if not 15 <= window_bits <= 21:
            raise ChmError(f"LZX: invalid window size 2^{window_bits}")
        self.window_size = 1 << window_bits
        self.window = bytearray(self.window_size)
        self.window_posn = 0
        posn_slots = {20: 42, 21: 50}.get(window_bits, window_bits * 2)
        self.main_elements = 256 + posn_slots * 8
        self.r0 = self.r1 = self.r2 = 1
        self.header_read = False
        self.block_type = _BT_INVALID
        self.block_length = 0
        self.block_remaining = 0
        self.frames_read = 0
        self.intel_filesize = 0
        self.intel_curpos = 0
        self.intel_started = False
        self.pretree_len = [0] * (_PRETREE_NUM + _LENTABLE_SAFETY)
        self.maintree_len = [0] * (_MAINTREE_MAXSYMBOLS + _LENTABLE_SAFETY)
        self.length_len = [0] * (_LENGTH_MAXSYMBOLS + _LENTABLE_SAFETY)
        self.aligned_len = [0] * (_ALIGNED_NUM + _LENTABLE_SAFETY)
        self.pretree_table = [0] * ((1 << _PRETREE_TABLEBITS) + _PRETREE_NUM * 2)
        self.maintree_table = [0] * ((1 << _MAINTREE_TABLEBITS) + _MAINTREE_MAXSYMBOLS * 2)
        self.length_table = [0] * ((1 << _LENGTH_TABLEBITS) + _LENGTH_MAXSYMBOLS * 2)
        self.aligned_table = [0] * ((1 << _ALIGNED_TABLEBITS) + _ALIGNED_NUM * 2)

    def reset(self) -> None:
        self.r0 = self.r1 = self.r2 = 1
        self.header_read = False
        self.frames_read = 0
        self.block_remaining = 0
        self.block_type = _BT_INVALID
        self.intel_curpos = 0
        self.intel_started = False
        self.window_posn = 0
        for i in range(len(self.maintree_len)):
            self.maintree_len[i] = 0
        for i in range(len(self.length_len)):
            self.length_len[i] = 0

    def _read_main_and_length_trees(self, bits: _Bits) -> None:
        _read_lens(bits, self.pretree_len, self.pretree_table, self.maintree_len, 0, _NUM_CHARS)
        _read_lens(bits, self.pretree_len, self.pretree_table, self.maintree_len, _NUM_CHARS, self.main_elements)
        _make_decode_table(_MAINTREE_MAXSYMBOLS, _MAINTREE_TABLEBITS, self.maintree_len, self.maintree_table)
        if self.maintree_len[0xE8] != 0:
            self.intel_started = True
        _read_lens(bits, self.pretree_len, self.pretree_table, self.length_len, 0, _NUM_SECONDARY_LENGTHS)
        _make_decode_table(_LENGTH_MAXSYMBOLS, _LENGTH_TABLEBITS, self.length_len, self.length_table)

    def _start_block(self, bits: _Bits, inp: bytes) -> None:
        if self.block_type == _BT_UNCOMPRESSED:
            if self.block_length & 1:
                bits.pos += 1
            bits.reinit()
        block_type = bits.read(3)
        blen = (bits.read(16) << 8) | bits.read(8)
        self.block_type = block_type
        self.block_length = blen
        self.block_remaining = blen
        if block_type == _BT_ALIGNED:
            for i in range(_ALIGNED_NUM):
                self.aligned_len[i] = bits.read(3)
            _make_decode_table(_ALIGNED_NUM, _ALIGNED_TABLEBITS, self.aligned_len, self.aligned_table)
            self._read_main_and_length_trees(bits)
        elif block_type == _BT_VERBATIM:
            self._read_main_and_length_trees(bits)
        elif block_type == _BT_UNCOMPRESSED:
            self.intel_started = True
            bits.ensure(16)
            if bits.left > 16:
                bits.pos -= 2
            raw = inp[bits.pos:bits.pos + 12]
            if len(raw) < 12:
                raise ChmError("LZX: illegal data (uncompressed header)")
            self.r0, self.r1, self.r2 = struct.unpack("<III", raw)
            bits.pos += 12
        else:
            raise ChmError("LZX: illegal block type")

    def _undo_intel_e8(self, out: bytearray, frame_size: int) -> None:
        curpos = self.intel_curpos
        self.intel_curpos = curpos + frame_size
        if not self.intel_started or len(out) <= _E8_TAIL:
            return
        filesize = self.intel_filesize
        end = len(out) - _E8_TAIL
        i = 0
        while i < end:
            if out[i] != 0xE8:
                i += 1
                curpos += 1
                continue
            abs_off = struct.unpack("<i", out[i + 1:i + 5])[0]
            if abs_off >= -curpos and abs_off < filesize:
                rel = abs_off - curpos if abs_off >= 0 else abs_off + filesize
                out[i + 1:i + 5] = struct.pack("<i", rel & 0xFFFFFFFF if rel < 0 else rel) if -2**31 <= rel < 2**31 else struct.pack("<I", rel & 0xFFFFFFFF)
            i += 5
            curpos += 5

    def _decode_matches(self, bits: _Bits, wp: int, this_run: int) -> None:
        window = self.window
        ws = self.window_size
        mask = ws - 1
        aligned = self.block_type == _BT_ALIGNED
        mt, ml = self.maintree_table, self.maintree_len
        lt, ll = self.length_table, self.length_len
        at, al = self.aligned_table, self.aligned_len
        while this_run > 0:
            main_element = bits.read_huffsym(mt, ml, _MAINTREE_TABLEBITS, _MAINTREE_MAXSYMBOLS)
            if main_element < _NUM_CHARS:
                window[wp] = main_element
                wp += 1
                this_run -= 1
                continue
            me = main_element - _NUM_CHARS
            match_length = me & _NUM_PRIMARY_LENGTHS
            if match_length == _NUM_PRIMARY_LENGTHS:
                match_length += bits.read_huffsym(lt, ll, _LENGTH_TABLEBITS, _LENGTH_MAXSYMBOLS)
            match_length += _LZX_MIN_MATCH
            slot = me >> 3
            if slot == 0:
                match_offset = self.r0
            elif slot == 1:
                self.r0, self.r1 = self.r1, self.r0
                match_offset = self.r0
            elif slot == 2:
                self.r0, self.r2 = self.r2, self.r0
                match_offset = self.r0
            else:
                extra = _EXTRA_BITS[slot]
                base = _POSITION_BASE[slot] - 2
                if not aligned:
                    match_offset = base if extra == 0 else base + bits.read(extra)
                elif extra == 0:
                    match_offset = base
                elif extra <= 2:
                    match_offset = base + bits.read(extra)
                elif extra == 3:
                    match_offset = base + bits.read_huffsym(at, al, _ALIGNED_TABLEBITS, _ALIGNED_NUM)
                else:
                    verbatim_bits = bits.read(extra - 3)
                    aligned_bits = bits.read_huffsym(at, al, _ALIGNED_TABLEBITS, _ALIGNED_NUM)
                    match_offset = base + (verbatim_bits << 3) + aligned_bits
                self.r2 = self.r1
                self.r1 = self.r0
                self.r0 = match_offset
            if match_offset == 0 or match_offset > ws:
                raise ChmError("LZX: illegal match offset")
            if wp + match_length > ws:
                raise ChmError("LZX: match runs past the window")
            src = (wp - match_offset) & mask
            if src + match_length <= ws and src + match_length <= wp:
                window[wp:wp + match_length] = window[src:src + match_length]
                wp += match_length
            else:
                for _ in range(match_length):
                    window[wp] = window[(wp - match_offset) & mask]
                    wp += 1
            this_run -= match_length
        self.window_posn = wp

    def decompress(self, inp: bytes, out_len: int) -> bytes:
        bits = _Bits(inp)
        togo = out_len
        if not self.header_read:
            self.intel_filesize = 0 if bits.read(1) == 0 else ((bits.read(16) << 16) | bits.read(16))
            if self.intel_filesize >= 2**31:
                self.intel_filesize -= 2**32
            self.header_read = True
        ws = self.window_size
        while togo > 0:
            if self.block_remaining == 0:
                self._start_block(bits, inp)
            if bits.pos > len(inp) + 2 or (bits.pos > len(inp) and bits.left < 16):
                raise ChmError("LZX: input exhausted")
            this_run = min(self.block_remaining, togo)
            togo -= this_run
            self.block_remaining -= this_run
            self.window_posn &= ws - 1
            wp = self.window_posn
            if wp + this_run > ws:
                raise ChmError("LZX: run straddles the window")
            if self.block_type in (_BT_VERBATIM, _BT_ALIGNED):
                self._decode_matches(bits, wp, this_run)
                self.window_posn = wp + this_run
            elif self.block_type == _BT_UNCOMPRESSED:
                raw = inp[bits.pos:bits.pos + this_run]
                if len(raw) < this_run:
                    raise ChmError("LZX: illegal data (uncompressed run)")
                self.window[wp:wp + this_run] = raw
                bits.pos += this_run
                self.window_posn = wp + this_run
            else:
                raise ChmError("LZX: illegal block type")
        final_pos = ws if self.window_posn == 0 else self.window_posn
        if final_pos < out_len:
            raise ChmError("LZX: data format error")
        out = bytearray(self.window[final_pos - out_len:final_pos])
        if self.frames_read < _MAX_E8_FRAMES and self.intel_filesize != 0:
            self._undo_intel_e8(out, out_len)
        self.frames_read += 1
        return bytes(out)


# ── ITSS container ───────────────────────────────────────────────────────────

_PATH_RESET_TABLE = "::DataSpace/Storage/MSCompressed/Transform/{7FC28940-9D31-11D0-9B27-00A0C91E9C7C}/InstanceData/ResetTable"
_PATH_CONTROL_DATA = "::DataSpace/Storage/MSCompressed/ControlData"
_PATH_CONTENT = "::DataSpace/Storage/MSCompressed/Content"


def _cword(buf: bytes, pos: int) -> Tuple[int, int]:
    acc = 0
    while True:
        if pos >= len(buf):
            raise ChmError("CHM: malformed directory entry")
        b = buf[pos]
        pos += 1
        acc = (acc << 7) | (b & 0x7F)
        if b < 0x80:
            return acc, pos
        if acc > (1 << 56):
            raise ChmError("CHM: directory integer overflow")


class ChmFile:
    """A parsed CHM archive: ``entries()`` lists paths, ``read(path)`` returns bytes."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        if len(data) < 0x58 or data[:4] != b"ITSF":
            raise ChmError("Not a CHM file (no ITSF header)")
        version = struct.unpack("<I", data[4:8])[0]
        self.dir_offset, dir_len = struct.unpack("<QQ", data[0x48:0x58])
        if version == 3:
            if len(data) < 0x60:
                raise ChmError("CHM: truncated ITSF header")
            self.data_offset = struct.unpack("<Q", data[0x58:0x60])[0]
        elif version == 2:
            self.data_offset = self.dir_offset + dir_len
        else:
            raise ChmError(f"CHM: unsupported ITSF version {version}")
        itsp = data[self.dir_offset:self.dir_offset + 0x54]
        if len(itsp) < 0x54 or itsp[:4] != b"ITSP":
            raise ChmError("CHM: bad ITSP directory header")
        header_len = struct.unpack("<I", itsp[8:12])[0]
        self.block_len = struct.unpack("<I", itsp[0x10:0x14])[0]
        if self.block_len < 0x14 or self.block_len > 0x100000:
            raise ChmError("CHM: bad directory block size")
        self.index_head = struct.unpack("<i", itsp[0x20:0x24])[0]
        self.blocks_start = self.dir_offset + header_len
        self.entries: Dict[str, Tuple[int, int, int]] = {}   # lower path → (space, start, length)
        self.paths: List[str] = []
        self._read_directory()
        self._decomp: Optional[Dict[str, Any]] = None
        self._cache: Dict[int, bytes] = {}
        self._last_block = -1
        self._init_compression()

    def _block(self, idx: int) -> bytes:
        off = self.blocks_start + idx * self.block_len
        return self.data[off:off + self.block_len]

    def _read_directory(self) -> None:
        cur = self.index_head
        seen: set = set()
        while cur >= 0 and cur not in seen:
            seen.add(cur)
            blk = self._block(cur)
            if blk[:4] != b"PMGL":
                break
            free = struct.unpack("<I", blk[4:8])[0]
            nxt = struct.unpack("<i", blk[0x10:0x14])[0]
            end = max(0, len(blk) - free)
            pos = 0x14
            while pos < end:
                plen, pos = _cword(blk, pos)
                if plen > 512 or pos + plen > len(blk):
                    raise ChmError("CHM: bad directory path")
                path = blk[pos:pos + plen].decode("utf-8", errors="replace")
                pos += plen
                space, pos = _cword(blk, pos)
                start, pos = _cword(blk, pos)
                length, pos = _cword(blk, pos)
                key = path.lower()
                if key not in self.entries:
                    self.paths.append(path)
                self.entries[key] = (space, start, length)
            if nxt >= 0 and nxt <= cur:
                break
            cur = nxt

    def _raw(self, path: str) -> Optional[bytes]:
        e = self.entries.get(path.lower())
        if e is None or e[0] != 0:
            return None
        _space, start, length = e
        off = self.data_offset + start
        if off + length > len(self.data):
            raise ChmError("CHM: entry runs past end of file")
        return self.data[off:off + length]

    def _init_compression(self) -> None:
        try:
            rt = self._raw(_PATH_RESET_TABLE)
            ctl = self._raw(_PATH_CONTROL_DATA)
        except ChmError:
            return
        cn = self.entries.get(_PATH_CONTENT.lower())
        if rt is None or ctl is None or cn is None or cn[0] != 0:
            return
        if len(rt) < 0x28 or len(ctl) < 0x18 or ctl[4:8] != b"LZXC":
            return
        if struct.unpack("<I", rt[0:4])[0] != 2:
            return
        block_count = struct.unpack("<I", rt[4:8])[0]
        table_offset = struct.unpack("<I", rt[0x0C:0x10])[0]
        uncompressed_len = struct.unpack("<Q", rt[0x10:0x18])[0]
        compressed_len, block_len = struct.unpack("<QQ", rt[0x18:0x28])
        version = struct.unpack("<I", ctl[8:12])[0]
        reset_interval, window_size, windows_per_reset = struct.unpack("<III", ctl[0x0C:0x18])
        if version == 2:
            reset_interval *= 0x8000
            window_size *= 0x8000
        if not (window_size and reset_interval and windows_per_reset and block_len and block_count):
            return
        if window_size & (window_size - 1) or reset_interval % (window_size // 2):
            return
        if block_len > window_size:
            return
        if table_offset + block_count * 8 > len(rt):
            return
        offsets = list(struct.unpack(f"<{block_count}Q", rt[table_offset:table_offset + block_count * 8]))
        offsets.append(compressed_len)
        if any(offsets[i] > offsets[i + 1] for i in range(len(offsets) - 1)):
            return
        window_bits = window_size.bit_length() - 1
        try:
            lzx = LzxDecoder(window_bits)
        except ChmError:
            return
        self._decomp = {
            "cn_start": self.data_offset + cn[1],
            "offsets": offsets,
            "block_len": int(block_len),
            "uncompressed_len": int(uncompressed_len),
            "reset_blkcount": (reset_interval // (window_size // 2)) * windows_per_reset,
            "lzx": lzx,
        }

    def _decode_one(self, block: int) -> bytes:
        d = self._decomp
        assert d is not None
        offs = d["offsets"]
        if block + 1 >= len(offs):
            raise ChmError("CHM: block index past reset table")
        start, end = offs[block], offs[block + 1]
        comp = self.data[d["cn_start"] + start:d["cn_start"] + end]
        # The last block is usually shorter than a full frame: ask the decoder
        # for exactly what the reset table says remains, never past the stream.
        remaining = d["uncompressed_len"] - block * d["block_len"]
        want = d["block_len"] if remaining <= 0 or remaining > d["block_len"] else int(remaining)
        out = d["lzx"].decompress(comp, want)
        if len(out) < d["block_len"]:
            out = out + b"\x00" * (d["block_len"] - len(out))
        self._cache[block] = out
        if len(self._cache) > 8:
            oldest = min(self._cache)
            if oldest != block:
                self._cache.pop(oldest, None)
        self._last_block = block
        return out

    def _decompress_block(self, block: int) -> bytes:
        d = self._decomp
        assert d is not None
        rb = d["reset_blkcount"]
        window_start = block - block % rb
        if window_start <= self._last_block < block:
            start = self._last_block + 1
        else:
            start = window_start
        out = b""
        for b in range(start, block + 1):
            if b % rb == 0:
                d["lzx"].reset()
            out = self._decode_one(b)
        return out

    def _read_compressed(self, start: int, length: int) -> bytes:
        d = self._decomp
        if d is None:
            raise ChmError("CHM: compressed content but no usable LZX section")
        bl = d["block_len"]
        total = max((len(d["offsets"]) - 1) * bl, d["uncompressed_len"])
        if start + length > total:
            raise ChmError("CHM: entry runs past the compressed section")
        out = bytearray()
        pos = start
        end = start + length
        while pos < end:
            block = pos // bl
            off = pos % bl
            avail = min(bl - off, end - pos)
            data = self._cache.get(block)
            if data is None:
                data = self._decompress_block(block)
            out += data[off:off + avail]
            pos += avail
        return bytes(out)

    def has_compression(self) -> bool:
        return self._decomp is not None

    def read(self, path: str) -> bytes:
        e = self.entries.get(path.lower())
        if e is None:
            raise KeyError(path)
        space, start, length = e
        if length == 0:
            return b""
        if space == 0:
            off = self.data_offset + start
            if off + length > len(self.data):
                raise ChmError("CHM: entry runs past end of file")
            return self.data[off:off + length]
        if space == 1:
            return self._read_compressed(start, length)
        raise ChmError(f"CHM: unknown content section {space}")

    def files(self) -> List[str]:
        """Ordinary content files (paths starting with ``/`` but not ``/#`` or ``/$``)."""
        return [p for p in self.paths if p.startswith("/") and not p.startswith(("/#", "/$")) and not p.endswith("/")]


# ── Help-project metadata ────────────────────────────────────────────────────


def _chm_system(chm: ChmFile) -> Dict[str, str]:
    """Title, default topic, TOC file, and index file from ``/#SYSTEM``."""
    out: Dict[str, str] = {}
    try:
        data = chm.read("/#SYSTEM")
    except (KeyError, ChmError):
        return out
    pos = 4
    while pos + 4 <= len(data):
        code, length = struct.unpack("<HH", data[pos:pos + 4])
        pos += 4
        val = data[pos:pos + length]
        pos += length
        text = val.split(b"\x00", 1)[0].decode("utf-8", errors="replace").strip()
        if code == 0:
            out["toc"] = text
        elif code == 1:
            out["index"] = text
        elif code == 2:
            out["default"] = text
        elif code == 3:
            out["title"] = text
        elif code == 4 and len(val) >= 4:
            out["lcid"] = str(struct.unpack("<I", val[:4])[0])
    return out


class _HhcParser(HTMLParser):
    """Sitemap (``.hhc``/``.hhk``) → ``[(depth, name, local)]``."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: List[Tuple[int, str, str]] = []
        self._depth = 0
        self._cur: Optional[Dict[str, str]] = None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "ul":
            self._depth += 1
        elif tag == "object" and a.get("type", "").lower() == "text/sitemap":
            self._cur = {}
        elif tag == "param" and self._cur is not None:
            name = a.get("name", "").lower()
            if name in ("name", "local") and name not in self._cur:
                self._cur[name] = a.get("value", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "ul":
            self._depth = max(0, self._depth - 1)
        elif tag == "object" and self._cur is not None:
            name = self._cur.get("name", "").strip()
            if name:
                self.items.append((max(1, self._depth), name, self._cur.get("local", "").strip()))
            self._cur = None


def _norm_local(local: str) -> str:
    local = local.split("#")[0].replace("\\", "/")
    if local.lower().startswith(("http://", "https://", "mailto:", "ms-its:")):
        return ""
    if not local.startswith("/"):
        local = "/" + local
    return local


def _decode_html(raw: bytes) -> str:
    m = re.search(rb"charset=[\"']?([\w-]+)", raw[:2048], re.I)
    enc = m.group(1).decode("ascii", errors="replace") if m else "utf-8"
    for candidate in (enc, "utf-8", "cp1252"):
        try:
            return raw.decode(candidate)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def _load_chm_full(path: str) -> Tuple[str, List[Tuple[str, str]], Dict[str, str]]:
    """``(markdown, chapters, metadata)`` for a CHM help file."""
    try:
        chm = ChmFile(Path(path).read_bytes())
    except ChmError as e:
        return f"# {Path(path).stem}\n\n**{e}**\n", [], {}
    except Exception as e:  # noqa: BLE001
        return f"# CHM Error\n\n```\n{e}\n```\n", [], {}
    system = _chm_system(chm)
    title = system.get("title") or Path(path).stem
    meta = {"title": title}
    files = chm.files()
    lower_set = {f.lower() for f in files}
    # Table of contents.
    toc_name = system.get("toc") or next((f for f in files if f.lower().endswith(".hhc")), "")
    toc_items: List[Tuple[int, str, str]] = []
    if toc_name:
        try:
            hp = _HhcParser()
            hp.feed(_decode_html(chm.read(_norm_local(toc_name))))
            hp.close()
            toc_items = hp.items
        except (KeyError, ChmError, Exception):  # noqa: BLE001
            toc_items = []
    ordered: List[str] = []
    seen: set = set()
    for _depth, _name, local in toc_items:
        loc = _norm_local(local)
        if loc and loc.lower() in lower_set and loc.lower() not in seen:
            seen.add(loc.lower())
            ordered.append(loc)
    default = _norm_local(system.get("default", ""))
    if default and default.lower() in lower_set and default.lower() not in seen:
        ordered.insert(0, default)
        seen.add(default.lower())
    for f in files:
        if f.lower().endswith((".htm", ".html", ".xhtml")) and f.lower() not in seen:
            seen.add(f.lower())
            ordered.append(f)
    parts: List[str] = [f"# {title}", ""]
    if toc_items:
        parts += ["## Contents", ""]
        for depth, name, local in toc_items:
            parts.append(f"{'  ' * (depth - 1)}- {name}")
        parts += ["", "---", ""]
    errors = 0
    for f in ordered:
        try:
            raw = chm.read(f)
        except (KeyError, ChmError):
            errors += 1
            continue
        html = _decode_html(raw)
        # The TOC already names each topic; a <title> would otherwise repeat
        # the page's own <h1> as a second heading.
        html = re.sub(r"<title\b[^>]*>.*?</title>", "", html, flags=re.I | re.S)
        md = _load_html_str(html).strip()
        if md:
            parts += [md, "", "---", ""]
    if errors and len(ordered) == errors:
        parts += ["*The topics in this help file could not be decompressed.*", ""]
    while parts and parts[-1] in ("", "---"):
        parts.pop()
    chapters = [(name, _norm_local(local) or name) for depth, name, local in toc_items if depth <= 2]
    md_text = re.sub(r"\n{3,}", "\n\n", "\n".join(parts)) + "\n"
    return md_text, chapters, meta


def _load_chm(path: str) -> str:
    return _load_chm_full(path)[0]
