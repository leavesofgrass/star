"""Document / WordPos data model and word-map builder."""
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


def _build_word_map(plain_text: str, rendered_lines: List[str]) -> List[WordPos]:
    """Build a word map that links TTS character offsets to display positions.

    Strategy: tokenize plain text into words; for each word, scan the rendered
    lines to find a matching occurrence.  Uses a rolling search start to keep
    the match order correct even for repeated words.

    Words whose only occurrence in the display is *before* the current search
    position (e.g. column-header names repeated in structured table-row
    narration) are assigned the last confirmed forward position so the
    highlight advances linearly rather than jumping backward.
    """
    words: List[WordPos] = []
    token_re = re.compile(r"\b\w[\w'-]*")
    search_line = 0  # rolling hint: don't search lines before this
    search_col = 0  # column offset on search_line; avoids re-matching an
    # earlier occurrence of a repeated word on the same line
    last_good_line = 0  # last display line from a forward-matched word
    last_good_col = 0

    for m in token_re.finditer(plain_text):
        word = m.group()
        offset = m.start()
        word_lower = word.lower()

        found_line = last_good_line
        found_col = last_good_col
        matched = False

        # Primary forward search.  On the starting line we begin the column
        # search from search_col so we never match a word that appeared
        # earlier on the same line (prevents the highlight jumping backward
        # for common words like "the" / "a" that repeat within a line).
        for li in range(search_line, min(search_line + 80, len(rendered_lines))):
            start = search_col if li == search_line else 0
            col = rendered_lines[li].lower().find(word_lower, start)
            if col >= 0:
                found_line = li
                found_col = col
                matched = True
                break

        if not matched:
            # Extended forward scan beyond the 80-line window.
            for li in range(
                min(search_line + 80, len(rendered_lines)), len(rendered_lines)
            ):
                col = rendered_lines[li].lower().find(word_lower, 0)
                if col >= 0:
                    found_line = li
                    found_col = col
                    matched = True
                    break

        if not matched:
            # Backward-only fallback: word exists but only before the current
            # search position (e.g. a table column header repeated in row
            # narration).  Keep found_line/col at last_good_* so the highlight
            # does not regress.
            for li, rline in enumerate(rendered_lines):
                col = rline.lower().find(word_lower, 0)
                if col >= 0:
                    matched = True  # word exists — audio is fine
                    break  # found_line/found_col stay at last_good_*

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
