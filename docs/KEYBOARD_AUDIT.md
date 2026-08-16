# Keyboard & Focus Accessibility Audit — Qt GUI

star is an accessibility-first reader, so *everything must be operable from the
keyboard alone* (WCAG 2.1.1 Keyboard, Level A) with a **logical, visible focus
order** (WCAG 2.4.3 Focus Order, Level A). This document enumerates every
keyboard shortcut, traces the tab/focus path through the main window, docks, and
dialogs, and flags any control that is reachable only by mouse.

Scope: the Qt GUI (`star/gui/`). The curses TUI has its own key model — the
arrow keys move a reading caret, `Enter` (or `Ctrl+Space`) reads aloud from
it, and `Ctrl+X` / `Esc` stop — documented under **Caret navigation (TUI)**
in [usage_guide.md](usage_guide.md). Verified against v0.1.29.

Legend: **[A]** = WCAG 2.1.1 Keyboard · **[F]** = WCAG 2.4.3 Focus Order ·
✅ pass · ⚠ recommendation (out of the accessibility-work file scope) ·
🔊 also announced to screen readers via a live region (`star/gui/a11y.py`).

---

## 1. Global shortcuts (menu-owned QActions)

Every command carries **exactly one** shortcut, owned by its menu `QAction`
(the icon toolbar deliberately carries none — see §3), so Qt never reports an
"ambiguous shortcut" and each binding fires regardless of which widget has
focus (Qt `WindowShortcut` context). All are remappable via **Help ▸ Customize
Shortcuts…** (`Ctrl+Alt+Q`); the registry keys on the English label so overrides
survive a UI-language switch. Source: `star/gui/mixin_chrome.py`.

### File

| Shortcut | Command |
|---|---|
| `Ctrl+N` | New — blank document, opens in edit mode |
| `Ctrl+O` | Open… |
| `Ctrl+Shift+M` | Open Feed… |
| `Ctrl+Shift+O` | Open URL… |
| `Ctrl+Shift+L` | Open Folder as Library… |
| `Ctrl+Shift+B` | Library / Bookshelf… |
| `Ctrl+Shift+C` | Batch Convert… |
| `Ctrl+Shift+W` | Watch Folder… (toggle) |
| `F9` | Publish… — styled EPUB/DOCX/HTML with template, metadata, cover, TOC |
| `Ctrl+Q` | Quit |
| *(no shortcut)* | Edit Document Metadata…, Import Obsidian Vault…, Open Archive… |

### File ▸ Export

| Shortcut | Command |
|---|---|
| `Ctrl+Alt+M` | Export as Markdown… |
| `Ctrl+Alt+P` | Export as PDF… |
| `Ctrl+Alt+B` | Export as Braille (BRF)… |
| `Ctrl+Alt+A` | Export as Audio… |
| `Ctrl+Alt+U` | Export Subtitles (SRT / VTT)… |
| `Ctrl+Alt+H` | Anki Flashcards… |
| *(no shortcut)* | Obsidian Vault…, Video (MP4)… (menu-only; `Ctrl+Alt+V` is Tools ▸ Dictate Note), Export Audiobook (M4B)…, plugin exporters (HTML/EPUB/DOCX/third-party) |

### Speech 🔊

| Shortcut | Command | Notes |
|---|---|---|
| `Space` | Play / Pause | 🔊 announces "Playing" / "Paused" |
| `Escape` | Stop | 🔊 announces "Stopped" |
| `Ctrl+Space` | Play from Cursor | 🔊 announces "Playing" (pairs with caret browsing) |
| `Ctrl+=` | Faster (+20 wpm) | |
| `Ctrl+-` | Slower (−20 wpm) | |
| `Ctrl+Shift+G` | Choose TTS Engine… | |
| `Ctrl+Shift+V` | Choose Voice… | |
| `F4` | Voice Manager… | |
| `Tab` | Speech Cursor Mode | see §2 — Tab is captured by the editor event filter |
| `Ctrl+Alt+Y` | Toggle SSML Prosody | hidden accelerator — the setting lives in Preferences ▸ Voice |
| `Ctrl+Shift+I` | Pronunciation Lexicon… | |
| *(bare `Ctrl` tap)* | Play / Pause | JAWS habit; opt-out `qt_ctrl_pause` |

### Navigate

| Shortcut | Command |
|---|---|
| `Alt+.` / `Alt+,` | Next / Previous Sentence |
| `Alt+;` | Replay Sentence |
| `Ctrl+P` / `Ctrl+Shift+P` | Next / Previous Paragraph |
| `Ctrl+R` | Replay Paragraph |
| `Ctrl+H` / `Ctrl+Shift+H` | Next / Previous Heading (read aloud) |
| `Ctrl+T` / `Ctrl+Shift+T` | Next / Previous Table |
| `Alt+Left` / `Alt+Right` | History Back / Forward |

### Edit

| Shortcut | Command |
|---|---|
| `Ctrl+F` | Find… (see §4) |
| `Ctrl+C` | Copy |
| `Ctrl+E` | Toggle Edit Mode |
| `Ctrl+S` | Save |
| `Ctrl+Z` | Undo (editor-scoped) |
| `Ctrl+Y` | Redo (editor-scoped) |
| *(no shortcut)* | Check Spelling — menu-only; F7 is View ▸ Caret Browsing (an ambiguous binding would fire neither) |
| `Ctrl+Shift+K` / `Ctrl+Shift+J` / `Ctrl+Shift+Y` | Save / Load / Delete Profile… (moved here from the retired Profiles menu) |
| `Ctrl+,` | Preferences… (six tabs: Reading / Reading Aids / Voice / Display / Fonts / General) |

### Format (Markdown authoring — edit mode)

| Shortcut | Command |
|---|---|
| `Ctrl+B` | Bold — wraps `**text**` |
| `Ctrl+I` | Italic — wraps `*text*` |
| `Ctrl+U` | Underline — wraps `<u>text</u>` |
| `Ctrl+K` | Insert Link — `[text](url)` |
| *(no shortcut)* | Inline Code, Heading, Bullet List, Numbered List, Block Quote, Horizontal Rule |

These commands no-op with a hint outside edit mode and mirror the edit-mode
Markdown toolbar (`_build_edit_toolbar`). Undo/Redo also appear on this menu but
are menu-only here — their shortcut owners are the editor-scoped `Ctrl+Z` /
`Ctrl+Y` listed under Edit.

### Annotate (highlights / notes / bookmarks — one menu since 0.1.27)

| Shortcut | Command |
|---|---|
| `Ctrl+Shift+1…5` | Highlight Yellow / Green / Cyan / Pink / Orange |
| `Ctrl+Shift+0` | Clear All Highlights |
| `Ctrl+Shift+A` | Add Note at Cursor… |
| `Ctrl+Shift+E` | Edit Selected Note… |
| `Ctrl+Shift+D` | Delete Selected Note |
| `Ctrl+Shift+N` | Toggle Notes Panel |
| `Ctrl+Alt+N` | Export Notes… |
| `Ctrl+M` | Add Bookmark (moved from Ctrl+B, which is now Bold) |

### Study (review + citations) / Graph

| Shortcut | Command |
|---|---|
| `Ctrl+Shift+F5` | Review Due Cards… (spaced repetition) |
| *(no shortcut)* | Sync with Anki (AnkiConnect)… |
| `Ctrl+Alt+I` | Import Citations… |
| *(no shortcut)* | Export Citations… — menu-only; Ctrl+Alt+E is View ▸ Reading Aids ▸ RSVP Mode |
| `Ctrl+Alt+C` | Add Citation… |
| `Ctrl+Alt+D` | Add Citation by DOI… |
| `Ctrl+Alt+R` | Insert Citation at Cursor… |
| `Ctrl+Alt+G` | Manage / Browse Citations… |
| `Ctrl+Shift+Q` | Show Graph View |
| *(no shortcut)* | Rebuild Graph, Add/Edit Relation, Extract Concepts, Auto-Suggest, all graph exports/imports |

### View 🔊

| Shortcut | Command | Notes |
|---|---|---|
| `Ctrl+\` | Toggle Contents Panel | |
| `F5` | Next Theme | 🔊 announces "Theme: {name}" |
| `Ctrl+Alt+T` | Choose Theme… | 🔊 announces the chosen theme |
| `Ctrl+Shift+R` | Reload CSS Themes | hidden accelerator — the buttons live in Preferences ▸ Display |
| `Ctrl+Shift+F` | Open Themes Folder | hidden accelerator — the buttons live in Preferences ▸ Display |
| `F7` | Caret Browsing (checkable) | see §2 |
| `Ctrl+Alt+F` | Change Font… |
| `Ctrl+L` | Reading Level |
| `Ctrl+Shift+Z` | Live HTML Preview (edit mode) |

### View ▸ Reading Aids (accessibility)

| Shortcut | Command |
|---|---|
| `Ctrl+Alt+W` | Text Spacing… (WCAG 1.4.12) — hidden accelerator; the spacing controls live in Preferences ▸ Fonts |
| `Ctrl+Alt+X` | Dyslexia-Friendly Font (checkable) |
| `Ctrl+Alt+J` | Bionic Reading (checkable) |
| `Ctrl+Alt+L` | Current-Line Highlight (checkable) |
| `Ctrl+Alt+O` | Highlight Difficult Words (checkable) |
| `Ctrl+D` | Define Word… |
| `Ctrl+Alt+E` | RSVP Mode (checkable) |

The Karaoke Highlight…, Reading Ruler…, and RSVP Position… settings dialogs
left this menu when their settings were centralized in **Edit ▸ Preferences…
(Ctrl+,)**; the live-tuning dialogs remain reachable from the Command Palette
(F2) as **Tune Karaoke Highlight… / Tune Reading Ruler… / Tune RSVP
Position…**. `Ctrl+Alt+K` is now bound to **Tools ▸ Voice Typing** in the Qt GUI
(dictate speech into the document at the cursor — see the Tools table).

### Tools / Help

| Shortcut | Command |
|---|---|
| `Ctrl+Alt+S` | Transcribe Audio File… |
| `Ctrl+Alt+V` | Dictate Note (record)… — files a separate annotation |
| `Ctrl+Alt+K` | Voice Typing — insert dictated speech into the document at the cursor |
| `Ctrl+Alt+Z` | Toggle Transcript Timestamps — hidden accelerator; the setting lives in Preferences ▸ Voice |
| `Ctrl+Shift+U` | Summarize Document… |
| `Ctrl+Shift+X` | Translate Document… |
| `Ctrl+Shift+S` | Reading Statistics… |
| `Ctrl+Shift+Delete` | Clear Document Cache |
| `F2` | Command Palette… |
| `F3` | Keyboard Shortcuts… |
| `Ctrl+Alt+Q` | Customize Shortcuts… |
| `Shift+F1` | Guided Tour |
| `F1` | Open README (Help) |
| `Ctrl+F1` | About star |

---

## 2. The document view (`self.editor`) — special key handling

The reading area is a **read-only `QTextEdit` with caret browsing** (`F7`,
`qt_caret_browsing`, default on). Caret browsing sets the
`TextSelectableByKeyboard` interaction flag so the arrow keys move a visible
caret and `Shift+arrow` selects — without it a read-only `QTextEdit` is
mouse-selectable only, so **caret browsing is the load-bearing keyboard-access
affordance for the reading pane** (`mixin_display._apply_caret_mode`). ✅ [A]

An event filter (`mixin_navigation.eventFilter`) intercepts a few keys on the
editor:

| Key | Behaviour |
|---|---|
| `Tab` | Enter/exit **Speech Cursor** mode (does *not* move focus out of the editor) |
| bare `Ctrl` tap | Play / Pause (JAWS habit; `qt_ctrl_pause`) |
| In SC mode: `↑`/`↓` | Previous / next block, read aloud |
| In SC mode: `Enter` | Exit SC mode and read on |
| In SC mode: `Esc` | Exit SC mode, stop |

⚠ **`Tab` is consumed by the editor** to toggle Speech Cursor, so it does *not*
advance focus while the editor holds focus. This is an intentional
reading-ergonomics trade-off, but it means the primary WCAG 2.4.3 tab traversal
starts from the menu bar / toolbar / docks rather than the editor. It is **not**
a keyboard trap [A]: `Esc` and every global menu shortcut still work, the menu
bar is reachable with `F10` / `Alt`, and focus can leave the editor by clicking
or by any dock-focusing shortcut. Documented here so the behaviour is a known,
deliberate exception rather than a silent gap.

---

## 3. Toolbar (icon-only)

The controls toolbar (`mixin_chrome._build_toolbar`) is icon-only. Each button
is a `QAction` whose **label is retained as the accessible name** and whose
tooltip repeats the equivalent keyboard shortcut, so a screen reader announces
every button and no functionality is toolbar-exclusive — every toolbar action
has a menu twin with a real shortcut. ✅ [A] Toolbar buttons are in the tab ring
(`QToolButton` is focusable) and precede the central widget in focus order. ✅ [F]

Toolbar buttons intentionally carry **no** shortcut (§1) so each binding is owned
by one QAction. Test `test_key_toolbar_actions_have_text` asserts every toolbar
action exposes non-empty accessible text.

---

## 4. Find bar (`Ctrl+F`, `mixin_find.py`)

Created lazily under the editor. Focus order within the bar: input → count
label (read-only) → Previous → Next → Match case → Replace ▾ → Close; the
Replace ▾ toggle reveals a replace row (Replace input → Replace → Replace All)
beneath the bar in edit mode. ✅ [F]

| Key (while the find input has focus) | Behaviour |
|---|---|
| `Enter` | Next match |
| `Shift+Enter` | Previous match |
| `F3` / `Shift+F3` | Next / Previous match |
| `Escape` | Close the bar, return focus to the editor |

🔊 The live "N of M" / "No matches" count is announced on every change (against
the find input, which holds focus) so a screen-reader user hears their search
progress without leaving the field, in addition to the visible status-bar
message. ✅ [A] All buttons carry accessible names/descriptions; the input has an
accessible name (screen readers do not read placeholder text reliably).

---

## 5. Docks

### Table of Contents (`Ctrl+\`)
`_toc_list` (`QListWidget`): `itemActivated` (Enter) scrolls to the heading;
`itemDoubleClicked` reads from it. ✅ [A] — Enter and double-click both work.
Accessible name + description set. Dock is toggleable by shortcut.

### Notes (`Ctrl+Shift+N`)
Panel = filter `QLineEdit` → notes `QListWidget` → Add / Edit / Delete / Export
buttons. Focus order top-to-bottom matches visual order. ✅ [F]
`_annot_list` pairs `itemActivated` (Enter, scroll) with `itemDoubleClicked`
(read). ✅ [A] Filter input and list both carry accessible names/descriptions.

### Knowledge Graph (`Ctrl+Shift+Q`)
`graph_view.py` node list connects **both** `itemActivated` and
`itemDoubleClicked` to the open handler, so a node is reachable by Enter as well
as double-click. ✅ [A] (This is the canonical pattern the two former gaps in §7
now follow.)

---

## 6. Dialogs

All modal dialogs carry a window title (announced on open —
`test_dependency_chooser_dialog`, `test_*` in `tests/test_accessibility.py`) and
standard `QDialogButtonBox` OK/Cancel reachable by `Tab` + `Enter`/`Esc`. ✅ [A][F]
The optional-feature chooser's checkboxes expose their detail text as an
accessible **description** (the gray sub-label is visual-only and not reliably
announced). List-bearing dialogs (Command Palette, Bookmarks, Presets, Library)
use `itemActivated` so Enter activates the selection. ✅ [A]

**Preferences (`Ctrl+,`)** opens **maximized** (since 0.1.27), so its six tabs
never scroll. `Tab` walks the tab strip and then every control in each tab in
build order (labels precede their fields via `QFormLayout`, so focus order
matches reading order); `Ctrl+PageUp`/`Ctrl+PageDown` switch tabs. Every
control announces *which* setting it is: checkboxes and buttons carry their
own text, and combo boxes / spin boxes / text fields — which show no text of
their own — are given an explicit accessible **name** derived from their form
label by `PreferencesDialog._ensure_accessible_names()` (guarded by
`tests/test_prefs_a11y.py`, which fails if any control would be announced as a
bare widget). Color swatches announce their purpose (e.g. "RSVP word color")
rather than their hex value. ✅ [A][F]

---

## 7. Mouse-only gaps found

| Location | Issue | Status |
|---|---|---|
| `mixin_doctools.py` (archive / library picker) | list wired only `itemDoubleClicked`; no `itemActivated`, so Enter on a row did nothing | ✅ Fixed — `itemActivated` now connects to the same open handler (`mixin_doctools.py:398`, "Enter opens (keyboard parity)"). |
| `mixin_voices.py` (Voice Manager) | list wired only `itemDoubleClicked`; the **Set as Current** button was keyboard-reachable, but Enter on a row did nothing | ✅ Fixed — `itemActivated` now connects to Set as Current (`mixin_voices.py:298`, "Enter sets (keyboard parity)"). |

Both were ergonomic parity gaps, not functional keyboard-access failures: in
each case the primary action was reachable via a focusable button. Each list now
pairs an `itemActivated` connection with `itemDoubleClicked`, mirroring
`graph_view.py`, so Enter on a row works everywhere.

No control was found that is **exclusively** operable by mouse with no keyboard
path at all. star therefore meets WCAG 2.1.1 (Level A) across the audited
surface; no mouse-only gaps remain.

---

## 8. Live-region announcements (Wave 2b)

`star/gui/a11y.py` `announce(widget, text)` sends
`QAccessible.updateAccessibility(QAccessibleEvent(widget, Announcement))` so a
screen reader speaks a state change **without moving focus** (the Qt analogue of
an ARIA live region). It is a no-op when the accessibility bridge is inactive
(e.g. the offscreen QPA used in tests) and never raises. Each announcement pairs
with the existing status-bar message. Announcement sites:

- **Playback** (`mixin_playback.py`): started → "Playing", paused → "Paused",
  stopped → "Stopped".
- **Document load** (`mixin_document.py`): "Loaded {title}".
- **Theme change** (`mixin_display.py`): "Theme: {name}" (Next Theme + Choose
  Theme).
- **Find** (`mixin_find.py`): "N of M" / "No matches" on every result change.

All announcement text flows through `tr()` and is translated in every catalog.

---

## 9. OS colour-scheme following (Wave 2b)

On startup `mixin_display._maybe_follow_os_theme` queries
`QStyleHints.colorScheme()` (Qt 6.5+; `themes.detect_os_color_scheme`) and, when
`qt_follow_os_theme` is on and the user has not **explicitly** chosen a theme
(`qt_theme_explicit`), adopts a matching built-in theme (Dark → `galaxy`,
Light → `galaxy-light`, high-contrast → `high-contrast`). An explicit pick via
Next Theme or Choose Theme sets `qt_theme_explicit` so auto-detection never
overrides it. On older Qt / PyQt5 / no running app, detection returns "unknown"
and the saved theme is left untouched. This keeps the default appearance in step
with the desktop's dark/light/high-contrast preference without ever fighting a
deliberate user choice.
