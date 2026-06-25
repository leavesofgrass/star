# 🧩 Architecture & Contributing

How the `star` package is laid out, how it is distributed, and how to contribute.

- [Project layout](#project-layout)
- [Distribution artifacts](#distribution-artifacts)
- [Project docs](#project-docs)
- [Contributing](#contributing)
- [Running the tests](#running-the-tests)

---

## Project layout

`star` is a small, importable Python package under [`star/`](../star/), and it is
the canonical source — there is no single-file `star.py` monolith. Optional
dependencies are imported lazily with graceful fallbacks, so the core package
runs on nothing but the Python standard library; add extras only for the formats
and features you want.

Run it as the installed `star` console command, with `python -m star`, or
straight from a checkout with `python run_star.py`. The same package is the unit
that ships in every distribution form.

| Module | Responsibility |
|---|---|
| `star/_runtime.py` | Foundational shared state: stdlib imports, vendored-tool wiring, optional-dependency detection, app metadata (`__version__`) and config paths. Re-exported wholesale via `from ._runtime import *`. |
| `star/settings.py` | Persistent settings store and defaults. |
| `star/ttstext.py` | TTS text preprocessing (SSML/DECtalk markup, abbreviation/number/date normalization). |
| `star/markup.py` | Lightweight markup → Markdown converters and the Pandoc bridge. |
| `star/documents.py` | Document model and the multi-format loaders (PDF, EPUB, DOCX, …). |
| `star/render.py` · `star/search.py` | Markdown → styled terminal lines; in-document search and the line editor. |
| `star/braille.py` · `star/annotations.py` · `star/citations.py` · `star/transcribe.py` | Braille export, notes, citation management, Whisper transcription. |
| `star/cache.py` · `star/stats.py` · `star/themes.py` | Document cache, reading statistics, color/CSS themes. |
| `star/convert.py` · `star/watch.py` · `star/feeds.py` · `star/translate.py` · `star/vocab.py` · `star/summarize.py` · `star/flashcards.py` · `star/spellcheck.py` | Batch convert, hot-folder watch, feeds, translation, difficult-word overlay, summarization, Anki export, spell check. |
| `star/tts.py` | TTS backends (pyttsx3, eSpeak-NG, DECtalk, Piper, Coqui, Apple `say`, …) and the manager. |
| `star/tui.py` | The curses terminal UI. |
| `star/gui/` | The Qt GUI **package** (see below). |
| `star/app.py` | Command-line entry point (`star.app:main`). |
| `star/diagnostics.py` | `OPTIONAL_DEPENDENCIES` registry powering `star --deps`. |
| `star/__main__.py` · `run_star.py` | `python -m star`, and the source-tree entry script. |

### The `star/gui/` package

The Qt GUI began as a single ~5,600-line `star/gui.py` whose entire contents were
nested inside one `_run_qt_gui()` function (a `StarWindow(QMainWindow)` nested in
that closure). As of 0.1.9 it became a **package**, and `StarWindow` was
subsequently lifted out of the closure and split into focused responsibility
**mixins** — so new GUI work no longer lands in one giant class:

| Module | Responsibility |
|---|---|
| `star/gui/__init__.py` | Re-export shim: exposes `_run_qt_gui` so `from star.gui import _run_qt_gui` (used by `star/app.py`) keeps working unchanged. |
| `star/gui/runner.py` | `_run_qt_gui()` — `QApplication` setup, the crash-log excepthook, and launch. Lazily imports and shows `StarWindow`. |
| `star/gui/main_window.py` | `StarWindow(QMainWindow)` — window assembly (`__init__`, `_setup_ui`, the menu/toolbar builders) — plus the `_RSVPOverlay` widget. |
| `star/gui/mixin_*.py` | `StarWindow`'s methods grouped by responsibility (playback, navigation, export, annotations, citations, graph, …); each is a mixin that `StarWindow` inherits. |
| `star/gui/_qtcompat.py` | Shared PyQt5/PyQt6 enum-compatibility constants. |
| `star/gui/graph_view.py` | The knowledge-graph dock and relation dialogs. |

The Qt-heavy modules (`main_window.py`, the `mixin_*.py` modules, `_qtcompat.py`,
`graph_view.py`) reference Qt at module scope, so they are imported **lazily**
from inside `_run_qt_gui()` — after its `_QT` guard — which keeps `import
star.gui` safe when PyQt is absent (the graceful-degradation invariant). The
PyQt5/PyQt6 enum-compat constants (e.g. `QTextCursor.MoveMode`, `Qt.ConnectionType`)
were captured closure values in the monolith; they now live in `_qtcompat.py` and
are imported by the modules that need them.

---

## Distribution artifacts

| Artifact | How it's built | Status |
|---|---|---|
| **Wheel + sdist** (`star_reader-<version>-py3-none-any.whl`) | `python -m build`; published to PyPI by CI | **Primary, stable — the only automated release artifact** |
| **`star.pyz`** (fat zipapp) | `python build_zipapp.py`; bundles `[all]` extras; platform-specific | Build-it-yourself (not built by CI, not attached to releases) |
| **`star.exe`** (PyInstaller, Windows) | `tools/build-windows.ps1 -AllowDeprecatedExe` | **Deprecated** manual fallback (not built by CI, not attached to releases) |

The automated release builds and publishes **only the wheel + sdist** (to PyPI,
plus attached to the GitHub Release). The `.pyz` and `.exe` are build-it-yourself
artifacts — see [Installation](installation.md#single-file-build-starpyz) and
[`star/BUILD.md`](../star/BUILD.md). The wheel is pure Python (`py3-none-any`) so
one build serves macOS, Linux, and Windows.

---

## Project docs

| Document | What's in it |
|---|---|
| [`README.md`](../README.md) | Introduction & links portal |
| [`docs/installation.md`](installation.md) | Requirements, PyPI / wheel / zipapp install, optional packages, native engines |
| [`docs/usage_guide.md`](usage_guide.md) | Running star, the quick command reference, keyboard map, M-x commands, CLI options |
| [`docs/features.md`](features.md) | The complete feature reference |
| [`docs/configuration.md`](configuration.md) | Every `settings.json` key |
| [`docs/architecture.md`](architecture.md) | This file |
| [`star/CHANGELOG.md`](../star/CHANGELOG.md) | Full record of changes |
| [`star/BUILD.md`](../star/BUILD.md) | Building the wheel (primary) and the deprecated `star.exe` |
| [`docs/RELEASING.md`](RELEASING.md) | Maintainer release runbook |
| [`pyproject.toml`](../pyproject.toml) | Wheel packaging metadata (`star` console command, dependency extras) |

---

## Contributing

Contributions are welcome. Please open an issue before submitting a pull request
for anything beyond small bug fixes.

**Keep dependencies optional.** Every third-party package is imported at runtime
with graceful fallbacks, and that pattern must be maintained — the core `star`
package must keep working with nothing beyond the Python standard library
installed. Contributions go into the relevant module under [`star/`](../star/).

Other guidelines:

- Target Python 3.11 compatibility. Do not use syntax or standard library
  features introduced after 3.11.
- All new keybindings must be documented in
  [`docs/usage_guide.md`](usage_guide.md) (and surfaced in the Qt **Help →
  Keyboard Shortcuts** / TUI `?` cheat sheet).
- New M-x commands must be added to both the command dispatch table and the
  Tab-completion list.
- New file format handlers should degrade gracefully when the required package is
  absent.
- **Register every new optional dependency.** When you add a guarded import
  (`try: import x … except ImportError`), add a matching entry to
  `OPTIONAL_DEPENDENCIES` in [`star/diagnostics.py`](../star/diagnostics.py) so it
  shows up in `star --deps`. The test suite enforces this.
- Follow the existing code style — keep lines ≤ 100 characters and write
  docstrings for all public functions.
- When you touch user-facing docs, refresh the copies bundled with the package
  (`star/README.md`, `star/LICENSE`, `star/CHANGELOG.md`) so F1 Help reflects the
  latest text.
- This project is licensed under the GPL v3. By submitting a pull request you
  agree your contribution will be released under the same license.

---

## Running the tests

The suite lives in [`tests/`](../tests/) and runs on `pytest`:

```bash
pip install -e ".[test]"   # installs pytest
pytest                     # run everything
pytest tests/test_dependencies.py -v   # just the dependency harness
```

The tests are written to pass with **none** of the optional packages installed —
checks that need a given package `skip` when it is absent rather than failing.
Two suites are worth knowing about:

- **`tests/test_dependencies.py`** — the dependency harness. It treats
  `star.diagnostics.OPTIONAL_DEPENDENCIES` as the source of truth and enforces
  *completeness* (every import guard is registered) and *consistency* (anything
  reported as available really does import).
- **`tests/test_features.py`** — unit tests for the study/reading features,
  including each one's graceful-degradation path.

---

See also: [Usage Guide](usage_guide.md) · [Features](features.md) ·
[Installation](installation.md) · [Configuration](configuration.md).
