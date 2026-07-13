# Translate a document

Load a document and translate it into another language with star's library API.
star uses Google Translate via deep-translator — no API key, no account. This
example translates a short English article to Spanish.

**You'll need:** `star-reader` with the translation extra:
`pip install deep-translator` (or let star install it on demand in the GUI).

## Run it

    cd docs/examples/library/translate-document
    python run.py

## What you should see

    Original (The Northern Lights):
    ----------------------------------------
    The Northern Lights

    The aurora borealis is a natural light display in the Earth's sky, predominantly
    seen in high-latitude regions. It is caused by charged particles from the sun
    colliding with gases in the atmosphere, creating shimmering curtains of green,
    purple, and red light.
    ...

    Spanish translation:
    ----------------------------------------
    La aurora boreal

    La aurora boreal es un espectáculo de luz natural en el cielo de la Tierra,
    predominantemente visto en regiones de altas latitudes. ...

## How it works

- `load_document()` opens the article; `translate_text(text, target_lang="es")`
  translates it.
- Long documents are automatically chunked (Google's backend rejects requests
  over 5000 characters) and reassembled with paragraph structure intact.
- `target_lang` is an ISO 639-1 code. star ships with 15 common languages
  (`star.translate.COMMON_LANGUAGES`), but any code Google Translate supports
  works.
- If deep-translator is not installed, the script prints the install command
  and exits cleanly — no traceback.

## Next steps

- [`../load-a-document`](../load-a-document) — the document-loading basics.
- [`../summarize-document`](../summarize-document) — summarize instead of
  translate.
- [Features > Translation](../../../features.md) — all 15 languages and the
  GUI workflow.
