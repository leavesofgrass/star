"""Hypothesis property tests for the document loaders and word-map builder.

Where ``tests/test_documents.py`` pins specific loader outputs with hand-picked
inputs, this module asserts *invariants* that must hold for **every** input
Hypothesis can generate:

  * ``_build_word_map`` produces a map whose display positions are in-bounds for
    the rendered lines it was given, whose TTS offsets are non-decreasing, and
    which never invents or drops a word relative to the source tokenization;
  * ``render_markdown`` yields a valid line structure — a list of lists of
    ``(text, role)`` string/str pairs — for arbitrary Markdown-ish text and any
    sane wrap width, and every word map built over that render stays in-bounds;
  * ``_load_csv_tsv`` round-trips arbitrary cell grids into a Markdown table with
    a consistent column count on every row and with the delimiter-sensitive pipe
    always escaped, so a cell value can never forge an extra column;
  * ``_load_html_str`` never raises and always returns a string.

These are pure functions over strings/lists — no Qt, no curses, no files beyond
a couple of temp CSVs — so the module runs on every CI leg.  hypothesis is a
declared ``test`` extra; the whole module is skipped if it is somehow absent.
"""
import csv
import importlib.util

import pytest

from star.documents import _build_word_map, _load_csv_tsv, _load_html_str
from star.render import render_markdown

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("hypothesis") is None, reason="hypothesis not installed"
)

if importlib.util.find_spec("hypothesis") is not None:
    from hypothesis import HealthCheck, given, settings
    from hypothesis import strategies as st
else:  # pragma: no cover - collection-time guard only
    st = None  # type: ignore[assignment]

# ── Strategies ───────────────────────────────────────────────────────────────

# Prose-ish text: letters, digits, spaces, newlines and a little punctuation —
# enough variety to exercise the tokenizer without generating pathological
# control characters that neither the renderer nor a real document would see.
_TEXT = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs"),
        whitelist_characters=" \n\t.,!?-'#*`[]()>|",
    ),
    max_size=400,
)

# CSV cell values: keep them free of the structural characters (newline, CR, and
# the raw delimiter) that `csv.writer` would legitimately quote — we are testing
# the *table* invariants of the loader, not the stdlib writer's quoting.  Pipes
# and commas are deliberately *included* so the escaping path is exercised.
_CELL = st.text(
    alphabet=st.characters(
        blacklist_characters="\r\n",
        whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po", "Sm"),
    ),
    max_size=12,
)
_ROW = st.lists(_CELL, min_size=1, max_size=5)
_GRID = st.lists(_ROW, min_size=1, max_size=8)


def _flatten(rendered):
    """Collapse rendered lines to the flat strings _build_word_map consumes."""
    return ["".join(t for t, _ in line) for line in rendered]


# ── _build_word_map invariants ───────────────────────────────────────────────


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(_TEXT)
def test_word_map_offsets_are_sorted_and_in_bounds(text):
    """Every WordPos maps a token of *text* to a valid slice, and the TTS
    offsets march forward (a backward jump would rewind the karaoke cursor)."""
    rendered = render_markdown(text, 60)
    flat = _flatten(rendered)
    wm = _build_word_map(text, flat)

    prev_offset = -1
    for wp in wm:
        # Offsets are non-decreasing across the map.
        assert wp.tts_offset >= prev_offset
        prev_offset = wp.tts_offset
        # The offset+length names a real slice of the source text…
        assert 0 <= wp.tts_offset <= len(text)
        assert wp.tts_offset + wp.tts_len <= len(text)
        # …and that slice is exactly the recorded word.
        assert text[wp.tts_offset : wp.tts_offset + wp.tts_len] == wp.word
        # Display coordinates land inside the rendered buffer.
        assert 0 <= wp.disp_line < len(flat) or not flat
        if flat:
            assert 0 <= wp.disp_col <= len(flat[wp.disp_line])


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(_TEXT)
def test_word_map_covers_exactly_the_tokenized_words(text):
    """The map has one entry per \\b\\w[\\w'-]* token, in source order — the
    builder must not silently drop or duplicate words."""
    import re

    expected = [m.group() for m in re.finditer(r"\b\w[\w'-]*", text)]
    wm = _build_word_map(text, _flatten(render_markdown(text, 60)))
    assert [wp.word for wp in wm] == expected


@settings(max_examples=100)
@given(_TEXT, st.integers(min_value=1, max_value=200))
def test_word_map_stays_in_bounds_for_any_wrap_width(text, width):
    """Rendering at any width must still yield disp_line/disp_col that index
    into the produced buffer (the wrap width feeds the display geometry)."""
    flat = _flatten(render_markdown(text, width))
    wm = _build_word_map(text, flat)
    for wp in wm:
        if flat:
            assert 0 <= wp.disp_line < len(flat)
            assert 0 <= wp.disp_col <= len(flat[wp.disp_line])


# ── render_markdown structural invariants ────────────────────────────────────


@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(_TEXT, st.integers(min_value=1, max_value=200))
def test_render_yields_valid_line_structure(text, width):
    """render_markdown always returns a list of lines, each a list of
    (str, str) segments — the exact shape the TUI drawer and word-map builder
    both rely on."""
    rendered = render_markdown(text, width)
    assert isinstance(rendered, list)
    for line in rendered:
        assert isinstance(line, list)
        for seg in line:
            assert isinstance(seg, tuple) and len(seg) == 2
            body, role = seg
            assert isinstance(body, str)
            assert isinstance(role, str)


@settings(max_examples=100)
@given(_TEXT)
def test_render_is_deterministic(text):
    """Same input, same width → identical render (no hidden global state)."""
    assert render_markdown(text, 50) == render_markdown(text, 50)


# ── _load_csv_tsv invariants ─────────────────────────────────────────────────


@settings(
    max_examples=150,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(grid=_GRID)
def test_csv_table_has_consistent_column_count(tmp_path, grid):
    """Every emitted table row (header, separator, body) has the same number of
    pipe-delimited columns = max row width, so ragged input can't desync the
    Markdown table."""
    p = tmp_path / "data.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(grid)

    md = _load_csv_tsv(str(p), ",")
    table_lines = [ln for ln in md.splitlines() if ln.startswith("|")]
    # Header + separator + one line per data row (row 0 is the header).
    assert len(table_lines) == 1 + 1 + max(0, len(grid) - 1)

    ncols = max(len(r) for r in grid)
    for ln in table_lines:
        # A "| a | b |" row has ncols+1 pipes; count cells between them.
        # Strip the outer pipes then split on the interior " | " boundaries is
        # fragile with empty cells, so count columns via the leading/trailing
        # pipe structure: ncols cells ⇒ ncols+1 pipe characters (pipes inside a
        # cell are escaped as \| and must not be counted).
        raw = ln
        unescaped_pipes = raw.replace("\\|", "")  # drop escaped pipes
        assert unescaped_pipes.count("|") == ncols + 1


@settings(
    max_examples=150,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(grid=_GRID)
def test_csv_escapes_every_literal_pipe(tmp_path, grid):
    """A literal '|' inside a cell is always backslash-escaped, so a cell value
    can never inject a spurious column into the rendered table."""
    p = tmp_path / "data.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(grid)

    md = _load_csv_tsv(str(p), ",")
    ncols = max(len(r) for r in grid)
    for ln in md.splitlines():
        if ln == "|" + "|".join([" --- "] * ncols) + "|":
            continue  # the separator row is all structural pipes
        if not ln.startswith("| "):
            continue
        # A data/header row is "| c0 | c1 | … |".  Splitting on the boundary
        # sentinel " | " (after trimming the outer pipes) must give exactly
        # ncols cells — which only holds if every content pipe was escaped to
        # \|, since a bare interior '|' would forge an extra cell.
        inner = ln[2:-2]  # drop the leading "| " and trailing " |"
        cells = inner.split(" | ")
        assert len(cells) == ncols
        for cell in cells:
            assert "|" not in cell.replace("\\|", "")


# ── _load_html_str total-function invariant ──────────────────────────────────


@settings(max_examples=150, suppress_health_check=[HealthCheck.too_slow])
@given(
    st.text(
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po"),
            whitelist_characters="<>/=\"' \n",
        ),
        max_size=300,
    )
)
def test_load_html_str_never_raises(html):
    """The HTML→Markdown parser must degrade gracefully on any string —
    malformed tags included — and always hand back a string."""
    out = _load_html_str(html)
    assert isinstance(out, str)
