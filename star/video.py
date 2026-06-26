"""Sentence-level karaoke video export.

Pipeline
--------
1. Synthesize document plain text → WAV (via the provided TTS backend).
2. Compute sentence spans + proportional timing cues.
3. Render one PNG frame per sentence (current sentence highlighted, rest dimmed).
   - Qt offscreen (QTextDocument → QImage) when Qt is available.
   - Pillow fallback when Qt is absent.
4. ffmpeg concat-demuxer (per-frame duration) + WAV + soft SRT → MP4.

All rendering runs on the caller's thread; wire to a background thread in the
GUI/TUI to keep the UI responsive.
"""
from ._runtime import *  # noqa: F401,F403
from .formats import Exporter

# Lazy availability — not literal True/False assignments, so not caught by the
# guard scanner; registered in diagnostics.py as probe-kind entries.
_PILLOW_AVAILABLE = _module_available("PIL")

# Holds the QGuiApplication used for offscreen frame rendering.  A QGuiApplication
# (or the GUI's QApplication) must exist before any QTextDocument/QPainter text
# rendering, otherwise the font subsystem is uninitialised and Qt hard-crashes
# the process on Windows.  Kept at module scope so the Python wrapper outlives a
# single render call and is reused across frames (instance() finds it again).
_QT_APP = None


# =============================================================================
# Public API
# =============================================================================


def export_video(document: Any, settings: Any, out_path: str, tts_backend: Any = None) -> Dict[str, Any]:
    """Export *document* as a karaoke MP4 video.

    Parameters
    ----------
    document:    a ``Document`` instance with ``plain_text`` populated.
    settings:    a ``Settings`` instance.
    out_path:    destination ``.mp4`` path (created or overwritten).
    tts_backend: optional TTS backend; if None a ``Pyttsx3Backend`` is created
                 from *settings* (useful for CLI / TUI calls).

    Returns a dict with keys ``path``, ``cues``, ``duration`` on success, or
    ``error`` (str) on failure.
    """
    plain = (document.plain_text or "").strip()
    if not plain:
        return {"error": "Document has no readable text"}

    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return {"error": "ffmpeg not found — install ffmpeg and put it on PATH"}

    vid = settings.get("video") or {}
    width, height = _parse_resolution(vid.get("resolution", "1280x720"))
    subtitle_mode = vid.get("subtitles", "soft")
    theme = settings.get("theme", "dark")

    import tempfile as _tmp
    with _tmp.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        wav_path = str(td / "audio.wav")

        # ── 1. Synthesise WAV ──────────────────────────────────────────────
        backend = tts_backend
        if backend is None:
            from .tts import Pyttsx3Backend
            backend = Pyttsx3Backend(
                rate=settings.get("tts_rate", 265),
                volume=settings.get("tts_volume", 1.0),
                voice=settings.get("tts_voice", ""),
            )
        try:
            backend.export_to_wav(plain, wav_path)
        except Exception as e:
            return {"error": f"TTS synthesis failed: {e}"}

        # ── 2. Timing: sentence spans + proportional cues ─────────────────
        from .tts import _wav_duration_seconds
        duration = _wav_duration_seconds(wav_path)
        if duration <= 0:
            return {"error": "Could not determine audio duration from WAV"}

        spans = _sentence_spans(plain)
        if not spans:
            return {"error": "No sentences detected in document text"}

        cues = _spans_to_cues(plain, spans, duration)

        # ── 3. Render frames ───────────────────────────────────────────────
        frame_paths: List[Tuple[str, float]] = []
        for i, (start, end, dur) in enumerate(cues):
            png_path = str(td / f"frame_{i:05d}.png")
            hi_start, hi_end = spans[i]
            ok = _render_frame(plain, hi_start, hi_end, png_path, width, height, theme)
            if not ok:
                return {"error": "Frame rendering failed (install PyQt6 or Pillow)"}
            frame_paths.append((png_path, dur))

        # ── 4. Write SRT ───────────────────────────────────────────────────
        srt_path = str(td / "subs.srt")
        from .tts import _format_subtitles
        srt_cues = [(s, s + d, plain[hi:ho]) for (s, _, d), (hi, ho) in zip(cues, spans)]
        Path(srt_path).write_text(_format_subtitles(srt_cues, "srt"), encoding="utf-8")

        # ── 5. Build concat list ──────────────────────────────────────────
        concat_path = str(td / "concat.txt")
        def _escape_concat(p):
            return p.replace("'", "'\\''")

        lines = []
        for png, dur in frame_paths:
            escaped = _escape_concat(png)
            lines.append("file '{0}'\nduration {1:.6f}".format(escaped, dur))
        # ffmpeg concat needs the last file repeated without duration
        if frame_paths:
            escaped = _escape_concat(frame_paths[-1][0])
            lines.append("file '{0}'\n".format(escaped))
        Path(concat_path).write_text("\n".join(lines), encoding="utf-8")

        # ── 6. ffmpeg ─────────────────────────────────────────────────────
        argv = _build_ffmpeg(ffmpeg, concat_path, wav_path,
                             srt_path if subtitle_mode == "soft" else None,
                             out_path)
        result = subprocess.run(argv, capture_output=True)
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            return {"error": f"ffmpeg failed:\n{stderr[:2000]}"}

        return {"path": out_path, "cues": len(cues), "duration": duration}


class MP4Exporter(Exporter):
    """Export the document as a sentence-level karaoke MP4 (wraps export_video)."""

    name = "mp4"

    @classmethod
    def extensions(cls) -> frozenset[str]:
        return frozenset({".mp4"})

    @classmethod
    def available(cls) -> bool:
        # Needs ffmpeg; a frame renderer (Qt or Pillow) is checked at render time.
        return bool(_find_ffmpeg())

    def export(self, document, path, **kwargs) -> None:
        settings = kwargs.get("settings")
        if settings is None:
            raise ValueError("MP4 export requires a `settings` keyword argument")
        result = export_video(
            document, settings, str(path), tts_backend=kwargs.get("backend")
        )
        if result.get("error"):
            raise RuntimeError(result["error"])


# =============================================================================
# Sentence span computation
# =============================================================================


def _sentence_spans(plain_text: str) -> List[Tuple[int, int]]:
    """Return ``(start, end)`` character spans for each sentence in *plain_text*.

    Reuses ``_SENTENCE_SPLIT_RE`` from ``_runtime`` for sentence boundary
    detection — same regex used by subtitle-cue building.
    """
    spans: List[Tuple[int, int]] = []
    prev_end = 0
    for m in _SENTENCE_SPLIT_RE.finditer(plain_text):
        seg_start, seg_end = prev_end, m.start()
        s = seg_start
        e = seg_end
        while s < e and plain_text[s].isspace():
            s += 1
        while e > s and plain_text[e - 1].isspace():
            e -= 1
        if s < e:
            spans.append((s, e))
        prev_end = m.end()
    # Trailing sentence
    s, e = prev_end, len(plain_text)
    while s < e and plain_text[s].isspace():
        s += 1
    while e > s and plain_text[e - 1].isspace():
        e -= 1
    if s < e:
        spans.append((s, e))
    return spans


def _spans_to_cues(
    plain_text: str,
    spans: List[Tuple[int, int]],
    total_duration: float,
) -> List[Tuple[float, float, float]]:
    """Convert sentence spans to ``(start_s, end_s, duration_s)`` timing cues.

    Duration is apportioned by sentence length (characters + 1).
    """
    if not spans or total_duration <= 0:
        return []
    weights = [max(1, hi - lo + 1) for lo, hi in spans]
    total_w = float(sum(weights))
    cues: List[Tuple[float, float, float]] = []
    acc = 0.0
    for w in weights:
        start = total_duration * acc / total_w
        acc += w
        end = total_duration * acc / total_w
        cues.append((start, end, end - start))
    return cues


# =============================================================================
# Frame rendering
# =============================================================================


def _render_frame(
    plain_text: str,
    hi_start: int,
    hi_end: int,
    png_path: str,
    width: int,
    height: int,
    theme: str,
) -> bool:
    """Render a single frame to *png_path*; return True on success.

    Tries Qt offscreen first, then Pillow; returns False when neither works.
    """
    if _try_render_qt(plain_text, hi_start, hi_end, png_path, width, height, theme):
        return True
    if _try_render_pillow(plain_text, hi_start, hi_end, png_path, width, height, theme):
        return True
    return False


def _try_render_qt(
    plain_text: str,
    hi_start: int,
    hi_end: int,
    png_path: str,
    width: int,
    height: int,
    theme: str,
) -> bool:
    """Render via Qt offscreen.  Returns False when Qt is unavailable."""
    try:
        from PyQt6.QtGui import (  # type: ignore[import]
            QTextDocument, QImage, QPainter, QTextCursor,
            QTextCharFormat, QColor, QFont, QGuiApplication,
        )
        from PyQt6.QtCore import QSizeF  # type: ignore[import]
    except ImportError:
        try:
            from PyQt5.QtGui import (  # type: ignore[import]
                QTextDocument, QImage, QPainter, QTextCursor,
                QTextCharFormat, QColor, QFont, QGuiApplication,
            )
            from PyQt5.QtCore import QSizeF  # type: ignore[import]
        except ImportError:
            return False

    # A QGuiApplication must exist before any text rendering: QTextDocument/
    # QPainter need the GUI font subsystem.  When star exports video headlessly
    # (no GUI running) none exists, and rendering hard-crashes the process on
    # Windows (a Qt fast-fail, 0xC0000409).  Reuse the GUI's running app (its
    # QApplication is a QGuiApplication subclass) when there is one — rendering
    # off the main thread against an existing app is fine.  Otherwise create a
    # minimal app, but ONLY on the main thread: a QGuiApplication constructed on
    # a worker thread (e.g. the TUI's export thread) segfaults at teardown, so
    # there we return False and let the caller fall back to the Pillow renderer.
    global _QT_APP
    try:
        if QGuiApplication.instance() is None:
            if threading.current_thread() is not threading.main_thread():
                return False
            _QT_APP = QGuiApplication([sys.argv[0] if sys.argv else "star"])
    except Exception:
        return False

    dark = theme not in ("light", "sepia")
    bg = QColor(30, 30, 30) if dark else QColor(245, 245, 245)
    fg_dim = QColor(90, 90, 90) if dark else QColor(180, 180, 180)
    fg_hi = QColor(240, 240, 240) if dark else QColor(20, 20, 20)
    hl_bg = QColor(0, 60, 130) if dark else QColor(200, 220, 255)

    try:
        td = QTextDocument()
        td.setPlainText(plain_text)
        td.setPageSize(QSizeF(width - 80, height))

        font = QFont("Segoe UI" if sys.platform == "win32" else "DejaVu Sans", 16)
        td.setDefaultFont(font)

        # Dim everything first
        cursor = QTextCursor(td)
        cursor.select(QTextCursor.SelectionType.Document)
        dim_fmt = QTextCharFormat()
        dim_fmt.setForeground(fg_dim)
        cursor.mergeCharFormat(dim_fmt)

        # Highlight the active sentence
        cursor.setPosition(hi_start)
        cursor.setPosition(min(hi_end, len(plain_text)), QTextCursor.MoveMode.KeepAnchor)
        hi_fmt = QTextCharFormat()
        hi_fmt.setForeground(fg_hi)
        hi_fmt.setBackground(hl_bg)
        cursor.mergeCharFormat(hi_fmt)

        img = QImage(width, height, QImage.Format.Format_RGB32)
        img.fill(bg)
        painter = QPainter(img)
        painter.translate(40, 40)
        td.drawContents(painter)
        painter.end()

        img.save(png_path, "PNG")
        return True
    except Exception:
        return False


def _try_render_pillow(
    plain_text: str,
    hi_start: int,
    hi_end: int,
    png_path: str,
    width: int,
    height: int,
    theme: str,
) -> bool:
    """Render via Pillow.  Returns False when Pillow is unavailable."""
    if not _PILLOW_AVAILABLE:
        return False
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore[import]

        dark = theme not in ("light", "sepia")
        bg_col = (30, 30, 30) if dark else (245, 245, 245)
        dim_col = (90, 90, 90) if dark else (180, 180, 180)
        hi_col = (240, 240, 240) if dark else (20, 20, 20)
        hl_bg = (0, 60, 130) if dark else (200, 220, 255)

        img = Image.new("RGB", (width, height), bg_col)
        draw = ImageDraw.Draw(img)

        font_size = max(14, height // 28)
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()

        margin = 50
        line_h = int(font_size * 1.6)
        max_w = width - 2 * margin

        # Tokenize into words with their char offsets
        words: List[Tuple[str, int, int]] = []
        for m in re.finditer(r"\S+", plain_text):
            words.append((m.group(), m.start(), m.end()))

        # Word-wrap into lines
        lines: List[List[Tuple[str, int, int]]] = []
        cur: List[Tuple[str, int, int]] = []
        cur_w = 0
        for word, ws, we in words:
            try:
                bbox = draw.textbbox((0, 0), word + " ", font=font)
                ww = bbox[2] - bbox[0]
            except AttributeError:
                ww = len(word) * (font_size // 2)
            if cur and cur_w + ww > max_w:
                lines.append(cur)
                cur = [(word, ws, we)]
                cur_w = ww
            else:
                cur.append((word, ws, we))
                cur_w += ww
        if cur:
            lines.append(cur)

        total_h = len(lines) * line_h
        y = max(margin, (height - total_h) // 2)

        for line in lines:
            x = margin
            for word, ws, we in line:
                in_hi = not (we <= hi_start or ws >= hi_end)
                try:
                    bbox = draw.textbbox((0, 0), word + " ", font=font)
                    ww = bbox[2] - bbox[0]
                except AttributeError:
                    ww = len(word) * (font_size // 2)
                if in_hi:
                    draw.rectangle([x - 2, y - 2, x + ww, y + line_h], fill=hl_bg)
                draw.text((x, y), word, font=font, fill=hi_col if in_hi else dim_col)
                x += ww
            y += line_h

        img.save(png_path, "PNG")
        return True
    except Exception:
        return False


# =============================================================================
# ffmpeg helpers
# =============================================================================


def _find_ffmpeg() -> Optional[str]:
    """Return the ffmpeg binary path (bundled > system PATH)."""
    try:
        from ._runtime import _FFMPEG_BUNDLED
        if _FFMPEG_BUNDLED.is_file():
            return str(_FFMPEG_BUNDLED)
    except Exception:
        pass
    return shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")


def _build_ffmpeg(
    ffmpeg: str,
    concat_path: str,
    wav_path: str,
    srt_path: Optional[str],
    out_path: str,
) -> List[str]:
    """Assemble the ffmpeg concat command for building the MP4."""
    cmd = [
        ffmpeg, "-y",
        "-f", "concat", "-safe", "0", "-i", concat_path,
        "-i", wav_path,
    ]
    if srt_path:
        cmd += ["-i", srt_path]
    cmd += [
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
    ]
    if srt_path:
        cmd += ["-c:s", "mov_text", "-map", "0:v", "-map", "1:a", "-map", "2:s"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path]
    return cmd


def _parse_resolution(res: str) -> Tuple[int, int]:
    """Parse ``'WxH'`` or ``'W×H'`` → ``(W, H)``; default 1280×720."""
    try:
        parts = re.split(r"[x×X]", res.strip(), 1)
        w, h = int(parts[0]), int(parts[1])
        # Force even dimensions (required by libx264)
        return (w if w % 2 == 0 else w + 1, h if h % 2 == 0 else h + 1)
    except Exception:
        return (1280, 720)
