"""LaTeX (.tex / .ltx) → Markdown heuristic converter."""
from .._runtime import *  # noqa: F401,F403


def _latex_to_md(text: str) -> str:  # noqa: C901
    """Strip LaTeX markup and convert to Markdown.

    Handles the constructs most commonly found in academic documents:
    preamble removal, sectioning, \\textbf / \\textit / \\emph,
    itemize / enumerate lists, verbatim / lstlisting / minted code
    blocks, quote / abstract environments, math stripping, special
    character normalization, and citation / cross-reference simplification.
    """
    # ─ Strip comments ───────────────────────────────────────────────────
    text = re.sub(r"%[^\n]*", "", text)

    # ─ Extract body (skip preamble) ─────────────────────────────────
    bm = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", text, re.DOTALL)
    body = bm.group(1) if bm else text

    # ─ Collect title / author / date from preamble for a header block ──
    header_lines: List[str] = []
    preamble = text[: bm.start()] if bm else ""
    for cmd, fmt in (
        (r"\\title", "# {}"),
        (r"\\author", "*{} *"),
        (r"\\date", "*{} *"),
    ):
        m = re.search(cmd + r"\{([^}]+)\}", preamble + body)
        if m:
            header_lines.append(fmt.format(m.group(1).strip()))
    if header_lines:
        header_lines.append("")
        body = re.sub(r"\\maketitle\b", "", body)

    # ─ Verbatim / code environments ───────────────────────────────
    body = re.sub(
        r"\\begin\{verbatim\}(.*?)\\end\{verbatim\}",
        lambda m: "\n```\n" + m.group(1).strip() + "\n```\n",
        body,
        flags=re.DOTALL,
    )
    body = re.sub(
        r"\\begin\{lstlisting\}[^\n]*(.*?)\\end\{lstlisting\}",
        lambda m: "\n```\n" + m.group(1).strip() + "\n```\n",
        body,
        flags=re.DOTALL,
    )
    body = re.sub(
        r"\\begin\{minted\}\{(\w+)\}(.*?)\\end\{minted\}",
        lambda m: f"\n```{m.group(1)}\n" + m.group(2).strip() + "\n```\n",
        body,
        flags=re.DOTALL,
    )

    # ─ Quote / abstract environments ─────────────────────────────
    def _blockquote(m: re.Match) -> str:
        return (
            "\n" + "\n".join("> " + ln for ln in m.group(1).strip().splitlines()) + "\n"
        )

    body = re.sub(
        r"\\begin\{(quote|quotation|abstract)\}(.*?)\\end\{\1\}",
        _blockquote,
        body,
        flags=re.DOTALL,
    )

    # ─ List environments ───────────────────────────────────────────
    def _list_env(bullet: str) -> Callable[[re.Match], str]:
        def _replace(m: re.Match) -> str:
            items = re.split(r"\\item\b", m.group(1))
            result = []
            for it in items:
                it = it.strip()
                if it:
                    # \item[label] text  → **label** text
                    it = re.sub(r"^\[([^\]]+)\]\s*", r"**\1** ", it)
                    result.append(bullet + " " + it.replace("\n", " "))
            return "\n".join(result) + "\n"

        return _replace

    body = re.sub(
        r"\\begin\{itemize\}(.*?)\\end\{itemize\}",
        _list_env("*"),
        body,
        flags=re.DOTALL,
    )
    body = re.sub(
        r"\\begin\{enumerate\}(.*?)\\end\{enumerate\}",
        _list_env("1."),
        body,
        flags=re.DOTALL,
    )
    body = re.sub(
        r"\\begin\{description\}(.*?)\\end\{description\}",
        _list_env("*"),
        body,
        flags=re.DOTALL,
    )

    # ─ Math (strip display; keep inline content for TTS) ───────────
    for env_name in (
        "equation",
        "equation*",
        "align",
        "align*",
        "gather",
        "gather*",
        "multline",
        "multline*",
        "eqnarray",
        "eqnarray*",
        "math",
        "displaymath",
    ):
        body = re.sub(
            r"\\begin\{"
            + re.escape(env_name)
            + r"\}.*?\\end\{"
            + re.escape(env_name)
            + r"\}",
            "",
            body,
            flags=re.DOTALL,
        )
    body = re.sub(r"\$\$.*?\$\$", "", body, flags=re.DOTALL)
    body = re.sub(r"\\\[.*?\\\]", "", body, flags=re.DOTALL)
    body = re.sub(r"\\\((.*?)\\\)", r" \1 ", body, flags=re.DOTALL)
    body = re.sub(r"\$([^$\n]{1,120})\$", r" \1 ", body)

    # ─ Sectioning ────────────────────────────────────────────────
    for cmd, hashes in [
        ("part", "#"),
        ("chapter", "#"),
        ("section", "##"),
        ("subsection", "###"),
        ("subsubsection", "####"),
        ("paragraph", "#####"),
        ("subparagraph", "######"),
    ]:
        body = re.sub(
            r"\\" + cmd + r"\*?\{([^}]+)\}",
            lambda m, h=hashes: f"\n{h} {m.group(1)}\n",
            body,
        )

    # ─ Inline formatting ──────────────────────────────────────────
    body = re.sub(r"\\textbf\{([^}]+)\}", r"**\1**", body)
    body = re.sub(r"\\textit\{([^}]+)\}", r"*\1*", body)
    body = re.sub(r"\\emph\{([^}]+)\}", r"*\1*", body)
    body = re.sub(r"\\texttt\{([^}]+)\}", r"`\1`", body)
    body = re.sub(r"\\textsc\{([^}]+)\}", r"\1", body)
    body = re.sub(r"\\textsuperscript\{([^}]+)\}", r"^\1^", body)
    body = re.sub(r"\\textsubscript\{([^}]+)\}", r"~\1~", body)
    body = re.sub(r"\\underline\{([^}]+)\}", r"\1", body)
    body = re.sub(r"\\uline\{([^}]+)\}", r"\1", body)

    # ─ References, citations, footnotes ──────────────────────────
    body = re.sub(r"\\(?:cite|citep|citet|citealt|citealp)\{([^}]+)\}", r"[\1]", body)
    body = re.sub(r"\\(?:ref|pageref|eqref|nameref)\{[^}]+\}", "", body)
    body = re.sub(r"\\label\{[^}]+\}", "", body)
    body = re.sub(r"\\footnote\{([^}]{1,200})\}", r" (\1)", body)
    body = re.sub(r"\\footnotemark(?:\[\d+\])?", "", body)
    body = re.sub(r"\\footnotetext\{([^}]{1,200})\}", r" (\1)", body)

    # ─ URLs / hyperlinks ────────────────────────────────────────
    body = re.sub(r"\\url\{([^}]+)\}", r"\1", body)
    body = re.sub(r"\\href\{([^}]+)\}\{([^}]+)\}", r"[\2](\1)", body)

    # ─ Skip remaining environments entirely ────────────────────────
    body = re.sub(
        r"\\begin\{(figure|table|algorithm|tikzpicture|tabular)[^}]*\}.*?"
        r"\\end\{\1\}",
        "",
        body,
        flags=re.DOTALL | re.I,
    )

    # ─ Special characters and ligatures ─────────────────────────
    for latex, md_equiv in [
        ("---", "—"),
        ("--", "–"),
        (r"\\ldots", "…"),
        (r"\\dots", "…"),
        (r"\\cdots", "…"),
        ("``", "“"),
        ("''", "”"),
        (r"\\%", "%"),
        (r"\\\$", "$"),
        (r"\\&", "&"),
        (r"\\#", "#"),
        (r"\\{", "{"),
        (r"\\}", "}"),
        (r"\\textasciitilde", "~"),
        (r"\\textasciicircum", "^"),
        (r"\\textbackslash", r"\\"),  # re.sub replacement: r"\\" → one literal backslash
        (r"\\slash", "/"),
        (r"\\,", " "),
        (r"\\;", " "),
        (r"\\!", ""),
        (r"\\quad", "  "),
    ]:
        body = re.sub(latex, md_equiv, body)

    # ─ Strip remaining block/environment tags ──────────────────────
    body = re.sub(r"\\begin\{[^}]+\}", "", body)
    body = re.sub(r"\\end\{[^}]+\}", "", body)

    # ─ Strip remaining LaTeX commands ───────────────────────────
    # Layout / spacing commands
    body = re.sub(
        r"\\(newpage|clearpage|pagebreak|noindent|par|linebreak|newline|\\)",
        "\n",
        body,
    )
    body = re.sub(
        r"\\(medskip|bigskip|smallskip|vspace\*?|hspace\*?)(?:\{[^}]*\})?",
        " ",
        body,
    )
    # Declaration-style commands
    body = re.sub(
        r"\\(centering|raggedright|raggedleft|normalfont|bfseries"
        r"|itshape|ttfamily|large|Large|LARGE|huge|Huge|small|footnotesize)",
        "",
        body,
    )
    # Any remaining command with an argument — keep the argument text
    body = re.sub(r"\\[a-zA-Z]+\*?\{([^}]{1,200})\}", r"\1", body)
    # Any remaining bare command
    body = re.sub(r"\\[a-zA-Z]+\*?\s*", " ", body)

    # ─ Clean up braces and whitespace ─────────────────────────────
    body = body.replace("{", "").replace("}", "")
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = re.sub(r" {2,}", " ", body)

    return "\n".join(header_lines) + body.strip()
