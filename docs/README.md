# 📚 star Documentation

The complete documentation for **star — Speaking Terminal Access Reader**. For
the project introduction and quick install, see the root
[`README.md`](../README.md).

| Document | What's in it |
|---|---|
| [Installation](installation.md) | Requirements, install from PyPI / wheel / zipapp, optional packages, native engines, platform notes |
| [Usage Guide](usage_guide.md) | Running star, the **quick command reference** (feature → menu · shortcut · TUI command), full keyboard map, M-x commands, screen layout, CLI options |
| [Features](features.md) | The complete feature reference — TTS backends, highlighting, notes, citations, export, study aids, themes, and more |
| [Knowledge Graph](knowledge-graph.md) | Typed relations between annotations, concept extraction, the interactive graph view, and SVG/PlantUML/DOT/JSON export |
| [Obsidian Vaults](obsidian.md) | Import an Obsidian vault into the knowledge graph and export the graph back out as linked Markdown notes |
| [Karaoke Video Export](video-export.md) | Produce a sentence-synchronized karaoke MP4 video from any document |
| [Configuration](configuration.md) | Every `settings.json` key and its default |
| [Architecture & Contributing](architecture.md) | Package layout, the `star/gui/` package, distribution artifacts, contributing, and the test suite |
| [Developing Plugins](plugins-developing.md) | Writing entry-point plugins that add a TTS voice engine, a new document format, or an export target — the plugin API contract, packaging as a pip distribution, and a copy-me template |
| [Performance & Large Documents](PERFORMANCE.md) | Runtime hot paths, word-map and pagination optimizations for large documents, and how to reproduce the measurements |
| [Keyboard & Focus Audit](KEYBOARD_AUDIT.md) | Every Qt-GUI shortcut, the tab/focus order through window/docks/dialogs, and WCAG 2.1.1 / 2.4.3 conformance notes |

Maintainer-only:

| Document | What's in it |
|---|---|
| [Releasing](RELEASING.md) | The release runbook (tagging, CI, PyPI publishing) |
| [Packaging & Distribution](PACKAGING.md) | Every way star is packaged and shipped — wheel/sdist, the `.pyz`, GPG signatures, and the optional native Windows/macOS/Linux installer jobs |

Also bundled with the package: [`star/CHANGELOG.md`](../star/CHANGELOG.md) (full
change history) and [`star/BUILD.md`](../star/BUILD.md) (building the wheel and the
self-contained Windows `star.exe`).
