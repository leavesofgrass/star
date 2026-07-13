# List available TTS voices

See every text-to-speech voice star can use on your system. Useful for picking
a voice before reading aloud or exporting to audio.

**You'll need:** nothing beyond `star-reader`.

## Run it

    cd docs/examples/cli/list-voices
    python run.py

## What you should see

    $ star --list-voices

    HKEY_...\TTS_MS_EN-US_DAVID_11.0    Microsoft David Desktop    en-US
    HKEY_...\TTS_MS_EN-US_ZIRA_11.0     Microsoft Zira Desktop     en-US
    ...

(The voices listed depend on your OS and installed engines. Windows shows SAPI5
voices, macOS shows NSSpeechSynthesizer voices, and Linux shows whatever
eSpeak-NG or pyttsx3 can find.)

## How it works

- `star --list-voices` creates a `TTSManager`, calls `list_voices()`, and
  prints each voice's ID, display name, and language code, tab-separated.
- star supports many engines: pyttsx3 (SAPI5 / NSSpeech / eSpeak), macOS
  `say`, eSpeak-NG, Festival, **Piper** (neural, offline), Coqui, DECtalk,
  and **ElevenLabs** (cloud). The command shows all voices across all backends
  that are available right now.
- In the GUI, the **Voice Manager (F4)** gives a richer view — browse, filter,
  preview, and favorite voices, plus one-click download of Piper neural voices.

## Next steps

- [`../export-audio`](../export-audio) — use a voice to export a document to
  a WAV file.
- Piper neural voices (free, offline): install with `star --install-optional`
  or from the Voice Manager.
- [Features > Voice](../../../features.md) — the full voice engine reference.
