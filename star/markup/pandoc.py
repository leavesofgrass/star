"""Pandoc bridge — run Pandoc with an explicit input-format flag.

The wiki-format loaders (RST · MediaWiki · AsciiDoc · Textile · Creole) each
follow the same three-tier strategy:

  1. Pandoc with an explicit --from flag  —  highest quality when available
  2. A dedicated Python library            —  no external binary required
  3. A built-in regex converter            —  always works, covers ~80% of
     real-world documents well enough for TTS
"""
from .._runtime import *  # noqa: F401,F403


def _pandoc_convert(path: str, from_fmt: str) -> Optional[str]:
    """Run Pandoc with an explicit input format flag.  Returns Markdown or None."""
    if _PYPANDOC:
        try:
            return _pypandoc.convert_file(path, "markdown", format=from_fmt)
        except Exception:
            pass
    if _PANDOC_BIN:
        try:
            r = subprocess.run(
                [_PANDOC_BIN, "--from", from_fmt, "--to", "markdown", path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout
        except Exception:
            pass
    return None
