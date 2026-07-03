"""Chaptered audiobook (M4B) export — chapter model + ffmpeg command building.

Pipeline
--------
1. Derive an ordered list of :class:`Chapter` (title + text) from the document's
   Markdown headings (fallback: one chapter for the whole document).
2. Synthesize each chapter to a temp WAV via the TTS backend and measure its
   duration.
3. Build an ffmpeg *ffmetadata* file with one ``[CHAPTER]`` block per chapter and
   a concat-demuxer list of the per-chapter WAVs.
4. ffmpeg concatenates + AAC-encodes to ``.m4b``, embedding chapter metadata and
   (if present) cover art.

Everything except the actual synthesis + ffmpeg subprocess call lives in the
**pure functions** below (:func:`derive_chapters`, :func:`build_chapters_metadata`,
:func:`build_concat_list`, :func:`build_ffmpeg_m4b_args`) so the interesting logic
is unit-testable without running ffmpeg or a speech engine.
"""
from ._runtime import *  # noqa: F401,F403

# Markdown ATX heading: 1–6 leading '#', a space, then the title text.  Setext
# headings (underlined with ==== / ----) are intentionally not treated as
# chapter breaks — ATX is what star's loaders emit for structured documents.
_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)

#: Default AAC bitrate for the audiobook track (spoken word needs little).
DEFAULT_M4B_BITRATE = "64k"

#: Cover-art metadata keys checked, in order, on ``document.metadata``.  Each maps
#: to a filesystem path to an image; the first present + existing wins.
_COVER_KEYS = ("cover", "cover_image", "cover_art", "cover_path")


@dataclass
class Chapter:
    """One audiobook chapter: a display *title* and the *text* to synthesize."""

    title: str
    text: str


# =============================================================================
# Chapter derivation (pure)
# =============================================================================


def derive_chapters(document: Any, *, fallback_title: str = "") -> "List[Chapter]":
    """Split *document* into chapters using its Markdown headings.

    Each ATX heading (``# …`` … ``###### …``) starts a new chapter whose body is
    the text up to the next heading.  Any text before the first heading becomes a
    leading chapter (titled from the document title / *fallback_title*).  When the
    document has no headings, a single chapter covering the whole text is
    returned.  Empty (whitespace-only) chapters are dropped, so a document that is
    all headings-and-blank still yields a usable list.

    The chapter *text* is taken from ``document.plain_text`` when available
    (that is what the TTS backend speaks); the heading lines themselves are kept
    as the first line of each chapter's spoken text so the title is read aloud.
    """
    plain = (getattr(document, "plain_text", "") or "").strip()
    markdown = getattr(document, "markdown", "") or ""
    title = (getattr(document, "title", "") or fallback_title or "Audiobook").strip()

    matches = list(_HEADING_RE.finditer(markdown))
    if not markdown.strip() or not matches:
        # No structure to split on: one chapter for everything we can speak.
        body = plain or _markdown_to_text(markdown)
        if not body.strip():
            return []
        return [Chapter(title=title or "Audiobook", text=body.strip())]

    chapters: List[Chapter] = []

    # Leading text before the first heading (a preface / abstract).
    lead = _markdown_to_text(markdown[: matches[0].start()]).strip()
    if lead:
        chapters.append(Chapter(title=title or "Introduction", text=lead))

    for i, m in enumerate(matches):
        head_title = m.group(2).strip()
        seg_start = m.start()
        seg_end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        seg_text = _markdown_to_text(markdown[seg_start:seg_end]).strip()
        if not seg_text:
            # Heading with no body — still worth a chapter so the title is spoken.
            seg_text = head_title
        if not seg_text.strip():
            continue
        chapters.append(Chapter(title=head_title or f"Chapter {len(chapters) + 1}", text=seg_text))

    if not chapters:
        body = plain or _markdown_to_text(markdown)
        if body.strip():
            chapters.append(Chapter(title=title or "Audiobook", text=body.strip()))
    return chapters


def _markdown_to_text(md: str) -> str:
    """Cheap Markdown → readable text for chapter bodies.

    Strips ATX heading markers and common inline emphasis so headings are spoken
    as plain words.  This is deliberately lightweight — chapter *timing* comes
    from the synthesized WAV, not from this text, so exactness is not critical.
    """
    out_lines: List[str] = []
    for line in md.splitlines():
        stripped = line.strip()
        hm = re.match(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*$", stripped)
        if hm:
            out_lines.append(hm.group(2).strip())
        else:
            out_lines.append(line)
    text = "\n".join(out_lines)
    # Drop the most common inline emphasis / code markers.
    text = re.sub(r"[*_`]{1,3}", "", text)
    return text


# =============================================================================
# ffmpeg metadata + command building (pure)
# =============================================================================


def build_chapters_metadata(
    chapters: "List[Chapter]",
    durations: "List[float]",
    *,
    album: str = "",
    artist: str = "",
) -> str:
    """Build an ffmpeg *ffmetadata* document string with per-chapter markers.

    *durations* are the chapters' lengths in seconds (same order/length as
    *chapters*).  Chapter timestamps are cumulative and expressed in
    milliseconds (``TIMEBASE=1/1000``), matching ffmpeg's metadata reader.
    """
    if len(chapters) != len(durations):
        raise ValueError("chapters and durations must be the same length")
    lines = [";FFMETADATA1"]
    if album:
        lines.append(f"album={_escape_meta(album)}")
    if artist:
        lines.append(f"artist={_escape_meta(artist)}")
    lines.append("genre=Audiobook")

    start_ms = 0
    for chapter, dur in zip(chapters, durations):
        dur_ms = max(1, int(round(dur * 1000)))
        end_ms = start_ms + dur_ms
        lines.append("[CHAPTER]")
        lines.append("TIMEBASE=1/1000")
        lines.append(f"START={start_ms}")
        lines.append(f"END={end_ms}")
        lines.append(f"title={_escape_meta(chapter.title)}")
        start_ms = end_ms
    return "\n".join(lines) + "\n"


def _escape_meta(value: str) -> str:
    """Escape ffmetadata special characters (``= ; # \\`` and newlines)."""
    out = []
    for ch in value:
        if ch in "=;#\\\n":
            out.append("\\" + (ch if ch != "\n" else "n"))
        else:
            out.append(ch)
    return "".join(out)


def build_concat_list(wav_paths: "List[str]") -> str:
    """Build the text body of an ffmpeg concat-demuxer list for *wav_paths*.

    Single-quotes each path and escapes embedded quotes, matching the escaping
    used by :mod:`star.video`.
    """
    lines = []
    for p in wav_paths:
        escaped = p.replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    return "\n".join(lines) + "\n"


def build_ffmpeg_m4b_args(
    ffmpeg: str,
    concat_path: str,
    metadata_path: str,
    out_path: str,
    *,
    cover_path: "Optional[str]" = None,
    bitrate: str = DEFAULT_M4B_BITRATE,
) -> "List[str]":
    """Assemble the ffmpeg argument list that builds the ``.m4b``.

    Inputs (in order): the concat list (audio), the ffmetadata file (chapters),
    and — when *cover_path* is given — the cover image.  The audio is AAC-encoded
    at *bitrate*; chapter metadata is mapped in; a cover image is attached as a
    still MJPEG video stream tagged as attached-picture so players show it.
    """
    cmd = [
        ffmpeg, "-y",
        "-f", "concat", "-safe", "0", "-i", concat_path,
        "-i", metadata_path,
    ]
    if cover_path:
        cmd += ["-i", cover_path]
    # Map streams: audio from input 0, chapter metadata from input 1.
    cmd += ["-map", "0:a", "-map_metadata", "1", "-map_chapters", "1"]
    if cover_path:
        cmd += ["-map", "2:v"]
    cmd += ["-c:a", "aac", "-b:a", bitrate]
    if cover_path:
        # Encode the cover as a single MJPEG frame flagged as the cover picture.
        cmd += ["-c:v", "mjpeg", "-disposition:v", "attached_pic"]
    # ``.m4b`` is an MP4 container; force it since the extension isn't .mp4/.m4a.
    cmd += ["-f", "mp4", "-movflags", "+faststart", out_path]
    return cmd


# =============================================================================
# ffmpeg / cover-art discovery (pure-ish helpers)
# =============================================================================


def find_ffmpeg() -> "Optional[str]":
    """Return the ffmpeg binary path (bundled > system PATH), or None."""
    try:
        from ._runtime import _FFMPEG_BUNDLED

        if _FFMPEG_BUNDLED.is_file():
            return str(_FFMPEG_BUNDLED)
    except Exception:
        pass
    return shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")


def cover_path_from_document(document: Any) -> "Optional[str]":
    """Return a filesystem path to cover art from ``document.metadata``, or None.

    Checks the keys in :data:`_COVER_KEYS`; the first that names an existing file
    wins.  Returns None when no usable cover is present.
    """
    meta = getattr(document, "metadata", None) or {}
    for key in _COVER_KEYS:
        val = meta.get(key)
        if val and isinstance(val, str):
            try:
                if Path(val).is_file():
                    return val
            except OSError:
                continue
    return None
