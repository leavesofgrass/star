"""Audiobooks: ``.m4b`` (MPEG-4) and ``.mp3`` → a navigable Markdown document.

An audiobook has no text, so the document star builds from one is its
*structure*: title, author/narrator, album, year, duration, the description,
and — the part that matters for navigation — the **chapter list with
timestamps**, which also feeds the chapter list (``Document.chapters``).  The
audio can then be read with **Tools ▸ Transcribe Audio** (Whisper) when that
optional feature is installed.

Parsing is native (stdlib only):

* **MP4/M4B** — the atom tree: ``mvhd`` for duration, ``udta/meta/ilst`` for
  the iTunes-style tags, chapters from the Nero ``chpl`` atom *or* the
  QuickTime chapter text track (``tref/chap`` → ``stts``/``stsc``/``stsz``/
  ``stco`` sample table).
* **MP3** — the ID3v2.2/2.3/2.4 header: ``TIT2``/``TPE1``/``TALB``/``TPE2``/
  ``TYER``/``TDRC``/``TCON``/``COMM``, and ``CHAP``/``CTOC`` chapter frames
  (the podcast-app standard); duration from the Xing/Info header or the first
  MPEG frame's bitrate.

When neither yields a title or chapters and ``ffprobe`` is on PATH, its JSON
output is used as a last resort.
"""
import struct

from .._runtime import *  # noqa: F401,F403


def _fmt_ms(ms: int) -> str:
    s, ms = divmod(int(ms), 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class _Book:
    def __init__(self) -> None:
        self.title = ""
        self.author = ""
        self.narrator = ""
        self.album = ""
        self.year = ""
        self.genre = ""
        self.description = ""
        self.duration_ms = 0
        self.chapters: List[Tuple[int, str]] = []   # (start_ms, title)


# ── MP4 / M4B ────────────────────────────────────────────────────────────────

_CONTAINERS = {b"moov", b"udta", b"trak", b"mdia", b"minf", b"stbl", b"ilst", b"tref", b"edts", b"dinf"}


def _atoms(data: bytes, start: int, end: int):
    """Yield ``(type, body_start, body_end)`` for the atoms in ``data[start:end]``."""
    pos = start
    while pos + 8 <= end:
        size = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        hdr = 8
        if size == 1:
            if pos + 16 > end:
                return
            size = struct.unpack(">Q", data[pos + 8:pos + 16])[0]
            hdr = 16
        elif size == 0:
            size = end - pos
        if size < hdr:
            return
        body = pos + hdr
        if typ == b"meta":
            body += 4  # full box: version + flags
        yield typ, body, min(pos + size, end)
        pos += size


def _find_atom(data: bytes, path: List[bytes], start: int = 0, end: Optional[int] = None) -> List[Tuple[int, int]]:
    """All ``(body_start, body_end)`` ranges matching an atom *path* like ``[b"moov", b"trak"]``."""
    end = len(data) if end is None else end
    ranges = [(start, end)]
    for name in path:
        nxt: List[Tuple[int, int]] = []
        for s, e in ranges:
            for typ, bs, be in _atoms(data, s, e):
                if typ == name:
                    nxt.append((bs, be))
        ranges = nxt
        if not ranges:
            break
    return ranges


def _ilst_text(data: bytes, s: int, e: int) -> str:
    for typ, bs, be in _atoms(data, s, e):
        if typ == b"data" and be - bs >= 8:
            flags = struct.unpack(">I", data[bs:bs + 4])[0] & 0xFFFFFF
            payload = data[bs + 8:be]
            if flags in (1, 0, 2):
                try:
                    return payload.decode("utf-8" if flags != 2 else "utf-16-be", errors="replace").strip("\x00").strip()
                except Exception:  # noqa: BLE001
                    return ""
            return ""
    return ""


def _mp4_read(data: bytes, book: _Book) -> None:
    moov = _find_atom(data, [b"moov"])
    if not moov:
        return
    ms, me = moov[0]
    # Duration.
    for s, e in _find_atom(data, [b"mvhd"], ms, me):
        ver = data[s]
        if ver == 1:
            timescale = struct.unpack(">I", data[s + 20:s + 24])[0]
            duration = struct.unpack(">Q", data[s + 24:s + 32])[0]
        else:
            timescale = struct.unpack(">I", data[s + 12:s + 16])[0]
            duration = struct.unpack(">I", data[s + 16:s + 20])[0]
        if timescale:
            book.duration_ms = int(duration * 1000 / timescale)
    # Tags.
    for s, e in _find_atom(data, [b"udta", b"meta", b"ilst"], ms, me):
        for typ, bs, be in _atoms(data, s, e):
            val = _ilst_text(data, bs, be)
            if not val:
                continue
            if typ == b"\xa9nam":
                book.title = book.title or val
            elif typ == b"\xa9ART":
                book.author = book.author or val
            elif typ == b"aART":
                book.author = book.author or val
            elif typ == b"\xa9wrt":
                book.author = book.author or val
            elif typ == b"\xa9alb":
                book.album = val
            elif typ == b"\xa9day":
                book.year = val[:4]
            elif typ == b"\xa9gen":
                book.genre = val
            elif typ in (b"ldes", b"desc", b"\xa9cmt", b"\xa9des"):
                if len(val) > len(book.description):
                    book.description = val
            elif typ == b"\xa9nrt":
                book.narrator = val
    # Nero chapters.
    for s, e in _find_atom(data, [b"udta", b"chpl"], ms, me):
        try:
            ver = data[s]
            pos = s + 4
            if ver == 1:
                pos += 4
                count = struct.unpack(">I", data[pos:pos + 4])[0]
                pos += 4
            else:
                count = data[pos]
                pos += 1
            chaps = []
            for _ in range(count):
                start = struct.unpack(">Q", data[pos:pos + 8])[0]  # 100 ns units
                ln = data[pos + 8]
                title = data[pos + 9:pos + 9 + ln].decode("utf-8", errors="replace")
                pos += 9 + ln
                chaps.append((start // 10000, title))
            if chaps:
                book.chapters = chaps
                return
        except (IndexError, struct.error):
            break
    # QuickTime chapter track.
    chap_ids: set = set()
    tracks = _find_atom(data, [b"trak"], ms, me)
    for ts, te in tracks:
        for s, e in _find_atom(data, [b"tref", b"chap"], ts, te):
            for i in range(s, e - 3, 4):
                chap_ids.add(struct.unpack(">I", data[i:i + 4])[0])
    if not chap_ids:
        return
    for ts, te in tracks:
        tk = _find_atom(data, [b"tkhd"], ts, te)
        if not tk:
            continue
        s, _e = tk[0]
        ver = data[s]
        tid = struct.unpack(">I", data[s + 20:s + 24])[0] if ver == 1 else struct.unpack(">I", data[s + 12:s + 16])[0]
        if tid not in chap_ids:
            continue
        chaps = _text_track_chapters(data, ts, te)
        if chaps:
            book.chapters = chaps
            return


def _text_track_chapters(data: bytes, ts: int, te: int) -> List[Tuple[int, str]]:
    md = _find_atom(data, [b"mdia", b"mdhd"], ts, te)
    if not md:
        return []
    s, _e = md[0]
    ver = data[s]
    timescale = struct.unpack(">I", data[s + 20:s + 24])[0] if ver == 1 else struct.unpack(">I", data[s + 12:s + 16])[0]
    if not timescale:
        return []
    stbl = _find_atom(data, [b"mdia", b"minf", b"stbl"], ts, te)
    if not stbl:
        return []
    ss, se = stbl[0]

    def full(name: bytes) -> Optional[Tuple[int, int]]:
        r = _find_atom(data, [name], ss, se)
        return r[0] if r else None

    stts = full(b"stts")
    stsz = full(b"stsz")
    stsc = full(b"stsc")
    stco = full(b"stco") or full(b"co64")
    if not (stts and stsz and stsc and stco):
        return []
    # Sample durations.
    n = struct.unpack(">I", data[stts[0] + 4:stts[0] + 8])[0]
    durations: List[int] = []
    p = stts[0] + 8
    for _ in range(n):
        cnt, dur = struct.unpack(">II", data[p:p + 8])
        durations += [dur] * cnt
        p += 8
    # Sample sizes.
    default_size = struct.unpack(">I", data[stsz[0] + 4:stsz[0] + 8])[0]
    count = struct.unpack(">I", data[stsz[0] + 8:stsz[0] + 12])[0]
    sizes = [default_size] * count if default_size else list(
        struct.unpack(f">{count}I", data[stsz[0] + 12:stsz[0] + 12 + 4 * count])
    )
    # Chunk offsets.
    is64 = data[stco[0] - 8:stco[0] - 4] == b"co64"
    cn = struct.unpack(">I", data[stco[0] + 4:stco[0] + 8])[0]
    fmt = ">%d%s" % (cn, "Q" if is64 else "I")
    width = 8 if is64 else 4
    offsets = list(struct.unpack(fmt, data[stco[0] + 8:stco[0] + 8 + width * cn]))
    # Sample-to-chunk.
    en = struct.unpack(">I", data[stsc[0] + 4:stsc[0] + 8])[0]
    entries = [struct.unpack(">III", data[stsc[0] + 8 + i * 12:stsc[0] + 20 + i * 12]) for i in range(en)]
    sample_offsets: List[int] = []
    for i, (first_chunk, per_chunk, _desc) in enumerate(entries):
        last_chunk = entries[i + 1][0] - 1 if i + 1 < len(entries) else len(offsets)
        for chunk in range(first_chunk, last_chunk + 1):
            if chunk - 1 >= len(offsets):
                break
            off = offsets[chunk - 1]
            for _ in range(per_chunk):
                idx = len(sample_offsets)
                if idx >= len(sizes):
                    break
                sample_offsets.append(off)
                off += sizes[idx]
    chaps: List[Tuple[int, str]] = []
    t = 0
    for idx, off in enumerate(sample_offsets):
        if idx >= len(sizes):
            break
        size = sizes[idx]
        if size >= 2 and off + 2 <= len(data):
            ln = struct.unpack(">H", data[off:off + 2])[0]
            raw = data[off + 2:off + 2 + min(ln, size - 2)]
            if raw[:2] in (b"\xfe\xff", b"\xff\xfe"):
                title = raw.decode("utf-16", errors="replace")
            else:
                title = raw.decode("utf-8", errors="replace")
            title = title.strip("\x00").strip()
            chaps.append((int(t * 1000 / timescale), title or f"Chapter {idx + 1}"))
        t += durations[idx] if idx < len(durations) else 0
    return chaps


# ── MP3 / ID3v2 ──────────────────────────────────────────────────────────────


def _syncsafe(b: bytes) -> int:
    return (b[0] << 21) | (b[1] << 14) | (b[2] << 7) | b[3]


def _id3_text(payload: bytes) -> str:
    if not payload:
        return ""
    enc = payload[0]
    body = payload[1:]
    try:
        if enc == 0:
            s = body.decode("latin-1", errors="replace")
        elif enc == 1:
            s = body.decode("utf-16", errors="replace")
        elif enc == 2:
            s = body.decode("utf-16-be", errors="replace")
        else:
            s = body.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return ""
    return s.replace("\x00", " ").strip()


def _id3_frames(data: bytes, start: int, end: int, version: int):
    pos = start
    while pos < end:
        if version == 2:
            if pos + 6 > end or data[pos] == 0:
                return
            fid = data[pos:pos + 3].decode("latin-1", errors="replace")
            size = (data[pos + 3] << 16) | (data[pos + 4] << 8) | data[pos + 5]
            hdr = 6
            flags = 0
        else:
            if pos + 10 > end or data[pos] == 0:
                return
            fid = data[pos:pos + 4].decode("latin-1", errors="replace")
            size = _syncsafe(data[pos + 4:pos + 8]) if version == 4 else struct.unpack(">I", data[pos + 4:pos + 8])[0]
            flags = struct.unpack(">H", data[pos + 8:pos + 10])[0]
            hdr = 10
        if size <= 0 or pos + hdr + size > end + 1:
            return
        payload = data[pos + hdr:pos + hdr + size]
        if version == 4 and flags & 0x02:   # unsynchronisation
            payload = payload.replace(b"\xff\x00", b"\xff")
        if version == 4 and flags & 0x01:   # data length indicator
            payload = payload[4:]
        yield fid, payload
        pos += hdr + size


def _id3_read(data: bytes, book: _Book) -> int:
    """Populate *book* from an ID3v2 tag; return the tag's total size (0 if none)."""
    if data[:3] != b"ID3" or len(data) < 10:
        return 0
    version = data[3]
    flags = data[5]
    size = _syncsafe(data[6:10])
    start = 10
    end = min(10 + size, len(data))
    if flags & 0x40:  # extended header
        if version == 4:
            start += _syncsafe(data[10:14])
        else:
            start += struct.unpack(">I", data[10:14])[0] + 4
    body = data[start:end]
    if flags & 0x80 and version < 4:  # whole-tag unsynchronisation
        body = body.replace(b"\xff\x00", b"\xff")
    chapters: Dict[str, Tuple[int, str]] = {}
    toc_order: List[str] = []
    for fid, payload in _id3_frames(body, 0, len(body), version):
        if fid in ("TIT2", "TT2"):
            book.title = book.title or _id3_text(payload)
        elif fid in ("TPE1", "TP1"):
            book.author = book.author or _id3_text(payload)
        elif fid in ("TPE2", "TP2"):
            book.narrator = _id3_text(payload)
        elif fid in ("TCOM", "TCM"):
            book.author = book.author or _id3_text(payload)
        elif fid in ("TALB", "TAL"):
            book.album = _id3_text(payload)
        elif fid in ("TYER", "TYE", "TDRC", "TDRL"):
            book.year = book.year or _id3_text(payload)[:4]
        elif fid in ("TCON", "TCO"):
            book.genre = _id3_text(payload)
        elif fid in ("COMM", "COM") and len(payload) > 4:
            enc = payload[0]
            rest = payload[4:]
            sep = b"\x00\x00" if enc in (1, 2) else b"\x00"
            idx = rest.find(sep)
            text = rest[idx + len(sep):] if idx >= 0 else rest
            desc = _id3_text(bytes([enc]) + text)
            if len(desc) > len(book.description):
                book.description = desc
        elif fid == "TLEN":
            try:
                book.duration_ms = book.duration_ms or int(_id3_text(payload))
            except ValueError:
                pass
        elif fid == "CHAP":
            nul = payload.find(b"\x00")
            if nul < 0 or len(payload) < nul + 17:
                continue
            elem = payload[:nul].decode("latin-1", errors="replace")
            start_ms = struct.unpack(">I", payload[nul + 1:nul + 5])[0]
            title = ""
            for sid, spay in _id3_frames(payload, nul + 17, len(payload), version):
                if sid == "TIT2":
                    title = _id3_text(spay)
                    break
            chapters[elem] = (start_ms, title)
        elif fid == "CTOC":
            nul = payload.find(b"\x00")
            if nul < 0 or len(payload) < nul + 3:
                continue
            tflags = payload[nul + 1]
            count = payload[nul + 2]
            p = nul + 3
            ids: List[str] = []
            for _ in range(count):
                n = payload.find(b"\x00", p)
                if n < 0:
                    break
                ids.append(payload[p:n].decode("latin-1", errors="replace"))
                p = n + 1
            if tflags & 0x02 or not toc_order:  # top-level
                toc_order = ids
    if chapters:
        ordered = [chapters[i] for i in toc_order if i in chapters] if toc_order else []
        if len(ordered) < len(chapters):
            ordered = sorted(chapters.values())
        book.chapters = [(st, t or f"Chapter {i + 1}") for i, (st, t) in enumerate(ordered)]
    return end


_BITRATES = {
    (1, 3): [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448],
    (1, 2): [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384],
    (1, 1): [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
    (2, 3): [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256],
    (2, 2): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
}
_SAMPLE_RATES = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def _mp3_duration_ms(data: bytes, start: int) -> int:
    """Duration from the Xing/Info frame count, else from the first frame's bitrate."""
    pos = start
    end = min(len(data) - 4, start + 65536)
    while pos < end:
        b1, b2 = data[pos], data[pos + 1]
        if b1 == 0xFF and (b2 & 0xE0) == 0xE0:
            ver_bits = (b2 >> 3) & 0x03
            layer_bits = (b2 >> 1) & 0x03
            if ver_bits == 1 or layer_bits == 0:
                pos += 1
                continue
            version = 1 if ver_bits == 3 else 2
            layer = 4 - layer_bits
            b3 = data[pos + 2]
            br_idx = b3 >> 4
            sr_idx = (b3 >> 2) & 0x03
            if br_idx in (0, 15) or sr_idx == 3:
                pos += 1
                continue
            table = _BITRATES.get((version, layer)) or _BITRATES[(2, 2)]
            bitrate = table[br_idx] * 1000
            sr = _SAMPLE_RATES[ver_bits][sr_idx]
            samples = 1152 if layer == 3 and version == 1 else (576 if layer == 3 else (384 if layer == 1 else 1152))
            if not bitrate or not sr:
                pos += 1
                continue
            # Xing/Info header (VBR) inside the first frame.
            frame = data[pos:pos + 200]
            for tag in (b"Xing", b"Info"):
                i = frame.find(tag)
                if i > 0 and len(frame) >= i + 12:
                    flags = struct.unpack(">I", frame[i + 4:i + 8])[0]
                    if flags & 1:
                        frames = struct.unpack(">I", frame[i + 8:i + 12])[0]
                        return int(frames * samples * 1000 / sr)
            return int((len(data) - start) * 8 * 1000 / bitrate)
        pos += 1
    return 0


# ── ffprobe fallback ─────────────────────────────────────────────────────────


def _ffprobe(path: str, book: _Book) -> None:
    exe = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
    if not exe:
        return
    try:
        r = subprocess.run(
            [exe, "-v", "quiet", "-print_format", "json", "-show_format", "-show_chapters", path],
            capture_output=True, text=True, timeout=30, creationflags=_SUBPROCESS_FLAGS,
        )
        if r.returncode != 0:
            return
        info = json.loads(r.stdout or "{}")
    except Exception:  # noqa: BLE001
        return
    fmt = info.get("format", {}) or {}
    tags = {k.lower(): v for k, v in (fmt.get("tags", {}) or {}).items()}
    book.title = book.title or tags.get("title", "")
    book.author = book.author or tags.get("artist", "") or tags.get("album_artist", "")
    book.album = book.album or tags.get("album", "")
    book.year = book.year or str(tags.get("date", ""))[:4]
    book.genre = book.genre or tags.get("genre", "")
    book.description = book.description or tags.get("description", "") or tags.get("comment", "")
    try:
        book.duration_ms = book.duration_ms or int(float(fmt.get("duration", 0)) * 1000)
    except (TypeError, ValueError):
        pass
    if not book.chapters:
        chaps = []
        for i, ch in enumerate(info.get("chapters", []) or []):
            try:
                start_ms = int(float(ch.get("start_time", 0)) * 1000)
            except (TypeError, ValueError):
                start_ms = 0
            title = (ch.get("tags", {}) or {}).get("title", "") or f"Chapter {i + 1}"
            chaps.append((start_ms, title))
        book.chapters = chaps


# ── document ─────────────────────────────────────────────────────────────────


def _audiobook_read(path: str) -> _Book:
    book = _Book()
    data = Path(path).read_bytes()
    ext = Path(path).suffix.lower()
    if data[4:8] == b"ftyp" or ext in (".m4b", ".m4a", ".mp4"):
        _mp4_read(data, book)
    elif data[:3] == b"ID3" or ext == ".mp3":
        tag_end = _id3_read(data, book)
        if not book.duration_ms:
            book.duration_ms = _mp3_duration_ms(data, tag_end)
    if not book.title and not book.chapters:
        _ffprobe(path, book)
    return book


def _audiobook_markdown(book: _Book, path: str) -> str:
    title = book.title or book.album or Path(path).stem
    out: List[str] = [f"# {title}", ""]
    if book.author:
        out += [f"*{book.author}*", ""]
    facts: List[Tuple[str, str]] = []
    if book.narrator and book.narrator != book.author:
        facts.append(("Narrator", book.narrator))
    if book.album and book.album != title:
        facts.append(("Album", book.album))
    if book.year:
        facts.append(("Year", book.year))
    if book.genre:
        facts.append(("Genre", book.genre))
    if book.duration_ms:
        facts.append(("Duration", _fmt_ms(book.duration_ms)))
    facts.append(("File", Path(path).name))
    out += ["| | |", "|---|---|"] + [f"| **{k}** | {v} |" for k, v in facts] + [""]
    if book.description:
        out += ["## Description", "", book.description.strip(), ""]
    out += ["## Chapters", ""]
    chapters = book.chapters or [(0, title)]
    for i, (start_ms, ctitle) in enumerate(chapters, start=1):
        out.append(f"### {i}. {ctitle}")
        out.append("")
        end = chapters[i][0] if i < len(chapters) else book.duration_ms
        span = f"{_fmt_ms(start_ms)}"
        if end and end > start_ms:
            span += f" – {_fmt_ms(end)} ({_fmt_ms(end - start_ms)})"
        out.append(f"Starts at {span}.")
        out.append("")
    out += [
        "---", "",
        "*This is an audiobook: the audio itself is not text. To read the narration, "
        "use **Tools ▸ Transcribe Audio** (offline Whisper speech-to-text) on this file.*",
        "",
    ]
    return "\n".join(out)


def _load_audiobook_full(path: str) -> Tuple[str, List[Tuple[str, str]], Dict[str, str]]:
    """``(markdown, chapters, metadata)`` for an M4B/MP3 audiobook."""
    try:
        book = _audiobook_read(path)
    except Exception as e:  # noqa: BLE001
        return f"# Audiobook Error\n\n```\n{e}\n```\n", [], {}
    md = _audiobook_markdown(book, path)
    chapters = [(f"{i}. {t}", f"t={start}") for i, (start, t) in enumerate(book.chapters, start=1)]
    meta: Dict[str, str] = {}
    if book.title:
        meta["title"] = book.title
    if book.author:
        meta["author"] = book.author
    if book.duration_ms:
        meta["duration"] = _fmt_ms(book.duration_ms)
    return md, chapters, meta


def _load_audiobook(path: str) -> str:
    return _load_audiobook_full(path)[0]
