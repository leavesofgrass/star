# 🎬 Karaoke Video Export

`star` can produce a sentence-synchronized karaoke MP4 video from any document.
The video shows a rendered page image while the TTS voice reads it aloud; the
current sentence is highlighted and all other text is dimmed, advancing sentence
by sentence through the document.

- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Settings reference](#settings-reference)
- [Troubleshooting](#troubleshooting)

---

## Quick start

### Qt GUI

1. Open a document.
2. **File ▸ Export ▸ Video (MP4)…** (`Ctrl+Alt+V`).
3. Choose an output path (`.mp4` extension).
4. The export runs on a background thread — the status bar shows progress and
   confirms the output path when done.

### TUI

```
M-x export-video [/path/to/output.mp4]
```

If no path is given, star prompts for one.

### CLI

There is no dedicated CLI flag for video export; open the file in the GUI or
TUI and use one of the methods above.

---

## How it works

The pipeline runs in five stages:

1. **TTS synthesis** — the document's plain text is synthesized to a temporary
   WAV file using the active TTS backend. The WAV's duration is measured; if no
   TTS engine is available the pipeline stops with a clear error.

2. **Sentence segmentation** — the plain text is split into sentences using the
   same regex boundary detector used for subtitle export (`_SENTENCE_SPLIT_RE`).

3. **Proportional cue timing** — each sentence is assigned a time window
   proportional to its character length. Longer sentences receive more time;
   the total matches the WAV duration exactly.

4. **Frame rendering** — one PNG frame is rendered per sentence (the highlighted
   sentence is the frame's "identity"; all other text is dimmed). Two renderers
   are tried in order:
   - **Qt offscreen (primary)** — `QTextDocument` → `QImage` with per-span
     `QTextCharFormat` for the highlight. Requires PyQt6 or PyQt5.
   - **Pillow fallback** — word-wrapped text drawn on a bitmap with a
     translucent rectangle behind the highlighted sentence. Requires `Pillow`
     (`pip install "star-reader[video]"`).
   - If neither renderer is available, the pipeline stops with an error.

5. **ffmpeg assembly** — a `concat.txt` demuxer list is generated with one entry
   per frame; each entry specifies the frame's duration. ffmpeg assembles the
   frames into a video stream, mixes in the WAV audio, and optionally muxes a
   soft SRT subtitle track (`-c:s mov_text`), producing the final MP4.

---

## Requirements

| Component | Required | Install |
|---|---|---|
| A TTS engine | Yes | Any backend star supports (pyttsx3, espeak, etc.) |
| ffmpeg | Yes | `winget install Gyan.FFmpeg` · `brew install ffmpeg` · `apt install ffmpeg` |
| PyQt6 or PyQt5 | Primary renderer | Already in the star base deps; usually present |
| Pillow | Fallback renderer | `pip install "star-reader[video]"` |

ffmpeg must be on the system `PATH`. On Windows the recommended install is
[Gyan.dev ffmpeg builds](https://www.gyan.dev/ffmpeg/builds/) or winget:

```powershell
winget install Gyan.FFmpeg
```

Check that ffmpeg is visible:

```bash
ffmpeg -version
```

Check your dependency status with:

```bash
star --deps
```

The `Pillow (video frame renderer)` row will show ✓ or × and the install hint.

---

## Settings reference

Video-export settings live under the `"video"` key in `settings.json`:

| Key | Default | Description |
|---|---|---|
| `resolution` | `"1280x720"` | Output resolution (`WxH`); libx264 requires even dimensions — star rounds up automatically |
| `theme` | `""` | Color theme for the frame renderer (`""` = use the active reading theme) |
| `font_scale` | `1.0` | Scale factor applied to the base font size in frame rendering |
| `subtitles` | `"soft"` | `"soft"` = embed SRT as a muxed subtitle track selectable in the player; `"none"` = no subtitle track |
| `last_export_dir` | `""` | Remembered last export directory (updated automatically) |

Edit these in `settings.json` or change them at runtime via `M-x settings`.

### Resolution

```json
"video": { "resolution": "1920x1080" }
```

Common values: `"1280x720"` (720p, default), `"1920x1080"` (1080p),
`"3840x2160"` (4K). The width and height must be even; star rounds odd
dimensions up automatically (libx264 requirement).

### Subtitles

`"soft"` embeds the SRT track as a selectable subtitle stream in the MP4
container — the viewer can turn it on or off in their media player. `"none"`
produces a plain video+audio MP4 with no subtitle track.

---

## Troubleshooting

**"ffmpeg not found"** — ffmpeg is not on PATH. Install it and restart the
terminal so `star` picks up the new PATH.

**"TTS synthesis failed"** — no TTS backend is available or the document
produced empty plain text. Run `star --deps` to check your TTS installation,
or try `M-x tts-backend` to pick a working engine first.

**"No frame renderer available"** — neither Qt nor Pillow is installed.
`pip install "star-reader[video]"` installs Pillow.

**Video is blank / shows only a placeholder** — the Pillow fallback rendered
frames but could not load a font; the output uses the default PIL bitmap font
(small, unscaled). Install a system TTF font or set `STAR_VIDEO_FONT_PATH` to
a `.ttf` file path.

**Video has no audio** — the WAV synthesis step failed silently. Check that the
active TTS backend can produce audio (`M-x export-audio` is a simpler test).

**Subtitle track missing in the player** — make sure `"subtitles": "soft"` is
set and the player supports embedded MP4 subtitles (VLC, mpv, and most modern
players do). Some players require you to enable the track explicitly.

**Frame count mismatch / truncated video** — if the document has very short
sentences (fewer characters than 1% of total), some may receive near-zero
duration. This is cosmetic and does not cause errors, but very short flashes
will appear. Try increasing `font_scale` or reducing `resolution` to give the
renderer more room per sentence.

---

See also: [Features](features.md) · [Usage Guide](usage_guide.md) ·
[Configuration](configuration.md).
