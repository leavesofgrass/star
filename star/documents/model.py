"""Document / WordPos data model and word-map builder."""
import bisect
import difflib

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


def _align_word_offsets(
    spoken: List[str], rendered: List[Tuple[str, int]]
) -> List[int]:
    """Map each spoken word to the character offset of its rendered occurrence.

    *spoken* is the lower-cased TTS word stream; *rendered* is
    ``(word_lower, char_offset)`` for every token of the rendered display
    text.  Returns one offset per spoken word, ``-1`` where no occurrence was
    found.  Shared by the TUI word map (:func:`_build_word_map`, offsets into
    the joined display lines) and the Qt GUI word→char map
    (``star.gui.mixin_document``, offsets into the editor text).

    This is a real sequence alignment (difflib), not a rolling substring
    search.  The spoken stream and the rendered text diverge legitimately in
    both directions — structured table narration adds spoken-only words
    ("Table with 3 columns", "Row 1", "… is …"), and skipped code blocks are
    rendered-only — and a rolling ``find`` derails on either: a spoken-only
    word like "with" matches some *later* rendered occurrence, drags the
    cursor forward past real content, and every word after that is pinned to
    a stale fallback position (the table-onward highlight breakage).
    Alignment instead matches the two token streams as sequences, so
    divergent runs are simply left unmatched and everything around them
    stays exact.

    Runs in re-anchored chunks: each chunk is aligned independently and the
    cursor resumes at the end of the last *matched* block, keeping the cost
    ~O(n · CHUNK) instead of difflib's worst-case O(n²) on book-sized text
    while remaining exact for local divergences (tables, code blocks, figure
    narration are all far smaller than a chunk).
    """
    n, m = len(spoken), len(rendered)
    r_words = [w for w, _ in rendered]
    # Fast path: the streams already agree token-for-token (plain prose with
    # no structural narration) — the alignment is the identity.
    if spoken == r_words:
        return [off for _, off in rendered]
    offsets = [-1] * n
    CHUNK = 2000
    PAD = 500
    si = ri = 0
    while si < n and ri < m:
        s_hi = min(n, si + CHUNK)
        r_hi = min(m, ri + CHUNK + PAD)
        sm = difflib.SequenceMatcher(
            None, spoken[si:s_hi], r_words[ri:r_hi], autojunk=False
        )
        blocks = [b for b in sm.get_matching_blocks() if b.size]
        if not blocks:
            # Pathological chunk (no single common token): skip half a chunk
            # on both sides rather than stall — later chunks re-anchor.
            si += CHUNK // 2
            ri += CHUNK // 2
            continue
        for a, b, size in blocks:
            for k in range(size):
                offsets[si + a + k] = rendered[ri + b + k][1]
        last = blocks[-1]
        new_si = si + last.a + last.size
        new_ri = ri + last.b + last.size
        if new_si <= si:  # guarantee forward progress
            new_si = s_hi
        si, ri = new_si, new_ri
    return offsets


def _build_word_map(plain_text: str, rendered_lines: List[str]) -> List[WordPos]:
    """Build a word map that links TTS character offsets to display positions.

    The spoken plain text and the rendered display legitimately diverge —
    structured table narration inserts spoken-only words, skipped code blocks
    are display-only — so the two token streams are sequence-aligned (see
    :func:`_align_word_offsets`, the same aligner the Qt GUI uses for its
    word→char map) rather than matched with a rolling substring search, which
    derailed on divergence: a narration word matched some later display
    occurrence, dragged the cursor past real content, and every word from the
    first table to document end was pinned to a stale ``disp_line``.

    Spoken words with no display counterpart borrow the position of the next
    aligned word — the highlight parks at the content the narration describes
    — falling back to the previous one at the tail, and to line 0 / column 0
    when nothing aligns at all (e.g. an empty display).  Matched blocks are
    monotone in both streams and the gap-fill copies neighbouring positions,
    so ``disp_line`` never decreases across the map (the caret and highlight
    consumers bisect on that ordering).
    """
    tokens = list(_WORD_TOKEN_RE.finditer(plain_text))
    if not tokens:
        return []
    # The display as one string: a word token never contains a newline, so
    # every display token lies inside a single line and its absolute blob
    # offset maps back to (line, col) via the line-start table + bisect.
    blob = "\n".join(rendered_lines)
    line_start: List[int] = []
    acc = 0
    for ln in rendered_lines:
        line_start.append(acc)
        acc += len(ln) + 1  # +1 for the joining "\n"

    spoken = [m.group().lower() for m in tokens]
    rendered = [
        (m.group().lower(), m.start()) for m in _WORD_TOKEN_RE.finditer(blob)
    ]
    offsets = _align_word_offsets(spoken, rendered)
    # Gap-fill: narration-only words borrow the next aligned offset, trailing
    # ones the previous, and a fully-unaligned document parks at offset 0.
    nxt = -1
    for i in range(len(offsets) - 1, -1, -1):
        if offsets[i] >= 0:
            nxt = offsets[i]
        elif nxt >= 0:
            offsets[i] = nxt
    prev = 0
    for i, off in enumerate(offsets):
        if off >= 0:
            prev = off
        else:
            offsets[i] = prev

    words: List[WordPos] = []
    for m, off in zip(tokens, offsets):
        if line_start:
            li = bisect.bisect_right(line_start, off) - 1
            col = off - line_start[li]
        else:
            li = col = 0  # no display at all — audio still plays
        words.append(
            WordPos(
                word=m.group(),
                tts_offset=m.start(),
                tts_len=len(m.group()),
                disp_line=li,
                disp_col=col,
            )
        )
    return words
