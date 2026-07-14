# UI translation catalogs

Each `<code>.json` file localizes star's **chrome** — the menu bar, toolbar
button labels, and dock titles. They are loaded at runtime by
[`star/i18n.py`](../i18n.py); there is **no build step** (unlike Qt's native
`.ts`/`.qm` workflow).

## How a catalog works

* Keys are the **English source strings** exactly as they appear in the code
  (including the trailing `…` ellipsis and any `(BRF)` / `(MP4)` tokens).
* Values are the translation.
* Any key that is **missing** falls back to the English source, so a partial
  catalog is fine — untranslated items simply stay in English.
* English (`en`) is the source language and has **no catalog file**.
* The optional `"@meta"` key is ignored at load time; use it for a note about
  the catalog.

## Adding a new language

1. Copy an existing catalog (e.g. `es.json`) to `<code>.json`, where `<code>`
   is the ISO-639-1 code (e.g. `it` for Italian).
2. Translate the values. Leave the keys untouched.
3. Add a row to `LANGUAGES` in [`star/i18n.py`](../i18n.py):

   ```python
   LANGUAGES = [
       ("English", "en"),
       ...
       ("Italiano", "it"),   # ← native display name, code
   ]
   ```

4. The new language appears in **Preferences ▸ General ▸ Interface language** on next launch.

## Finding the strings to translate

The authoritative list of source strings is whatever the GUI passes to `tr()`
(see `star/gui/runner.py`). `tests/test_i18n.py` checks that every shipped
catalog only uses real keys and parses as a flat string→string map, so run the
test suite after editing a catalog.
