"""Subtitle cue construction and SRT/VTT formatting."""
from .._runtime import *  # noqa: F401,F403
from .audio import _wav_duration_seconds


def _fmt_subtitle_time(seconds: float, vtt: bool = False) -> str:
    """Format *seconds* as an SRT (``HH:MM:SS,mmm``) or VTT (``HH:MM:SS.mmm``)
    timestamp."""
    seconds = max(0.0, seconds)
    ms = int(round(seconds * 1000))
    hh, ms = divmod(ms, 3_600_000)
    mm, ms = divmod(ms, 60_000)
    ss, ms = divmod(ms, 1000)
    sep = "." if vtt else ","
    return f"{hh:02d}:{mm:02d}:{ss:02d}{sep}{ms:03d}"


def _build_subtitle_cues(
    text: str,
    duration: float,
    word_level: bool = False,
    max_words: int = 12,
    max_chars: int = 90,
) -> List[Tuple[float, float, str]]:
    """Return ``(start_s, end_s, caption_text)`` cues spanning *duration*.

    Audio duration is apportioned to whitespace-delimited tokens by length
    (characters + 1) so longer words occupy proportionally more time.  In
    sentence mode tokens are grouped into readable caption lines that break at
    sentence boundaries (or when *max_words* / *max_chars* is reached); in
    word mode every token becomes its own cue.
    """
    tokens = [(m.group(), m.start(), m.end()) for m in re.finditer(r"\S+", text)]
    if not tokens or duration <= 0:
        return []

    weights = [len(tok) + 1 for tok, _s, _e in tokens]
    total_w = float(sum(weights)) or 1.0
    # Per-token start/end times from the cumulative weight fraction.
    spans: List[Tuple[float, float]] = []
    acc = 0
    for w in weights:
        start = duration * acc / total_w
        acc += w
        spans.append((start, duration * acc / total_w))

    if word_level:
        return [(spans[i][0], spans[i][1], tokens[i][0]) for i in range(len(tokens))]

    # Character offsets at which a new sentence begins.
    boundaries = {m.end() for m in _SENTENCE_SPLIT_RE.finditer(text)}

    cues: List[Tuple[float, float, str]] = []
    cur_words: List[str] = []
    cur_start = spans[0][0]
    cur_chars = 0
    for i, (tok, s_char, _e_char) in enumerate(tokens):
        starts_sentence = s_char in boundaries
        too_long = cur_words and (
            len(cur_words) >= max_words or cur_chars + len(tok) + 1 > max_chars
        )
        if cur_words and (starts_sentence or too_long):
            cues.append((cur_start, spans[i - 1][1], " ".join(cur_words)))
            cur_words = []
            cur_start = spans[i][0]
            cur_chars = 0
        cur_words.append(tok)
        cur_chars += len(tok) + 1
    if cur_words:
        cues.append((cur_start, spans[-1][1], " ".join(cur_words)))
    return cues


def _format_subtitles(cues: List[Tuple[float, float, str]], fmt: str = "srt") -> str:
    """Render *cues* as SRT or WebVTT text."""
    vtt = fmt.lower() == "vtt"
    out: List[str] = []
    if vtt:
        out.append("WEBVTT")
        out.append("")
    for i, (start, end, caption) in enumerate(cues, 1):
        # SRT requires end > start; nudge zero-length cues so players accept them.
        if end <= start:
            end = start + 0.05
        if not vtt:
            out.append(str(i))
        out.append(
            f"{_fmt_subtitle_time(start, vtt)} --> {_fmt_subtitle_time(end, vtt)}"
        )
        out.append(caption)
        out.append("")
    return "\n".join(out).strip() + "\n"


def _generate_subtitles(
    text: str, wav_path: str, fmt: str = "srt", word_level: bool = False
) -> str:
    """Build an SRT/VTT subtitle document for *text* synchronized to the audio
    in *wav_path*.  Returns "" when timing cannot be estimated."""
    duration = _wav_duration_seconds(wav_path)
    cues = _build_subtitle_cues(text, duration, word_level=word_level)
    if not cues:
        return ""
    return _format_subtitles(cues, fmt)
