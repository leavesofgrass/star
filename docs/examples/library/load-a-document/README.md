# Load a document from Python

star's document loaders are a library you can use without the GUI:
`load_document(path, settings)` opens any supported format and hands back a
`Document` with the rendered Markdown, the clean plain text the voice reads, the
detected format, and a title.

**You'll need:** nothing beyond `star-reader`.

## Run it

    cd docs/examples/library/load-a-document
    python run.py

## What you should see

    Title:  Bioluminescence
    Format: markdown
    Words:  61

    Plain text (what the voice reads aloud):
    ----------------------------------------
    Bioluminescence

    Some living things make their own light through a chemical reaction.

    Where it happens

    Bioluminescence is most common in the deep ocean, where sunlight never
    reaches. ...

## How it works

- `from star.documents import load_document` — the public entry point; it detects
  the format from the extension/content and dispatches to the right loader.
- It takes a `Settings()` (loaders read a few preferences, e.g. table-reading
  mode), and returns a `Document` dataclass.
- Useful fields: `doc.title`, `doc.format`, `doc.markdown` (styled source) and
  `doc.plain_text` (clean text for TTS or your own pipeline).
- Swap `article.md` for a `.pdf`, `.docx`, or `.epub` and the same three lines
  work — star picks the loader for you.

## Next steps

- The CLI one-liner equivalent: [`../../cli/extract-text`](../../cli/extract-text)
  (`star --plain`).
- [Architecture](../../../architecture.md) — how loaders, the word map, and
  TTS fit together.
