# =============================================================================
# SSML / prosody helpers
# =============================================================================
"""SSML and DECtalk prosody markup for TTS backends."""
from .._runtime import *  # noqa: F401,F403


def _text_to_ssml(
    text: str,
    backend: str = "pyttsx3",
    sentence_ms: int = 350,
    clause_ms: int = 150,
) -> str:
    """Wrap *text* in SSML markup, inserting pauses at sentence and clause
    boundaries for more natural-sounding speech.

    The output is always wrapped in ``<speak>…</speak>`` tags:

    * eSpeak-NG accepts this directly with its ``-m`` flag.
    * SAPI5 (Windows / pyttsx3) interprets it natively.
    * DECtalk receives its own notation via ``_text_to_dectalk()`` instead.

    If *text* is already SSML (starts with ``<speak>``) it is returned
    unchanged to avoid double-wrapping.
    """
    if text.lstrip().startswith("<speak>"):
        return text  # already wrapped
    if backend == "dectalk":
        return _text_to_dectalk(text, sentence_ms, clause_ms)

    # Escape XML-reserved characters before inserting any tags.
    s = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

    long_ms = sentence_ms * 2

    # Paragraph breaks → long pause
    s = re.sub(r"\n{2,}", f'<break time="{long_ms}ms"/>\n', s)
    # Sentence-ending punctuation → medium pause
    s = re.sub(
        r"([.!?\u2026])(\s+)",
        lambda m: f'{m.group(1)}<break time="{sentence_ms}ms"/>{m.group(2)}',
        s,
    )
    # Clause punctuation (comma, colon) → short pause.
    s = re.sub(
        r"([,:])(\s+)",
        lambda m: f'{m.group(1)}<break time="{clause_ms}ms"/>{m.group(2)}',
        s,
    )
    # Semicolons too — but NOT the ";" that terminates an XML entity we escaped
    # above (&amp; &lt; &gt; &quot;); a break there would split the entity.
    s = re.sub(
        r"(?<!&amp)(?<!&lt)(?<!&gt)(?<!&quot);(\s+)",
        lambda m: f';<break time="{clause_ms}ms"/>{m.group(1)}',
        s,
    )
    # Em-dash / en-dash → brief pause
    s = re.sub(
        r"[\u2014\u2013]",
        f' <break time="{clause_ms}ms"/> ',
        s,
    )

    return f"<speak>{s}</speak>"


def _text_to_dectalk(
    text: str,
    sentence_ms: int = 350,
    clause_ms: int = 150,
) -> str:
    """Convert plain text to DECtalk phoneme notation for improved prosody.

    DECtalk uses ``[:pau N]`` to insert N milliseconds of silence.
    """
    s = text
    s = re.sub(
        r"([.!?\u2026])(\s+)",
        lambda m: f"{m.group(1)} [:pau {sentence_ms}] ",
        s,
    )
    s = re.sub(
        r"([,;:])(\s+)",
        lambda m: f"{m.group(1)} [:pau {clause_ms}] ",
        s,
    )
    s = re.sub(r"[\u2014\u2013]", f" [:pau {clause_ms}] ", s)
    return s
