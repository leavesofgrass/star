"""Markdown-to-plain-text stripping for TTS.

Produces clean text suitable for reading aloud — no asterisks, slashes,
pound signs, pipe characters, or code fences.
"""
from .._runtime import *  # noqa: F401,F403

from .tables import _tables_to_narration


def _strip_markdown_for_tts(
    md: str,
    skip_code: bool = True,
    table_mode: str = "structured",
) -> str:
    """Remove markdown syntax to produce clean text suitable for TTS.
    The result should sound natural when read aloud — no asterisks, slashes,
    pound signs, pipe characters, or code fences.

    table_mode is forwarded to _tables_to_narration() and controls how tables
    are rendered for speech (structured / flat / skip).
    """
    text = md

    # List markers — stripped BEFORE the indented-code pass below, because a
    # CommonMark nested list item ("    - apples") is also 4-space-indented:
    # stripping "indented code" first silently deleted every nested list item
    # from narration (content loss in a reader whose job is reading).
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+[.)]\s+", "", text, flags=re.MULTILINE)

    # Remove fenced code blocks entirely if requested
    if skip_code:
        text = re.sub(r"```[\s\S]*?```", "", text)
        text = re.sub(r"~~~[\s\S]*?~~~", "", text)
        text = re.sub(r"^    .+$", "", text, flags=re.MULTILINE)  # indented code
    else:
        text = re.sub(r"```\w*\n?", "", text)
        text = re.sub(r"```", "", text)

    # Headings — keep text, drop pounds
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Horizontal rules
    text = re.sub(r"^(\*{3,}|-{3,}|_{3,})\s*$", "", text, flags=re.MULTILINE)

    # Links: keep display text
    text = re.sub(r"!\[([^\]]*)\]\([^\)]*\)", r"\1", text)  # images
    text = re.sub(r"\[([^\]]*)\]\([^\)]*\)", r"\1", text)  # links

    # Inline code
    text = re.sub(r"`+(.+?)`+", r"\1", text)

    # Bold / italic
    text = re.sub(r"\*{3}(.+?)\*{3}", r"\1", text)
    text = re.sub(r"_{3}(.+?)_{3}", r"\1", text)
    text = re.sub(r"\*{2}(.+?)\*{2}", r"\1", text)
    text = re.sub(r"_{2}(.+?)_{2}", r"\1", text)
    text = re.sub(r"\*([^*\n]+?)\*", r"\1", text)
    text = re.sub(r"_([^_\n]+?)_", r"\1", text)

    # Blockquotes — collapse the whole marker run so nested/email-style
    # quotes (">> quoted") don't leak ">" characters into narration.
    text = re.sub(r"^(?:>\s?)+", "", text, flags=re.MULTILINE)

    # Table narration — must run before pipes are stripped.
    # _tables_to_narration() is defined later in the file; it operates on the
    # still-raw markdown lines and replaces table blocks with spoken prose.
    text = _tables_to_narration(text, mode=table_mode)

    # Collapse extra blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
