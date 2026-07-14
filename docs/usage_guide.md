# 📖 Usage Guide

How to launch `star`, the quick command reference, the full keyboard map, the
TUI `M-x` command set, the Qt screen layout, and the command-line options.

- [Running star](#running-star)
- [First run](#first-run)
- [Common tasks (how-to)](#common-tasks-how-to)
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

## First run

The first time you launch the Qt GUI, star helps you get set up. None of these
steps is required — you can skip everything and start reading immediately.

### The guided tour

A short, skippable walkthrough of the controls that matter most — opening a
file, play/pause, changing speed, highlights & notes, the Voice Manager, the
library, and the reading aids — appears as a small floating card near each
control.

1. Read a step, then press **Right / Enter / N** for **Next** or **Left /
   Backspace / B** for **Back**.
2. Press **Esc** (or click **Skip tour**) to dismiss it. It will not pop up
   again on its own.
3. To take it again any time, choose **Help ▸ Guided Tour** (**Shift+F1**).

The tour is non-blocking (the window stays live behind it) and each step is
spoken to your screen reader as it appears.

### Pick your language

star's menus, toolbar, and messages are available in English, Spanish, French,
German, and Portuguese (the terminal UI is translatable too). Arabic is also
included as a first right-to-left catalog.

1. On first launch, the **Optional Features** window opens with an **Interface
   language** dropdown at the top — choose your language there. The whole
   interface switches immediately, with no restart.
2. To change it later, use **View ▸ Interface Language** in the Qt GUI.

**Right-to-left languages.** Selecting a right-to-left interface language (such
as Arabic) mirrors the whole app — menus, toolbar, and panels flip to the right
— and the reading view renders right-to-left as well. Switching back to a
left-to-right language restores the normal layout live, with no restart.

### Add optional features (no `pip` needed)

star runs fully on its own; extra capabilities (OCR, an offline dictionary,
summarize, translate, and more) are optional downloads. On first launch a
chooser lets you pick what to fetch:

1. Pick a preset — **Thin** (lightweight everyday reading and study aids) or
   **All** (everything star can use) — or tick individual features. Each entry
   shows its purpose and approximate download size.
2. Click **Install selected** (or **Not now** to skip). star downloads the
   packages in the background while you keep reading.
3. Reopen the chooser any time from **Tools ▸ Install Optional Features…**.

You never have to run `pip` yourself. See
[Getting an optional feature on demand](#getting-an-optional-feature-on-demand)
below for what happens when you first use a feature you haven't installed yet.

### Check for updates

star does **not** phone home unless you ask it to. To see whether a newer
release is on PyPI, choose **Help ▸ Check for Updates…**. It reports the result
either way — a newer version (with a link), "up to date", or an offline
notice. (Power users: `star --check-update` does the same from the command
line.)

---

## Common tasks (how-to)

Task-oriented steps for the everyday workflows. Shortcuts below are the Qt GUI
defaults; every one is remappable from **Help ▸ Customize Shortcuts…**
(`Ctrl+Alt+Q`).

### Find text in the current document

An incremental find bar searches the open document as you type.

1. Press **Ctrl+F** (or **Edit ▸ Find…**). A search bar opens at the bottom of
   the window with focus in the input box.
2. Start typing. Matches highlight live; every match is tinted amber and the
   active one bright orange, and a **"N of M"** counter shows your position.
3. Press **Enter** (or **Next**) for the next match, **Shift+Enter** (or
   **Previous**) for the previous one. **F3 / Shift+F3** work too. Search
   **wraps around** the ends of the document.
4. Tick **Match case** for case-sensitive searching.
5. Press **Esc** (or the **×** button) to close the bar and clear the
   highlights.

The match count is also announced to screen readers, so you hear "3 of 12" or
"No matches" without leaving the search box.

### Set bookmarks and jump back and forth

Bookmarks are named positions saved per document; navigation history remembers
where you jumped from so you can retrace your steps. Both are shared with the
terminal UI, so a bookmark set in one interface shows up in the other.

**Add and use bookmarks**

1. Move to the spot you want to remember, then press **Ctrl+M** (or
   **Bookmarks ▸ Add Bookmark**). star saves it with an auto-name (`mark1`,
   `mark2`, …) and shows the position percentage in the status bar.
2. To name it yourself, use **Bookmarks ▸ Add Named Bookmark…** and type a name.
3. To return to one, open **Bookmarks ▸ Bookmarks…**, pick an entry (they are
   listed in document order), and press **Enter** or click **Go**. Use
   **Delete** to remove one.

**Back / forward history**

Every jump — a bookmark, a heading move, a search result — records where you
came from.

1. Press **Alt+←** (or **Navigate ▸ Back**) to step back to your previous
   reading position.
2. Press **Alt+→** (or **Navigate ▸ Forward**) to move forward again.

### Search your whole library by content

star can search *inside* every document in your library, not just their titles
and metadata.

1. Point star at a folder of documents as a library first
   (**File ▸ Open Folder as Library…**, or run `star <folder>`). See
   [Build a library](#build-a-library) below if you haven't set one up.
2. Open the library with **Ctrl+Shift+B** (**File ▸ Library / Bookshelf…**) and
   type in the filter box to narrow by title, path, or folder. Press **Enter**
   to open the highlighted document.
3. For a content search — finding documents by words that appear *inside* them —
   use **`M-x library-search`** in the terminal UI, which matches titles,
   authors, DOI/ISBN, annotations, and full document text. The full-text index
   is built on demand the first time you search and cached, so later searches
   are fast.

### Choose and download voices (Voice Manager)

The Voice Manager gathers every installed voice — across all your speech
engines — plus downloadable neural voices, in one searchable place.

1. Press **F4** (or **Speech ▸ Voice Manager…**).
2. Type in the **Filter** box to narrow the list by language or name, or tick
   **Favorites only** to see just your pinned voices.
3. Select a voice and click **Preview** to hear a short sample without
   committing to it.
4. Click **Set as Current** (or press **Enter** / double-click) to start using
   it for speech.
5. Click **Toggle Favorite** to pin a voice; favorites are marked with a ★ and
   persist across sessions.

**Download an offline Piper neural voice**

High-quality **Piper** neural voices (nine, covering all five interface
languages) appear in the list marked with a ⬇ download tag.

1. Select a ⬇ voice and click **Download**. star fetches the model in the
   background and reports progress.
2. When it finishes, star switches to the Piper engine and selects the new
   voice automatically — it works right away, fully offline from then on.

Worked example: [`docs/examples/cli/list-voices`](examples/cli/list-voices) shows every voice star can see.

### Pick a speech engine (system and cloud voices)

Beyond the built-in engines, star can also speak with your operating system's
own voices or with a cloud service. Change engines from **Speech ▸ Choose TTS
Engine…** (**Ctrl+Shift+G**), or `M-x tts-backend` in the terminal UI. The
Voice Manager (**F4**) then lists that engine's voices for filtering and
preview.

- **`elevenlabs` — cloud neural voices (opt-in).** Premium neural speech from
  the ElevenLabs service. **Nothing is sent anywhere** until you both paste your
  key and select a cloud voice: put your key in the **`elevenlabs_api_key`**
  setting (edit `settings.json` via **`M-x settings`**, or set the
  `ELEVENLABS_API_KEY` environment variable), then select the `elevenlabs`
  engine and choose a voice. With no key the engine stays unavailable and star
  keeps using a local engine; on any network error it silently falls back to a
  local voice too. Cloud voices are never auto-selected.

### Study what you read (spaced repetition)

Your highlights and notes can become a review deck that schedules each card for
you (using the FSRS spaced-repetition algorithm).

**Make cards**

1. Select a passage and apply a **Highlight** (toolbar button or
   **Ctrl+Shift+1…5**).
2. Add a note with **Ctrl+Shift+A** (**Notes ▸ Add Note at Cursor…**). The
   highlighted passage becomes the front of a card and your note the back.

**Review due cards**

1. Choose **Study ▸ Review Due Cards…** (**Ctrl+Shift+F5**).
2. Read the prompt on the front, then press **Enter** (or **Show Answer**) to
   reveal the note.
3. Grade your recall with **1** = Again, **2** = Hard, **3** = Good, **4** =
   Easy (or click the buttons). star reschedules the card immediately and moves
   to the next one — closing mid-session loses nothing.

The header shows how many cards are due and a running retention estimate.

**Export cards / sync with Anki**

- Export an Anki deck with **File ▸ Export ▸ Anki Flashcards…** (**Ctrl+Alt+H**).
  When prompted, answer **Yes** to also generate **cloze** (fill-in-the-blank)
  cards from your highlighted passages.
- To sync two-way with a running Anki, choose **Study ▸ Sync with Anki
  (AnkiConnect)…** (this needs the AnkiConnect add-on in Anki; if Anki isn't
  running you get a friendly hint instead of an error).

### Getting an optional feature on demand

When you use a feature whose add-on isn't installed yet, star offers to fetch it
for you — there is **never** a `pip install` instruction to copy.

1. Trigger the feature (for example **Tools ▸ Transcribe Audio File…**). If its
   add-on is missing, star asks *"Install `<feature>`?"* and shows the
   approximate download size.
2. Click **Install** (Yes). star downloads it in the background while you keep
   reading.
3. Most features become usable in the same session, and the status bar confirms
   *"… installed — you can use it now."* Only the large **speech-to-text**
   (dictation) pack asks you to **restart star** before using it.

Power users can install features from the command line instead:
`star --install-optional` (installs the `all` preset), `star --install-optional
thin`, or a comma-separated list of feature keys such as
`star --install-optional ocr,dictionary`. Run it with no value to list every
feature with its size and install status.

### Type by voice (Voice Typing)

Voice Typing dictates speech straight into the document at the cursor (unlike
Dictate Note, which files a separate annotation).

1. Choose **Tools ▸ Voice Typing** (**Ctrl+Alt+K**) or click the microphone
   button on the toolbar. star enters edit mode and starts listening; speech
   playback pauses while you record.
2. Speak, then toggle it off (same shortcut/button) to insert the transcribed
   text at the cursor.

### Reading aids for comfortable reading

star includes several aids for low-vision, dyslexic, and fatigued readers. All
live under **View ▸ Reading Aids** unless noted.

- **High-contrast (AAA) theme.** Press **F5** to cycle themes until you reach
  **high-contrast**, or pick it directly with **View ▸ Choose Theme…**
  (**Ctrl+Alt+T**). It clears the AAA 7:1 contrast ratio for low-vision
  readers.
- **Follow your operating system.** By default star adopts your desktop's
  light / dark / high-contrast appearance on startup and keeps tracking it —
  until you deliberately pick a theme yourself, after which your choice sticks.
- **Dyslexia-friendly font.** Toggle **View ▸ Reading Aids ▸ Dyslexia-Friendly
  Font** (**Ctrl+Alt+X**) to apply the **OpenDyslexic** typeface across the
  whole interface — document, menus, toolbar, and panels. If no such font is
  installed, star fetches OpenDyslexic automatically in the background (no `pip`,
  nothing to install by hand) and falls back gracefully offline.
- **Reading font chooser.** For more choices than the dyslexia toggle, open
  **View ▸ Reading Aids ▸ Reading Font** and pick **Default**, **OpenDyslexic**,
  **Atkinson Hyperlegible** (a Braille Institute face designed for low vision),
  or **Lexend**. The chosen font applies everywhere; each is fetched on first use
  in the background (no `pip`). Menu-only — no shortcut. (The `Ctrl+Alt+X`
  toggle above is a quick shortcut for OpenDyslexic on/off.)
- **Syllable splitting.** Toggle **View ▸ Reading Aids ▸ Syllable Splitting** to
  show words broken into syllables (`read·a·bil·i·ty`) — a decoding aid. It is
  display-only, so speech and highlighting are unaffected. Menu-only — no
  shortcut. (Installs itself on first use, then works immediately with no
  restart.)
- **Reading ruler.** Toggle **View ▸ Reading Aids ▸ Reading Ruler** to show a
  movable, translucent band (a typoscope) that follows the caret line to help
  you keep your place. To adjust its height, opacity, and band color, open
  **Edit ▸ Preferences… (Ctrl+,)** — or **Tune Reading Ruler…** in the
  **Command Palette (F2)** for live tuning; the color picker there includes a
  **Use highlight color** button to match the reading highlight. The toggle is
  menu-only — no shortcut.
- **Highlight colors.** Open **Edit ▸ Preferences… (Ctrl+,)** — or **Tune
  Karaoke Highlight…** in the **Command Palette (F2)** — to pick the
  spoken-**Word color** and, for **Both**
  granularity, the **Sentence color** band — the band can **follow the theme**
  (a **Use theme** button) or use a color you choose, so the word and the band
  stand apart.
- **Follow-scroll.** While speech plays, the reading view auto-scrolls to keep
  the spoken word in a steady middle reading band instead of drifting to the
  bottom edge. It is on by default; turn it off with the `qt_autoscroll` setting.
- **RSVP one-word mode.** Turn on **View ▸ Reading Aids ▸ RSVP Mode**
  (**Ctrl+Alt+E**) to show one word at a time in a large panel synced to
  speech — an aid many dyslexic readers find easier to track. Choose where the
  panel sits in **Edit ▸ Preferences… (Ctrl+,)**, or with **Tune RSVP
  Position…** in the **Command Palette (F2)**.
- **Clickable footnotes.** In documents with footnotes, click a footnote marker
  to jump to the note; a ↩ backlink jumps you back to where you were reading.
- **Math rendering.** Inline LaTeX math is rendered as readable Unicode, so
  equations are spoken and shown as text rather than raw `\command` markup.

Walkthrough: [`docs/examples/gui/reading-aids`](examples/gui/reading-aids).

<a id="build-a-library"></a>
### Build a library

Point star at *any* folder — including one synced by Dropbox, OneDrive,
Syncthing, or iCloud — and every document inside it becomes your library.

1. Use **File ▸ Open Folder as Library…**, or run `star <folder>`, and pick a
   folder.
2. Browse everything (alongside recently-opened files) via **File ▸ Library /
   Bookshelf…** (**Ctrl+Shift+B**).
3. Reading progress is saved per document and travels with the folder, so you
   can read on one machine and pick up where you left off on another.

### Read very large documents smoothly

For very large documents, star can render only a window of the document at a
time (pagination) so the first page appears almost instantly instead of after a
multi-second layout.

1. Pagination is **opt-in**. Turn it on by setting **`qt_paginate_large_docs`**
   to `true` in `settings.json` (open it with **`M-x settings`**, or **Tools**
   in the TUI).
2. Once enabled, it engages **automatically** only when a document is very large
   (past roughly 60,000 words) — smaller documents render whole as before.
3. It is **transparent to reading**: playback, highlighting, and Define Word
   stay correct across page boundaries, and the status bar notes when a document
   is paginated.

Two things always render the **whole** document (so nothing is missed):

- **Find** (`Ctrl+F`) searches the entire document, not just the visible window.
- **Highlighting** a document — or turning on **Highlight Difficult Words** —
  renders it in full so highlight placement stays exact. Highlighting a very
  large document turns pagination off for that session (with a status note).

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
| New document | File ▸ New | `Ctrl+N` | — |
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
| Export audiobook (M4B) | File ▸ Export ▸ Export Audiobook (M4B)… | — (menu only) | — |
| Export Anki flashcards | File ▸ Export ▸ Anki Flashcards… | `Ctrl+Alt+H` | — |
| Quit | File ▸ Quit | `Ctrl+Q` | `M-x quit` (`q`) |
| Play / pause | (Playback toolbar) | `Space` · tap `Ctrl` | `M-x play` / `pause` (`Space`) |
| Stop | (Playback toolbar) | `Esc` | `M-x stop` (`Esc`) |
| Speed up (+20 wpm) | (Playback toolbar) | `Ctrl+=` | `M-x rate-up` (`+`) |
| Slow down (−20 wpm) | (Playback toolbar) | `Ctrl+-` | `M-x rate-down` (`-`) |
| Play from cursor / selection | — | `Ctrl+Space` | `Enter` / `Ctrl+Space` |
| Cycle speed preset | — | `F8` | `M-x speed <name>` (`F8`) |
| Toggle SSML prosody | — | `Ctrl+Alt+Y` | `M-x ssml` |
| Choose TTS engine | Speech ▸ Choose TTS Engine… | `Ctrl+Shift+G` | `M-x tts-backend` |
| Choose voice | Speech ▸ Choose Voice… | `Ctrl+Shift+V` | `M-x tts-voice` (`Ctrl+T`) |
| Voice Manager (filter/preview/favorite/download) | Speech ▸ Voice Manager… | `F4` | — |
| Pronunciation lexicon | Speech ▸ Pronunciation Lexicon… | `Ctrl+Shift+I` | `M-x pron-add` / `pron-list` |
| Speech Cursor mode | (SC toolbar button) | `Tab` | `Tab` |
| Next / previous heading | (Navigate toolbar) | `Ctrl+H` / `Ctrl+Shift+H` | `h` / `<` |
| Next / previous paragraph | (Navigate toolbar) | `Ctrl+P` / `Ctrl+Shift+P` | `p` / `P` |
| Replay paragraph | (Navigate toolbar) | `Ctrl+R` | `r` |
| Next / previous table | — | `Ctrl+T` / `Ctrl+Shift+T` | `t` / `T` |
| Next / previous sentence | (Navigate toolbar) | `Alt+.` / `Alt+,` | `.` / `,` |
| History: back / forward | Navigate ▸ Back / Forward | `Alt+←` / `Alt+→` | `H` / `L` |
| Add bookmark | Bookmarks ▸ Add Bookmark | `Ctrl+M` | `M-x bookmark-set` |
| Add named bookmark | Bookmarks ▸ Add Named Bookmark… | — | `M-x bookmark-set <name>` |
| List / jump to bookmarks | Bookmarks ▸ Bookmarks… | — | `M-x bookmark-list` / `bookmark-goto` |
| Save settings as a profile | Profiles ▸ Save Current Settings… | `Ctrl+Shift+K` | `M-x profile-save <name>` |
| Load a profile | Profiles ▸ Load Profile… | `Ctrl+Shift+J` | `M-x profile-load <name>` |
| Delete a profile | Profiles ▸ Delete Profile… | `Ctrl+Shift+Y` | `M-x profile-delete <name>` |
| Toggle edit mode | (Edit toolbar button) | `Ctrl+E` | — |
| Save document | (Save toolbar button) | `Ctrl+S` | — |
| Bold / italic / underline (edit mode) | Format ▸ Bold / Italic / Underline | `Ctrl+B` / `Ctrl+I` / `Ctrl+U` | — |
| Insert link (edit mode) | Format ▸ Insert Link | `Ctrl+K` | — |
| Live HTML preview | View ▸ Live HTML Preview | `Ctrl+Shift+Z` | — |
| Check spelling | Edit ▸ Check Spelling | `F7` | — |
| Preferences (Reading / Reading Aids / Voice / Display / Fonts / General) | Edit ▸ Preferences… | `Ctrl+,` | — |
| Find in document (find bar) | Edit ▸ Find… | `Ctrl+F` | `M-x search` (`/`) |
| Find next / previous match | (find bar Next / Previous) | `Enter`/`F3` · `Shift+Enter`/`Shift+F3` | `n` / `N` |
| Search backward (TUI) | — | — | `M-x search-backward` (`?`) |
| Cycle color theme (incl. high-contrast) | View ▸ Next Theme | `F5` | `F5` |
| Choose theme by name | View ▸ Choose Theme… | `Ctrl+Alt+T` | `M-x theme <name>` |
| Reload CSS themes | View ▸ Reload CSS Themes | `Ctrl+Shift+R` | — |
| Open themes folder | View ▸ Open Themes Folder | `Ctrl+Shift+F` | — |
| Toggle Contents panel | View ▸ Toggle Contents Panel | `Ctrl+\` | — |
| Toggle Notes panel | View ▸ Toggle Notes Panel | `Ctrl+Shift+N` | `M-x annotations-list` |
| Change font | View ▸ Change Font… | `Ctrl+Alt+F` | `M-x font <family>` |
| Text spacing | View ▸ Reading Aids ▸ Text Spacing… | `Ctrl+Alt+W` | — |
| Karaoke highlight / granularity / colors | Edit ▸ Preferences… (or Command Palette: Tune Karaoke Highlight…) | `Ctrl+,` | `M-x highlight-granularity` |
| Dyslexia-friendly font | View ▸ Reading Aids ▸ Dyslexia-Friendly Font | `Ctrl+Alt+X` | — |
| Reading font (Default/OpenDyslexic/Atkinson/Lexend) | View ▸ Reading Aids ▸ Reading Font | — (menu only) | — |
| Bionic reading | View ▸ Reading Aids ▸ Bionic Reading | `Ctrl+Alt+J` | — |
| Syllable splitting | View ▸ Reading Aids ▸ Syllable Splitting | — (menu only) | — |
| Current-line highlight | View ▸ Reading Aids ▸ Current-Line Highlight | `Ctrl+Alt+L` | — |
| Reading ruler | View ▸ Reading Aids ▸ Reading Ruler | — (menu only) | — |
| Reading ruler height / opacity / color | Edit ▸ Preferences… (or Command Palette: Tune Reading Ruler…) | `Ctrl+,` | — |
| Highlight difficult words | View ▸ Reading Aids ▸ Highlight Difficult Words | `Ctrl+Alt+O` | — |
| RSVP mode | View ▸ Reading Aids ▸ RSVP Mode | `Ctrl+Alt+E` | `M-x rsvp-mode` |
| RSVP position | Edit ▸ Preferences… (or Command Palette: Tune RSVP Position…) | `Ctrl+,` | `M-x rsvp-position` |
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
| Voice typing (dictate into document) | Tools ▸ Voice Typing | `Ctrl+Alt+K` | — |
| Toggle transcript timestamps | Tools ▸ Toggle Transcript Timestamps | `Ctrl+Alt+Z` | — |
| Reading statistics | Tools ▸ Reading Statistics… | `Ctrl+Shift+S` | `M-x reading-stats` |
| Install optional features | Tools ▸ Install Optional Features… | — | (`star --install-optional` CLI) |
| Review due cards (spaced repetition) | Study ▸ Review Due Cards… | `Ctrl+Shift+F5` | — |
| Sync with Anki (AnkiConnect) | Study ▸ Sync with Anki… | — | — |
| Clear document cache | Tools ▸ Clear Document Cache | `Ctrl+Shift+Delete` | `M-x cache-clear` |
| Command palette | — | `F2` | `F2` · `M-x` · `:` |
| Keyboard cheat sheet | Help ▸ Keyboard Shortcuts | `F3` | `M-x shortcuts` (`?`) |
| Customize shortcuts | Help ▸ Customize Shortcuts… | `Ctrl+Alt+Q` | — |
| Guided tour (replay) | Help ▸ Guided Tour | `Shift+F1` | — |
| Check for updates | Help ▸ Check for Updates… | — | (`star --check-update` CLI) |
| Open documentation | Help ▸ Open Documentation | — | — |
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
| Play from cursor / selection | `Ctrl+Space` | `Enter` / `Ctrl+Space` |
| Choose TTS engine | `Ctrl+Shift+G` | `M-x tts-backend` |
| Choose voice | `Ctrl+Shift+V` | `Ctrl+T` |
| Pronunciation lexicon | `Ctrl+Shift+I` | `M-x pron-add` / `pron-list` |
| Speech Cursor mode | `Tab` | `Tab` |
| Toggle SSML prosody | `Ctrl+Alt+Y` | `M-x ssml` |
| Cycle speed preset | `F8` | `F8` |

Walkthrough: [`docs/examples/gui/read-aloud`](examples/gui/read-aloud).

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
| Play from cursor / selection | `Ctrl+Space` | `Enter` / `Ctrl+Space` |

### Caret navigation (TUI)

The arrow keys move a free, word-granularity reading caret through the
document — the view follows it, and `Enter` reads aloud from wherever it
stands. While speech plays, the caret follows the spoken word (the
`tui_caret_follow_speech` setting, on by default), so `Enter` always resumes
"from here"; a deliberate caret move gets a ~3-second grace window during
which the view stays with you instead of snapping back to the speech.

| Key | Action |
|---|---|
| `←` / `→` | Move the caret one word back / forward |
| `↑` / `↓` | Move the caret one line (sticky column; view follows) |
| `PgUp` / `PgDn` | Move the caret one screenful |
| `Home` / `End` | Caret to beginning / end of document |
| `Enter` (or `Ctrl+Space`) | Read aloud from the caret |
| `Ctrl+X` / `Esc` | Stop reading |
| `j` / `k` | Plain scroll one line (caret-free, classic behavior) |
| `H` | History: go back to previous position |
| `L` | History: go forward |

### File & export

| Action | Qt GUI | TUI |
|---|---|---|
| New document | `Ctrl+N` | — |
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
| Export audiobook (M4B) | File ▸ Export ▸ Export Audiobook (M4B)… | — |
| Reload document | — | `F9` |
| Quit | `Ctrl+Q` | `Ctrl+Q`   `q` |

### Editing

| Key | Action |
|---|---|
| `Ctrl+E` | Enter edit mode; while editing, **finish** and return to read mode (offers to save if there are unsaved changes) |
| `Ctrl+S` | Save and **keep editing** (in edit mode); export as Markdown in read mode |
| `Ctrl+Shift+Z` | Toggle the live HTML preview pane (enters edit mode if needed) |
| `Ctrl+Z` / `Ctrl+Y` | Undo / redo |
| `Ctrl+B` / `Ctrl+I` / `Ctrl+U` | Bold / italic / underline the selection (edit mode) |
| `Ctrl+K` | Insert a Markdown link — [text](url) (edit mode) |
| `Ctrl+X` / `Ctrl+C` / `Ctrl+V` | Cut / copy / paste |
| `Ctrl+C` | Copy selection or current paragraph (read mode) |

**In the TUI:** `Ctrl+E` / `M-x edit` opens the document's source in your
`$VISUAL`/`$EDITOR` and reloads it when the editor exits (text formats in
place; binary formats via a Markdown draft plus a Save-As prompt), and
`Ctrl+N` / `M-x new-document` creates a new Markdown file the same way.

**Live-edit loop:** `Ctrl+S` saves in place and leaves you in edit mode, so you
can keep typing and formatting without being bounced to read mode. Formatting
actions update the live preview immediately. When you're done, `Ctrl+E` finishes
editing — and if anything is unsaved it asks whether to save, discard, or cancel.

**Find & Replace:** while editing, the find bar (`Ctrl+F`, or **Edit ▸ Find &
Replace…**) has a **Replace ▾** toggle that reveals a replacement field. Use
**Replace** to change the current match and advance, or **Replace All** to change
every match at once (a single undo step). Replacing is available only in edit
mode; in read mode the bar is find-only.

**Tables & images:** **Format ▸ Insert Table…** (also a toolbar button) drops in
a Markdown table of the size you choose, and **Add Table Row** appends a row to
the table your cursor is in. **Format ▸ Insert Image…** picks an image and
inserts `![alt](path)` — using a path relative to the saved document when it can,
so the reference keeps working if you move the pair together.

**Autosave & crash recovery:** while you edit with unsaved changes, star quietly
snapshots your work every few seconds. If star is quit or crashes before you
save, the next launch offers to **recover** it — handy for brand-new **Untitled**
documents that have no file to fall back on. Turn it off with the
`autosave_recovery` setting (see [Configuration](configuration.md)).

**Export a draft mid-edit:** the **File ▸ Export** commands (Markdown, PDF,
Braille, audio, subtitles, audiobook) act on the **live editor buffer**, so you
can export what you're working on without saving or leaving edit mode first.

Walkthrough: [`docs/examples/gui/write-and-export`](examples/gui/write-and-export).

### Search

In the Qt GUI, `Ctrl+F` opens an incremental **find bar** at the bottom of the
window with a live match counter, next/previous, a case toggle, and wrap-around
(see [Find text in the current document](#find-text-in-the-current-document)).

| Action | Qt GUI | TUI |
|---|---|---|
| Open find bar / search forward | `Ctrl+F` | `Ctrl+F`   `/` |
| Next match | `Enter`   `F3` | `n` |
| Previous match | `Shift+Enter`   `Shift+F3` | `N` |
| Toggle case sensitivity | (Match case checkbox) | — |
| Search backward | — | `Ctrl+R`   `?` |
| Close find / clear search | `Esc` | `Esc`   `C-g` |

In the Qt find bar, every match is tinted amber and the active match bright
orange, with a "N of M" counter. In the TUI, the current match shows in magenta
and the others in blue.

### Bookmarks & navigation history

| Action | Qt GUI | TUI |
|---|---|---|
| Add bookmark (auto-named) | `Ctrl+M` | `M-x bookmark-set` |
| Add named bookmark | Bookmarks ▸ Add Named Bookmark… | `M-x bookmark-set <name>` |
| List / jump to bookmarks | Bookmarks ▸ Bookmarks… | `M-x bookmark-list` / `bookmark-goto` |
| History: back | `Alt+←` | `H` |
| History: forward | `Alt+→` | `L` |

Bookmarks are stored per document and shared between the Qt GUI and the TUI, so
a bookmark set in one interface appears in the other.

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
| Tune karaoke highlight (style / colors / speed) | `Ctrl+,` (Preferences) / Command Palette (F2) | — |
| Highlight granularity (word/sentence/both) | `Ctrl+,` (Preferences) | `M-x highlight-granularity` |
| Dyslexia-friendly font | `Ctrl+Alt+X` | — |
| Reading font (Default/OpenDyslexic/Atkinson/Lexend) | View ▸ Reading Aids ▸ Reading Font | — |
| Bionic reading | `Ctrl+Alt+J` | — |
| Syllable splitting | View ▸ Reading Aids ▸ Syllable Splitting | — |
| Current-line highlight | `Ctrl+Alt+L` | — |
| Reading ruler (+ height/opacity/color in Preferences) | View ▸ Reading Aids ▸ Reading Ruler / `Ctrl+,` | — |
| RSVP mode | `Ctrl+Alt+E` | `M-x rsvp-mode` |
| RSVP position picker | `Ctrl+,` (Preferences) / Command Palette (F2) | `M-x rsvp-position` |
| Live HTML preview (edit mode) | `Ctrl+Shift+Z` | — |
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

### Study (Qt GUI)

Notes and highlights become spaced-repetition cards. See
[Study what you read](#study-what-you-read-spaced-repetition).

| Action | Shortcut |
|---|---|
| Review due cards | `Ctrl+Shift+F5` |
| Sync with Anki (AnkiConnect) | Study ▸ Sync with Anki… |
| Export Anki flashcards (with optional cloze cards) | `Ctrl+Alt+H` |
| Reveal card answer (in review) | `Enter` |
| Grade recall: Again / Hard / Good / Easy | `1` / `2` / `3` / `4` |

### Tools & help

| Action | Qt GUI | TUI |
|---|---|---|
| Transcribe audio file | `Ctrl+Alt+S` | — |
| Dictate note (record) | `Ctrl+Alt+V` | — |
| Voice typing (dictate into document) | `Ctrl+Alt+K` | — |
| Toggle transcript timestamps | `Ctrl+Alt+Z` | — |
| Reading statistics | `Ctrl+Shift+S` | `M-x reading-stats` |
| Install optional features | Tools ▸ Install Optional Features… | (`star --install-optional`) |
| Clear document cache | `Ctrl+Shift+Delete` | `M-x cache-clear` |
| Command palette | `F2` | `F2`   `M-x`   `:` |
| Keyboard cheat sheet | `F3` | `M-x shortcuts`   `?` |
| Customize shortcuts | `Ctrl+Alt+Q` | — |
| Guided tour (replay) | `Shift+F1` | — |
| Check for updates | Help ▸ Check for Updates… | (`star --check-update`) |
| Command history (session log) | Help ▸ Command History… | — |
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
| `library-search` | Multi-criteria search over the library (title, DOI, ISBN, author, annotation text, and full document text) |
| `reading-stats` (`stats`) | Show the reading-statistics dashboard |
| `cache-clear` | Delete the cached version of the current document |

### Library & Metadata

| Command | Description |
|---|---|
| `metadata-edit` | Edit the current document's metadata (title, author, year, DOI, ISBN, publisher) with optional DOI/ISBN lookup |
| `library-search` | Search the library by title/path/annotation and full document text (`query`), DOI, ISBN, and/or author |

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
| `tts-backend` | Switch TTS engine at runtime (`pyttsx3`/`espeak`/`festival`/`piper`/`coqui`/`dectalk`/`elevenlabs`/`none`) |
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
│  word is shown with an orange background highlight                   │  ← word highlight
│  (in the default theme).                                             │
├──────────────────────────────────────────────────────────────────────┤
│ Document Title   Line 42/380   11%                                   │  ← status bar
│   Space:play/pause  Enter:read-here  Ctrl-O:open  Ctrl-F:search      │  ← key hints
│ M-x: open█                                                           │  ← minibuffer
└──────────────────────────────────────────────────────────────────────┘
```

In the TUI the terminal cursor is always parked at the **minibuffer** so screen
readers receive echoed text in one predictable location; the document scrolls
visually without moving the cursor.

### Qt menus

**File menu** — New (`Ctrl+N`, opens a blank document in edit mode), Open…, Open
URL…, Open Archive…, Open Feed…, Edit Document
Metadata…, Library / Bookshelf…, Batch Convert, Watch Folder, Export ▸
(Markdown / PDF / Braille (BRF) / Audio / Subtitles / Video (MP4) / **Export
Audiobook (M4B)…** / Anki Flashcards), Quit. **Export Audiobook (M4B)…** writes
a chaptered `.m4b` (chapters come from the document's headings) for listening on
the go; it is menu-only and needs `ffmpeg` on your PATH.

**Edit menu** — Find… (`Ctrl+F`, the incremental find bar), **Find & Replace…**
(the find bar with the replace row shown; edit mode), Copy, Toggle Edit
Mode, Save, Check Spelling, and **Preferences…** (`Ctrl+,`) — all reader
settings in one tabbed dialog (Reading, Reading Aids, Voice, Display, Fonts, General).

**Format menu** — Markdown authoring commands (also on the edit-mode formatting
toolbar): Undo, Redo, Bold (`Ctrl+B`), Italic (`Ctrl+I`), Underline (`Ctrl+U`),
Inline Code, Heading, Bullet List, Numbered List, Block Quote, Insert Link
(`Ctrl+K`), Horizontal Rule, **Insert Table…**, **Add Table Row**, and **Insert
Image…**. The commands apply to the Markdown source and no-op with a hint outside
edit mode.

**Highlight menu** — Highlight Yellow / Green / Cyan / Pink / Orange, Clear All
Highlights. (`Ctrl+H` is the **Next Heading** shortcut, matching NVDA/JAWS
convention; use the toolbar Highlight button or this menu to apply colors.)

**Navigate menu** — sentence / paragraph / heading / table moves, plus **Back**
(`Alt+←`) and **Forward** (`Alt+→`) through your navigation history.

**Bookmarks menu** — Add Bookmark (`Ctrl+M`), Add Named Bookmark…, and
Bookmarks… (the jump/delete list).

**Study menu** — Review Due Cards… (`Ctrl+Shift+F5`, spaced-repetition review of
your notes and highlights) and Sync with Anki (AnkiConnect)….

**View menu** — Toggle Contents Panel (`Ctrl+\`), Toggle Notes Panel
(`Ctrl+Shift+N`), Next Theme (`F5`), Choose Theme…, Reload CSS Themes, Open
Themes Folder, Change Font…, Reading Level (`Ctrl+L`), and **Reading Aids ▸**
Text Spacing… /
Reading Font (Default / OpenDyslexic / Atkinson Hyperlegible / Lexend) /
Dyslexia-Friendly Font / Bionic Reading / Syllable Splitting / Current-Line
Highlight / Reading Ruler /
Highlight Difficult Words / Define Word… / RSVP Mode / Live HTML Preview.
(Karaoke-highlight, reading-ruler, and RSVP-position settings live in
**Edit ▸ Preferences…** (`Ctrl+,`); the live-tuning dialogs are in the
**Command Palette (F2)** as Tune Karaoke Highlight… / Tune Reading Ruler… /
Tune RSVP Position….)

**Speech menu** — Play/Pause, Stop, speed, Choose TTS Engine… (`Ctrl+Shift+G`;
engines include the opt-in `elevenlabs` cloud engine — see [Pick a speech engine](#pick-a-speech-engine-system-and-cloud-voices)),
Choose Voice…, **Voice Manager…** (`F4`, filter / preview / favorite / download
voices), Speech Cursor Mode, and the Pronunciation Lexicon.

**Tools menu** — leads with **Install Optional Features…** (the download
chooser), then Transcribe Audio File…, Dictate Note…, **Voice Typing**
(`Ctrl+Alt+K`), Summarize / Translate, Reading Statistics…, and Clear Document
Cache.

**Help menu** — Command Palette…, Keyboard Shortcuts…, Customize Shortcuts…,
**Guided Tour** (`Shift+F1`), Help (`F1`), Open Documentation, **Command
History…**, **Check for Updates…**, and **About star** (`Ctrl+F1`) — a short summary of what star is and
does, the version and license, and a clickable link to the project on GitHub
(opens in your browser).

**Profiles, Notes, Citations menus** — see the
[Quick command reference](#quick-command-reference) for every item, its menu
path, and its shortcut.

### Toolbar

The toolbar is divided into labeled groups separated by dividers: **File** (New
· Open · URL), **Playback** (Play/Pause · Stop · − Speed · + Speed), **Navigate**
(sentence / paragraph / heading moves), **Voice / Mode** (Voice… · SC · Voice
Typing 🎙), **Text** (Copy · Highlight · Clear Highlights), **View** (Theme · ToC
· Level · Font), **Edit** (Edit · Save), and **App** (Help · Quit). Every button
shows a tooltip describing its action and keyboard shortcut. In edit mode a
second **Formatting** toolbar appears (Undo · Redo · Bold · Italic · Underline ·
Inline Code · Heading · Bullet/Numbered List · Quote · Link · Horizontal Rule);
it is hidden while reading.

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

Worked example: [`docs/examples/cli/extract-text`](examples/cli/extract-text).

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
| `--install-optional [PRESET]` | Install optional features and exit — no `pip` needed. `PRESET` is `thin`, `all` (default), or a comma-separated list of feature keys (e.g. `ocr,dictionary`). Run with no value to list every feature with its size and status |
| `--check-update` | Check PyPI for a newer release of star and exit (best-effort, offline-safe; prints the result as plain text) |
| `--plugins [SUBCOMMAND]` | Inspect the plugin system and exit: `list` (registered backends / format handlers / exporters), `info <group> <name>`, or `api` (the plugin contracts) |
| `--version` | Print version number and exit |
| `--help` | Print help summary and exit |

---

Worked examples for many of these options are in [`docs/examples/`](examples/).

See also: [Installation](installation.md) · [Features](features.md) ·
[Configuration](configuration.md) · [Architecture](architecture.md).
