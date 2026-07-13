# List the registered plugins

star discovers its TTS voices, document-format handlers, and exporters through
`importlib.metadata` entry points — so a third-party package (or the bundled
[`plugin-template`](../../plugin-template)) can add its own. This prints every
plugin star can see.

**You'll need:** nothing beyond `star-reader`.

## Run it

    cd examples/cli/list-plugins
    python run.py

## What you should see

    $ star --plugins list

    star 0.1.26 - registered plugins (30 total)

    TTS backends [star.backends] (backends) - 11:
      [?] pyttsx3        -> star.tts.pyttsx3:Pyttsx3Backend  prio=20
      [?] espeak         -> star.tts.espeak:ESpeakBackend  prio=50
      [?] elevenlabs     -> star.tts.cloud.elevenlabs:ElevenLabsBackend  prio=900
      ...
    Document format handlers [star.formats] (formats) - 12:
      [+] pdf            -> star.documents.handlers:PDFHandler  prio=10  .pdf
      [+] docx           -> star.documents.handlers:DocxHandler  prio=50  .docx
      [+] markdown       -> star.documents.handlers:MarkdownHandler  prio=50  .markdown .md
      ...

## How it works

- Three plugin groups are shown: **TTS backends** (voices), **format handlers**
  (what star can open), and **exporters** (what star can save to).
- `prio=` sets selection order — a lower number wins when several plugins can
  handle the same job (e.g. which voice is chosen automatically).
- `[+]` means the plugin's dependencies are importable now; `[?]` means it would
  load on demand.
- `star --plugins info <group> <name>` details one plugin; `star --plugins api`
  prints the ABC contracts you implement to write your own.

## Next steps

- Write your own voice/format/exporter: start from
  [`../../plugin-template`](../../plugin-template).
- [Developing plugins](../../../docs/plugins-developing.md) — the full guide.
