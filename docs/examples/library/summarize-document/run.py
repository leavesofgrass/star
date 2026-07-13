#!/usr/bin/env python3
"""Load a document and produce an extractive summary with star's library API.

star can summarize any document it opens using the LexRank algorithm (via sumy).
This example loads a multi-section article, summarizes it to a few key
sentences, and prints both the original and the summary — the same pipeline the
GUI's **Tools > Summarize Document…** uses.
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

    from star.summarize import _SUMY

    if not _SUMY:
        print(
            "Summarization needs sumy:\n"
            "    pip install sumy\n\n"
            "Or let star install it for you: open the GUI and use\n"
            "Tools > Summarize Document… — star offers to fetch it."
        )
        return 0

    from star.summarize import summarize_document

    doc = load_document(str(HERE / "article.md"), Settings())

    print(f"Document: {doc.title}")
    print(f"Words:    {len(doc.plain_text.split())}")
    print()

    summary = summarize_document(doc.plain_text, sentence_count=3)

    print("Summary (3 sentences):")
    print("-" * 40)
    print(summary)
    print()
    print(f"Summary words: {len(summary.split())}  "
          f"(~{100 * len(summary.split()) // len(doc.plain_text.split())}% of original)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
