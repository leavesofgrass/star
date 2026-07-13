#!/usr/bin/env python3
"""Load a document with star's library API and inspect its text.

star's document loaders work without the GUI. ``load_document(path, settings)``
returns a ``Document`` carrying the rendered Markdown, the clean **plain text**
that the voice reads, the detected format, and a title — everything you need to
build your own reading or conversion tool on top of star.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    try:
        from star.documents import load_document
        from star.settings import Settings
    except ImportError:
        print("This example needs star installed:  pip install star-reader")
        return 0  # degrade gracefully so the smoke test stays green

    doc = load_document(str(HERE / "article.md"), Settings())

    print(f"Title:  {doc.title}")
    print(f"Format: {doc.format}")
    print(f"Words:  {len(doc.plain_text.split())}")
    print()
    print("Plain text (what the voice reads aloud):")
    print("-" * 40)
    print(doc.plain_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
