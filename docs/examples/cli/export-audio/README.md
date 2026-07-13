# Export a document to spoken audio

Turn any document star can open into a WAV file — the same pipeline the GUI's
**File > Export > Audio...** uses. Great for producing an audio version of
lecture notes, articles, or study materials to listen to on the go.

**You'll need:** `star-reader` with a TTS voice available. On Windows and macOS
the system voices (SAPI5 / NSSpeech) work out of the box; on Linux install
`pyttsx3` or `espeak-ng`.

## Run it

    cd docs/examples/cli/export-audio
    python run.py

## What you should see

    Document: Photosynthesis
    Voice:    pyttsx3
    Saving:   .../out/photosynthesis.wav

    Done — 736 KB written to .../out/photosynthesis.wav

    Tip: change the format by changing the extension:
      .mp3 / .ogg / .mp4 — requires ffmpeg or pydub

(The voice and file size depend on your system's TTS engine and speaking rate.)

## How it works

- The script loads `sample.md` with `load_document()`, then creates a
  `TTSManager` (the same object the GUI uses for playback and export).
- `mgr.export_audio(text, path)` synthesizes the document's plain text and
  writes it to the destination path. The output format is inferred from the
  file extension — `.wav` works everywhere; `.mp3`, `.ogg`, and `.mp4` need
  ffmpeg or pydub.
- If no TTS voice is available the script prints guidance and exits cleanly.
- The output directory is cleaned up after the demo.

## Next steps

- [`../list-voices`](../list-voices) — see every voice star can use.
- Want subtitles too? `export_audio` accepts a `subtitle_path` argument that
  writes a synchronized SRT or VTT alongside the audio.
- Full export options: [Features](../../../features.md).
