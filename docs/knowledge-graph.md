# 🕸️ Knowledge Graph

star can link your annotations across documents into a typed **knowledge graph** —
turning a pile of per-document notes into a navigable web of how ideas relate.

- [Concept](#concept)
- [Annotation relations](#annotation-relations)
- [Concept extraction](#concept-extraction)
- [Graph view](#graph-view)
- [Export](#export)
- [Viewing external formats](#viewing-external-formats)
- [Optional dependencies](#optional-dependencies)
- [Keyboard shortcuts & palette commands](#keyboard-shortcuts--palette-commands)

---

## Concept

Ordinary annotations answer "what did I note *here*?" The knowledge graph answers
"how does this note relate to *that* one, in another paper?" Each annotation
becomes a **node**; you draw typed, directed **edges** between them
(`CONFLICTS_WITH`, `SUPPORTS`, `CITES`, …). For a researcher juggling dozens of
sources, this surfaces contradictions, lines of support, and citation chains that
are invisible in a flat notes list — and exports to formats other graph tools can
consume.

Nodes and edges live inside your existing `settings.json` (each annotation gains
a stable `id` and an optional `relations` list), so the graph is just a view over
notes you already have. Nothing breaks if you never use it: annotations without
ids or relations work exactly as before.

---

## Annotation relations

A **relation** is a directed edge from one annotation to another, with a type and
an optional free-text label.

### Adding a relation

- **Qt GUI:** open the **Notes** panel (`Ctrl+Shift+N`), select the source note,
  then **Graph ▸ Add Relation…**. Pick a relation type, search/select the target
  annotation (any document with notes), add an optional edge note, and click
  **Add**.
- **TUI:** `M-x graph-add-relation` — you'll be prompted for the source note
  index, relation type (Tab-completes from the type list), target document path,
  target note index, and an optional note.

### Relation types

| Type | Meaning |
|---|---|
| `CONFLICTS_WITH` | The two notes are in tension / disagree |
| `SUPPORTS` | The source backs up the target |
| `IS_EXAMPLE_OF` | The source is an instance of the target's concept |
| `CITES` | The source cites the target |
| `CONTRADICTS` | A stronger, explicit contradiction |
| `DEFINES` | The source defines the target's term |
| `EXTENDS` | The source builds on / extends the target |
| `SEE_ALSO` | A loose "related reading" link |
| `PRECEDES` | The source comes before the target (sequence/chronology) |
| `FOLLOWS` | The source comes after the target |

### Deleting a relation

- **Qt GUI:** select the source note, **Graph ▸ Edit Relations…**, choose the
  edge to delete.
- **TUI:** edit `settings.json` directly, or remove and re-add via
  `graph-add-relation` (a dedicated delete prompt is GUI-only for now).

---

## Concept extraction

star can scan the open document's text and pull out candidate **concepts**
(people, organizations, laws, places, works) to seed relations.

- **Run it:** **Graph ▸ Extract Concepts…** (Qt) or `M-x graph-extract-concepts`
  (TUI). Results open in a read-only list.
- **Domain** (`graph.concept_domain` setting): `general`, `legal`, `medical`, or
  `sociological`. The domain tunes the **regex fallback** — e.g. `legal` also
  catches `Section 12`, `Article 5`, `Act of 1990`, `§ 3`; `medical` catches
  drug-name patterns (all-caps abbreviations, `-mab`/`-ine`/`-ase` suffixes).
  When spaCy or NLTK is installed, their NER is used instead and the domain only
  affects the fallback.
- **Auto-suggest:** **Graph ▸ Auto-Suggest Relations…** / `M-x
  graph-suggest-relations` cross-references extracted concepts against your
  existing annotations and lists concepts that already appear in your notes —
  candidates for new relation edges you can then add.

---

## Graph view

- **Open it:** **Graph ▸ Show Graph View** (`Ctrl+Shift+Q`) or `M-x graph-show`
  (the TUI shows the DOT source in a scrollable pager).
- **Layout:** a colour-coded, force-directed rendering (edges coloured by
  relation type). With `graphviz` installed, its layout engine is used; otherwise
  a built-in pure-Python spring layout renders the SVG.
- **Filter:** click **Filter** in the dock toolbar to reveal a search box —
  type text (or `#tag`) and **Apply** to restrict the graph to matching nodes.
- **Navigate:** the dock lists every node; **double-click a node** to jump to that
  annotation in its document (opening the document first if needed).
- **Empty graph:** with no relations yet, the dock shows
  *"No relations yet. Add relations via Graph ▸ Add Relation…"*.

---

## Export

**Graph ▸ Export Graph ▸ …** (Qt) or `M-x graph-export-*` (TUI) writes the graph
to disk. The TUI writes next to the current document as `<name>.graph.<ext>`.

| Format | Command | Consumed by |
|---|---|---|
| **SVG** | Export as SVG… / `graph-export-svg` | Any browser, Inkscape, image viewers |
| **PlantUML** | Export as PlantUML… / `graph-export-plantuml` | [PlantUML](https://plantuml.com) (online server or the `plantuml` jar/CLI) |
| **DOT** | Export as DOT… / `graph-export-dot` | Graphviz `dot` command (`dot -Tpng graph.dot -o graph.png`) |
| **JSON** | Export as JSON… / `graph-export-json` | Gephi, Cytoscape, or any custom tooling (a `{nodes, edges}` document) |

The SVG export works with **no external packages** thanks to the built-in
layout; `graphviz`, when present, produces a more polished SVG/DOT layout.

---

## Viewing external formats

star can also open graph files produced elsewhere:

- **Graph ▸ View Formats ▸ Open SVG File…** — renders an `.svg` in a viewer
  (falls back to showing the raw markup if Qt's SVG component is unavailable).
- **Open DOT File…** — renders via `graphviz` if installed, otherwise shows the
  raw DOT text.
- **Open PlantUML File…** — shows the `.puml` text (and renders it when a
  `plantuml` renderer is available).

---

## Optional dependencies

Everything here works with **zero** optional packages — concept extraction falls
back to a regex heuristic, and SVG export uses the built-in spring layout. The
following improve it:

| Package | Improves |
|---|---|
| `spacy` (+ a model, e.g. `en_core_web_sm`) | Best-quality concept extraction (real NER) |
| `nltk` | NER fallback when spaCy is absent |
| `graphviz` (+ the Graphviz binary) | Higher-quality graph layout and SVG/DOT rendering |
| `plantuml` | Render PlantUML exports to SVG |

Run `star --deps` to see which are installed. Install hints are listed there and
in [Installation](installation.md).

---

## Keyboard shortcuts & palette commands

| Action | Qt menu | Shortcut | TUI palette |
|---|---|---|---|
| Show graph view | Graph ▸ Show Graph View | `Ctrl+Shift+Q` | `M-x graph-show` |
| Rebuild graph | Graph ▸ Rebuild Graph | — | `M-x graph-rebuild` |
| Add relation | Graph ▸ Add Relation… | — | `M-x graph-add-relation` |
| Edit relations | Graph ▸ Edit Relations… | — | — |
| Extract concepts | Graph ▸ Extract Concepts… | — | `M-x graph-extract-concepts` |
| Auto-suggest relations | Graph ▸ Auto-Suggest Relations… | — | `M-x graph-suggest-relations` |
| Export as SVG | Graph ▸ Export Graph ▸ Export as SVG… | — | `M-x graph-export-svg` |
| Export as PlantUML | Graph ▸ Export Graph ▸ Export as PlantUML… | — | `M-x graph-export-plantuml` |
| Export as DOT | Graph ▸ Export Graph ▸ Export as DOT… | — | `M-x graph-export-dot` |
| Export as JSON | Graph ▸ Export Graph ▸ Export as JSON… | — | `M-x graph-export-json` |
| Open SVG file | Graph ▸ View Formats ▸ Open SVG File… | — | `M-x graph` (palette) |
| Open DOT file | Graph ▸ View Formats ▸ Open DOT File… | — | — |
| Open PlantUML file | Graph ▸ View Formats ▸ Open PlantUML File… | — | — |

> **Shortcut note:** the spec's `Ctrl+Shift+G` / `Ctrl+Shift+R` were already
> bound (Choose TTS Engine / Reload CSS Themes), so Show Graph View uses
> `Ctrl+Shift+Q`; the other Graph actions are reachable via the menu and the
> command palette (`F2`). The whole Graph menu opens with `Alt+G`.

Every Graph action is also in the **command palette** (`F2`) — type "graph" to
filter.

---

See also: [Obsidian Vaults](obsidian.md) · [Usage Guide](usage_guide.md) ·
[Features](features.md) · [Configuration](configuration.md) ·
[Architecture](architecture.md).
