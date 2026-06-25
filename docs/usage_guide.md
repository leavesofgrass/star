# 📖 Usage Guide

How to launch `star`, the quick command reference, the full keyboard map, the
TUI `M-x` command set, the Qt screen layout, and the command-line options.

- [Running star](#running-star)
- [Quick command reference](#quick-command-reference) — **feature → GUI menu · shortcut · TUI command**
- [Keyboard shortcuts](#keyboard-shortcuts)
- [M-x commands (TUI)](#m-x-commands-tui)
- [Qt screen layout & menus](#qt-screen-layout--menus)
- [Plain-text mode](#plain-text-mode)
- [Command-line options](#command-line-options)

---

## Running star

```bash
star                        # launch Qt GUI (default when PyQt6/PyQt5 is installed)
star document.pdf          # open a PDF in the Qt GUI
star https://example.com   # fetch and read a URL
star notes.md              # open a Markdown file
star --tui report.docx     # force terminal UI mode
star --plain paper.pdf     # extract clean text to stdout (no UI)
star --rate 200 book.epub  # open with a slower reading speed
star --theme contrast      # start with the high-contrast theme
star --list-themes         # print available theme names and exit
star --list-voices         # list available TTS voices and exit
star --keytest             # open the key-code diagnostic tool (TUI)
```

The `star` command is provided by the wheel and the installer scripts. Running
from a source checkout instead? Use `python -m star …` (or `python run_star.py
…`) with the same arguments.

**Default mode:** The Qt GUI is star's primary interface — it opens
automatically when PyQt6/PyQt5 is installed. Without Qt, star falls back to the
secondary terminal TUI; use `--tui` to force the terminal interface even when Qt
is available.

---

## Quick command reference

Every primary feature mapped to its **Qt GUI menu path**, its **keyboard
shortcut**, and its **TUI command palette** (`M-x`) command. A `—` means the
action is not available in that interface. In the Qt GUI, tapping the `Ctrl` key
on its own also toggles play/pause (a JAWS habit; chords like `Ctrl+O` never
trigger it).

| Feature | GUI menu path | Keyboard shortcut | TUI palette command |
|---|---|---|---|
| Open a file | File ▸ Open… | `Ctrl+O` | `M-x open` (`Ctrl+O`) |
| Open a URL | File ▸ Open URL… | `Ctrl+Shift+O` | `M-x open-url` |
| Open an RSS / Atom feed | File ▸ Open Feed… | `Ctrl+Shift+M` | — |
| Open an archive | File ▸ Open Archive… | — | `M-x open-archive` |
| Edit document metadata | File ▸ Edit Document Metadata… | — | `M-x metadata-edit` |
| Library / Bookshelf | File ▸ Library / Bookshelf… | `Ctrl+Shift+B` | `M-x library` |
| Library search | — | — | `M-x library-search` |
| Batch convert files | File ▸ Batch Convert | `Ctrl+Shift+C` | `M-x batch-convert` |
| Watch a hot folder | File ▸ Watch Folder | `Ctrl+Shift+W` | (`star --watch` CLI) |
| Export as Markdown | File ▸ Export ▸ Export as Markdown… | `Ctrl+Alt+M` | `M-x export-markdown` |
| Export as PDF | File ▸ Export ▸ Export as PDF… | `Ctrl+Alt+P` | — |
| Export as Braille (BRF) | File ▸ Export ▸ Export as Braille… | `Ctrl+Alt+B` | `M-x export-braille` |
| Export as Audio | File ▸ Export ▸ Export as Audio… | `Ctrl+Alt+A` | `M-x export-audio` |
| Export subtitles (SRT/VTT) | File ▸ Export ▸ Export Subtitles… | `Ctrl+Alt+U` | `M-x export-subtitles` |
| Export karaoke video (MP4) | File ▸ Export ▸ Video (MP4)… | `Ctrl+Alt+V` | `M-x export-video` |
| Export Anki flashcards | File ▸ Export ▸ Anki Flashcards… | `Ctrl+Alt+H` | — |
| Quit | File ▸ Quit | `Ctrl+Q` | `M-x quit` (`q`) |
| Play / pause | (Playback toolbar) | `Space` · tap `Ctrl` | `M-x play` / `pause` (`Space`) |
| Stop | (Playback toolbar) | `Esc` | `M-x stop` (`Esc`) |
| Speed up (+20 wpm) | (Playback toolbar) | `Ctrl+=` | `M-x rate-up` (`+`) |
| Slow down (−20 wpm) | (Playback toolbar) | `Ctrl+-` | `M-x rate-down` (`-`) |
| Play from cursor / selection | — | `Ctrl+Return` | — |
| Cycle speed preset | — | `F8` | `M-x speed <name>` (`F8`) |
| Toggle SSML prosody | — | `Ctrl+Alt+Y` | `M-x ssml` |
| Choose TTS engine | Speech ▸ Choose TTS Engine… | `Ctrl+Shift+G` | `M-x tts-backend` |
| Choose voice | Speech ▸ Choose Voice… | `Ctrl+Shift+V` | `M-x tts-voice` (`Ctrl+T`) |
| Pronunciation lexicon | Speech ▸ Pronunciation Lexicon… | `Ctrl+Shift+I` | `M-x pron-add` / `pron-list` |
| Speech Cursor mode | (SC toolbar button) | `Tab` | `Tab` |
| Next / previous heading | (Navigate toolbar) | `Ctrl+H` / `Ctrl+Shift+H` | `h` / `<` |
| Next / previous paragraph | (Navigate toolbar) | `Ctrl+P` / `Ctrl+Shift+P` | `p` / `P` |
| Replay paragraph | (Navigate toolbar) | `Ctrl+R` | `r` |
| Next / previous table | — | `Ctrl+T` / `Ctrl+Shift+T` | `t` / `T` |
| Next / previous sentence | (Navigate toolbar) | `Alt+.` / `Alt+,` | `.` / `,` |
| Save settings as a profile | Profiles ▸ Save Current Settings… | `Ctrl+Shift+K` | `M-x profile-save <name>` |
| Load a profile | Profiles ▸ Load Profile… | `Ctrl+Shift+J` | `M-x profile-load <name>` |
| Delete a profile | Profiles ▸ Delete Profile… | `Ctrl+Shift+Y` | `M-x profile-delete <name>` |
| Toggle edit mode | (Edit toolbar button) | `Ctrl+E` | — |
| Save document | (Save toolbar button) | `Ctrl+S` | — |
| Live HTML preview | View ▸ Live HTML Preview | `Ctrl+Shift+L` | — |
| Check spelling | Edit ▸ Check Spelling | `F7` | — |
| Search forward | — | `Ctrl+F` | `M-x search` (`/`) |
| Search backward | — | — | `M-x search-backward` (`?`) |
| Cycle color theme | View ▸ Next Theme | `F5` | `F5` |
| Choose theme by name | View ▸ Choose Theme… | `Ctrl+Alt+T` | `M-x theme <name>` |
| Reload CSS themes | View ▸ Reload CSS Themes | `Ctrl+Shift+R` | — |
| Open themes folder | View ▸ Open Themes Folder | `Ctrl+Shift+F` | — |
| Toggle Contents panel | View ▸ Toggle Contents Panel | `Ctrl+\` | — |
| Toggle Notes panel | View ▸ Toggle Notes Panel | `Ctrl+Shift+N` | `M-x annotations-list` |
| Change font | View ▸ Change Font… | `Ctrl+Alt+F` | `M-x font <family>` |
| Text spacing | View ▸ Reading Aids ▸ Text Spacing… | `Ctrl+Alt+W` | — |
| Karaoke highlight / granularity | View ▸ Reading Aids ▸ Karaoke Highlight… | `Ctrl+Alt+K` | `M-x highlight-granularity` |
| Dyslexia-friendly font | View ▸ Reading Aids ▸ Dyslexia-Friendly Font | `Ctrl+Alt+X` | — |
| Bionic reading | View ▸ Reading Aids ▸ Bionic Reading | `Ctrl+Alt+J` | — |
| Current-line highlight | View ▸ Reading Aids ▸ Current-Line Highlight | `Ctrl+Alt+L` | — |
| Highlight difficult words | View ▸ Reading Aids ▸ Highlight Difficult Words | `Ctrl+Alt+O` | — |
| RSVP mode | View ▸ Reading Aids ▸ RSVP Mode | `Ctrl+Alt+E` | `M-x rsvp-mode` |
| RSVP position | View ▸ Reading Aids ▸ RSVP Position… | — | `M-x rsvp-position` |
| Show reading level | View ▸ Reading Level | `Ctrl+L` | `M-x reading-level` |
| Interface language | View ▸ Interface Language | — | — |
| Highlight selection (5 colors) | Highlight ▸ Yellow … Orange | `Ctrl+Shift+1` … `Ctrl+Shift+5` | — |
| Clear all highlights | Highlight ▸ Clear All Highlights | `Ctrl+Shift+0` | — |
| Add note at cursor | Notes ▸ Add Note at Cursor… | `Ctrl+Shift+A` | `M-x annotate` (`a`) |
| Edit selected note | Notes ▸ Edit Note | `Ctrl+Shift+E` | `M-x annotation-goto` |
| Delete selected note | Notes ▸ Delete Note | `Ctrl+Shift+D` | `M-x annotation-delete` |
| Export notes | Notes ▸ Export Notes… | `Ctrl+Alt+N` | `M-x annotations-export` |
| Import citations | Citations ▸ Import… | `Ctrl+Alt+I` | — |
| Export citations | Citations ▸ Export… | `Ctrl+Alt+E` | — |
| Add citation | Citations ▸ Add Citation… | `Ctrl+Alt+C` | — |
| Add citation by DOI | Citations ▸ Add by DOI… | `Ctrl+Alt+D` | — |
| Insert citation at cursor | Citations ▸ Insert at Cursor | `Ctrl+Alt+R` | — |
| Manage / browse citations | Citations ▸ Manage / Browse… | `Ctrl+Alt+G` | — |
| Summarize document | Tools ▸ Summarize Document | `Ctrl+Shift+U` | — |
| Translate document | Tools ▸ Translate Document | `Ctrl+Shift+X` | — |
| Transcribe audio file | Tools ▸ Transcribe Audio File… | `Ctrl+Alt+S` | — |
| Dictate note (record) | Tools ▸ Dictate Note (record)… | `Ctrl+Alt+V` | — |
| Toggle transcript timestamps | Tools ▸ Toggle Transcript Timestamps | `Ctrl+Alt+Z` | — |
| Reading statistics | Tools ▸ Reading Statistics… | `Ctrl+Shift+S` | `M-x reading-stats` |
| Clear document cache | Tools ▸ Clear Document Cache | `Ctrl+Shift+Delete` | `M-x cache-clear` |
| Command palette | — | `F2` | `F2` · `M-x` · `:` |
| Keyboard cheat sheet | Help ▸ Keyboard Shortcuts | `F3` | `M-x shortcuts` (`?`) |
| Customize shortcuts | Help ▸ Customize Shortcuts… | `Ctrl+Alt+Q` | — |
| Open README (help) | Help ▸ Help | `F1` | `F1` (`M-x help`) |
| About star | Help ▸ About star | `Ctrl+F1` | `M-x about` |

---

## Keyboard shortcuts

Both interfaces share the same navigation philosophy — single-letter or
`Ctrl+letter` shortcuts follow **NVDA / JAWS browse-mode conventions** so
screen-reader users have the same muscle memory in both modes.

> **Every Qt GUI menu item has a keyboard shortcut.** The shortcut is shown next
> to each command in its menu, and the full set is listed below (and in **Help →
> Keyboard Shortcuts**, `F3`). Each binding is owned by exactly one action, so
> there are no "ambiguous shortcut" conflicts. Any binding can be remapped from
> **Help → Customize Shortcuts…** (`Ctrl+Alt+Q`).
>
> **Modifier scheme:** `Ctrl+letter` = forward / primary action,
> `Ctrl+Shift+letter` = backward / secondary, `Alt+punctuation` = sentence
> navigation, and `Ctrl+Alt+letter` = exports, citations, tools, and reading aids.

### Play / pause with the Ctrl key (JAWS habit)

Tapping (pressing and releasing) the **`Ctrl`** key on its own toggles speech,
mirroring the JAWS muscle memory of hitting Ctrl to silence speech. Using Ctrl as
a modifier in a chord (`Ctrl+O`, `Ctrl+H`, …) never triggers it — only a clean
solo tap does. It is active while the document view has focus and can be turned
off with the `qt_ctrl_pause` setting.

### Playback (both modes)

| Action | Qt GUI | TUI |
|---|---|---|
| Play / pause | `Space`  ·  tap `Ctrl` | `Space` |
| Stop | `Esc` | `Esc` |
| Speed up (+20 wpm) | `Ctrl+=` | `+` |
| Slow down (−20 wpm) | `Ctrl+-` | `-` |
| Play from cursor / selection | `Ctrl+Return` | — |
| Choose TTS engine | `Ctrl+Shift+G` | `M-x tts-backend` |
| Choose voice | `Ctrl+Shift+V` | `Ctrl+T` |
| Pronunciation lexicon | `Ctrl+Shift+I` | `M-x pron-add` / `pron-list` |
| Speech Cursor mode | `Tab` | `Tab` |
| Toggle SSML prosody | `Ctrl+Alt+Y` | `M-x ssml` |
| Cycle speed preset | `F8` | `F8` |

The default reading rate is **265 wpm**. New users should start at 150–180 wpm
and increase gradually.

### Profiles (saved setting bundles)

| Action | Qt GUI | TUI |
|---|---|---|
| Save current settings as a profile | `Ctrl+Shift+K` | `M-x profile-save <name>` |
| Load a profile | `Ctrl+Shift+J` | `M-x profile-load <name>` |
| Delete a profile | `Ctrl+Shift+Y` | `M-x profile-delete <name>` |
| List profiles | Profiles menu | `M-x profile-list` |

### Structure navigation (both modes)

Keys are shared between the Qt GUI and the TUI. The TUI also accepts the legacy
bracket keys as fallbacks.

| Action | Qt GUI | TUI |
|---|---|---|
| Next heading (reads aloud) | `Ctrl+H` | `h`   `>`   `}` (legacy) |
| Previous heading (reads aloud) | `Ctrl+Shift+H` | `<`   `{` (legacy) |
| Next paragraph | `Ctrl+P` | `p`   `Ctrl+P`   `]` (legacy) |
| Previous paragraph | `Ctrl+Shift+P` | `P`   `[` (legacy) |
| Replay paragraph | `Ctrl+R` | `r`   `Ctrl+R` |
| Next table | `Ctrl+T` | `t` |
| Previous table | `Ctrl+Shift+T` | `T` |
| Next sentence | `Alt+.` | `.` |
| Previous sentence | `Alt+,` | `,` |
| Replay sentence | `Alt+;` | `;` |
| Play from cursor / selection | `Ctrl+Return` | — |

### Scroll navigation (TUI)

| Key | Action |
|---|---|
| `↑` / `k` | Scroll one line up |
| `↓` / `j` | Scroll one line down |
| `PgUp` / `b` | Page up |
| `PgDn` | Page down |
| `Home` | Jump to beginning of document |
| `End` | Jump to end of document |
| `H` | History: go back to previous position |
| `L` | History: go forward |

### File & export

| Action | Qt GUI | TUI |
|---|---|---|
| Open a file | `Ctrl+O` | `Ctrl+O` |
| Open a URL | `Ctrl+Shift+O` | `M-x open-url` |
| Open an archive | File ▸ Open Archive… | `M-x open-archive` |
| Edit document metadata | File ▸ Edit Document Metadata… | `M-x metadata-edit` |
| Library / Bookshelf | `Ctrl+Shift+B` | `M-x library` |
| Library search | — | `M-x library-search` |
| Export as Markdown | `Ctrl+Alt+M` | `M-x export-markdown` |
| Export as PDF | `Ctrl+Alt+P` | — |
| Export as Braille (BRF) | `Ctrl+Alt+B` | `M-x export-braille` |
| Export as Audio | `Ctrl+Alt+A` | `M-x export-audio` |
| Export Subtitles (SRT/VTT) | `Ctrl+Alt+U` | `M-x export-subtitles` |
| Export karaoke video (MP4) | `Ctrl+Alt+V` | `M-x export-video` |
| Reload document | — | `F9` |
| Quit | `Ctrl+Q` | `Ctrl+Q`   `q` |

### Editing (Qt GUI only)

| Key | Action |
|---|---|
| `Ctrl+E` | Toggle edit mode (raw Markdown ↔ rendered view) |
| `Ctrl+S` | Save in edit mode; export as Markdown in read mode |
| `Ctrl+Shift+L` | Toggle the live HTML preview pane (enters edit mode if needed) |
| `Ctrl+Z` / `Ctrl+Y` | Undo / redo |
| `Ctrl+X` / `Ctrl+C` / `Ctrl+V` | Cut / copy / paste |
| `Ctrl+C` | Copy selection or current paragraph (read mode) |

### Search

| Action | Qt GUI | TUI |
|---|---|---|
| Search forward | `Ctrl+F` | `Ctrl+F`   `/` |
| Search backward | — | `Ctrl+R`   `?` |
| Next match | — | `n` |
| Previous match | — | `N` |
| Clear search | `Esc` | `Esc`   `C-g` |

All matches are highlighted: current match in magenta, others in blue.

### View & reading aids

| Action | Qt GUI | TUI |
|---|---|---|
| Cycle color theme | `F5` | `F5` |
| Choose theme by name | `Ctrl+Alt+T` | `M-x theme <name>` |
| Reload CSS themes | `Ctrl+Shift+R` | — |
| Open themes folder | `Ctrl+Shift+F` | — |
| Toggle Contents panel | `Ctrl+\` | — |
| Toggle Notes panel | `Ctrl+Shift+N` | `M-x annotations-list` |
| Change font | `Ctrl+Alt+F` | — |
| Text spacing | `Ctrl+Alt+W` | — |
| Tune karaoke highlight | `Ctrl+Alt+K` | — |
| Highlight granularity (word/sentence/both) | `Ctrl+Alt+K` (dialog) | `M-x highlight-granularity` |
| Dyslexia-friendly font | `Ctrl+Alt+X` | — |
| Bionic reading | `Ctrl+Alt+J` | — |
| Current-line highlight | `Ctrl+Alt+L` | — |
| RSVP mode | `Ctrl+Alt+E` | `M-x rsvp-mode` |
| RSVP position picker | — | `M-x rsvp-position` |
| Live HTML preview (edit mode) | `Ctrl+Shift+L` | — |
| Show reading level | `Ctrl+L` | `M-x reading-level` |
| Toggle line numbers | — | `F6` |
| Toggle syntax highlight | — | `F7` |

### Highlights (Qt GUI)

| Action | Shortcut |
|---|---|
| Highlight selection — Yellow / Green / Cyan / Pink / Orange | `Ctrl+Shift+1` … `Ctrl+Shift+5` |
| Clear all highlights | `Ctrl+Shift+0` |

### Notes / annotations

| Action | Qt GUI | TUI |
|---|---|---|
| Add note at cursor | `Ctrl+Shift+A` | `a`   `M-x annotate` |
| Edit selected note | `Ctrl+Shift+E` | `M-x annotation-goto` |
| Delete selected note | `Ctrl+Shift+D` | `M-x annotation-delete` |
| Toggle Notes panel | `Ctrl+Shift+N` | `M-x annotations-list` |
| Export notes | `Ctrl+Alt+N` | `M-x annotations-export` |

### Citations (Qt GUI)

| Action | Shortcut |
|---|---|
| Import citations | `Ctrl+Alt+I` |
| Export citations | `Ctrl+Alt+E` |
| Add citation | `Ctrl+Alt+C` |
| Add citation by DOI | `Ctrl+Alt+D` |
| Insert citation at cursor | `Ctrl+Alt+R` |
| Manage / browse citations | `Ctrl+Alt+G` |

### Tools & help

| Action | Qt GUI | TUI |
|---|---|---|
| Transcribe audio file | `Ctrl+Alt+S` | — |
| Dictate note (record) | `Ctrl+Alt+V` | — |
| Toggle transcript timestamps | `Ctrl+Alt+Z` | — |
| Reading statistics | `Ctrl+Shift+S` | `M-x reading-stats` |
| Clear document cache | `Ctrl+Shift+Delete` | `M-x cache-clear` |
| Command palette | `F2` | `F2`   `M-x`   `:` |
| Keyboard cheat sheet | `F3` | `M-x shortcuts`   `?` |
| Customize shortcuts | `Ctrl+Alt+Q` | — |
| Open README.md (help) | `F1` | `F1` |
| About star | `Ctrl+F1` | `M-x about` |

---

## M-x commands (TUI)

These are the commands of the **secondary terminal UI**, opened with `M-x`,
`F2`, or `:` — begin typing any part of a command name and press `Tab` to
complete.

> In the primary **Qt GUI** you rarely need the palette: the same actions live in
> the menus, each with its own keyboard shortcut (see the
> [Quick command reference](#quick-command-reference) and **Help → Keyboard
> Shortcuts**, `F3`).

### Document

| Command | Description |
|---|---|
| `open` | Open a local file |
| `open-url` | Fetch and open a URL |
| `close` | Close the current document |
| `reload` | Reload the current document from disk |
| `export-markdown` | Save the rendered document as a `.md` file |
| `batch-convert` | Convert many files / a folder to one format (Markdown, text, or Braille) |
| `export-braille` | Export a BRF braille file (requires `louis`) |
| `open-archive [path]` | Open an archive (ZIP/TAR/.7z/.rar) and browse its members |
| `export-audio [fmt]` | Synthesize document to audio; `fmt` is `mp3` (default), `ogg`, `mp4`, or `wav` |
| `export-subtitles` | Write a timestamped **SRT/VTT** caption track synchronized to the speech |
| `export-video [path]` | Export a sentence-synchronized karaoke MP4 video |
| `subtitle-format srt\|vtt` | Set the caption format used for subtitle export |
| `subtitle-word-level` | Toggle one cue per word vs. sentence-grouped cues |
| `subtitles-with-audio` | Toggle emitting captions automatically alongside audio export |
| `recent` | Pick from recently opened files |
| `library` (`bookshelf`) | Browse the document library and reopen a document |
| `library-search` | Multi-criteria search over the library (title, DOI, ISBN, author, annotation text) |
| `reading-stats` (`stats`) | Show the reading-statistics dashboard |
| `cache-clear` | Delete the cached version of the current document |

### Library & Metadata

| Command | Description |
|---|---|
| `metadata-edit` | Edit the current document's metadata (title, author, year, DOI, ISBN, publisher) with optional DOI/ISBN lookup |
| `library-search` | Search the library by title/path/annotation (`query`), DOI, ISBN, and/or author |

### Speech

| Command | Description |
|---|---|
| `play` | Begin or resume TTS |
| `stop` | Stop TTS |
| `pause` | Pause TTS |
| `speak-line` | Read the current line without advancing |
| `rate-up` | Increase reading rate by 20 wpm |
| `rate-down` | Decrease reading rate by 20 wpm |
| `volume-up` | Increase TTS volume |
| `volume-down` | Decrease TTS volume |
| `tts-backend` | Switch TTS engine at runtime (`pyttsx3`/`espeak`/`festival`/`piper`/`coqui`/`dectalk`/`none`) |
| `highlight-granularity word\|sentence\|both` | Highlight the spoken word, the whole sentence, or both |
| `tts-voice` | Switch TTS voice by ID |
| `ssml-on` / `ssml-off` | Enable/disable SSML prosody markup |
| `speed <name>` | Apply a named speed preset: `skim`, `normal`, `study`, `slow` |
| `speed-add <name> <wpm>` | Define a new speed preset |
| `speed-list` | List all defined speed presets |

### Search & Navigation

| Command | Description |
|---|---|
| `search` | Search forward |
| `search-backward` | Search backward |
| `search-regex` | Search with a regular expression |
| `goto-line` | Jump to a line number |
| `chapter-list` | List document chapters / headings |
| `chapter-next` / `chapter-prev` | Navigate to adjacent chapter |
| `chapter-goto` | Jump to a named chapter |
| `bookmark-set` | Set a named bookmark at the current position |
| `bookmark-goto` | Jump to a named bookmark |
| `bookmark-list` | List all bookmarks for this document |
| `bookmark-delete` | Delete a named bookmark |

### Display

| Command | Description |
|---|---|
| `theme [name]` | Switch color theme |
| `line-numbers` | Toggle line numbers |
| `syntax-highlight` | Toggle code syntax highlighting |
| `wrap-width` | Set text wrap width in columns |
| `font-size-up` / `font-size-down` | Adjust font size (Qt GUI) |
| `font <family>` | Set font family (Qt GUI) |
| `table-mode` | Switch table reading: `structured`, `flat`, or `skip` |
| `footnote-mode` | Switch footnote handling: `inline`, `deferred`, or `skip` |
| `reading-level` | Show Flesch-Kincaid grade and ease score |
| `rsvp-mode` | Toggle RSVP one-word-at-a-time overlay on/off |
| `rsvp-position` | Choose the panel position (9 named positions) |

### Abbreviations, Pronunciations & Numbers

| Command | Description |
|---|---|
| `abbrev-add` | Add a custom abbreviation expansion for TTS |
| `abbrev-list` | List all active abbreviation expansions |
| `pron-add <term> <spoken>` | Add/update a pronunciation override for a term |
| `pron-remove <term>` | Remove a pronunciation override |
| `pron-list` | List all pronunciation overrides |
| `pronunciations` | Toggle the pronunciation lexicon on/off |

### Voice & Profile Presets

| Command | Description |
|---|---|
| `profile-save <name>` | Save the current settings as a named profile |
| `profile-load <name>` | Apply a saved profile (voice, rate, theme, font, spacing, highlight) |
| `profile-list` | List saved profiles |
| `profile-delete <name>` | Delete a saved profile |

### Notes & Annotations

| Command | Description |
|---|---|
| `annotate` | Add a note at the current reading position (also `a`) |
| `annotations-list [query]` | Browse all notes, optionally filtered (also `A`) |
| `annotations-search` | Prompt for a filter (text or `#tag`) and list matches |
| `annotation-goto <n>` | Jump to note number `n` |
| `annotation-delete <n>` | Delete note number `n` |
| `annotations-export` | Export notes to `.md` / `.json` / `.bib` / `.ris` / `.txt` |

### System

| Command | Description |
|---|---|
| `shortcuts` | Show the keyboard cheat sheet (also `?`) |
| `help` | Open the built-in help manual |
| `about` | Version, author, and license |
| `license` | Full GPL v3 license text |
| `settings` | Open `settings.json` in your system editor |
| `quit` | Exit `star` |

All standard Emacs line-editing keys work inside the minibuffer (`C-a`, `C-e`,
`C-f`, `C-b`, `C-d`, `C-k`, `C-u`, `C-w`, `C-y`, etc.).

---

## Qt screen layout & menus

### Qt GUI

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ File  Highlight  View                                                         │  ← menu bar
├─────┬──────────────────────────────────────────────────────────────────────  │
│     │ [Open] [Play/Pause ▶⏸] [Stop ■] [+ Speed] [− Speed] [SC ○] [Voice…]   │  ← toolbar
│ ToC │ [Theme] [Help] [Quit] [Copy] [Level] [Highlight]                        │
│     ├────────────────────────────────────────────────────────────────────────│
│ Ch1 │                                                                         │
│ Ch2 │  # Chapter 1: Introduction                                              │  ← document
│ Ch3 │                                                                         │     view
│ ... │  This paragraph is being read aloud. The [current]                      │  ← TTS word
│     │  word is shown with a cyan background highlight.                        │     highlight
├─────┴────────────────────────────────────────────────────────────────────────│
│ ▶  "word"  —  42%  —  265 wpm                                                 │  ← status bar
└──────────────────────────────────────────────────────────────────────────────┘
```

### Terminal TUI

```
┌──────────────────────────────────────────────────────────────────────┐
│ star  │  Document Title                ▶ Speaking  265 wpm  pyttsx3  │  ← title bar
├──────────────────────────────────────────────────────────────────────┤
│  # Chapter 1: Introduction                                           │  ← document
│  This paragraph is being read aloud. The [current]                  │     view
│  word is shown with a cyan background highlight.                     │  ← word highlight
├──────────────────────────────────────────────────────────────────────┤
│ Document Title   Line 42/380   11%                                   │  ← status bar
│   Space:read/pause  ↑↓:scroll  Ctrl-O:open  Ctrl-F:search           │  ← key hints
│ M-x: open█                                                           │  ← minibuffer
└──────────────────────────────────────────────────────────────────────┘
```

In the TUI the terminal cursor is always parked at the **minibuffer** so screen
readers receive echoed text in one predictable location; the document scrolls
visually without moving the cursor.

### Qt menus

**File menu** — Open…, Open URL…, Open Archive…, Open Feed…, Edit Document
Metadata…, Library / Bookshelf…, Batch Convert, Watch Folder, Export ▸
(Markdown / PDF / Braille (BRF) / Audio / Subtitles / Video (MP4) / Anki
Flashcards), Quit.

**Highlight menu** — Highlight Yellow / Green / Cyan / Pink / Orange, Clear All
Highlights. (`Ctrl+H` is the **Next Heading** shortcut, matching NVDA/JAWS
convention; use the toolbar Highlight button or this menu to apply colors.)

**View menu** — Toggle Contents Panel (`Ctrl+\`), Toggle Notes Panel
(`Ctrl+Shift+N`), Next Theme (`F5`), Choose Theme…, Reload CSS Themes, Open
Themes Folder, Change Font…, Reading Level (`Ctrl+L`), and **Reading Aids ▸**
Text Spacing… / Karaoke Highlight… / Dyslexia-Friendly Font / Bionic Reading /
Current-Line Highlight / Highlight Difficult Words / Live HTML Preview.

**Speech, Profiles, Notes, Citations, Tools, Help menus** — see the
[Quick command reference](#quick-command-reference) for every item, its menu
path, and its shortcut.

### Toolbar

The toolbar is divided into labeled groups separated by dividers: **File** (Open
· URL), **Playback** (Play/Pause · Stop · − Speed · + Speed), **Navigate**
(sentence / paragraph / heading moves), **Voice / Mode** (Voice… · SC), **Text**
(Copy · Highlight · Clear Highlights), **View** (Theme · ToC · Level · Font),
**Edit** (Edit · Save), and **App** (Help · Quit). Every button shows a tooltip
describing its action and keyboard shortcut.

The left-side **Table of Contents** dock lists all headings in the current
document; click any entry to jump there. Toggle it with `Ctrl+\`.

---

## Plain-text mode

```bash
star --plain document.pdf
```

`--plain` skips all UI and writes clean, stripped plain text to stdout — the same
text the TTS engine would receive. Useful for:

- **Piping** — `star --plain paper.pdf | festival --tts`
- **Batch processing** — extract text from many files in a shell script
- **Word counting** — `star --plain thesis.pdf | wc -w`
- **Headless server use** — where no display is available

---

## Command-line options

```
star [OPTIONS] [FILE_OR_URL]
```

| Option | Description |
|---|---|
| `FILE_OR_URL` | File path or HTTP/HTTPS URL to open on launch |
| `--gui` | Force Qt GUI mode (errors if PyQt6/PyQt5 not installed) |
| `--tui` | Force terminal UI mode even when Qt is available |
| `--plain` | Extract clean text to stdout; no UI |
| `--rate RATE` | Initial TTS reading rate in wpm |
| `--theme THEME` | Initial color theme: `dark`, `light`, `contrast`, `phosphor` |
| `--backend BACKEND` | TTS backend: `auto`, `pyttsx3`, `espeak`, `festival`, `coqui`, `dectalk`, `none` |
| `--watch DIR` | Watch DIR and convert files dropped into it (headless hot-folder mode); requires `--output` |
| `--output DIR` | Output directory for `--watch` conversions |
| `--format FMT` | Output format for `--watch`: `markdown`, `text`, or `braille` (default: markdown) |
| `--keytest` | Open the key-code diagnostic tool (TUI only) |
| `--list-themes` | Print available theme names and exit |
| `--list-voices` | Print available TTS voice IDs and exit |
| `--deps` | Print the status of every optional dependency (installed or not, with install hints) and exit |
| `--version` | Print version number and exit |
| `--help` | Print help summary and exit |

---

See also: [Installation](installation.md) · [Features](features.md) ·
[Configuration](configuration.md) · [Architecture](architecture.md).
