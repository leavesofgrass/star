"""Document / WordPos data model and word-map builder."""
import bisect

from .._runtime import *  # noqa: F401,F403


@dataclass
class WordPos:
    """Maps one word in the TTS plain-text to a position in the display."""

    word: str  # the word text (stripped of punctuation)
    tts_offset: int  # char offset in the TTS plain-text string
    tts_len: int  # length in the TTS string
    disp_line: int  # rendered display line index
    disp_col: int  # starting column in that display line


@dataclass
class Document:
    path: str = ""
    title: str = ""
    markdown: str = ""  # markdown for display
    plain_text: str = ""  # clean text for TTS
    word_map: List[WordPos] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)
    format: str = ""  # detected format
    encoding: str = "utf-8"
    # Chapter list for EPUB/DAISY navigation: [(title, href, word_idx), ...]
    chapters: List[Tuple[str, str, int]] = field(default_factory=list)


# Word tokenizer for the TTS plain-text.  Compiled once at import (was
# per-call): the pattern is constant, so hoisting it removes a re.compile on
# every _build_word_map call without changing tokenization.
_WORD_TOKEN_RE = re.compile(r"\b\w[\w'-]*")


def _build_word_map(plain_text: str, rendered_lines: List[str]) -> List[WordPos]:
    """Build a word map that links TTS character offsets to display positions.

    Strategy: tokenize plain text into words; for each word, scan the rendered
    lines to find a matching occurrence.  Uses a rolling search start to keep
    the match order correct even for repeated words.

    Words whose only occurrence in the display is *before* the current search
    position (e.g. column-header names repeated in structured table-row
    narration) are assigned the last confirmed forward position so the
    highlight advances linearly rather than jumping backward.

    Performance
    -----------
    The output is byte-for-byte identical to the previous implementation, but
    this version is effectively O(n) rather than O(n²) on large documents.
    The transformation rests on one observation: the old algorithm's forward
    "scan lines from ``search_line`` to end, first ``.find`` hit wins" is
    exactly a single substring search over the display text — a word token
    never contains a newline, so a match in ``"\n".join(lowered)`` is always
    contained within one line, and the first blob match at or after the rolling
    cursor is the first line-scan match.  So:

    * Each display line is lower-cased **once** into ``lowered`` and joined into
      one ``blob`` (the previous code re-lowered every candidate line for every
      token scanned, and its primary/extended forward windows re-walked lines
      in a Python loop per token).
    * The forward match is a single ``blob.find(word_lower, cursor)`` — one C
      call instead of a per-line Python loop — with the absolute offset mapped
      back to ``(line, col)`` via a precomputed line-start table and ``bisect``.
    * The backward "does it exist anywhere?" fallback is a single ``in blob``.

    Both the primary and the fallback are therefore ~O(len(word)); the previous
    code re-scanned to end-of-document (or the whole document) in Python for
    every token that did not match ahead — the quadratic blow-up on structured
    docs that repeat header words in row narration.
    """
    words: List[WordPos] = []
    # Lower-case each display line exactly once (previously recomputed per
    # token — the dominant constant-factor cost on large documents).
    lowered = [ln.lower() for ln in rendered_lines]
    n_lines = len(lowered)
    # ``blob`` is the display text, lines joined by newlines; ``line_start[i]``
    # is the absolute offset of line ``i`` within ``blob``.  Searching ``blob``
    # forward from an absolute cursor reproduces the old line-by-line forward
    # scan exactly: a word token has no newline, so every match lies inside a
    # single line, and starting the search at ``line_start[search_line] +
    # search_col`` enforces the same "no earlier occurrence on the start line"
    # column constraint the old inner loop did.
    blob = "\n".join(lowered)
    line_start: List[int] = []
    acc = 0
    for ln in lowered:
        line_start.append(acc)
        acc += len(ln) + 1  # +1 for the joining "\n"

    search_line = 0  # rolling hint: don't search lines before this
    search_col = 0  # column offset on search_line; avoids re-matching an
    # earlier occurrence of a repeated word on the same line
    last_good_line = 0  # last display line from a forward-matched word
    last_good_col = 0

    for m in _WORD_TOKEN_RE.finditer(plain_text):
        word = m.group()
        offset = m.start()
        word_lower = word.lower()

        found_line = last_good_line
        found_col = last_good_col
        matched = False

        # Forward search from the rolling cursor to end-of-document, in one C
        # call.  ``cursor`` is the absolute blob offset of (search_line,
        # search_col); the first hit at or after it is the first line-scan hit
        # because the needle cannot straddle a newline.  On the start line this
        # begins from search_col so a word that appeared earlier on that line is
        # never re-matched (keeps the highlight from jumping backward for common
        # words like "the" / "a" that repeat within a line).
        if n_lines:
            # Absolute blob offset of (search_line, search_col).  If search_col
            # runs past the end of the start line (possible only when a token's
            # length changes under .lower(), e.g. U+0130), the old per-line
            # ``.find`` skipped that line and resumed at the next line's col 0;
            # replicate that so the two implementations stay bit-identical.
            if search_col <= len(lowered[search_line]):
                cursor = line_start[search_line] + search_col
            elif search_line + 1 < n_lines:
                cursor = line_start[search_line + 1]
            else:
                cursor = len(blob) + 1  # past EOF → no forward match
            pos = blob.find(word_lower, cursor)
            if pos >= 0:
                # Map the absolute offset back to (line, col).  ``line_start`` is
                # sorted, so bisect gives the containing line in O(log n_lines).
                li = bisect.bisect_right(line_start, pos) - 1
                found_line = li
                found_col = pos - line_start[li]
                matched = True

        if not matched:
            # Backward-only fallback: the word exists but only *before* the
            # current search position (e.g. a table column header repeated in
            # row narration).  We only need to know that it exists somewhere so
            # the token still counts as matched; found_line/col stay at
            # last_good_* so the highlight does not regress.  ``in blob`` is
            # exactly the old whole-document per-line ``.find`` scan.
            if word_lower in blob:
                matched = True  # word exists — audio is fine

        words.append(
            WordPos(
                word=word,
                tts_offset=offset,
                tts_len=len(word),
                disp_line=found_line,
                disp_col=found_col,
            )
        )
        # Only advance the search position for genuine forward matches.
        # Remove the old "-2" look-back: that was intended as a robustness
        # margin but it caused common words to cascade-match 2 lines before
        # their actual display position, making the highlight appear stuck.
        if matched and found_line >= search_line:
            search_line = found_line
            search_col = found_col + len(word)
            last_good_line = found_line
            last_good_col = found_col

    return words
