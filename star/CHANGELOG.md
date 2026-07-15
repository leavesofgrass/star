# 📜 Changelog

All notable changes to **star — Speaking Terminal Access Reader** are documented
in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### 🐛 Fixed

- **Your word-highlight color is actually used now.** The spoken-word
  highlight painted every word in the theme's selection color (the default
  theme's purple) no matter what **Preferences ▸ Reading ▸ Word color**
  said: the reader parked the real text cursor on the word with the word
  still *selected*, and the native selection painted over the custom
  highlight. The caret now parks collapsed at the word start — the color
  you pick is the color you see.
- **The Preferences dialog opens maximized.** Six tabs of settings didn't
  fit a small fixed-size dialog on every display — and nobody likes a
  scrolling dialog.
- **No more phantom RSVP checkmark.** Closing the app with RSVP on (or
  applying it from Preferences) persisted `qt_rsvp_mode: true`, but the
  overlay is never restored at startup — so the Reading Aids menu showed a
  checkmark for a mode that wasn't running. RSVP is a live mode, not a
  restorable preference: it is normalized to off at session start, so the
  menu, Preferences, and reality always agree.

### ✨ Added

- **RSVP display options: show exactly the words you want.** The previous
  and next context words are now independently toggleable
  (`qt_rsvp_show_prev` / `qt_rsvp_show_next`, on the Reading and Reading
  Aids tabs) — turn both off and the overlay collapses to only the single
  large word. The old combined switch is migrated.
- **Every reading-aid color is now pickable — right on the Reading Aids
  tab.** Each visual aid pairs its toggle with a color swatch: the spoken
  word, the current-line tint (new `qt_current_line_color` — previously
  always the theme's selection color), the reading ruler, and the RSVP
  overlay's word and panel colors (new `qt_rsvp_text_color` /
  `qt_rsvp_bg_color`; the context words fade the same hue and the panel
  keeps its translucency). Colors apply live, and every swatch has a reset
  button that returns the element to its theme-derived default.
- **Eight popular color themes — in both the GUI and the terminal.**
  Dracula, Nord, Solarized Dark, Solarized Light, Gruvbox Dark, Tokyo
  Night, Catppuccin Mocha, and Monokai join the built-ins, cycled with
  **F5**, picked from **Choose Theme…**, Preferences ▸ Display, or
  `M-x theme` — the same names in both UIs, so a profile carries across.
  Because star is a reader first, every text color clears WCAG AA (4.5:1)
  on its background even where the upstream scheme does not (Solarized's
  canonical accents famously miss; ours are nudged, character intact).
  Each theme is also seeded as an editable CSS file in the themes folder,
  and the terminal versions approximate the palettes in xterm-256 color
  with clean base-8 fallbacks.

### 🔧 Changed

- **The system voice (pyttsx3) is star's default speech engine.** Auto
  engine selection now tries pyttsx3 first — SAPI 5 on Windows, the system
  speech voice on macOS — so a fresh install always starts with the
  familiar OS voice. A bundled DECtalk is the second choice instead of
  jumping the queue (it previously outranked the system voice when
  present); it remains one **Choose TTS Engine…** click away.
- **Theme renames: `obsidian` → `galaxy`, `obsidian-light` →
  `galaxy-light`, `zed-one-dark` → `one-dark`, `zed-one-light` →
  `one-light`.** star's own themes no longer carry another project's name.
  Old names keep working everywhere — saved settings and profiles are
  migrated on load, seeded CSS files are renamed (hand edits carry over),
  and the legacy names still resolve if anything else supplies them.
- **The menu bar slimmed from 15 menus to 11 — with every command and every
  shortcut retained.** **Highlight**, **Notes**, and **Bookmarks** merged
  into one **Annotate** menu; **Citations** joined **Study**; **Profiles**
  moved into **Edit** beside Preferences. Settings-type menu items whose
  home is now Preferences left the menus: the SSML and transcript-timestamp
  toggles, the Interface Language submenu, the Reading Font submenu, the
  theme reload/folder pair, and the Text Spacing dialog entry. Their classic
  shortcuts (Ctrl+Alt+Y, Ctrl+Alt+Z, Ctrl+Alt+W, Ctrl+Shift+R,
  Ctrl+Shift+F) all still work as hidden window-level accelerators, remain
  remappable in Customize Shortcuts, and every command is still one F2
  palette search away.
- **Every setting now has a home in Preferences (Ctrl+,).** Settings that
  previously lived only as menu items — SSML prosody, transcript
  timestamps, caret browsing, bionic reading, the interface language — plus
  two that had no UI at all (table reading mode, skip code blocks) are now
  on the Preferences tabs, with the same live-apply behavior as everything
  else. The Display tab also gained **Reload CSS themes** and **Open themes
  folder…** buttons, and its theme list now includes your custom CSS themes
  alongside the built-ins.
- **`[all]` now includes voice dictation.** The `[transcribe]` stack
  (faster-whisper, sounddevice, numpy) joins the `all` extra — the old
  exclusion dated from the openai-whisper/PyTorch era, when it weighed over
  2 GB; the CTranslate2 stack is ~150 MB. `pipx install "star-reader[all]"`
  now really is batteries-included. The installer scripts' `--all` profile
  matches. Only Coqui TTS and the spaCy `[ner]` backend remain separate.

---

## [0.1.27] 2026-07-14

### 🐛 Fixed

- **The spoken-word highlight stays in sync — even in documents with
  tables.** The map that ties each spoken word to its place in the rendered
  view was built with a rolling text search, and the structured table
  narration ("Table with 3 columns… Row 1…") derailed it: narration-only
  words matched unrelated text further down the page, and from the first
  table to the end of the document the highlight no longer tracked the
  voice. The map is now built by aligning the spoken and rendered word
  streams as sequences, so tables, skipped code blocks, and any other place
  where what is *said* differs from what is *shown* stay in sync — narration
  words simply park the highlight on the content they describe. Both reading
  views are covered: the graphical window and the terminal reader now share
  the same aligner.
- **The highlight can no longer run away from the voice.** The word-timing
  estimate is paced by the speech engine's own word events, but engine
  positions behind the estimate were discarded, so once the estimate crept
  ahead (a slow voice, a long pause) nothing could ever pull it back — after
  1.5 s of silence it sprinted to the end of the document. Engine positions
  are now always recorded and the highlight snaps to the word whose audio is
  actually playing; during a pause it holds instead of running, and the
  free-run escape remains only for engines that stop reporting entirely.
  Measured against a live SAPI5 voice: the painted word now *is* the spoken
  word (drift 0) from the first word to the last.
- **Speech flows across line breaks.** Source files wrapped at a fixed width
  (README files, hand-wrapped Markdown) were spoken with a pause at the end of
  every line, because each raw newline reached the speech engine as a sentence
  boundary. Single newlines inside a paragraph — soft breaks that render as
  spaces — are now joined before speech, so prose reads straight through;
  paragraph breaks (blank lines) still pause naturally.

### ⚠️ Deprecated

- **The legacy openai-whisper (PyTorch) dictation backend.** faster-whisper
  replaced it as the installed and bundled stack in 0.1.25; the Torch path is
  kept only so older installs keep working and is scheduled for removal in
  **0.2.0**. Using it now emits a one-time `DeprecationWarning`. Switch with
  `pip install faster-whisper` (star prefers openai-whisper only when it is
  the one installed, or when forced via `STAR_WHISPER_BACKEND=openai`).

### 🔧 Changed

- **star now describes itself as what it has become: study tools for reading
  *and* writing.** The About dialog, the welcome page, and the PyPI summary
  all said "document reader"; they now cover the writing half too — the
  Markdown editor, voice dictation, and new-document flow — and the welcome
  page gained a short **Write your own** section (`Ctrl+N`, `Ctrl+E`,
  `Ctrl+Alt+K`).
- **The keyboard cheat sheet's GUI/TUI parity table caught up with reality.**
  The TUI column now shows the new editing bindings (`Ctrl+E`, `Ctrl+N`), the
  dictation model picker, and the `M-x transcribe-file` / `M-x dictate-note`
  commands it has had since 0.1.23 but the table still listed as missing.
- **Frozen builds now honor the `whisper_model` setting.** The packaged app
  used to load its bundled base dictation model no matter what `whisper_model`
  said; now the bundle covers the default (`base`, fully offline) and any
  other size is downloaded once and cached, exactly like a pip install. A
  user-set `HF_HUB_OFFLINE` is always respected.

### ✨ Added

- **New documents from the TUI — `Ctrl+N` / `M-x new-document`.** Prompts for
  a destination (default `untitled.md`), seeds a title heading, writes it in
  your `$EDITOR`, and opens the result — File ▸ New parity for the terminal.
- **The TUI can edit documents now — `Ctrl+E` / `M-x edit`.** The terminal
  idiom, not a home-grown editor: star suspends the screen, opens the
  document's source in **`$VISUAL` / `$EDITOR`** (notepad or nano/vi when
  unset), and reloads it when the editor exits — so your own (screen-reader
  configured) editor does the editing. Text formats (Markdown, txt, reST,
  org, AsciiDoc) are edited in place; binary formats (PDF, EPUB, DOCX…) get
  their Markdown conversion as a draft, then a Save-As prompt — mirroring the
  GUI's edit-mode flow.
- **Pick your dictation model size in Preferences ▸ Voice.** A new
  **Dictation model** chooser (tiny / base / small / medium / large-v3 /
  large-v3-turbo) controls the Whisper model used for dictation and audio
  transcription. `base` (the default) ships inside the packaged app and works
  fully offline; larger sizes are more accurate and are downloaded once on
  first use. The TUI has the same picker as **`M-x whisper-model`** (with tab
  completion over the sizes).
- **A runnable `docs/examples/` tree and a Quick start at the top of the README.**
  12 task-focused examples — CLI (extract text, export to audio, list voices,
  check dependencies, list plugins), library (load a document, translate,
  summarize), and GUI walkthroughs (read-aloud, reading aids, write-and-export)
  — each with its own README and real output. A catalog
  (`docs/examples/README.md`) maps every area to an example or a guide, and a
  smoke test (`tests/test_examples_smoke.py`) executes every runnable so they
  can't rot. The README now opens with an install → run → **first 60 seconds** →
  where-next Quick start.

---

## [0.1.26] 2026-07-11

### ✨ Added

- **Authoring depth: the editor grew real writing tools.** In edit mode you can
  now:
  - **Find & Replace** — the Find bar (Ctrl+F) gained a **Replace ▾** row (also
    on **Edit ▸ Find & Replace…**), with Replace and Replace All (a single undo
    step). Replacing is edit-mode only; the row is hidden while reading.
  - **Insert tables** — **Format ▸ Insert Table…** (and a toolbar button) drops
    in a Markdown table of a size you choose, and **Add Table Row** appends a row
    matching the current table's columns.
  - **Insert images** — **Format ▸ Insert Image…** (and a toolbar button) picks
    an image and inserts `![alt](path)`, preferring a path relative to the saved
    document so the reference survives moving the pair.
  - **Export straight from the editor** — Markdown / PDF / Braille / audio /
    subtitle / audiobook / plugin exports now use the **live editor buffer**, so
    you can export a draft mid-edit without saving first (and without losing a
    later Discard — `self.doc` is never mutated).
- **Autosave & crash recovery for in-progress edits.** While you edit with
  unsaved changes, star snapshots the buffer to `<config>/recovery/` every few
  seconds; if star is quit or crashes before you save, the next launch offers to
  **recover** it. This matters most for brand-new **Untitled** documents that
  have no file to fall back on. Snapshots are cleared the moment the work is
  saved or you deliberately leave edit mode, so a recovery prompt only ever
  appears for genuinely lost work. Turn it off with the `autosave_recovery`
  setting.

### 🔧 Changed

- **New Document opens ready to write.** File ▸ New (`Ctrl+N`) now drops you
  straight into edit mode with the **live HTML preview on** and the space
  **split evenly** between the Markdown source and the preview, so you can
  author against a rendered view from the first keystroke. (The 50/50 split also
  applies whenever the preview is turned on — `Ctrl+Shift+Z` — instead of the
  editor keeping nearly all the width.)
- **Voice dictation installs and works in the same session — no restart.** Now
  that speech-to-text is faster-whisper (no PyTorch), the in-app installer pulls
  **faster-whisper (~150 MB)** instead of openai-whisper + PyTorch (~2 GB), and
  the feature becomes usable immediately after it downloads (star re-detects the
  backend live) instead of asking you to close and reopen. Transcribing an audio
  file no longer requires `ffmpeg` on your PATH when using faster-whisper — it
  decodes audio itself.

### 🐛 Fixed

- **Typing in edit mode no longer looks like a rendered heading.** The editor is
  the same widget the read view renders styled HTML into, so switching to the
  Markdown source view could leave the typing format carrying the heading's
  **bold** weight — text typed on the first line of a new document showed up
  bold, as if it were a heading, even without a leading `#`. Entering edit mode
  now strips all block/character formatting so the source is uniformly plain
  text; rendering stays in the live preview where it belongs.
- **The Notes and Contents panes no longer sit open and empty, stealing reading
  space.** Both docks now derive their visibility per-document: the **Notes**
  pane appears only for a document that has notes, and the **Contents** pane only
  for a document that has headings — so the welcome page (which has headings)
  shows its outline, while a new/blank document keeps the full width for text.
  You can still toggle either (`Ctrl+Shift+N` for Notes, `Ctrl+\` for Contents),
  and adding a note reveals the Notes pane. Previously the Notes pane was pinned
  open on every launch after you'd added any note, and the Contents pane was
  always shown. The `qt_show_notes` and `qt_show_toc` settings are retired (any
  saved values are ignored).
- **The docs no longer say offline dictation is missing on macOS.** A cluster of
  packaging/installation docs still described the old Whisper + PyTorch,
  “multi-GB”, “not bundled on macOS” dictation stack; they now match the 0.1.25
  faster-whisper reality.

---

## [0.1.25] 2026-07-11

### 🔧 Changed

- **Offline dictation is now on every desktop — including macOS — and the
  downloads are far smaller.** star's speech-to-text moved from openai-whisper +
  PyTorch to **faster-whisper (CTranslate2)**. The whole dictation stack drops
  from multiple gigabytes to about 140 MB, so the self-contained **Windows
  `star.exe` drops from ~700 MB to ~580 MB** (the vendored ffmpeg/Tesseract/…
  engines are now the bulk; a `-Lean` build without them is ~250 MB), and the
  **macOS `.app` now bundles offline dictation out of the box** at ~380 MB (it
  previously couldn't — Torch was too heavy). Transcription is the same or faster, uses less memory, and no
  longer needs `ffmpeg` on your PATH (faster-whisper decodes audio itself).
  Nothing changes in how you dictate. `pip install "star-reader[transcribe]"`
  now installs faster-whisper; power users can force either backend with
  `STAR_WHISPER_BACKEND=openai|faster`.

### 🐛 Fixed

- **New Document no longer forces you to throw away unsaved work.** Starting a
  new document (File ▸ New / Ctrl+N) while you have unsaved edits now offers
  **Save / Discard / Cancel** — the same choice as finishing editing — instead
  of a discard-or-cancel-only prompt.
- **Screen readers hear the "open a document first" prompts.** The voice-typing,
  dictate-note, and add-annotation guards now speak their message, matching the
  rest of star's spoken feedback.

---

## [0.1.24] 2026-07-09

star grows up as a writing tool: create documents from scratch, format with a
toolbar or the keyboard, dictate straight into the page, and undo mistakes — now
with a smooth live-edit loop that saves without kicking you out of editing. Plus
self-contained download-and-run builds for **all three** desktops (Windows,
macOS, Linux).

### ✨ Added

- **Undo/Redo and a command history.** Made a formatting mistake? **Undo** and
  **Redo** buttons lead the editing toolbar, the standard **Edit** menu (with
  **Ctrl+Z / Ctrl+Y** shown next to them), and the Format menu, and the editor's
  own **Ctrl+Z / Ctrl+Y** still work — each formatting action is a single undo
  step. **Help ▸ Command History…** shows a timestamped log of the
  commands you've run this session (and any errors that came up), with a
  **Copy** button so you can paste it straight into a bug report.
- **Create documents from scratch + a Markdown formatting toolbar.** star is
  now a writing tool, not just a reader. **File ▸ New (Ctrl+N)** opens a blank
  document straight into edit mode, and a second toolbar appears while editing
  with one-click **Bold, Italic, Underline, Inline Code, Heading, Bullet /
  Numbered list, Quote, Link, and Horizontal rule** — so you can author
  Markdown without memorising the syntax (and dictate into it with Voice
  Typing). Saving a new document prompts for a location the first time, then
  it behaves like any other file (Recents, save-in-place). The formatting
  toolbar is hidden in reading mode so it never clutters the view.
- **Keyboard formatting + a Format menu.** The common authoring commands have
  standard, single-owner bindings — **Bold Ctrl+B, Italic Ctrl+I, Underline
  Ctrl+U (wraps `<u>…</u>`), Insert Link Ctrl+K** — gathered under a new
  **Format** menu (with Undo/Redo, Inline Code, Heading, lists, Block Quote,
  and Horizontal Rule). They're also on the editor's right-click menu while
  editing. *Add Bookmark moved from Ctrl+B to **Ctrl+M** ("Mark")* to free
  Ctrl+B for Bold.
- **Reading Aids and Fonts tabs in Preferences.** Two convenience tabs for
  ease of use: **Reading Aids** collects the on/off toggles (spoken-word
  highlight, current-line tint, auto-scroll, reading ruler, syllable
  splitting, difficult-word highlight, RSVP) in one place — several now
  reachable from Preferences for the first time — and **Fonts** gathers the
  reading font, display font, and line-height / letter / word spacing. The
  Preferences dialog now has six tabs: Reading, Reading Aids, Voice, Display,
  Fonts, General.
- **Voice typing — dictate straight into the document.** Alongside Dictate
  Note (which files a separate annotation), there's now a **microphone button
  on the toolbar** (and **Tools ▸ Voice Typing**, **Ctrl+Alt+K**): toggle it
  on, speak, toggle off, and what you said is inserted into the document at the
  cursor — so you can compose by voice, not just annotate. The toolbar mic
  button stays highlighted while it's listening. It drops you into edit mode
  automatically, pauses the reading voice so it doesn't transcribe itself, shows
  a live timer while recording, and announces each step for screen-reader users.
  Toggle on and off as many times as you like to keep dictating.
- **Self-contained Windows `star.exe` on every release.** For students who
  can't install Python, each GitHub Release now attaches a double-click
  `star-<version>-windows-x64.exe` (the same "download one file and run it"
  story the Linux AppImage already provides) with everything baked in —
  Python, the GUI, all document loaders, offline dictation, and the helper
  tools for audio export / OCR / braille / extra voices. DECtalk (a
  commercial synthesizer) is excluded from the public build.
- **macOS `star.app` + `.dmg` on every release.** Mac users get a
  double-clickable app too: each Release now attaches a
  `star-<version>-macos-arm64.dmg` (drag star to Applications) built with
  PyInstaller from the same build recipe as the Windows exe. Speech uses the
  built-in macOS voices, so nothing extra to install. It's ad-hoc-signed, so
  the first launch needs a right-click ▸ **Open** to get past Gatekeeper
  (a one-time step); a fully notarized build follows once signing is set up.
  Apple-Silicon Macs for now.

### 🐛 Fixed

- **A real live-edit loop while editing.** Saving with **Ctrl+S** now keeps you
  in edit mode — it writes the file and lets you keep typing and formatting,
  instead of throwing you back to read mode on every save. Formatting actions
  (Bold, Heading, lists, …) refresh the live preview **immediately** rather than
  after a typing pause, so you see the styled result at once. **Ctrl+E** is now
  the deliberate "finish editing" action and, if you have unsaved changes, asks
  whether to Save, Discard, or Cancel — so a stray press can't lose your work.
  Editing an imported file (PDF/DOCX/EPUB) asks once where to save the Markdown,
  then keeps saving there; and opening a different document while you're editing
  asks about unsaved changes first instead of quietly carrying the edit session
  onto the new file.
- **Dictation never tells you to run `pip`.** When the speech-to-text stack
  isn't loaded yet, star used to leak a raw "pip install …" message — the one
  thing its no-pip design forbids. Voice input now checks availability freshly
  (so a just-installed mic works without a restart) and any remaining
  package-not-ready case says "restart star to finish setting up" instead.
- **The Install Optional Features dialog fits a 1080p screen.** Its contents
  scroll, it opens near full-screen so many features are visible at once, and
  it's clamped to the display so the Install / Not-now buttons never fall off
  the bottom.
- **The menu bar fits on 1080p.** Tighter per-item spacing keeps all of
  star's menus visible instead of spilling the last few into a `»` overflow.

---

## [0.1.23] 2026-07-05

Testing-driven usability fixes — translation and dictation now behave the way
a reader actually needs them to, in both interfaces — plus the packaging
lessons from the first standalone Windows build, baked into the recipe for
good.

### ✨ Added

- **The TUI gets the study tools.** Four new M-x commands bring the terminal
  to full parity: `translate` (pick a language with Tab completion),
  `summarize`, `dictate-note` (record until Enter, Esc cancels, live elapsed
  time in the status line), and `transcribe-file <path>` — results open as
  live, speakable documents, and dictated notes attach at the caret exactly
  like `a`.
- **Auto-play works in the GUI.** The `tts_auto_play` setting ("start
  reading when a document opens") was honored only by the TUI; the GUI now
  starts reading too — from your saved position, not the top — and the
  option has a checkbox in **Preferences ▸ Voice**.

### 🔧 Changed

- **Translate opens a readable document — and translates all of it.**
  Translating used to drop the result into a read-only pane, and silently
  failed for anything longer than a couple of pages (the translation service
  rejects big requests). The document is now translated in pieces (with
  "part 3 of 8" progress) and the result opens as a live document: press
  Space to hear it, caret and highlighting all work; your original stays
  put — reopen it from **File ▸ Recent**.
- **Dictate records until you say stop.** No more guessing "how many
  seconds?" up front — a recording dialog shows a live timer and a **Stop**
  button (Enter to stop, Esc to cancel); the note is transcribed when you're
  done. And if star was reading aloud, it pauses **before** the microphone
  opens, so the note no longer transcribes star's own voice — press Space
  afterwards and the reading resumes right where it stopped.

### 🐛 Fixed

- **Dictation no longer needs ffmpeg.** The recorded audio is handed to
  Whisper as an in-memory array instead of a temp WAV, so dictating a note
  works without ffmpeg installed — and the windowed Windows build no longer
  flashes a console window while transcribing. (Transcribing an audio *file*
  still uses ffmpeg to decode it.)
- **You can hear dictation and downloads finish.** Every step of the
  dictate flow (transcribing, note added, cancelled, no audio, errors) and
  of an optional-feature download (started, ready, failed) is now announced
  to screen readers, not just painted on the status bar.
- **Standalone Windows build: speech, spell check, Define Word, syllable
  splitting.** The PyInstaller recipe now bundles the entry-point metadata
  the TTS plugin registry discovers backends through (the first build had
  no voices at all), pyspellchecker's frequency dictionary, the
  WordNet/CMUdict data behind **Define Word**, and pyphen's hyphenation
  dictionaries for the syllable-splitting aid — all verified inside the
  frozen app.
- **The standalone build is honest about add-ons.** "Install it now?" could
  never work inside the frozen app (it has no pip); star now explains that
  this build can't add features instead of offering a download that always
  fails.
- **No more console-window flashes on Windows.** Every helper star runs
  (pandoc when opening Word/HTML files, ffmpeg when exporting audio, the
  speech engines) now starts without popping a focus-stealing black console
  window in the windowed app.

---

## [0.1.22] 2026-07-05

A settings-and-polish release: every reader preference now lives in one tabbed
**Preferences** dialog, the menus are leaner, and a post-release refinement
audit's fixes are all in — including two persistence bugs and a master switch
that existed only on paper.

### ✨ Added

- **Preferences dialog.** All reader settings in one place — **Edit ▸
  Preferences… (`Ctrl+,`)** with Reading, Voice, Display, and General tabs:
  spoken-word highlight (style, colors, speed, lead), reading ruler, RSVP,
  auto-scroll, syllable separator, TTS engine/rate/volume, fonts, theme, and
  the general options. Apply-on-OK with an Apply button; **Restore Defaults**
  re-stages every field from the shipped defaults without saving until you
  confirm. Fully translated (Spanish, French, German, Portuguese).
- **Spoken-word highlight master switch.** `highlight_current_word` is now
  honored by the GUI (Preferences ▸ Reading): turn the karaoke highlight off
  entirely while keeping auto-scroll, the status line, and RSVP alive.
- **Menu tooltips.** Hovering a menu item now shows its description — the
  explanatory tips existed but Qt never displayed them.
- **Terminal caret browsing.** The TUI now has a true, freely movable reading
  caret: arrow keys move it word-by-word / line-by-line (PgUp/PgDn by screen,
  Home/End to the ends), the view follows it, and **Enter** (or Ctrl+Space)
  reads aloud from wherever it stands. While reading, the caret tracks the
  spoken word so Enter always resumes "from here"; sentence replay, notes,
  and Define Word all operate at the caret. `j`/`k` keep classic scrolling.
- **The terminal welcome page reads aloud.** Launching the TUI with no file
  now opens the bundled welcome page as a real document — Space, navigation,
  and Define Word work on the very first screen (it stays out of recents and
  the library, like the GUI).

### 🔧 Changed

- **Leaner Reading Aids menu.** The three settings dialogs (Karaoke
  Highlight…, Reading Ruler…, RSVP Position…) moved into Preferences; their
  richer live-tuning dialogs stay one `F2` away as Command Palette **Tune …**
  entries. The toggles are unchanged.
- **Preferences lives in Edit.** Settings are under **Edit ▸ Preferences…**,
  the conventional home (was briefly Tools).
- **Better defaults.** The visual highlight now leads the audio by one word
  (`highlight_lead_words` 0 → 1) and audiobooks export at 128 kb/s
  (`audiobook_bitrate` 64k → 128k) — both promoted from real-world use.

### 🐛 Fixed

- **File ▸ Open Archive works again.** Opening a document from a zip/tar
  archive had been broken since roughly 0.1.12 — the action called a method
  that no longer existed. Now fixed and covered by a test.
- **Everything in a nested list is spoken.** Standard 4-space-indented
  sub-items ("    - apples") were silently skipped by the text-to-speech
  narration — the indented-code filter ran before list markers were
  removed. Nested ">>" quote markers no longer leak into speech either.
- **Deferred footnotes survive exports.** With footnotes set to "deferred",
  HTML and EPUB exports shipped an empty "Footnotes" heading — the note
  text itself was dropped. Notes now export as a plain numbered list.
- **Resizing the terminal keeps your place.** The TUI used to jump back to
  the previous session's saved position on every window resize (and re-toast
  "Resumed at N%"); the view now stays anchored to what you were reading.
  The saved position restores only when a document is opened.
- **Failed opens no longer masquerade as success.** A file that couldn't be
  opened used to toast "Opened: Error", enter the recent-files list, and —
  with auto-play on — read the raw error text aloud in the terminal. Both
  UIs now say "Could not open …" plainly and leave recents alone.
- **OCR language setting works.** `ocr_lang` (e.g. `"eng+spa"`) is now
  passed to Tesseract — it was documented but never wired, so OCR always
  ran in English. `recent_files_limit`, `video.theme`, and
  `video.font_scale` are wired too; four settings that did nothing were
  removed.
- **ElevenLabs audio is a real WAV.** The cloud voice returned headerless
  PCM that star saved into .wav files; it is now properly containerized,
  fixing playback and audio/audiobook export with the cloud voice.
- **Braille fixes.** Grade-1 BRF now emits the letter sign for a–j after
  numbers ("3a" no longer embosses as "31") and folds accented letters to
  their base instead of dropping them ("café" kept its é as *e*).
- **No more freeze on pathological files.** A multi-megabyte single-line
  file froze the terminal reader for half a minute per redraw; wrapping is
  now linear-time. Oversized `scroll_margin` values and a resize race that
  could briefly blank the TUI screen are also fixed.
- **No network on a default launch.** The GUI no longer downloads the
  OpenDyslexic font at startup when no reading font was ever selected —
  fonts fetch on first *use*, as documented, with a once-per-machine retry
  guard. The summarizer's tokenizer download now honors the
  `auto_install` / `STAR_NO_AUTOINSTALL` kill-switch like everything else.
- **The GUI starts without curses.** Installs without `windows-curses`
  (pipx, `--no-deps`) crashed before a window appeared because the GUI's
  import chain touched the terminal stack; the import is now lazy and a
  test locks it in.
- **A corrupt settings file is backed up, not silently erased.** Preferences,
  reading positions, and highlights now survive as a timestamped `.bak`, and
  star tells you what happened instead of quietly starting fresh.
- **A failing cloud voice speaks up.** An invalid ElevenLabs key or an outage
  used to "read" the document in total silence; star now says the cloud
  voice failed and continues aloud with a local voice.
- **Terminal caret no longer jumps documents.** Opening a new file resets the
  reading caret instead of carrying an arbitrary position across.
- **Voice favorites and the difficult-words toggle now persist.** Both were
  silently dropped on every restart (their keys were missing from the settings
  schema the loader accepts).
- **Reading font picked in Preferences applies immediately** — including the
  on-demand font fetch and the View-menu radio sync; previously it saved but
  changed nothing until relaunch.
- **A theme picked in Preferences sticks.** It now counts as an explicit
  choice, so OS light/dark auto-detection no longer overrides it on the next
  launch; re-ticking "Follow OS theme" re-arms auto-detection.
- **Font-size settings unified.** The stylesheet honored only the legacy
  `font_size` key, so a hand-edited `qt_font_size` changed nothing (and the
  two could disagree). Both now resolve through one chain.
- **Live overlays follow Preferences.** Applying ruler height/opacity/color
  and RSVP position/size/context updates a visible overlay immediately.
- **The terminal UI is no longer red on Windows.** The TUI hardcoded colors
  in Linux (ncurses) order, but Windows terminals number them differently —
  so every intended blue (title bar, status bar, headings) rendered red, a
  poor default for colorblind readers. Colors now use the portable named
  constants, and the default dark theme gains a proper **orange** accent for
  the chrome and the spoken-word highlight (256-color terminals; yellow on
  basic ones). A regression test keeps red out of every theme.

### 🧪 Quality

- New Preferences test suite (construct-smoke for the palette-only dialogs,
  apply-hook spies, Restore-Defaults staging, theme-explicit both ways) and a
  CI coverage floor for the dialog module; the accessibility pass gives the
  color swatches screen-reader names.
- **Errors look, sound, and persist like errors.** Terminal error toasts are
  styled and logged to a `tui.log` beside your settings; GUI failures
  (save, exports, transcription) persist in the status bar and are spoken to
  screen readers; Preferences Apply and reading-font changes are announced.
  Transcription without ffmpeg now explains itself up front.
- The welcome page's speed-key hint was wrong (and it now greets terminal
  readers too); the manual documents the terminal caret keys; a new test
  keeps every settings key documented automatically.

---

## [0.1.21] 2026-07-03

A voices-and-reading release delivered as three multi-agent waves, then hardened
by an adversarial multi-agent review before shipping. New ways to hear a document,
new decoding and low-vision aids, faster very-large documents, and a maintenance
pass that splits the last big modules into packages. Every optional capability
still installs itself in one click — students never see `pip`.

### ✨ Added

- **Cloud neural voices (opt-in).** An `elevenlabs` engine for premium neural
  speech. Nothing ever leaves your machine unless you paste a key **and** choose
  the cloud voice; on any failure star silently falls back to a local engine.
- **Audiobook export (M4B).** Export a document as a chaptered `.m4b` audiobook —
  chapters come from its headings — to listen on the go (needs ffmpeg).
- **Reading Font chooser.** Pick **OpenDyslexic**, **Atkinson Hyperlegible**
  (Braille Institute, for low vision), or **Lexend** from View ▸ Reading Aids;
  the font is fetched on first use and applied everywhere.
- **Syllable splitting.** A decoding aid that shows words split into syllables
  (`read·a·bil·i·ty`); display-only, so speech and highlighting are unaffected.
- **Reading ruler.** A movable, translucent band that follows the caret to help
  keep your place (adjustable height and opacity).
- **Highlight color pickers.** Pick the exact colors for the spoken-word
  highlight and the sentence band (in "Both" mode) from a color picker in
  **View ▸ Reading Aids ▸ Karaoke Highlight…** — so the two are easy to tell
  apart. The sentence band can follow the theme or use a color you choose.
- **Reading-ruler color.** The reading ruler's band color is now pickable too
  (**View ▸ Reading Aids ▸ Reading Ruler…**) — independent of the word highlight,
  or set to match it.
- **Faster very-large documents.** Opt-in pagination renders only a window of a
  huge document at a time — a ~500-page document's first paint drops from several
  seconds to well under one, with reading, highlighting, Find, and Define-Word
  still correct across page boundaries. Off by default; see Configuration.
- **Right-to-left groundwork.** Choosing a right-to-left interface language now
  mirrors the whole app and reading view; Arabic is included as a first catalog.

### 🔧 Changed

- **Play from cursor is now `Ctrl+Space`** (was `Ctrl+Return`), which makes caret
  browsing a full navigation tool: move the caret with the arrow keys, then press
  `Ctrl+Space` to start reading from that point.
- **The reading view follows the spoken word more steadily.** Auto-scroll now
  keeps the highlighted word in a comfortable middle reading band (with context
  above and text ahead below) instead of nudging it to the bottom edge — so it's
  easy to keep your place while listening. Set `qt_autoscroll` to `false` to
  scroll manually.
- **Crisp toolbar icons on high-resolution displays.** The monochrome toolbar
  glyphs now render at the display's device-pixel ratio instead of upscaling a
  small bitmap, so they stay sharp and legible on hi-DPI screens.
- **About dialog** rewritten: a short summary of what star is and does, a
  clickable link to the project on GitHub, and the version and licence.
- **Reading progress syncs without losing work.** When the same document is read
  on two machines through a synced folder, star now *merges* the sidecars instead
  of last-write-wins: reading position resolves by a policy you choose (newest,
  furthest, or manual) and annotations union by id, so no edit is dropped.
- **Internal maintainability.** The last large modules — `markup`, `ttstext`, the
  TTS `manager`, and the GUI navigation mixin — were split into packages
  (behaviour-identical, public API unchanged).

### 🐛 Fixed

- **Highlights & the difficult-word overlay stay put under pagination.** Saved
  highlights no longer paint over the wrong text after the page window advances,
  and highlights created while paginated are stored at correct absolute offsets.
- **Corrupted synced sidecars can't erase progress.** A malformed sidecar value no
  longer discards valid reading progress or crashes resume.
- **Syllable splitting works the moment it installs** — no restart required, like
  every other one-click feature.

### 📝 Note

- To keep highlight and difficult-word placement exact, a document you have
  highlighted — or have the difficult-word overlay enabled on — renders in full
  rather than paginating. Highlighting a very large document turns pagination off
  for that session (with a status note), the same way opening Find does.

---

## [0.1.20] 2026-07-02

A large capability-and-polish release: ten roadmap areas delivered together, plus
a batch of reading-experience fixes. The guiding principle — star's users are
students, not programmers — so every optional capability now installs itself with
one click instead of asking anyone to run `pip`.

### ✨ Added

- **Find in document (Ctrl+F).** An incremental find bar with match highlighting,
  a live "N of M" count, case toggle, and wrap-around.
- **Bookmarks & navigation history.** Named per-document bookmarks (**Ctrl+B**)
  and back/forward navigation (**Alt+←/→**) in the GUI, mirroring the TUI.
- **Full-text library search.** Search *inside* every document in your library,
  not just titles and metadata.
- **Voice Manager (F4).** Browse, filter, preview, and favorite voices across
  every installed speech engine, and download offline **Piper** neural voices
  (nine, covering all five interface languages) with one click.
- **Study & spaced repetition.** Turn your highlights and notes into a review
  deck (FSRS scheduler), review due cards in-app (**Study ▸ Review Due Cards…**,
  Ctrl+Shift+F5), auto-generate cloze / fill-in-the-blank cards, and optionally
  two-way sync with Anki (AnkiConnect).
- **One-click optional features.** When a feature needs an add-on that isn't
  installed, star offers to download it in the background — no `pip` instructions
  anywhere — and the feature works right away. New CLIs: `star --install-optional`,
  `star --plugins list|info|api`, and `star --check-update`.
- **Richer documents.** Inline LaTeX math renders as readable Unicode; tables keep
  their header structure; footnote markers are clickable and jump to the note (and
  a ↩ backlink jumps back); images show captions / alt text.
- **High-contrast (AAA) theme** plus automatic light / dark / high-contrast
  theming that follows your operating system.
- **Guided tour.** A skippable first-run walkthrough of the core features,
  replayable any time from **Help ▸ Guided Tour** (Shift+F1). Plus **Help ▸ Check
  for Updates** and **Open Documentation**.
- **Plugin developer kit.** A developer guide, a real example plugin template, a
  versioned plugin API, and the `star --plugins` introspection CLI.

### ♿ Accessibility

- **Screen-reader announcements** for playback, document load, theme changes, and
  find results — state changes are spoken without moving focus.
- Keyboard reachability audit (docs/KEYBOARD_AUDIT.md); list dialogs open on Enter.
- The dyslexia-friendly font (OpenDyslexic, auto-fetched) applies across the whole
  UI — document, menus, toolbar, and panels.

### 🌍 Internationalization

- The **terminal UI is now translatable**, with a **first-run language picker**;
  the Spanish, French, German, and Portuguese catalogs are kept complete by a CI
  gate; and TTS prefers a voice matching your interface language.

### 🔧 Changed

- **"All" optional features now means everything**, including the large
  speech-to-text and named-entity packs (the download size is shown upfront).
- **Faster large documents** — a linear-time word map (up to ~12× on big files).
- A real **terminal-UI clipboard** (selection / paragraph aware).
- **Safer cross-device sync** — atomic sidecar/settings writes and machine-agnostic
  reading metadata that travels with a synced folder.

### 🐛 Fixed

- Optional features no longer **dead-end on a `pip install` message** — they
  install and become usable in the same session (only the large speech-to-text
  pack asks for a restart), and an explicit install never falsely reports a
  network error.
- **RSVP one-word reading mode** no longer crashes (and shows the word display as
  intended).
- **`.7z` archives** open on modern py7zr; **`prefer_pandoc = false`** is honored
  for Pandoc-only formats.

### 🧰 Internal

- The ten-area roadmap was delivered through coordinated multi-agent waves. The
  test suite grew from 654 to **937** (adding pytest-qt interactive, end-to-end,
  TUI, and property-based tests) with a new "full-fat" CI leg, and the two largest
  GUI modules were split into focused mixins.

---

## [0.1.19] 2026-07-01

star still runs out of the box on nothing but the Python standard library — now
it can also grow on demand, guided by a first-run chooser.

### ✨ Added

- **Optional-features chooser (selection menu).** On first launch star offers a
  short menu of optional capabilities instead of silently fetching everything.
  Pick a preset — **Thin** (the lightweight everyday reading and study aids) or
  **All** (everything star can use) — or tick individual features (OCR,
  offline dictionary, summarize, translate, knowledge-graph extras, and more).
  Each entry shows its purpose and approximate download size. star then fetches
  the Python packages in the background, best-effort, and remembers what it has
  attempted so it never re-tries on every launch. The very large packs
  (speech-to-text dictation, named-entity extraction) stay unchecked and opt-in,
  so **All** can never trigger a multi-gigabyte download. Re-open the chooser any
  time from **Tools → Install Optional Features…**.
- **`star --install-optional` (headless install).** Install optional features
  from the command line: `star --install-optional` (defaults to the `all`
  preset), `star --install-optional thin`, or a comma-separated list of feature
  keys such as `star --install-optional ocr,dictionary`. Run it with no value (or
  an unknown value) to list every feature with its size and install status. This
  is the scriptable counterpart to the GUI chooser; the fetch runs in the
  foreground with plain progress output.
- **Opt-out.** The chooser and background fetching honour a settings switch
  (`auto_install`) and the `STAR_NO_AUTOINSTALL` environment variable; once the
  chooser has been shown, `deps_prompted` keeps it from re-appearing on its own.

- **System tools in view.** The optional-features chooser and `star --deps` now
  also show the native engines star can use but cannot install for you —
  Tesseract, Pandoc, ffmpeg, Graphviz, liblouis, piper, eSpeak NG, DECtalk —
  each with a ✓/✗ availability indicator and an install hint.
- **OpenDyslexic font, everywhere.** *View ▸ Reading Aids ▸ Dyslexia-Friendly
  Font* applies a dyslexia-friendly typeface across the entire interface — the
  document itself as well as menus, toolbar, dialogs, and panels — and toggles
  cleanly back off. If no dyslexia-friendly family is installed, OpenDyslexic
  (SIL OFL) is fetched automatically in the background (like the other optional
  dependencies); nothing is bundled, and it falls back gracefully offline. It
  appears as an optional item in the chooser's System tools list and in
  `star --deps`.

### 🔧 Changed

- **Accessibility.** Screen-reader accessible names and descriptions added
  across the window — the Table-of-Contents and Notes docks and lists, the notes
  filter and action buttons, the live HTML preview, the command-palette /
  navigation / library / feed / pronunciation lists, the knowledge-graph views,
  and every checkbox in the optional-features chooser. Keyboard fix: graph nodes
  now open with Enter, not just a double-click.
- **Terminal-UI clipboard.** Copy now takes the current selection or the whole
  paragraph (not just the top visible line), using the system clipboard when
  `pyperclip` is present and falling back to an OSC-52 terminal escape otherwise.
- **Interface translations.** The icon-toolbar labels and the optional-features
  chooser are now translated in the Spanish, French, German, and Portuguese
  interface catalogs.
- **More resilient settings.** A failed settings write is now logged instead of
  silently discarding your preferences, profiles, notes, and reading positions.
- Internal: the two largest GUI modules were split into focused mixins, and the
  offscreen GUI / chooser / clipboard / fonts / accessibility paths gained test
  coverage.

### 🐛 Fixed

- **`.7z` archives open again** on current py7zr. py7zr 1.0 removed the in-memory
  `read()` API star relied on, so opening a document inside a `.7z` raised an
  error on any modern install; extraction now uses the stable `extract()` API.
- **`prefer_pandoc = false` is honored** for Pandoc-only formats (e.g. `.rtf`).
  Since the 0.1.16 plugin rewrite these were converted by Pandoc even when the
  preference was off; they now fall back to the install-guidance note as intended.

---

## [0.1.18] 2026-06-28

A clearer toolbar and a working out-of-the-box first screen.

### ✨ Added

- **Icon toolbar.** Every toolbar button is now a hand-drawn vector icon with a
  descriptive tooltip (including its keyboard shortcut), replacing the old mix of
  text labels and stray Unicode glyphs. The icons are drawn programmatically and
  tinted to the system theme — no image files — so the toolbar looks consistent
  on every platform. Each button keeps its text as the accessible name, so screen
  readers still announce it.
- **Readable welcome page.** The startup welcome screen is now a real document:
  press **Space** to hear it read aloud, move the caret with the arrow keys,
  select to highlight, and look words up with **Ctrl+D** — every control works on
  the very first screen instead of a static splash.

### 🐛 Fixed

- **F1 (Help) now opens the README on every install.** It previously looked for
  the README next to the GUI modules and failed for `pip`/wheel/zipapp installs
  (it only worked from a source checkout). The README and welcome page now ship
  inside the package and are resolved reliably wherever star is installed.

---

## [0.1.17] 2026-06-27

Obsidian & Zed themes (Obsidian is the new default), caret browsing for free
keyboard navigation of documents, richer Markdown rendering, and folder-as-
library with synced reading progress.

### ✨ Added

- **Obsidian & Zed themes.** Four new GUI color themes — **`obsidian`** (now the
  default), `obsidian-light`, `zed-one-dark`, and `zed-one-light` — with
  authentic palettes. The theme schema gained code-block background, link, and
  blockquote/table-border colors; existing themes and user CSS files are
  unaffected and fall back gracefully. Cycle with **F5** or pick via **View ▸
  Choose Theme**. (Existing users keep their saved theme; only fresh installs
  default to Obsidian.)
- **Caret browsing (accessibility).** A visible, keyboard-navigable text caret in
  the document view: move freely with the arrow keys (character / word / line /
  Home-End), select passages for highlighting with Shift, and look up the word
  under the caret with **Define Word (Ctrl+D)**. On by default; toggle with **F7**
  or **View ▸ Caret Browsing**. Turning it off restores the clean, caret-free
  reader view (mouse selection still works).
- **Folder as library.** Point star at *any* folder — including one synced by
  Dropbox, OneDrive, Syncthing, or iCloud — and every document inside it
  (recursively) becomes your library. Because the library is the filesystem
  itself, it syncs across machines and services for free. Add one via **File ▸
  Open Folder as Library…** (or run `star <folder>` / open a folder from the
  file dialog), then browse everything in **File ▸ Library** alongside your
  recently-opened files, with reading progress. Multiple library folders are
  supported. **Reading progress syncs too:** each library folder keeps a
  `.star/progress.json` sidecar keyed by relative path, so where you left off in
  a document follows it across machines — read on your laptop, pick up on your
  desktop.

### 🔧 Changed

- **Richer document rendering.** The Qt Markdown renderer now lays out fenced
  code blocks, tables, ordered/unordered lists, blockquotes, horizontal rules,
  headings up to level 6, and links — so documents (and the themes applied to
  them) render with real structure instead of plain paragraphs.

## [0.1.16] 2026-06-26

Adds HTML and EPUB export, and opens star up to third-party plugins: TTS
engines, document formats, and export targets are now discovered through
standard entry-points.

### ✨ Added

- **HTML and EPUB export.** File ▸ Export can now write the current document to
  a standalone HTML page or an EPUB book (rendered through Pandoc, so it
  requires Pandoc or `pip install "star-reader[markup]"`). They appear in the
  Export menu automatically when Pandoc is available.
- **Plugin system (entry-points).** TTS backends, document-format handlers, and
  exporters are now discovered via `importlib.metadata` entry-points
  (`star.backends`, `star.formats`, `star.exporters`). A third-party package can
  contribute a new speech engine, file loader, or export target — for example
  `pip install star-tts-azure` — and it is picked up with **no changes to star
  itself**: new engines become selectable in the engine picker, new loaders open
  their file types, and new exporters appear in File ▸ Export. The built-in
  implementations are registered the same way.

### 🔧 Changed

- The document loader and TTS engine selection now route through the plugin
  registry instead of hard-coded dispatch tables. Behavior is **identical** for
  every existing configuration — the change is what makes the system extensible.
  `TTSBackend` is now a formal abstract base class, so a misbehaving custom
  backend fails fast at construction rather than silently doing nothing.

## [0.1.15] 2026-06-26

Adds offline word definitions, and fixes a regression that broke the Qt GUI on
launch in 0.1.14.

### ✨ Added

- **Offline dictionary / Define Word.** Select a word (or place the cursor on
  it) and look up an offline definition — part of speech, senses, synonyms, and
  an ARPAbet pronunciation — which closes the loop the difficult-word overlay
  opens. **Qt:** View ▸ Reading Aids ▸ *Define Word* (**Ctrl+D**, also in the
  command palette). **TUI:** the **`d`** key or `M-x define`, shown in the text
  pager. Backends, in order: a user-supplied custom JSON dictionary (the new
  `dictionary_file` setting, checked first), then **WordNet** via nltk, with
  **CMUdict** pronunciation when present. Optional and guarded as usual:
  `pip install "star-reader[dictionary]"` then a one-time
  `python -m nltk.downloader wordnet omw-1.4 cmudict`; without it the UI shows an
  install hint. Listed in `star --deps`.

### 🐛 Fixed

- **Qt GUI no longer crashes on launch.** The 0.1.14 `tui.py` → `star/tui/`
  package refactor moved `_shortcuts_text` into `star/tui/text.py`, but
  `star/gui/mixin_commands.py` still imported it from `star.tui`, raising
  `ImportError` when the (lazily-imported) GUI started. The import now points at
  `star.tui.text`. (TUI and CLI were unaffected.)

## [0.1.14] 2026-06-26

Fixes a Windows crash in headless / TUI video export, and modularizes the
curses TUI into a package (the same treatment the Qt GUI received in 0.1.12).
No user-facing behavior change beyond the bug fix.

### 🐛 Fixed

- **Karaoke video export no longer crashes on Windows when run without the GUI.**
  `export_video` rendered frames with Qt (`QTextDocument`/`QPainter`) but never
  ensured a `QGuiApplication` existed first; with no GUI running — the TUI's
  `export-video` command (which renders on a worker thread) or any headless
  export — Qt's font subsystem was uninitialised and the process hard-crashed
  on Windows. The Qt renderer now reuses a running `QApplication` when present
  and otherwise creates a minimal `QGuiApplication` on the main thread; off the
  main thread with no app it cleanly falls back to the Pillow renderer. (This
  was also the root cause of the long-standing full-test-suite crash at
  interpreter shutdown on Windows.)

### ♻️ Refactor

- **`star/tui.py` is now the `star/tui/` package.** The ~5,000-line curses TUI
  module — a single 177-method `StarApp` class — was split into a package
  mirroring `star/gui/`: `app.py` holds the core (`__init__`, the `run()` loop,
  color setup, `notify`), and the rest of `StarApp`'s methods move into 17
  responsibility **mixins** (`mixin_document`, `mixin_playback`,
  `mixin_navigation`, `mixin_speechcursor`, `mixin_bookmarks`, `mixin_search`,
  `mixin_voice`, `mixin_export`, `mixin_display`, `mixin_commands`, `mixin_graph`,
  `mixin_help`, `mixin_docops`, `mixin_rsvp`, `mixin_annotations`, `mixin_keys`,
  `mixin_draw`). Module-level helpers split into `theming.py` (color roles +
  `THEMES` + `_setup_colors`), `_screen.py` (curses draw primitives), and
  `text.py` (the M-x command table, shortcut data, and help text). Behavior is
  identical — every method moved verbatim, `StarApp` keeps the same public
  surface (`from star.tui import StarApp` and 176 callable members, each
  resolving from exactly one mixin via the MRO).

### 🧪 Tests / CI

- **CI now installs `ffmpeg`** (plus `espeak-ng` on Linux for a TTS engine) on
  the Linux and Windows test legs, so `test_export_video_smoke` actually runs
  instead of being skipped — turning it into a real regression guard for the
  video-export fix above.

### 📚 Documentation

- **`docs/architecture.md`** documents the new `star/tui/` package layout
  (core + mixins + `theming`/`_screen`/`text`), alongside the existing
  `star/gui/` section.

## [0.1.13] 2026-06-26

Makes **Pandoc a first-class importer** so `star` can open many more document
formats when Pandoc is installed, and adds the first **direct test suite and
coverage gate** for the speech engine.

### ✨ Added

- **Pandoc-first importing.** When Pandoc is installed and the new
  `prefer_pandoc` setting is on (default), `star` routes the office/markup
  formats Pandoc handles well — DOCX, ODT, PPTX, HTML, reStructuredText, LaTeX,
  MediaWiki, Textile, Org, Jupyter, CSV/TSV/XLSX — through Pandoc instead of the
  native loader, and **opens ~22 formats that were previously unsupported**
  (`.rtf`, `.fb2`, `.docbook`, `.jats`, `.ris`, `.bib`, `.opml`, `.t2t`,
  `.muse`, `.typst`, `.dokuwiki`, `.twiki`, `.vimwiki`, `.jira`, `.man`, `.pod`,
  …). If a Pandoc conversion fails, `star` falls back to the native loader.
  - **EPUB stays native** so chapter (NCX/NAV) navigation is preserved, as do
    Markdown/plain text and the formats Pandoc cannot read (PDF, images/OCR,
    code, DAISY, archives, URLs).
  - **Toggle:** the new `prefer_pandoc` setting — `true` (default) or `false` to
    always use the native loaders. See [Configuration](../docs/configuration.md).
  - Requires the optional `markup` extra (`pip install "star-reader[markup]"`)
    plus the Pandoc binary; without Pandoc, behavior is unchanged.

### 🧪 Tests

- **Direct tests for the TTS engine.** `star/tts.py` (the ~2,900-line
  multi-backend speech engine) gains its first dedicated test module
  (`tests/test_tts.py`, 66 tests) covering the pure, deterministic surface: the
  timestamped-subtitle pipeline, the WAV helpers, Piper model resolution, eSpeak
  chunking, the Coqui player command, DECtalk voice/markup mapping, and
  `TTSManager` backend selection + default-voice resolution.
- **Per-module coverage gate.** A new CI job enforces a coverage floor on
  `star/tts.py` (`pytest --cov=star.tts --cov-fail-under=30`); the floor is a
  ratchet to be raised as more of the engine's pure logic gains tests.

### 🐛 Fixed

- **Document cache now reacts to the reading-order and importer settings.** The
  document-cache fingerprint now includes `pdf_reading_order` (a latent miss
  since 0.1.12) and `prefer_pandoc`, so toggling either re-parses the document
  instead of serving a stale cached parse.

## [0.1.12] 2026-06-25

Adds **PDF reading-order intelligence** — multi-column academic PDFs now read
top-to-bottom, column by column, instead of interleaving columns into gibberish.
Also an internal modularization of the Qt GUI (no user-facing behavior change)
plus dead-code and import cleanup.

### ✨ Added

- **PDF reading-order reconstruction.** In layout mode, `star` now rebuilds the
  reading order of a PDF page from box geometry: it detects columns (via a
  vertical projection of text-box extents), reads **column by column,
  top-to-bottom**, and treats full-width boxes (titles, spanning figures) as
  dividers that interrupt the column flow at their position. **Running headers,
  footers, and page numbers** in the page margins are suppressed from the spoken
  stream. This fixes the dominant failure mode for two-column journal articles,
  where the previous order read across columns and produced gibberish for TTS.
  - **Toggle:** the new `pdf_reading_order` setting — `"reconstruct"` (default)
    or `"raw"` to fall back to the previous (pdfminer-native) order when the
    heuristics misfire. See [Configuration](../docs/configuration.md).
  - Single-column PDFs are unaffected by the column logic (the page is detected
    as one column); they still gain header/footer/page-number suppression.

### ♻️ Refactor

- **`star/gui/` modularized.** `StarWindow(QMainWindow)` — ~6,100 lines / 194
  methods, previously nested inside the `_run_qt_gui()` closure — is lifted to
  module scope in **`star/gui/main_window.py`** and split into 16 focused
  responsibility mixins, **`star/gui/mixin_*.py`** (playback, navigation, export,
  annotations, citations, graph, document, display, presets, highlights, ToC,
  commands, transcription, docops, fontspacing, aiddialogs). The shared PyQt5/6
  enum-compat constants moved to **`star/gui/_qtcompat.py`**. `star/gui/runner.py`
  is now ~90 lines (Qt setup + launch only). Behavior is identical — every method
  was moved verbatim and all 184 `StarWindow` methods resolve exactly once via the
  mixin MRO. The Qt-heavy modules stay lazily imported, so `import star.gui`
  remains safe when PyQt is absent.

### 🧩 Internal

- Removed the dead `_HelpWindow` dialog (`star/gui/help_window.py`): it was built
  but never shown. **Help (F1)** opens `README.md` as a readable document, exactly
  as before.
- Dropped over-inclusive / unused imports across the new GUI modules (`ruff`-clean).

### 📚 Documentation

- **`docs/architecture.md`** — the `star/gui/` package section now describes the
  `main_window.py` + `mixin_*.py` + `_qtcompat.py` layout.

## [0.1.11] 2026-06-25

### ✨ Added

#### Epic I — Archive ingestion

- **`star/archive.py`** — new pure-Python archive-member module.  Supports ZIP
  and TAR (.tar, .tar.gz, .tgz, .tar.xz, .tar.bz2) via stdlib; `.7z` via
  optional `py7zr`; `.rar` via optional `rarfile`.  Ref form:
  `/abs/book.zip!inner/paper.pdf`.  API: `is_archive`, `is_archive_ref`,
  `make_ref`, `parse_ref`, `list_members`, `open_member` (context manager),
  `build_index_markdown`.
- **Archive loading in `load_document`** — opening an archive ref extracts the
  member to a temp file, loads it by format, and keys annotations/library by the
  ref.  Opening an archive directly produces a Markdown member index and registers
  each member in the library under its ref.
- **File ▸ Open Archive…** (Qt GUI) — pick an archive, select a member from the
  member list, and open it.
- **`M-x open-archive`** (TUI) — same workflow from the command palette.
- **Bookshelf** — archive members appear grouped by their `"source"` archive.
- **New `[archive]` extra:** `pip install "star-reader[archive]"` pulls in `py7zr`
  and `rarfile` for .7z / .rar support (ZIP and TAR are always available).
- **diagnostics** — `py7zr` and `rarfile` registered as `probe`-kind entries.

#### Epic II — Metadata & discovery

- **ISBN validation** (`star.citations._valid_isbn`) — checksum-valid ISBN-10
  and ISBN-13 detection (hyphens/spaces stripped).
- **OpenLibrary ISBN lookup** (`star.citations._fetch_metadata_by_isbn`) — fetches
  title, author, year, and publisher from the OpenLibrary Books API (keyless,
  no account required); returns `(dict, message)` with a clear "unavailable"
  message when offline.
- **`star/discovery.py`** — `search_library(settings, query, doi, isbn, author)`:
  AND-combined library search over title/author/path/annotation text plus exact
  DOI/ISBN matching.
- **Library metadata** — `library[key]["meta"]` dict (`title`, `author`, `year`,
  `doi`, `isbn`, `publisher`) persisted in settings.
- **Metadata Editor dialog** (Qt GUI: File ▸ Edit Document Metadata…) — inline
  form with "Look up DOI" and "Look up ISBN" buttons that auto-fill fields.
- **`M-x metadata-edit`** (TUI) — field-by-field metadata editing with DOI/ISBN
  lookup from the command palette.
- **`M-x library-search`** (TUI) — multi-criteria library search.

#### Epic III — Sentence-level karaoke video export

- **`star/video.py`** — `export_video(document, settings, out_path, tts_backend)`.
  Pipeline: TTS → WAV → sentence-span timing cues → PNG frames (one per
  sentence, current sentence highlighted / rest dimmed) → ffmpeg concat →
  MP4 with soft SRT subtitle track.
- **Renderers** (in priority order): Qt offscreen (`QTextDocument` → `QImage`
  with per-span `QTextCharFormat` highlight); Pillow fallback (word-wrapped
  text, translucent highlight rectangle).
- **`_sentence_spans`** — character-offset sentence segmentation reusing
  `_SENTENCE_SPLIT_RE` from `_runtime`.
- **File ▸ Export ▸ Video (MP4)…** (`Ctrl+Alt+V`, Qt GUI) — runs on a background
  thread; status bar shows progress and confirms the path.
- **`M-x export-video`** (TUI) — same pipeline from the TUI command palette.
- **New `[video]` extra:** `pip install "star-reader[video]"` pulls in `Pillow`
  for the fallback renderer (Qt is the primary renderer, already in the base
  deps; ffmpeg must be on PATH).
- **diagnostics** — `pillow_video` registered as a `probe`-kind entry.
- **`"video"` settings block** — `resolution`, `theme`, `font_scale`, `subtitles`
  (`soft|none`), `last_export_dir`.

#### Epic IV — RSVP reading mode

- **RSVP (Rapid Serial Visual Presentation)** — one-word-at-a-time reading aid
  that synchronises with TTS playback, recognized as an accessibility aid for
  many dyslexic readers.
- **Qt GUI:** floating overlay (`_RSVPOverlay`) drawn on top of the document
  with a rounded dark-background panel.  Shows the current word in large type
  plus optional previous/next context words.  Toggle with `Ctrl+Alt+E`
  (**View ▸ Reading Aids ▸ RSVP Mode**); position picker opens a 3×3 grid dialog
  (**View ▸ Reading Aids ▸ RSVP Position…**).
- **TUI:** RSVP overlay drawn in the document viewport between the content and
  the status bar.  Toggle with `M-x rsvp-mode`; position with `M-x rsvp-position`.
- **9 placement positions** — `top-left`, `top-center`, `top-right`,
  `center-left`, `center`, `center-right`, `bottom-left`, `bottom-center`,
  `bottom-right` — so readers with limited visual field can place the panel
  where it is easiest to see.
- **Settings:** `qt_rsvp_mode` (bool), `qt_rsvp_position` (str),
  `qt_rsvp_font_size` (int, default 48), `qt_rsvp_context` (bool, default true),
  `tui_rsvp_mode` (bool), `tui_rsvp_position` (str).

#### Epic V — UI internationalization (i18n)

- **Localized chrome** — star's own menus, toolbar button labels, and dock
  titles can now be shown in a language other than English.  Ships with
  **Spanish, French, German, and Portuguese**; English is the source language.
- **`star/i18n.py`** — a small, gettext-style layer: `tr(text)` returns the
  active language's translation or the English source unchanged when none
  exists, so any untranslated string degrades quietly to English.  Catalogs are
  plain JSON in `star/locale/<code>.json` loaded at runtime — **no build
  tooling** (unlike Qt's native `.ts`/`.qm` workflow).  API: `tr`,
  `set_language`, `get_language`, `available_languages`, `language_codes`.
- **View ▸ Interface Language** (Qt GUI) — pick a language from the live list;
  the menu bar and toolbar are rebuilt in place immediately (no restart), and
  the choice persists.
- **Adding a language** needs no code: drop a `star/locale/<code>.json` catalog
  and add one row to `LANGUAGES` — see `star/locale/README.md`.
- **Settings:** `ui_language` (ISO-639-1 code, default `"en"`).

### 📦 Packaging

- **Knowledge-graph / Obsidian optional dependencies are now installable through
  the standard paths.** New `graph` (`graphviz`, `plantuml`, `pyyaml`) and `ner`
  (`spacy`, `nltk`) extras in `pyproject.toml`; the light `graph` deps are now in
  `[all]`. The `install.sh` / `install.ps1` `--all` profile — which had drifted —
  now installs the full optional set (document formats, study aids, hot-folder
  watching, and the graph/Obsidian helpers) and prints how to add the heavier
  `[transcribe]` and `[ner]` extras. spaCy stays opt-in (it also needs a language
  model, `python -m spacy download en_core_web_sm`).
- **New extras:** `archive` (`py7zr`, `rarfile`), `video` (`Pillow`).

### 🧩 Internal

- New modules: `star/archive.py`, `star/discovery.py`, `star/video.py`,
  `star/i18n.py`.
- New data: `star/locale/{es,fr,de,pt}.json` UI catalogs (shipped via
  `package-data`) and `star/locale/README.md`.
- `star/citations.py` gains `_valid_isbn` and `_fetch_metadata_by_isbn`.
- `star/documents.py` — archive-ref and direct-archive dispatch in
  `load_document`; `_record_archive_members` helper.
- `star/settings.py` — `"video"` settings block (all keys optional); RSVP
  settings block.
- `star/diagnostics.py` — `py7zr`, `rarfile`, `pillow_video` probe entries;
  new "Archive" group.
- `star/gui/runner.py` — `_RSVPOverlay` widget; RSVP hooks in
  `_apply_word_highlight`; Reading Aids submenu entries.  Menu-bar and toolbar
  building extracted into `_build_menu_bar` / `_build_toolbar` so they can be
  rebuilt on a language switch; menu labels routed through `tr()`; new
  `_set_ui_language` and an Interface Language submenu.
- `star/tui.py` — `_draw_rsvp`, `_rsvp_mode_cmd`, `_rsvp_position_cmd`;
  RSVP state variables; `_fillrow_range` helper.
- `star/settings.py` — `ui_language` default.
- `tests/test_rsvp.py` — 18 tests covering position geometry, settings
  defaults, and word-extraction edge cases.
- `tests/test_i18n.py` — 29 tests covering `tr()` fallback, language switching,
  and catalog integrity audits.

---

## [0.1.10] 2026-06-24

### ✨ Added

- **Knowledge graph.** Annotations can now be linked across documents with typed,
  directed relations — `CONFLICTS_WITH`, `SUPPORTS`, `IS_EXAMPLE_OF`, `CITES`,
  `CONTRADICTS`, `DEFINES`, `EXTENDS`, `SEE_ALSO`, `PRECEDES`, `FOLLOWS`. Each
  annotation gains a stable `id` and an optional `relations` list, assigned
  lazily so existing notes keep working unchanged.
  - **New `Graph` menu** (`Alt+G`) in the Qt GUI: Show Graph View
    (`Ctrl+Shift+Q`), Rebuild, Add/Edit Relation, Extract Concepts, Auto-Suggest
    Relations, Export (SVG / PlantUML / DOT / JSON), and open external
    SVG/DOT/PlantUML files. An interactive **knowledge-graph dock** renders the
    graph (colour-coded by relation type); double-clicking a node navigates to
    that annotation in its document.
  - **TUI commands**: `graph-show`, `graph-rebuild`, `graph-add-relation`,
    `graph-extract-concepts`, `graph-suggest-relations`, and
    `graph-export-svg` / `-dot` / `-plantuml` / `-json`.
  - **Concept extraction**: spaCy → NLTK → a pure-regex, domain-aware fallback
    (`general` / `legal` / `medical` / `sociological`), plus auto-suggested
    relations from concepts that match existing notes.
  - **Export** to SVG, PlantUML, DOT, and JSON. SVG works with no external
    packages via a built-in spring-layout renderer; `graphviz` is used for nicer
    layout when installed.
  - New optional dependencies (`spacy`, `nltk`, `graphviz`, `plantuml`) — all
    guarded; the feature works fully without them. See
    [`docs/knowledge-graph.md`](../docs/knowledge-graph.md).
- **`graph` settings block** — layout, node colouring, concept domain, orphan
  visibility, and last export directory.
- **Obsidian vault import/export.** Import an [Obsidian](https://obsidian.md)
  vault (a folder of Markdown notes) two ways — into the **knowledge graph**
  (each note becomes a library document plus a `#obsidian-note` graph node, and
  `[[wikilinks]]`, including typed Dataview `rel:: [[target]]` fields, become
  relations) or into the **library / bookshelf only** (notes registered as
  documents, no graph) — and export the graph back out as linked Markdown.
  **File ▸ Import Obsidian Vault…** / **File ▸ Export ▸ Obsidian Vault…**, or
  `M-x import-vault` / `export-vault`. Front matter is parsed with a built-in
  reader (`pyyaml` optional, now registered, for richer YAML). See
  [`docs/obsidian.md`](../docs/obsidian.md).
- **`vault` settings block** — last vault directory and the default relation type
  for untyped wikilinks.

### 🧩 Internal

- New pure-Python, Qt-free modules: `star/graph.py`, `star/ner.py`,
  `star/export_graph.py`; the Qt viewer lives in `star/gui/graph_view.py` and is
  imported lazily.

---

## [0.1.9] 2026-06-23

### ⚡ Performance

- **Much faster startup.** Heavy optional packages (PyTorch/Whisper, Coqui,
  wordfreq, sounddevice, the document loaders PyMuPDF/openpyxl/python-docx/
  python-pptx/pdfminer, and the study-aid libraries) are no longer imported at
  launch — they are detected cheaply with `importlib.util.find_spec` and imported
  lazily on first use. `star/app.py` also branches its imports so each mode loads
  only its own UI stack. On a fully-loaded install, `import star.app` dropped from
  ~3.0 s to ~0.2 s.

### ✨ Added

- **`STAR_VENDOR_DIR`.** Point this environment variable at a directory of
  vendored native engines (ffmpeg, Tesseract, liblouis, Pandoc, DECtalk,
  libespeak-ng) and star will load them from there. This is the supported way to
  add the native engines — including the in-process **DECtalk.dll** and
  **libespeak-ng.dll** the old `star.exe` bundled — to a wheel / pipx / source
  install. See [`docs/installation.md`](../docs/installation.md).
- **Source checkouts auto-detect `vendor/`.** A source run now also looks for the
  `vendor/` tree at the project root (where `tools/build-vendor.py` assembles it),
  fixing a long-standing mismatch where star only checked `star/vendor`.

### 📚 Documentation

- **Modular `docs/` tree.** The deep reference material that had accumulated in
  the root `README.md` now lives in a structured [`docs/`](../docs/) directory
  (`installation.md`, `usage_guide.md`, `features.md`, `configuration.md`,
  `architecture.md`). `README.md` is now a concise introduction-and-links portal.
- **Quick command reference.** `docs/usage_guide.md` adds a single table mapping
  every primary feature to its **GUI menu path**, **keyboard shortcut**, and
  **TUI palette command** in one place.

### 🏗️ Build & CI

- **Wheel + PyPI is the only automated release output.** The pure-Python wheel
  (`py3-none-any`) plus sdist, published to PyPI (and attached to the GitHub
  Release), is now the canonical, stable distribution. `pyproject.toml` documents
  this explicitly.
- **Windows `star.pyz` no longer built by CI.** The fat zipapp is no longer built
  on tag pushes or attached to releases — it is now build-it-yourself (`python
  build_zipapp.py`; a manual `workflow_dispatch` with `build_pyz: true` can still
  produce one). See [`docs/installation.md`](../docs/installation.md).
- **Windows `star.exe` deprecated to a manual fallback.** The PyInstaller
  `star.exe` is no longer built on tag pushes and is no longer attached to the
  GitHub Release. The build logic is preserved but gated behind an explicit
  opt-in (`tools/build-windows.ps1 -AllowDeprecatedExe`, or a manual
  `workflow_dispatch` with `build_exe: true`) for maintainers who still need it.
  See [`BUILD.md`](BUILD.md).

### ♻️ Refactor

- **`star/gui.py` is now a package (`star/gui/`).** The monolithic Qt GUI module
  was split into a package with a re-export shim, and the self-contained
  `_HelpWindow` dialog was extracted into its own module. Public imports
  (`from star.gui import _run_qt_gui`) are unchanged.

---

## [0.1.8] 2026-06-23

### ✨ Added

- **Published to PyPI.** star is now installable with `pip install star-reader`
  (or `pipx install star-reader`) — no manual wheel download. The release
  workflow publishes the wheel and sdist via PyPI **trusted publishing** (OIDC,
  no stored API token): pre-release tags (e.g. `v0.1.8-rc1`) go to TestPyPI and
  final tags to PyPI.

### 🏗️ Build & CI

- **Continuous integration.** A GitHub Actions test matrix (Linux / Windows /
  macOS × Python 3.11–3.13, with one leg that installs the optional packages so
  the real-behaviour tests run) and a non-blocking `ruff` lint gate run on every
  push and pull request.
- **Automated releases.** A tag-triggered workflow builds the universal wheel +
  sdist, the Windows `star.pyz`, and the Windows `star.exe`, and publishes a
  GitHub Release with generated notes.
- **Optional lean Windows build.** The Windows `star.exe` still bundles the
  offline dictation stack (Whisper + PyTorch + the `base` model) **by default**,
  so users get voice dictation out of the box. A new `-Lean` switch on
  `tools/build-windows.ps1` (or the release workflow's `lean: true` input) skips
  that multi-GB stack for a fast, small build — useful for quick test builds and
  CI iteration; a lean `star.exe` reports dictation as unavailable in
  `star --deps` and is otherwise fully functional.

---

## [0.1.7] 2026-06-23

### ✨ Added

- **Document translation.** A new **Tools ▸ Translate Document…**
  (`Ctrl+Shift+X`) translates the open document into any of 15 common languages
  via Google Translate (no API key, no account). A picker dialog chooses the
  target language and shows the result in a read-only pane; the network call
  runs on a background thread so the window stays responsive, and the input is
  capped at 15 000 characters per request to stay within rate limits. Requires
  the optional `deep-translator` package; the menu item prompts to install it
  when absent.
- **RSS / Atom feed reading.** **File ▸ Open Feed…** (`Ctrl+Shift+M`) fetches a
  feed URL, lists its articles, and opens the chosen one in the reader through
  star's normal URL-loading path. Useful for tracking arXiv, PubMed, bioRxiv,
  or journal feeds without leaving star. Requires the optional `feedparser`
  package; the menu item prompts to install it when absent.
- **Difficult-word overlay.** **View ▸ Reading Aids ▸ Highlight Difficult
  Words** (`Ctrl+Alt+O`) tints uncommon / academic vocabulary by word
  frequency, giving a visual pre-scan of dense terminology before reading. The
  overlay is non-destructive (it rides the existing extra-selection pipeline,
  sitting under user highlights and the TTS word highlight), persists across
  sessions (`qt_vocab_highlight`), and recomputes on each document load.
  Requires the optional `wordfreq` package.
- **Dependency status report.** A new `star --deps` flag prints the
  availability of every optional dependency, grouped by area, with a one-line
  description and a copy-paste install hint for anything missing — backed by a
  new `star.diagnostics` module that is the single source of truth for star's
  optional dependencies.
- **New optional-dependency groups.** `translate` (`deep-translator`), `feeds`
  (`feedparser`), and `vocab` (`wordfreq`), all folded into the `all` extra and
  mirrored in `requirements-optional.txt`.

### 🧪 Tests

- **General dependency harness.** `tests/test_dependencies.py` verifies the new
  diagnostics registry against the codebase: a completeness check fails if any
  import guard is ever added without being registered, and a per-dependency
  consistency check asserts that anything reported as available really does
  import. `tests/test_features.py` covers the translation, feed, and
  difficult-word logic, including their graceful-degradation paths.

### 📝 Notes

- The three new commands use `Ctrl+Shift+X`, `Ctrl+Shift+M`, and `Ctrl+Alt+O`
  — the more intuitive `Ctrl+Shift+L/F` and `Ctrl+Alt+W` were already bound
  (live preview, themes folder, text spacing). All three are also reachable
  from the F2 command palette, which now additionally lists Summarize, Anki
  export, and Check Spelling for completeness.

---

## [0.1.6] 2026-06-23

### ✨ Added

- **Document summarization.** A new **Tools ▸ Summarize Document**
  (`Ctrl+Shift+U`) condenses the open document to its key sentences using the
  LexRank algorithm (via the optional `sumy` package) and shows the result in a
  read-only dialog. The number of sentences is configurable through the
  `summary_sentences` setting (default 7). Summarization runs on a background
  thread so the window stays responsive on long documents. Requires
  `pip install sumy`; the menu item prompts to install it when absent. The
  NLTK sentence-tokenizer data it needs is fetched automatically on first use.
- **Anki flashcard export.** **File ▸ Export ▸ Anki Flashcards…**
  (`Ctrl+Alt+H`) turns the current document's notes into an Anki deck
  (`.apkg`): each note becomes one card with the highlighted passage on the
  front and your note on the back. Requires the optional `genanki` package;
  the menu item prompts to install it when absent, and prompts you to add a
  note first if the document has none.
- **Spell checking in edit mode.** While editing a document's Markdown source,
  misspelled words are underlined with a red squiggle, rechecked as you type.
  **Edit ▸ Check Spelling** (`F7`) counts the misspellings and lists them in a
  dialog, in or out of edit mode. Both use the optional `pyspellchecker`
  package and degrade gracefully — edit mode stays fully usable, and the menu
  item prompts to install it — when it is absent.
- **New optional-dependency groups.** `summarize` (`sumy`), `flashcards`
  (`genanki`), and `spellcheck` (`pyspellchecker`), all folded into the `all`
  extra, plus a comment-annotated `requirements-optional.txt` mirroring the
  optional packages for `pip install -r` users.

### 🐛 Fixed

- **Reading highlight no longer runs ahead of eSpeak-NG speech.** In its
  in-process (libespeak-ng) mode, eSpeak synthesizes a whole sentence's audio
  in a burst and reports all of that sentence's word events at once — well
  before the words are actually heard — which made the highlight race up to a
  sentence ahead of the audio. star now paces each word event to the word's
  real audio position (which the engine reports per event) and only advances
  the highlight when that moment arrives, so the highlight follows playback
  instead of synthesis. The highlight timer also tracks these playback-accurate
  events tightly (within a single word) for this backend. A new
  `espeak_highlight_offset_ms` setting (default 120) compensates for audio
  output latency — raise it if highlights still lead the audio, lower it toward
  0 if they lag.

### 📝 Notes

- Summarize Document uses `Ctrl+Shift+U` rather than `Ctrl+Shift+S`, which was
  already bound to Reading Statistics. Every new command has both a menu entry
  and a keyboard shortcut, keeping star fully keyboard-drivable.

---

## [0.1.5] 2026-06-22

### ✨ Added

- **In-process eSpeak-NG via libespeak-ng (ctypes).** A new backend drives
  eSpeak-NG through its C library instead of the `espeak-ng` command line. The
  library reports a per-word event for every spoken word, tagged with the
  word's audio position (milliseconds into the output stream), which `star`
  forwards to the reading highlight. It is preferred automatically when the
  shared library is available — the bundled `libespeak-ng.dll` in the
  self-contained Windows build, or a system `libespeak-ng` on Linux/macOS — and
  falls back to the `espeak-ng` command-line backend otherwise. Speech is
  synthesized in short sentence-sized chunks, so pausing, stopping, or switching
  away silences playback promptly instead of running on in the background.
- **Bundled libespeak-ng in the self-contained Windows build.**
  `tools/build-vendor.py` now fetches eSpeak-NG (1.52.0) and vendors its 64-bit
  `libespeak-ng.dll` plus the `espeak-ng-data` tree, so `star.exe` speaks with
  eSpeak — and the playback-synced highlight — with no separate install.
- **Batch conversion.** Convert many documents — selected files or a whole
  folder — to one output format (Markdown, plain text, or Braille/BRF) in a
  single step, via **File ▸ Batch Convert** (`Ctrl+Shift+C`) in the Qt GUI or
  `M-x batch-convert` in the terminal UI. Each file runs through the existing
  single-file load→export pipeline; a corrupt, password-protected, or
  unsupported file is recorded and skipped instead of aborting the run. Outputs
  reuse the source basename (collisions disambiguated, never overwritten), and a
  timestamped summary — what succeeded, what failed and why, and where outputs
  went — is written alongside the outputs.
- **Hot-folder watching.** Watch a folder and convert files dropped into it,
  unattended: `star --watch <input_dir> --output <output_dir> --format <fmt>`
  for headless use, or **File ▸ Watch Folder** (`Ctrl+Shift+W`, a toggle) from
  the Qt GUI. Built on the batch core (same formats and validation). Files are
  debounced (processed only once their size has stabilised, so a file still
  being copied in is never read half-written); every attempt is logged with a
  timestamp to `<output>/star-watch.log`; successful sources move to
  `<input>/processed/` and failures to `<input>/failed/` (collisions
  disambiguated, never overwritten); and Ctrl+C / SIGTERM shut it down cleanly
  without interrupting a file mid-conversion. Uses `watchdog` when installed
  (the new `[watch]` optional-dependency group) and falls back to directory
  polling otherwise.
- **Every Qt menu item now has a keyboard shortcut**, keeping star fully
  keyboard-drivable.

### 🔧 Changed

- **The Qt GUI is now star's primary interface.** Ongoing development is focused
  on the Qt GUI, so it is the default and the recommended way to run star. The
  curses terminal UI (`--tui`) remains fully supported and keyboard-driven as a
  secondary interface for headless or text-only environments.

### 🐛 Fixed

- **Reading highlight no longer runs ahead of the audio.** The highlight is
  now anchored to the engine's actual word progress rather than a free-running
  words-per-minute estimate:
  - With eSpeak-NG driven through libespeak-ng, the highlight follows each
    word's reported audio position, so it tracks playback across the whole
    document instead of drifting further ahead over time.
  - For backends that report real word events (pyttsx3 and libespeak-ng), the
    highlight now waits for the first event before starting, so it begins when
    audio actually begins rather than when synthesis was requested — removing a
    constant head start.
  - Note: the previous attempt to read `<mark>` events from the `espeak-ng`
    command line could never work (the CLI does not emit them), so the
    command-line backend remains timer-paced; use libespeak-ng for synced
    highlighting.

---

## [0.1.4] — 2026-06-22

### ✨ Added

- **Fat zipapp build (`star.pyz`).** A new `build_zipapp.py` produces a
  single-file `star.pyz` that bundles star together with its Python
  dependencies (the `[all]` extras group). It is self-extracting: on first run
  it unpacks its bundled packages into the per-user config directory (so
  compiled packages such as PyQt6 and PyMuPDF load from real files on disk),
  then starts normally. This removes the `pip install` step — running star this
  way needs only a Python interpreter plus the external engines (ffmpeg,
  Tesseract, liblouis, eSpeak-NG, DECtalk) on `PATH`. Because it carries
  compiled packages, the artifact is **platform-specific** (build one per target
  platform). It is additive and does not replace the self-contained Windows
  `star.exe`, which additionally bundles the external engines.

### 🔧 Changed

- **Minimum supported Python is now 3.11** (previously 3.8). The
  `requires-python` constraint, the installer and build scripts, and the build
  documentation were updated to match.

---

## [0.1.3] — 2026-06-16

A focused round of reading, speech, and study-workflow additions, all built on
the existing single-file architecture — `star.py` still runs with zero extras
installed.

### ✨ Added

- **Sentence-level highlight option.** A new **highlight granularity**
  control lets the spoken text be highlighted by **word** (default), by whole
  **sentence** (much less visual flicker for readers who find rapid word-by-word
  movement distracting), or **both** (a soft sentence band with the current word
  marked on top). Works in **both** the Qt GUI and the curses TUI. Set it from
  **View → Reading Aids → Karaoke Highlight…** (new *Granularity* selector) or
  `M-x highlight-granularity word|sentence|both` in the TUI. New setting:
  `highlight_granularity` (default `word`).
- **Timestamped subtitle export — SRT / VTT.** Audio export can now emit a
  synchronized caption track so the highlight "travels" with the audio into any
  media player. Export captions on their own (**File → Export → Export Subtitles
  (SRT / VTT)…**, or `M-x export-subtitles`), or have them written automatically
  alongside every audio export (`M-x subtitles-with-audio`). Captions are grouped
  into readable sentence-length cues by default, or one cue per word with
  `M-x subtitle-word-level`. Timing is estimated from the synthesized audio's
  duration, so it needs no external tools. New settings: `subtitle_format`
  (`srt`/`vtt`), `subtitle_word_level`, `export_subtitles_with_audio`. New TUI
  commands: `export-subtitles`, `subtitle-format`, `subtitle-word-level`,
  `subtitles-with-audio`.
- **A keyboard shortcut for every GUI menu item.** Every command in the Qt
  menus now has a shortcut shown beside it and listed in **Help → Keyboard
  Shortcuts** (`F3`). Bindings follow a consistent scheme — `Ctrl+letter`
  (forward/primary), `Ctrl+Shift+letter` (backward/secondary), `Alt+punct`
  (sentences), `Ctrl+Alt+letter` (exports, citations, tools, reading aids) —
  and each is owned by exactly one action, eliminating the previous duplicate
  toolbar/window bindings that risked Qt “ambiguous shortcut” conflicts. New:
  highlight colors (`Ctrl+Shift+1`…`5`), export commands (`Ctrl+Alt+M/P/B/A/U`),
  citation commands (`Ctrl+Alt+I/E/C/D/R/G`), reading aids, and more. All
  bindings remain remappable via **Help → Customize Shortcuts…**.
- **Tap `Ctrl` to play/pause (JAWS habit).** Pressing and releasing the `Ctrl`
  key on its own toggles speech, mirroring the JAWS “Ctrl silences speech”
  reflex. Using Ctrl as a modifier in a chord never triggers it. New setting:
  `qt_ctrl_pause` (default `true`).
- **Reading statistics & progress tracking.** STAR now records time read,
  furthest word reached, progress %, and session count per document while
  speech plays, and surfaces them in a dashboard — **Tools → Reading
  Statistics…** (`Ctrl+Shift+S`) in the Qt GUI and `M-x reading-stats` in the
  TUI — with overall totals and a most-read list. New setting: `reading_stats`.
- **Library / bookshelf view.** Every opened document is remembered with
  its title, format, progress, and last-opened time. **File → Library /
  Bookshelf…** (`Ctrl+Shift+B`) opens a searchable list (Enter / double-click
  reopens a document); the TUI offers `M-x library`. New setting: `library`.
- **Live HTML preview while editing.** In edit mode a split pane can show a
  live-rendered HTML preview of the Markdown source beside the editor,
  re-rendering as you type (debounced). Toggle it with **View → Live HTML
  Preview** (`Ctrl+Shift+L`); turning it on outside edit mode enters edit mode.
  New setting: `qt_edit_preview`.
- **Voice & profile presets.** Save the current voice, rate, volume, theme,
  font, spacing, and highlight settings as a named profile (e.g. “Skim”, “Deep
  Study”, “Low-Light”) and switch between them in one step. A new **Profiles**
  menu offers **Save Current Settings as Profile…** (`Ctrl+Shift+K`), **Load
  Profile…** (`Ctrl+Shift+J`), and **Delete Profile…** (`Ctrl+Shift+Y`); the TUI
  adds `M-x profile-save`, `profile-load`, `profile-list`, and `profile-delete`.
  New setting: `profiles`.
- **Pronunciation lexicon editor.** A user-editable dictionary maps domain
  terms — drug names, anatomy, acronyms — to a spoken form so TTS says them
  correctly and consistently across every backend. Edit it from **Speech →
  Pronunciation Lexicon…** (`Ctrl+Shift+I`) in the Qt GUI, or `M-x pron-add`,
  `pron-list`, `pron-remove`, and `pronunciations` (on/off) in the TUI.
  Pronunciation overrides are applied first, before abbreviation and number
  normalization. New settings: `pronunciations`, `use_pronunciations`.
- **Piper neural TTS backend.** A new optional **`piper`** backend brings
  free, offline, neural-quality voices via the standalone
  [Piper](https://github.com/rhasspy/piper) binary — no Python package, no
  subscription, no network. Point STAR at a `.onnx` voice model with the new
  `piper_model` setting (or the `PIPER_MODEL` env var, or by dropping models in
  a Piper voice directory) and select it from **Speech → Choose TTS Engine…**
  (new GUI engine picker) or `M-x tts-backend piper`. Like Coqui, it is opt-in
  and never chosen in `auto` mode. New setting: `piper_model`.
- **Fully self-contained Windows binary.** The portable `star.exe` can now
  bundle the native engines that previously had to be installed separately, so
  a single file does *everything* on a clean PC:
  - **ffmpeg** → MP3 / OGG / MP4 audio export
  - **Tesseract** + English language data → OCR of images and scanned PDFs
  - **liblouis** + translation tables → Grade 2 (contracted) Braille
  - **Pandoc** → high-fidelity markup conversion (RST, Org, MediaWiki,
    AsciiDoc, Textile, LaTeX, legacy `.doc`, …)
  - **DECtalk** → the classic “Perfect Paul” voice, via the bundled
    `DECtalk.dll` + dictionary driven **in-process through ctypes** (no
    separate CLI required); the architecture-matched 64-/32-bit engine is
    selected automatically. On the self-contained Windows build DECtalk is now
    the **default engine** and **Perfect Paul the default voice**, and all
    nine classic speakers — Perfect Paul, Beautiful Betty, Huge Harry, Frail
    Frank, Doctor Dennis, Kit the Kid, Uppity Ursula, Rough Rita, Whispering
    Wendy — appear in the voice picker (**Speech → Choose Voice…**,
    `Ctrl+Shift+V`). DECtalk is only chosen automatically when the engine
    actually starts (a real startup is probed once), so machines without a
    working DECtalk fall back to pyttsx3/SAPI as before

  `star.py` locates each bundled engine via a new `_vendor_dir()` resolver
  (`sys._MEIPASS` when frozen) and falls back to a system install when a tool
  is absent, so running from source still needs nothing extra. For Pandoc the
  bundled binary is also exposed to `pypandoc` via `$PYPANDOC_PANDOC`; for
  DECtalk a `say`/`dtalk` CLI (on `PATH` or via `DECTALK_BIN`) still works as a
  fallback. A new `build-vendor.py` helper downloads and assembles the engines
  into `vendor/`, which `star.spec` packs into the bundle (see `BUILD.md`). The
  fully self-contained build is ~300+ MB (Pandoc alone adds ~150 MB); a lean
  build without `vendor/` remains ~90–100 MB.

### 🏗️ Packaging & architecture

- **`star.py` can now be split into an importable `star/` package.** A new
  [`tools/split_star.py`](tools/split_star.py) refactors the monolithic
  `star.py` into logical submodules (`tts`, `tui`, `gui`, `documents`,
  `markup`, `render`, `braille`, `citations`, …) under a `star/` package,
  with shared foundational state (stdlib imports, vendored-tool wiring,
  optional-dependency flags, paths, metadata) in `star/_runtime.py` and
  re-exported via `from ._runtime import *`. The tool moves exact source by
  top-level AST node — **nothing is re-typed** — and computes the
  cross-module imports automatically, so the package stays byte-for-byte
  faithful to `star.py`. `star.py` remains the canonical single-file source
  and still runs with zero extras; the generated `star/` package is what the
  wheel ships and what `python -m star` / the `star` console command import.
- **Pure-Python wheel for macOS / Linux / Windows.** A new
  [`pyproject.toml`](pyproject.toml) builds a single `py3-none-any` wheel
  (`star_reader-<version>-py3-none-any.whl`) that installs `star` and its
  `star` command into any environment. Recommended dependencies (Qt GUI, TTS,
  common document loaders) install by default; the optional features are
  available as extras — `[ocr]`, `[formats]`, `[markup]`, `[braille]`,
  `[audio]`, `[transcribe]`, and `[all]`. Build it with `python -m build
  --wheel` (see `BUILD.md`).
- **macOS / Linux native-engine bootstrap.** A new
  [`tools/install_native.py`](tools/install_native.py) is the cross-platform
  counterpart of `build-vendor.py`: it installs the native engines (ffmpeg,
  Tesseract + English data, liblouis, Pandoc, and eSpeak-NG on Linux) through
  the system package manager (Homebrew / apt / dnf / pacman / zypper),
  installing only what is missing. Supports `--dry-run` and per-engine
  selection.
- **Voice dictation & transcription now bundled in the Windows binary.** The
  self-contained `star.exe` ships the full Whisper stack — `openai-whisper`
  with its PyTorch backend, `sounddevice` for microphone capture, and the
  Whisper **`base` model** — so **Tools → Dictate Note** and **Transcribe
  Audio File** work **offline, with no install and no first-run download** on a
  clean machine. A PyInstaller runtime hook
  ([`tools/rthook_star.py`](tools/rthook_star.py)) puts the bundled ffmpeg on
  `PATH` (Whisper decodes audio through it) and points Whisper's model cache at
  the bundled `base` model; `tools/build-windows.ps1` installs the dictation
  dependencies and stages the model automatically. PyTorch makes this the
  largest single addition to the bundle (the binary grows to ~600+ MB); the
  dependencies are guarded, so a build without them still succeeds and the
  feature falls back to its “requires Whisper” hint. The frozen entry point is
  now [`run_star.py`](run_star.py), which imports `star.app.main` from the
  generated package.

### 📝 Notes for upgrading users

- All new settings have safe defaults, so existing `settings.json` files keep
  working unchanged; the new keys are added on next save.
- Subtitle timing is *estimated* (proportional to spoken-token length) because
  file-based TTS synthesis exposes no per-word callbacks. It is accurate enough
  for review and study recordings.

---

## [0.1.2] — 2026-06-14

A substantial revision focused on **reliable, accessible defaults out of the
box**: native speech on every platform, dependency-free Braille export, smoother
word-highlight tracking, a more professional default look, and a new set of
reading-accessibility aids. The single-file architecture is unchanged —
`star.py` still runs with zero extras installed.

### ✨ Added

- **Reading accessibility aids (Qt GUI).** A new **View → Reading Aids** submenu
  collects low-friction, high-impact accommodations:
  - **Adjustable text spacing** (WCAG 1.4.12) — independently tune line height,
    letter spacing, and word spacing from a live-preview dialog. New settings:
    `qt_line_height` (default `1.5`), `qt_letter_spacing`, `qt_word_spacing`.
  - **Dyslexia-friendly font preference** — opt in to an installed
    OpenDyslexic / Atkinson Hyperlegible / Lexend / Comic Sans face, with a
    graceful fallback and prompt when none is installed. New setting:
    `qt_dyslexia_font`.
  - **Bionic reading** — embolden the leading part of each word to pull the
    eye forward. New setting: `qt_bionic_reading`.
  - **Current-line focus band** — tint the line being read. New setting:
    `qt_current_line_highlight`.
  - **Karaoke highlight tuning** — choose the spoken-word highlight style
    (`background`, `underline`, `box`, `bold`, `color`), color, pacing
    (`highlight_speed`), and a lead/lag offset. New settings: `highlight_style`,
    `highlight_lead_words`.
- **Notes dock stays hidden by default.** The Qt **Notes** panel is hidden on
  launch (`qt_show_notes` defaults to `false`) to maximize the reading area; it
  opens on demand via **Ctrl+Shift+N**, **View → Toggle Notes Panel**, or when a
  note is added.
- **Annotations / notes — now in both interfaces, with tags & search.** The Qt
  **Notes** dock and a new curses TUI notes pager share one per-document store.
  Add at the cursor/selection (`Ctrl+Shift+A` in Qt, `a` in the TUI), attach
  **tags**, and **filter with full-text or `#tag` search** (filter box in Qt;
  `M-x annotations-search` / `annotations-list` in the TUI). Notes carry both a
  Qt char offset and a `word_idx`, so a note made in one interface navigates
  correctly in the other. Export to Markdown, JSON, BibTeX, or RIS. New TUI
  commands: `annotate`, `annotations-list`, `annotations-search`,
  `annotation-goto`, `annotation-delete`, `annotations-export`.
- **Citation manager (Qt GUI).** A shared citation library with **import and
  export of BibTeX, RIS, and CSL-JSON** (`Citations` menu). Add references by
  hand, browse/copy/delete them, and **link a citation to a note** so exported
  study notes carry attribution. New setting: `citations`.
- **Whisper voice dictation & transcription (optional).** `Tools → Transcribe
  Audio File…` opens a transcription as a new document; `Tools → Dictate Note…`
  records from the microphone and saves the transcription as a note. Backed by
  `openai-whisper` or `faster-whisper` (+ `sounddevice`/`numpy` for the mic);
  fully guarded when absent. New setting: `whisper_model`.
- **Keyboard cheat sheet & GUI/TUI parity.** A canonical shortcut scheme is now
  documented in one place and shown in-app (`Help → Keyboard Shortcuts` in Qt,
  `?` / `M-x shortcuts` in the TUI).
- **Full menu coverage (Qt GUI).** New **Speech**, **Navigate**, **Edit**,
  **Citations**, **Tools**, and **Help** menus put every command within reach
  of the mouse — important for users who don't drive the app by keyboard.
- **macOS native speech backend (`applesay`).** A new TTS backend drives the
  built-in `/usr/bin/say` command, giving Mac users Apple's high-quality system
  voices with **no extra dependencies** (no `pyobjc`, no Homebrew, no eSpeak).
  In `auto` mode it is ranked **above eSpeak** so a Mac never silently falls
  back to the robotic eSpeak voice.
- **Preferred default voice resolution.** When no voice is explicitly set,
  star now auto-selects a voice matching the new `tts_prefer_voice` setting
  (default `"eloquence"`), favoring a US-English variant. This makes the
  **Eloquence (US English)** voices bundled with recent macOS the default when
  present. A user's explicit voice choice is never overridden.
- **Built-in, dependency-free Braille (Grade 1) translator.** BRF export now
  works out of the box with a pure-Python North-American Braille-ASCII (NABCC)
  translator — letters, capital signs, number signs, common punctuation, and
  standard 40-cell / 25-line page geometry with form feeds.
- **Settings migration.** Settings files written by earlier versions are
  upgraded on load: the deprecated serif `Georgia` font and the lagging `0.85`
  highlight speed are replaced with the new defaults (only when they exactly
  match the old default, so deliberate choices are preserved).
- New settings keys: `tts_prefer_voice`, `braille_grade2`,
  `audio_export_format`.
- **Cross-platform installers**: `install.sh` (Linux/macOS) and `install.ps1`
  (Windows) with `minimal` / `recommended` / `all` profiles, virtual-env by
  default, and platform-aware dependency hints (incl. `pyobjc` on macOS,
  `windows-curses` on Windows).
- **Portable Windows binary build.** A PyInstaller recipe (`star.spec`) and a
  one-command wrapper (`build-windows.ps1`) produce a single, self-contained
  `dist\star.exe` that runs on Windows machines with no Python or dependencies
  installed — ideal for demos. Bundles the Qt GUI, SAPI5 speech, and the core
  document loaders. Documented in `BUILD.md`.
- New documentation: `CHANGELOG.md` and `BUILD.md` (portable Windows binary).

### 🔧 Changed

- **Word-highlight tracking is smooth and continuous.** The highlight timer no
  longer freezes mid-document when SAPI5 word callbacks arrive late or stop
  firing. The pacing guard now allows the highlight to run up to **4 words**
  ahead of the last confirmed audio position and is **bypassed after 1.5 s**
  of callback silence, so the cursor keeps following speech instead of getting
  stuck. (Builds on the timer-generation race fixes already in place.)
- **Word-position map is monotonic and column-aware.** Repeated common words
  (`the`, `a`, `and`) on a single line are matched in document order instead of
  always snapping back to the first occurrence, and the search position never
  moves backward — eliminating the "highlight stuck several lines back" effect.
- **Audio export now defaults to WAV** (`audio_export_format`). WAV needs no
  external tools; MP3/OGG/MP4 still work when `ffmpeg` or `pydub` is present.
- **Default display font is now sans-serif** (`Helvetica Neue` on macOS,
  `Segoe UI` on Windows, `DejaVu Sans` on Linux). Serif faces are discouraged
  for on-screen reading accessibility.
- **Polished default dark theme** with a modern, professional neutral-dark
  palette (Zed/Ghostty-inspired) for the Qt GUI editor, HTML rendering, and the
  seeded `dark.css` theme.
- **`highlight_speed` default is now `1.0`** (match speech rate exactly); the
  pacing guard is the real throttle, so the highlight stays tight to the audio.
- BRF export gained a `braille_grade2` opt-in for contracted Grade 2 via
  liblouis (when installed and the table resolves).

### 🐛 Fixed

- **Qt GUI now runs on PyQt6.** `QAction` was imported from `QtWidgets`, but
  PyQt6 moved it to `QtGui`; the bad import made the whole PyQt6 branch fail, so
  star silently fell back to PyQt5 (and could not start the GUI at all on a
  PyQt6-only machine). `QAction` is now imported from `QtGui` under PyQt6, and a
  couple of PyQt6 enum-to-int conversions (`line height`, full-width selection)
  were hardened. This also makes the frozen Windows binary work.
- **BRF export no longer crashes the app.** Previously, exporting Braille with
  `louis` installed but a translation table missing could make liblouis call
  `exit()` at the C level, abruptly closing the window. liblouis is now opt-in
  and fully guarded; the built-in Grade 1 translator is the reliable default and
  can never terminate the process.
- **macOS no longer defaults to eSpeak.** With the new `applesay` backend ranked
  above eSpeak, Macs speak with a native Apple voice by default.
- Highlighting that previously got "stuck" and stopped advancing down the page
  while speech continued now tracks reading position reliably.

### 📝 Notes for upgrading users

- Existing `settings.json` files are migrated automatically (see above). To
  adopt the new dark palette, delete `themes/dark.css` in your config directory
  (a fresh, updated copy is regenerated) or pick it from **View → Theme**.
- macOS users who want pyttsx3's word-boundary callbacks (rather than the
  timer-based highlight used by `say`) can `pip install pyobjc pyttsx3`.

---

## [0.1.1] — earlier

Initial public lineage of star prior to the 0.1.2 revision: single-file Qt GUI
and curses TUI, multi-format document loading (PDF, EPUB, DAISY/DTBook, DOCX,
PPTX, ODT, HTML, Markdown, LaTeX, RST and many markup formats, CSV/XLSX, images
via OCR, notebooks, source code), multiple TTS backends, themes, search,
bookmarks, reading-position memory, speed presets, Speech Cursor mode,
table-of-contents navigation, user highlights, audio export, document caching,
and screen-reader compatibility.

[0.1.3]: #013--2026-06-16
[0.1.2]: #012--2026-06-14
[0.1.1]: #011--earlier
