# Summarize a document

Load a document and produce an extractive summary — the most important sentences
picked by the LexRank algorithm. This is the same pipeline the GUI's
**Tools > Summarize Document...** uses.

**You'll need:** `star-reader` with the summarization extra:
`pip install sumy` (or let star install it on demand in the GUI).

## Run it

    cd docs/examples/library/summarize-document
    python run.py

## What you should see

    Document: Sleep and Memory
    Words:    373

    Summary (3 sentences):
    ----------------------------------------
    Chronic sleep disorders such as insomnia and obstructive sleep apnea are
    associated with measurable deficits in memory. ...

    Summary words: 24  (~6% of original)

(The exact sentences and compression ratio depend on the article and the
sentence count you choose.)

## How it works

- `load_document()` opens the article; `summarize_document(text, sentence_count=3)`
  returns the top sentences ranked by LexRank.
- LexRank is an **extractive** algorithm — it picks the most important sentences
  from the original text rather than generating new ones, so the summary is
  always faithful to the source.
- `sentence_count` controls the summary length. More sentences = more detail;
  fewer = more compression.
- If sumy is not installed, the script prints the install command and exits
  cleanly — no traceback.

## Next steps

- [`../translate-document`](../translate-document) — translate instead of
  summarize.
- [`../load-a-document`](../load-a-document) — the document-loading basics.
- [Features > Summarization](../../../features.md) — the GUI workflow and
  options.
