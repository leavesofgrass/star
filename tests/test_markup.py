"""Direct unit tests for :mod:`star.markup` — the lightweight markup→Markdown
converters (Org, reStructuredText, MediaWiki, AsciiDoc, Textile, Creole,
LaTeX).  All seven converters are pure ``str -> str`` (the Pandoc bridge
``_pandoc_convert`` needs the external binary and is not exercised here).

Assertions were derived by observing each converter's actual output, not by
guessing.  They use substring checks so incidental formatting differences don't
make the tests brittle.
"""
from star.markup import (
    _asciidoc_to_md,
    _creole_to_md,
    _latex_to_md,
    _mediawiki_to_md,
    _orgmode_to_md,
    _rst_to_md,
    _textile_to_md,
)


# ── Org-mode ──────────────────────────────────────────────────────────────────


def test_orgmode_headings_and_title():
    out = _orgmode_to_md("#+TITLE: My Doc\n* Heading\n** Sub")
    assert "# My Doc" in out
    assert "# Heading" in out
    assert "## Sub" in out


def test_orgmode_inline_and_links_and_lists():
    out = _orgmode_to_md(
        "This is *bold* and /italic/ and ~code~.\n"
        "- item one\n- item two\n"
        "[[http://x.com][link]]"
    )
    assert "**bold**" in out
    assert "*italic*" in out
    assert "`code`" in out
    assert "* item one" in out
    assert "[link](http://x.com)" in out


def test_orgmode_strips_todo_and_tags_from_headline():
    out = _orgmode_to_md("* TODO Do the thing  :work:urgent:")
    assert "# Do the thing" in out
    assert "TODO" not in out
    assert ":work:" not in out


def test_orgmode_src_block_becomes_fence():
    out = _orgmode_to_md("#+BEGIN_SRC python\nprint(1)\n#+END_SRC")
    assert "```python" in out
    assert "print(1)" in out


# ── reStructuredText ──────────────────────────────────────────────────────────


def test_rst_headings_and_inline():
    out = _rst_to_md("Title\n=====\n\nSection\n-------\n\nThis is **bold** and *italic*.")
    assert "# Title" in out
    assert "## Section" in out
    assert "**bold**" in out and "*italic*" in out


def test_rst_lists():
    out = _rst_to_md("- a\n- b\n")
    assert "- a" in out and "- b" in out


# ── MediaWiki ─────────────────────────────────────────────────────────────────


def test_mediawiki_headings_and_inline():
    out = _mediawiki_to_md("== Heading ==\n=== Sub ===\n'''bold''' and ''italic''")
    assert "# Heading" in out
    assert "## Sub" in out
    assert "**bold**" in out and "*italic*" in out


def test_mediawiki_list_and_link():
    out = _mediawiki_to_md("* item\n[[Link]]")
    assert "* item" in out
    assert "Link" in out


# ── AsciiDoc ──────────────────────────────────────────────────────────────────


def test_asciidoc_headings_and_inline():
    out = _asciidoc_to_md("= Title\n== Section\n*bold* _italic_")
    assert "# Title" in out
    assert "## Section" in out
    assert "**bold**" in out and "*italic*" in out


def test_asciidoc_bullet_list():
    out = _asciidoc_to_md("* item one\n* item two")
    assert "* item one" in out and "* item two" in out


# ── Textile ───────────────────────────────────────────────────────────────────


def test_textile_headings_and_inline():
    out = _textile_to_md("h1. Heading\n\nh2. Sub\n\n*bold* _italic_")
    assert "# Heading" in out
    assert "## Sub" in out
    assert "**bold**" in out and "*italic*" in out


def test_textile_list():
    out = _textile_to_md("* item")
    assert "* item" in out


# ── Creole ────────────────────────────────────────────────────────────────────


def test_creole_headings_and_inline():
    # Creole uses == for level-2 headings (= would be level-1, but the converter
    # maps == -> ## as observed).
    out = _creole_to_md("== Heading\n=== Sub\n**bold** //italic//")
    assert "## Heading" in out
    assert "### Sub" in out
    assert "**bold**" in out and "*italic*" in out


def test_creole_link_with_text():
    out = _creole_to_md("[[Link|text]]")
    assert "[text](Link)" in out


# ── LaTeX ─────────────────────────────────────────────────────────────────────


def test_latex_sections_and_inline():
    out = _latex_to_md(
        r"\section{Intro}" "\n" r"\subsection{Background}" "\n"
        r"\textbf{bold} and \textit{italic} and \texttt{code}."
    )
    assert "## Intro" in out
    assert "### Background" in out
    assert "**bold**" in out
    assert "*italic*" in out
    assert "`code`" in out


def test_latex_itemize_list():
    out = _latex_to_md(r"\begin{itemize}" "\n" r"\item one" "\n" r"\item two" "\n" r"\end{itemize}")
    assert "* one" in out and "* two" in out


def test_latex_textbackslash_does_not_crash_and_maps_to_backslash():
    # Regression guard: _latex_to_md used to crash unconditionally because the
    # "\\textbackslash" -> "\\" substitution had an invalid re.sub replacement
    # template (a lone trailing backslash -> "bad escape").
    out = _latex_to_md(r"A backslash \textbackslash and a tilde \textasciitilde here.")
    assert "\\" in out  # textbackslash → a literal backslash
    assert "~" in out  # textasciitilde → tilde


def test_latex_ellipsis():
    assert "…" in _latex_to_md(r"And so on \ldots")


# ── shared: empty input is handled cleanly ───────────────────────────────────


def test_converters_accept_empty_string():
    for fn in (
        _orgmode_to_md,
        _rst_to_md,
        _mediawiki_to_md,
        _asciidoc_to_md,
        _textile_to_md,
        _creole_to_md,
        _latex_to_md,
    ):
        assert isinstance(fn(""), str)
