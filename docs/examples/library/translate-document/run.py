#!/usr/bin/env python3
"""Load a document and translate it to Spanish with star's library API.

star can translate documents into 15 languages using Google Translate (no API
key, no account). This example loads a short English article, translates it to
Spanish, and prints the result — the same pipeline the GUI's **Tools > Translate
Document…** uses.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    try:
        from star.documents import load_document
        from star.settings import Settings
    except ImportError:
        print("This example needs star installed:  pip install star-reader")
        return 0

    try:
        from star.translate import translate_text
    except ImportError:
        print(
            "Translation needs deep-translator:\n"
            "    pip install deep-translator\n\n"
            "Or let star install it for you: open the GUI and use\n"
            "Tools > Translate Document… — star offers to fetch it."
        )
        return 0

    from star.translate import _DEEP_TRANSLATOR

    if not _DEEP_TRANSLATOR:
        print(
            "Translation needs deep-translator:\n"
            "    pip install deep-translator\n\n"
            "Or let star install it for you: open the GUI and use\n"
            "Tools > Translate Document… — star offers to fetch it."
        )
        return 0

    doc = load_document(str(HERE / "article.md"), Settings())

    print(f"Original ({doc.title}):")
    print("-" * 40)
    print(doc.plain_text)
    print()

    translated = translate_text(doc.plain_text, target_lang="es")

    print("Spanish translation:")
    print("-" * 40)
    print(translated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
