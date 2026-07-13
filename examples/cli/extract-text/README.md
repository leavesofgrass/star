# Extract a document's text to stdout

Turn any supported document into clean reading text on the command line — no
GUI, no window. Great for piping star's document loaders into search, word
counts, or another tool.

**You'll need:** nothing beyond `star-reader`.

## Run it

    cd examples/cli/extract-text
    python run.py

## What you should see

    $ star --plain sample.md

    The Water Cycle

    Water moves through the environment in a continuous cycle.

    Evaporation

    The sun heats water in rivers, lakes, and the ocean, turning it into vapor
    that rises into the air.

    Condensation

    As the vapor cools, it forms tiny droplets that gather into clouds.

    ... (Precipitation section follows)

## How it works

- `star --plain FILE` loads the document, strips the Markdown/markup, and writes
  the **plain reading text** (exactly what the voice would speak) to stdout, then
  exits — no TUI, no GUI.
- Because it's just stdout, you can pipe it:
  `star --plain report.pdf | wc -w` counts the words,
  `star --plain notes.docx > notes.txt` saves the text.
- It works on every format star can open — PDF, DOCX, EPUB, ODT, HTML, and more —
  so it's a one-liner way to get text out of formats that don't have an easy
  extractor.

## Next steps

- [`../check-dependencies`](../check-dependencies) — see which formats your
  install can open.
- Prefer code? [`../../library/load-a-document`](../../library/load-a-document)
  does the same thing through star's Python API.
- Full CLI reference: [Usage guide](../../../docs/usage_guide.md).
