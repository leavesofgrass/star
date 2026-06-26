"""Direct unit tests for :mod:`star.render` — the Markdown→styled-terminal-lines
renderer and code lexers.  All functions are pure (string/list in → list out),
so this needs no curses/Qt.
"""
from star.render import (
    _lex_python_line,
    _lex_r_line,
    _parse_inline,
    _wrap_segs,
    lines_to_plain,
    render_markdown,
)


def _roles(segs):
    return {role for _txt, role in segs}


def _texts(segs):
    return "".join(t for t, _r in segs)


# ── _parse_inline ───────────────────────────────────────────────────────────


def test_parse_inline_plain():
    assert _parse_inline("just text") == [("just text", "normal")]


def test_parse_inline_code_bold_italic():
    segs = _parse_inline("a `code` b **bold** c *it* d")
    assert ("code", "code") in segs
    assert ("bold", "bold") in segs
    assert ("it", "italic") in segs


def test_parse_inline_bolditalic():
    segs = _parse_inline("x ***both*** y")
    assert ("both", "bolditalic") in segs


def test_parse_inline_link_and_image():
    link = _parse_inline("see [text](http://x)")
    assert ("text", "link") in link
    img = _parse_inline("![alt](pic.png)")
    assert any(role == "image" and "alt" in t for t, role in img)


def test_parse_inline_empty_string():
    assert _parse_inline("") == [("", "normal")]


# ── _wrap_segs ────────────────────────────────────────────────────────────────


def test_wrap_segs_wraps_to_width():
    segs = [("one two three four five", "normal")]
    lines = _wrap_segs(segs, 9)
    assert len(lines) > 1
    for ln in lines:
        assert len(_texts(ln)) <= 9


def test_wrap_segs_zero_width_returns_single_line():
    segs = [("anything goes", "normal")]
    assert _wrap_segs(segs, 0) == [segs]


def test_wrap_segs_short_fits_one_line():
    lines = _wrap_segs([("hi there", "normal")], 80)
    assert len(lines) == 1
    assert _texts(lines[0]) == "hi there"


def test_wrap_segs_hard_splits_overlong_word():
    lines = _wrap_segs([("abcdefghij", "normal")], 4)
    assert len(lines) >= 3
    assert all(len(_texts(ln)) <= 4 for ln in lines)


# ── render_markdown ───────────────────────────────────────────────────────────


def test_render_markdown_returns_list_of_lines():
    out = render_markdown("# Title\n\nA paragraph.", 80)
    assert isinstance(out, list)
    assert all(isinstance(ln, list) for ln in out)


def test_render_markdown_heading_and_paragraph_text_present():
    plain = lines_to_plain(render_markdown("# Hello\n\nworld body here", 80))
    assert "Hello" in plain
    assert "world body here" in plain


def test_render_markdown_fenced_code_preserves_content():
    md = "```python\ndef f():\n    return 1\n```"
    plain = lines_to_plain(render_markdown(md, 80))
    assert "def f():" in plain
    assert "return 1" in plain


def test_render_markdown_bullet_list():
    plain = lines_to_plain(render_markdown("- one\n- two\n- three", 80))
    for item in ("one", "two", "three"):
        assert item in plain


def test_render_markdown_narrow_width_does_not_crash():
    out = render_markdown("a very long line of words " * 5, 12)
    assert all(len(_texts(ln)) <= 12 for ln in out)


# ── code lexers ───────────────────────────────────────────────────────────────


def test_lex_python_keyword_and_comment():
    segs = _lex_python_line("def f():  # comment")
    assert ("def", "keyword") in segs or any(
        t == "def" and "key" in r for t, r in segs
    )
    assert any("comment" in r for _t, r in segs)


def test_lex_python_string_literal():
    segs = _lex_python_line('x = "hello"')
    assert any("string" in r for _t, r in segs)


def test_lex_r_keyword():
    segs = _lex_r_line("if (x > 1) function(y)")
    roles = " ".join(r for _t, r in segs)
    assert "keyword" in roles


# ── lines_to_plain ────────────────────────────────────────────────────────────


def test_lines_to_plain_roundtrip():
    plain = lines_to_plain(render_markdown("Plain words here.", 80))
    assert "Plain words here." in plain


def test_lines_to_plain_empty():
    assert lines_to_plain([]) == "" or lines_to_plain([]).strip() == ""
