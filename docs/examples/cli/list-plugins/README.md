# List the registered plugins

star discovers its TTS voices, document-format handlers, and exporters through
`importlib.metadata` entry points — so a third-party package (or the bundled
[`plugin-template`](../../plugin-template)) can add its own. This prints every
plugin star can see.

**You'll need:** nothing beyond `star-reader`.

## Run it

    cd docs/examples/cli/list-plugins
    python run.py

## What you should see

    $ star --plugins list

    star 0.1.32 - registered plugins (47 total)

    TTS backends [star.backends] (backends) - 13:
      [?] applesay       -> star.tts.applesay:AppleSayBackend  prio=15
      [-] eloquence      -> star.tts.eloquence:EloquenceBackend  prio=18
      [?] pyttsx3        -> star.tts.pyttsx3:Pyttsx3Backend  prio=20
      [?] qtspeech       -> star.tts.qtspeech:QtSpeechBackend  prio=35
      [?] espeak         -> star.tts.espeak:ESpeakBackend  prio=50
      [?] elevenlabs     -> star.tts.cloud.elevenlabs:ElevenLabsBackend  prio=900
      ...
    Document format handlers [star.formats] (formats) - 26:
      [+] pdf            -> star.documents.handlers:PDFHandler  prio=10  .pdf
      [+] fb2            -> star.documents.handlers:FB2Handler  prio=40  .fb2
      [+] man            -> star.documents.handlers:ManPageHandler  prio=40  .man .roff
      [+] rtf            -> star.documents.handlers:RTFHandler  prio=40  .rtf
      [+] audiobook      -> star.documents.handlers:AudiobookHandler  prio=50  .m4a .m4b .mp3
      ...

## How it works

- Three plugin groups are shown: **TTS backends** (voices), **format handlers**
  (what star can open), and **exporters** (what star can save to).
- `prio=` sets selection order — a lower number wins when several plugins can
  handle the same job (e.g. which voice is chosen automatically).
- `[+]` means the plugin's dependencies are importable now; `[?]` means it would
  load on demand; `[-]` means it can't run here yet (wrong platform, or an
  optional engine that isn't installed — `eloquence` shows `[-]` until you
  accept its one-time OpenEVV download).
- `star --plugins info <group> <name>` details one plugin; `star --plugins api`
  prints the ABC contracts you implement to write your own.

## Next steps

- Write your own voice/format/exporter: start from
  [`../../plugin-template`](../../plugin-template).
- [Developing plugins](../../../plugins-developing.md) — the full guide.
