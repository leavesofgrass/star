# See which optional features are installed

star's core runs on the Python standard library; every extra capability is
optional and installed on demand. This shows a status report of what's present
and what each missing piece unlocks — a zero-setup health check for your install.

**You'll need:** nothing beyond `star-reader`.

## Run it

    cd docs/examples/cli/check-dependencies
    python run.py

## What you should see

    $ star --deps

    star 0.1.27 - optional dependency status (34/38 available)

    Documents:
      [+] PDF text extraction - Open and read PDF files
      [+] Word (.docx) - Open Word documents
      [+] OCR (pytesseract) - Read scanned PDFs and images
      ...
    Speech:
      [+] pyttsx3 (system TTS) - Cross-platform system voices (SAPI5 / NSSpeech / eSpeak)
      [-] Coqui TTS (neural) - Coqui neural text-to-speech
            install: pip install TTS
      [+] Whisper (speech-to-text) - Voice dictation and audio transcription
    ...

(The exact counts and `[+]`/`[-]` marks reflect *your* machine.)

## How it works

- `star --deps` prints every optional dependency grouped by area (Documents,
  Speech, Reading aids, …), with `[+]` for available and `[-]` for missing.
- Each missing item shows the one command that installs it — but you rarely need
  to: star fetches features **on demand** the first time you use them.
- It's read-only and exits immediately, so it's safe to run anywhere.

## Next steps

- Install everything up front:  `star --install-optional` (or a preset:
  `star --install-optional thin`).
- [`../list-plugins`](../list-plugins) — the pluggable backends/formats/exporters.
- [Installation guide](../../../installation.md) for the full extras matrix.
