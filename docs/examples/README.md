# star examples

Runnable, task-focused examples for **star** — the accessible document reader and
Markdown authoring tool with built-in text-to-speech. Each folder is one concrete
task with its own README.

**How to run any runnable example:**

    cd docs/examples/<category>/<name>
    python run.py

Runnable examples need only `star-reader` installed (`pip install star-reader`).
The **GUI** entries are walkthroughs you follow inside the app — they have no
`run.py`.

---

## Command line — text in, text out

star's CLI extracts and inspects without opening a window.

| I want to… | Example | Runs? |
|---|---|---|
| Get a document's plain text on stdout (pipe-friendly) | [`cli/extract-text`](cli/extract-text) | ✅ `python run.py` |
| Export a document to spoken audio (WAV/MP3) | [`cli/export-audio`](cli/export-audio) | ✅ `python run.py` |
| See every TTS voice available on my system | [`cli/list-voices`](cli/list-voices) | ✅ `python run.py` |
| See which optional features are installed | [`cli/check-dependencies`](cli/check-dependencies) | ✅ `python run.py` |
| List the pluggable voices, formats, and exporters | [`cli/list-plugins`](cli/list-plugins) | ✅ `python run.py` |

More CLI: `star --install-optional`, `star --check-update`, and headless batch
conversion with `star --watch DIR --output DIR` — see the
[Usage guide](../usage_guide.md).

## From your own code

star's core is a library, not just an app.

| I want to… | Example | Runs? |
|---|---|---|
| Open any document and read its text/title/format in Python | [`library/load-a-document`](library/load-a-document) | ✅ `python run.py` |
| Translate a document to another language | [`library/translate-document`](library/translate-document) | ✅ `python run.py` |
| Summarize a document to key sentences | [`library/summarize-document`](library/summarize-document) | ✅ `python run.py` |

More: the loaders, word map, and TTS pipeline are described in
[Architecture](../architecture.md).

## Reading (GUI)

The primary experience — walkthroughs to follow in the app (`star`).

| I want to… | Walkthrough |
|---|---|
| Open a document and hear it read, word-by-word | [`gui/read-aloud`](gui/read-aloud) |
| Use dyslexia / decoding aids (define, syllables, fonts, difficult words) | [`gui/reading-aids`](gui/reading-aids) |

Depth: [Features](../features.md) · [Usage guide](../usage_guide.md).

## Writing & exporting (GUI)

| I want to… | Walkthrough |
|---|---|
| Write a Markdown document, dictate, and export to PDF / audio / Braille | [`gui/write-and-export`](gui/write-and-export) |

Depth: [Usage guide ▸ authoring](../usage_guide.md).

## Extending star with plugins

| I want to… | Example |
|---|---|
| Write my own TTS voice, format loader, or exporter | [`plugin-template`](plugin-template) |
| See what plugins are registered | [`cli/list-plugins`](cli/list-plugins) |

Depth: [Developing plugins](../plugins-developing.md).

## More capabilities (in the guides)

Not every feature has a dedicated example folder yet — these are covered in the
docs:

| Area | Where |
|---|---|
| Knowledge graph & Obsidian vault import | [knowledge-graph](../knowledge-graph.md) · [obsidian](../obsidian.md) |
| Karaoke video export | [video-export](../video-export.md) |
| Configuration & settings reference | [configuration](../configuration.md) |
| Keyboard shortcuts (full audit) | [KEYBOARD_AUDIT](../KEYBOARD_AUDIT.md) |
| Install, extras, native engines, per-platform notes | [installation](../installation.md) |

---

Every runnable example here is executed by the test suite
(`tests/test_examples_smoke.py`) so it can't rot silently.
