# Publish a styled, accessible EPUB

Turn a document you're reading (or writing) into a styled EPUB with real
metadata, a cover, and a table of contents — using one of star's bundled
accessibility templates.

**You'll need:** Pandoc (bundled in the Windows `star.exe`; elsewhere
`pip install pypandoc` or a system `pandoc`). Nothing to run here — this is a
GUI walkthrough.

## Walkthrough

1. Open any document — or press `Ctrl+N` and write one.
2. Press **`F9`** (File ▸ Publish…).
3. In the dialog:
   - **Format:** EPUB
   - **Stylesheet template:** `large-print` (or `dyslexia-friendly` /
     `high-contrast` — each mirrors the matching star reading aid)
   - **Title / Author / Language / Date:** prefilled from the document's
     metadata; edit freely — your values win.
   - **Cover image:** optional; Browse… to a PNG/JPG.
   - Leave **Include a table of contents** checked.
4. Choose **Publish**, pick the output file, and watch the status bar —
   the conversion runs in the background.

## What you should see

A `.epub` that opens in any reader (Calibre, Thorium, Apple Books) with your
chosen styling, the title/author on the title page, and a navigable table of
contents. Re-open the dialog with `F9`: every choice is remembered for this
document.

## How it works

- The dialog builds a `PublishOptions` (star/publish.py) and the EPUB exporter
  turns it into Pandoc flags — metadata, `--css` with your template,
  `--epub-cover-image`, `--toc`.
- Templates are plain CSS. The bundled three are seeded into
  `publish-styles/` in star's config folder on first use — copy one, rename
  it, edit it, and it appears in the picker. Your edits are never overwritten.
- In the terminal UI the same flow is `M-x publish` (format → template →
  output path, with completion), sharing the per-document memory.

## Next steps

- The quick, unstyled converters stay at **File ▸ Export ▸ HTML/EPUB**.
- [features.md — Publishing](../../../features.md#publishing-epub--html) for
  the full option reference.
