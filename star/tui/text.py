"""Static command/help text: the M-x command table, the keyboard-shortcut data + renderer, and the embedded help pager text."""
from .._runtime import *  # noqa: F401,F403


# M-x command catalog
# =============================================================================

MX_COMMANDS = sorted(
    [
        "about",
        "backend",
        "batch-convert",
        "book-next",
        "book-prev",
        "close",
        "dictate-note",
        "edit",
        "summarize",
        "transcribe-file",
        "whisper-model",
        "translate",
        "contrast-up",
        "contrast-down",
        "export-braille",
        "export-markdown",
        "export-audio",
        "export-subtitles",
        "subtitle-format",
        "subtitle-word-level",
        "subtitles-with-audio",
        "highlight-granularity",
        "font-size-down",
        "font-size-up",
        "goto-line",
        "graph-add-relation",
        "graph-export-dot",
        "graph-export-json",
        "graph-export-plantuml",
        "graph-export-svg",
        "graph-extract-concepts",
        "graph-rebuild",
        "graph-show",
        "graph-suggest-relations",
        "help",
        "import-vault",
        "export-vault",
        "license",
        "line-numbers",
        "next-heading",
        "next-paragraph",
        "read-next-heading",
        "read-prev-heading",
        "speech-cursor",
        "stop-speech",
        "abbrev-add",
        "abbrev-list",
        "pron-add",
        "pron-list",
        "pron-remove",
        "pronunciations",
        "profile-save",
        "profile-load",
        "profile-list",
        "profile-delete",
        "expand-abbreviations",
        "normalize-numbers",
        "table-mode",
        "next-sentence",
        "open",
        "open-url",
        "pause",
        "play",
        "preset-add",
        "preset-list",
        "prev-heading",
        "prev-paragraph",
        "prev-sentence",
        "replay-paragraph",
        "replay-sentence",
        "save-position",
        "clear-position",
        "jump-saved",
        "speed",
        "ssml",
        "ssml-on",
        "ssml-off",
        "rate-down",
        "rate-up",
        "reload",
        "search",
        "search-backward",
        "settings",
        "speak-line",
        "speak-selection",
        "stop",
        "syntax-highlight",
        "theme",
        "tts-backend",
        "tts-voice",
        "voice-picker",
        "volume-down",
        "volume-up",
        "voice",
        "quit",
        "wrap-width",
        "abbrev-add",
        "abbrev-list",
        "bookmark-delete",
        "bookmark-goto",
        "bookmark-list",
        "bookmark-set",
        "cache-clear",
        "chapter-goto",
        "chapter-list",
        "chapter-next",
        "chapter-prev",
        "copy",
        "expand-abbreviations",
        "footnote-mode",
        "font",
        "history-back",
        "define",
        "history-forward",
        "normalize-math",
        "normalize-numbers",
        "pubmed",
        "reading-level",
        "reading-stats",
        "stats",
        "library",
        "bookshelf",
        "recent",
        "search-regex",
        "table-mode",
        "wiki",
        "annotate",
        "annotations-list",
        "annotations-search",
        "annotation-goto",
        "annotation-delete",
        "annotations-export",
        "shortcuts",
        # Epic I — Archive ingestion
        "open-archive",
        # Epic II — Metadata & discovery
        "metadata-edit",
        "library-search",
        # Epic III — Video export
        "export-video",
        # RSVP reading mode
        "rsvp-mode",
        "rsvp-position",
    ]
)


# The GUI bindings are the canonical set.  The TUI mirrors them where the
# terminal can express the chord; where it cannot (terminals can't see
# Ctrl+Shift+<letter>), an equivalent single-key or M-x command is listed.
_SHORTCUTS: List[Tuple[str, List[Tuple[str, str, str]]]] = [
    (
        "Playback",
        [
            ("Play / pause", "Space  (or tap Ctrl)", "Space"),
            ("Stop", "Esc", "Esc / M-x stop"),
            ("Speed up / slow down", "Ctrl+= / Ctrl+-", "+ / -"),
            ("Play from cursor / caret", "Ctrl+Space", "Enter / Ctrl+Space"),
            ("Choose TTS engine", "Ctrl+Shift+G", "M-x tts-backend"),
            ("Choose voice", "Ctrl+Shift+V", "M-x voice-picker"),
            ("Speech-cursor mode", "Tab", "Tab"),
            ("Toggle SSML prosody", "Ctrl+Alt+Y", "M-x ssml"),
            ("Speak current line", "—", "M-x speak-line"),
        ],
    ),
    (
        "Navigation",
        [
            ("Next / prev heading", "Ctrl+H / Ctrl+Shift+H", "> / <"),
            ("Next / prev paragraph", "Ctrl+P / Ctrl+Shift+P", "] / ["),
            ("Next / prev sentence", "Alt+. / Alt+,", ". / ,"),
            ("Replay sentence", "Alt+;", ";"),
            ("Replay paragraph", "Ctrl+R", "r"),
            ("Next / prev table", "Ctrl+T / Ctrl+Shift+T", "M-x next-table"),
            ("Caret: word left / right", "← / →", "← / →"),
            ("Caret: line up / down", "↑ / ↓", "↑ / ↓  (j/k scroll)"),
        ],
    ),
    (
        "Notes / Annotations",
        [
            ("Add note at cursor", "Ctrl+Shift+A", "a / M-x annotate"),
            ("Edit / delete note", "Ctrl+Shift+E / Ctrl+Shift+D", "M-x annotation-*"),
            ("Toggle Notes panel", "Ctrl+Shift+N", "M-x annotations-list"),
            ("Export notes", "Ctrl+Alt+N", "M-x annotations-export"),
            (
                "Search / filter notes",
                "(search box in panel)",
                "M-x annotations-search",
            ),
        ],
    ),
    (
        "Highlights",
        [
            ("Highlight colors 1-5", "Ctrl+Shift+1 … 5", "—"),
            ("Clear all highlights", "Ctrl+Shift+0", "—"),
        ],
    ),
    (
        "Citations",
        [
            ("Import / export", "Ctrl+Alt+I / Ctrl+Alt+E", "—"),
            ("Add citation / by DOI", "Ctrl+Alt+C / Ctrl+Alt+D", "—"),
            ("Insert at cursor", "Ctrl+Alt+R", "—"),
            ("Manage / browse", "Ctrl+Alt+G", "—"),
        ],
    ),
    (
        "View & Reading Aids",
        [
            ("Cycle / choose theme", "F5 / Ctrl+Alt+T", "F5"),
            ("Toggle Contents panel", "Ctrl+\\", "—"),
            ("Reading level", "Ctrl+L", "M-x reading-level"),
            ("Define word (offline)", "Ctrl+D", "d / M-x define"),
            ("Change font", "Ctrl+Alt+F", "—"),
            ("Text spacing / karaoke", "Ctrl+Alt+W / Ctrl+, (Preferences)", "—"),
            ("Dyslexia font / bionic", "Ctrl+Alt+X / Ctrl+Alt+J", "—"),
            ("Current-line highlight", "Ctrl+Alt+L", "—"),
            ("RSVP mode (one word at a time)", "Ctrl+Alt+R", "M-x rsvp-mode"),
            ("RSVP position (quadrant)", "Ctrl+, (Preferences)", "M-x rsvp-position"),
            ("Reload / open CSS themes", "Ctrl+Shift+R / Ctrl+Shift+F", "—"),
            ("Line numbers / syntax", "—", "F6 / F7"),
        ],
    ),
    (
        "File & Export",
        [
            ("Open file / URL", "Ctrl+O / Ctrl+Shift+O", "Ctrl+O / M-x open-url"),
            ("Open Archive…", "File ▸ Open Archive…", "M-x open-archive"),
            ("Export Markdown / PDF", "Ctrl+Alt+M / Ctrl+Alt+P", "M-x export-markdown"),
            ("Export Braille / Audio", "Ctrl+Alt+B / Ctrl+Alt+A", "M-x export-*"),
            ("Export Subtitles", "Ctrl+Alt+U", "M-x export-subtitles"),
            ("Export Video (MP4)", "File ▸ Export ▸ Video…", "M-x export-video"),
            ("Quit", "Ctrl+Q", "Ctrl+Q / q"),
        ],
    ),
    (
        "Library & Metadata",
        [
            ("Library / Bookshelf", "Ctrl+Shift+B", "M-x library"),
            ("Library search", "—", "M-x library-search"),
            ("Edit document metadata", "—", "M-x metadata-edit"),
        ],
    ),
    (
        "Edit",
        [
            ("Toggle edit mode", "Ctrl+E", "—"),
            ("Save", "Ctrl+S", "—"),
            ("Copy", "Ctrl+C", "M-x copy"),
        ],
    ),
    (
        "Tools & Help",
        [
            ("Transcribe / dictate", "Ctrl+Alt+S / Ctrl+Alt+V", "—"),
            ("Transcript timestamps", "Ctrl+Alt+Z", "—"),
            ("Clear document cache", "Ctrl+Shift+Delete", "M-x cache-clear"),
            ("Command palette", "F2", "M-x / F2 / :"),
            ("Keyboard cheat sheet", "F3", "M-x shortcuts"),
            ("Customize shortcuts", "Ctrl+Alt+Q", "—"),
            ("Help (README) / About", "F1 / Ctrl+F1", "F1"),
        ],
    ),
    (
        "Knowledge Graph",
        [
            ("Show graph view", "Ctrl+Shift+Q", "M-x graph-show"),
            ("Rebuild graph", "Graph ▸ Rebuild", "M-x graph-rebuild"),
            ("Add relation", "Graph ▸ Add Relation…", "M-x graph-add-relation"),
            ("Edit relations", "Graph ▸ Edit Relations…", "—"),
            ("Extract concepts", "Graph ▸ Extract Concepts…", "M-x graph-extract-concepts"),
            ("Auto-suggest relations", "Graph ▸ Auto-Suggest…", "M-x graph-suggest-relations"),
            ("Export graph", "Graph ▸ Export Graph", "M-x graph-export-svg/dot/plantuml/json"),
        ],
    ),
]


def _shortcuts_text(plain: bool = False) -> str:
    """Render the canonical shortcut scheme as text.

    *plain* True produces a column layout for the curses pager; otherwise a
    Markdown table suitable for the Qt help dialog.
    """
    if plain:
        lines = ["Keyboard Shortcuts  (GUI bindings are canonical)", ""]
        for section, rows in _SHORTCUTS:
            lines.append(f"== {section} ==")
            for action, gui, tui in rows:
                lines.append(f"  {action:<26} GUI: {gui:<24} TUI: {tui}")
            lines.append("")
        return "\n".join(lines)
    md = [
        "# Keyboard Shortcuts",
        "",
        "GUI bindings are canonical; the TUI mirrors them where the terminal allows.",
        "",
    ]
    for section, rows in _SHORTCUTS:
        md.append(f"## {section}")
        md.append("")
        md.append("| Action | GUI | TUI |")
        md.append("|---|---|---|")
        for action, gui, tui in rows:
            md.append(f"| {action} | `{gui}` | `{tui}` |")
        md.append("")
    return "\n".join(md)


# =============================================================================
# Main TUI Application
# =============================================================================


# =============================================================================
# Embedded help text
# =============================================================================

_HELP_TEXT = (
    """\
# star — Speaking Terminal Access Reader"""
    + APP_VERSION
    + """

star is a reading application with built-in text-to-speech designed for
students with print disabilities.

---

## Quick Start

Open a file:          `Ctrl+O`  or  `star document.pdf`
Start / pause:        `Space`
Read from caret:      `Enter`   (arrow keys move the caret)
Stop reading:         `Esc`
Search:               `Ctrl+F`    then `F3` / `Shift+F3` to step through hits
Commands:             `F2`
Quit:                 `Ctrl+Q`  or  `q`

---

## Navigation (caret browsing)

The arrow keys move a free reading caret through the words of the document —
the view follows it, and `Enter` reads aloud from wherever it stands.

| Key | Action |
|---|---|
| `↑` / `↓` | Move the caret one line (view follows) |
| `←` / `→` | Move the caret one word |
| `Page Down` / `Page Up` | Move the caret one screen |
| `Home` / `End` | Caret to beginning / end of document |
| `Enter` (or `Ctrl+Space`) | Read aloud from the caret |
| `j` / `k` | Plain scroll (caret-free, classic behavior) |

While reading aloud, the caret follows the spoken word (setting
`tui_caret_follow_speech`), so `Enter` always resumes "from here"; move it
mid-read and the view yields to you for a few seconds.

---

## Skip Navigation — Fine to Coarse

All skip keys **restart speech automatically** if reading is already in
progress — no need to press Space again after skipping.

| Key | Granularity | Action |
|---|---|---|
| `,` | Sentence | Jump to previous sentence * |
| `.` | Sentence | Jump to next sentence |
| `;` | Sentence | **Replay** current sentence from its beginning |
| `r` | Paragraph | **Replay** current paragraph from its beginning |
| `[` | Paragraph | Jump to previous paragraph |
| `]` | Paragraph | Jump to next paragraph |
| `{` (Shift+[) | Heading | Scroll to previous heading (resume if playing) |
| `}` (Shift+]) | Heading | Scroll to next heading (resume if playing) |
| `<` (Shift+,) | Heading | **Read** from previous heading (always starts TTS) |
| `>` (Shift+.) | Heading | **Read** from next heading (always starts TTS) |

---

## Speech Cursor Mode (`Tab`)

Press `Tab` to enter **Speech Cursor mode** — a dedicated navigation mode
where every movement key also starts TTS reading from the new position.
This lets you browse a document by unit (line, sentence, paragraph, heading,
table) and hear each one immediately without holding a separate play key.

| Key | Action |
|---|---|
| `↑` / `k` | Previous line — read it |
| `↓` / `j` | Next line — read it |
| `,` | Previous sentence — read it |
| `.` | Next sentence — read it |
| `[` / Page Up | Previous paragraph — read it |
| `]` / Page Down | Next paragraph — read it |
| `{` / `<` | Previous heading — read it |
| `}` / `>` | Next heading — read it |
| `t` | Next table — read it |
| `T` | Previous table — read it |
| `r` | Re-read current cursor line |
| `Space` | Pause / resume |
| `Ctrl+X` | Stop speech (cursor stays) |
| `Enter` | Exit SC mode and start continuous reading from cursor |
| `Esc` | Exit SC mode and stop speech |
| `Tab` | Exit SC mode, leave speech running |

The SC cursor is shown as a full-width reverse-video bar.  The title bar
shows `● SC CURSOR` when the mode is active.

## Instant Speech Stop

`Ctrl+X` (or `Esc`) stops all TTS output immediately from any mode.
`Ctrl+Space` reads from the caret, matching the GUI binding.

Note: If you are more than 3 words into the current sentence, `,` replays
the current sentence first; press it again to go to the previous one.

The status bar shows a preview of the sentence you land on (first
5 words) and its number within the document.

All commands are also available in the command palette (`F2`):
`next-sentence`, `prev-sentence`, `replay-sentence`, `replay-paragraph`,
`next-paragraph`, `prev-paragraph`, `next-heading`, `prev-heading`,
`read-next-heading`, `read-prev-heading`.

---

## Speech

| Key | Action |
|---|---|
| `Space` | Play / pause from the current position |
| `Enter` | Read aloud from the caret |
| `Esc` | Stop speech and clear search |
| `+` or `=` | Speed up (+20 wpm) |
| `-` | Slow down (−20 wpm) |

The word currently being spoken is highlighted in the document.

---

## File Operations

| Key | Action |
|---|---|
| `Ctrl+O` | Open a file (Tab completes the path) |
| `Ctrl+S` | Export document as a Markdown file |
| `Ctrl+Q` or `q` | Quit |
| `F9` | Reload the current document |

---

## Search

| Key | Action |
|---|---|
| `Ctrl+F` | Open search box |
| `F3` | Jump to next match |
| `F4` | Jump to previous match |
| `n` / `N` | Next / previous match (when no text box is open) |
| `Esc` | Clear search and stop speech |

---

## Chapter Navigation  (for EPUB, DAISY, and long documents)

| Key | Action |
|---|---|
| `F10` | Previous chapter |
| `F11` | Next chapter |
| `F12` | List all chapters |
| `H` | History back |
| `L` | History forward |

Also available in the command palette: `chapter-next`, `chapter-prev`, `chapter-list`, `chapter-goto`, `history-back`, `history-forward`, `bookmark-set`, `bookmark-goto`, `bookmark-list`.

---

## Command Palette  (press `F2` to open)

Type any command name and press **Enter**.  Press **Tab** to cycle through
completions.  Use `↑` / `↓` to recall previous commands.  Press **Esc** to cancel.

| Command | Description |
|---|---|
| `open` | Open a file |
| `open-url` | Open a URL |
| `export-markdown` | Export document as Markdown |
| `export-braille` | Export as BRF braille file (requires liblouis) |
| `export-audio [fmt]` | Export TTS audio as MP3/OGG/MP4/WAV (requires ffmpeg or pydub) |
| `play` | Start reading |
| `stop` | Stop reading |
| `pause` | Toggle play/pause |
| `speak-line` | Speak the current line |
| `next-paragraph` | Jump to next paragraph (restarts speech) |
| `prev-paragraph` | Jump to previous paragraph (restarts speech) |
| `next-heading` | Jump to next heading (restarts speech) |
| `prev-heading` | Jump to previous heading (restarts speech) |
| `rate-up` | Increase reading speed |
| `rate-down` | Decrease reading speed |
| `volume-up` | Increase volume |
| `volume-down` | Decrease volume |
| `tts-backend` | Switch TTS engine |
| `tts-voice` | Set TTS voice |
| `search` | Search forward |
| `search-backward` | Search backward |
| `goto-line` | Jump to line number |
| `theme [name]` | Switch color theme |
| `line-numbers` | Toggle line numbers |
| `syntax-highlight` | Toggle syntax highlighting |
| `wrap-width` | Set text wrap width |
| `reload` | Reload current document |
| `settings` | Show settings file path |
| `help` | Show this help |
| `about` | Version information |
| `license` | Show license |
| `quit` | Quit star |

---

## Themes  (`F5` to cycle, or `F2` then `theme dark`)

| Name | Description |
|---|---|
| `dark` | Modern dark — blue/cyan/magenta accents (default) |
| `light` | Light background with blue/magenta accents |
| `contrast` | High contrast — bold white on black |
| `phosphor` | Monochrome green phosphor terminal |

---

## Supported File Formats

PDF, DOCX, ODT, EPUB, HTML, DAISY/DTBook, Markdown, plain text,
CSV/TSV (rendered as tables), XLSX (rendered as tables),
LaTeX, Org-mode, Jupyter Notebook, R, R Markdown, Python, Rust, C/C++,
JavaScript, URLs (http/https).

OCR of image-based PDFs and image files (PNG, JPEG, etc.) is supported
when `pytesseract` and `pymupdf` are installed.

---

## Screen Reader & Braille

star works with NVDA, JAWS, Orca, and VoiceOver.  The terminal cursor
is always parked at the start of the minibuffer so screen readers
following the hardware cursor will track the correct position.

Braille display output via BrlTTY is automatic on Linux; on Windows,
NVDA and JAWS drive Braille displays via their built-in support.

BRF (Braille Ready Format) export: open the command palette (`F2`) and
type `export-braille`  (requires `pip install louis`)

---

Press `q` or `Esc` to close this help screen.
"""
)
