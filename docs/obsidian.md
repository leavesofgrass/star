# 🔗 Obsidian Vaults

star can **import** an [Obsidian](https://obsidian.md) vault — a folder of
Markdown notes linked by `[[wikilinks]]` — into its [knowledge
graph](knowledge-graph.md), and **export** the graph back out as a vault.

- [How notes map into star](#how-notes-map-into-star)
- [Importing a vault](#importing-a-vault)
- [Exporting a vault](#exporting-a-vault)
- [Typed relations & round-trip](#typed-relations--round-trip)
- [What is and isn't preserved](#what-is-and-isnt-preserved)
- [Optional dependencies](#optional-dependencies)
- [Commands](#commands)

---

## How notes map into star

| Obsidian | star |
|---|---|
| A `.md` note | A **document** at its existing path **and** one whole-note **annotation** that is the note's node in the knowledge graph |
| Note title / filename | The node's `anchor`; a stable `star_id` is kept in the note's front matter |
| `#tags` and front-matter `tags:` | The node's tags |
| `[[Target]]` wikilink | A **relation** to the target note's node |
| Dataview `supports:: [[Target]]` | A **typed** relation (key matched against the [relation types](knowledge-graph.md#annotation-relations)) |

This is the **knowledge-graph** import mode; in **library-only** mode each note
is registered as a document with no graph node or relations (see
[Importing a vault](#importing-a-vault)).

Every imported note's node is tagged **`#obsidian-note`**, so you can filter the
Notes panel (type `#obsidian-note`) to see exactly the nodes that came from a
vault, separate from your own in-document notes.

---

## Importing a vault

- **Qt GUI:** **File ▸ Import Obsidian Vault…**, pick the vault folder, then
  choose how to import it.
- **TUI:** `M-x import-vault`, enter the folder path, then the mode
  (`graph` or `library`).

You choose one of two **import modes**:

| Mode | What it creates |
|---|---|
| **Knowledge graph** (notes + links) | Each note becomes a **library document** *and* a knowledge-graph node, and every `[[wikilink]]` becomes a relation. This is the default. |
| **Library only** (documents) | Each note is registered only as a **document in the library / bookshelf** — no graph nodes or relations. Use this when you just want to read/browse the vault's notes in star, not graph them. |

Either way star walks the folder recursively, skipping `.obsidian/` and
`.trash/`. In graph mode it also parses front matter and tags and resolves
wikilinks; the status bar reports how many notes and relations were created and
how many links could not be resolved (a link whose target note doesn't exist).
In library mode it reports how many notes were added to the library.

Open imported documents from **File ▸ Library / Bookshelf…** (`Ctrl+Shift+B`).

**Re-import is safe.** Notes that already carry a `star_id` (e.g. a vault star
previously exported) are updated in place rather than duplicated, and each note's
relations are rebuilt from the file, so importing the same vault twice does not
pile up duplicate edges.

---

## Exporting a vault

- **Qt GUI:** **File ▸ Export ▸ Obsidian Vault…**, then pick a target folder.
- **TUI:** `M-x export-vault`, then enter the target folder.

star writes one Markdown note per graph node into the folder: YAML front matter
(`star_id`, `title`, `source`, `tags`), the node's text, and a `## Links` section
listing its relations. The result opens directly in Obsidian, and the links show
up in Obsidian's graph view.

---

## Typed relations & round-trip

Obsidian wikilinks are untyped, but star's relations are typed. To bridge this,
relations are exported as **Dataview inline fields**:

```markdown
## Links

- CONFLICTS_WITH:: [[Casey]]
- SUPPORTS:: [[Planned Parenthood v. Casey]]
```

`REL_TYPE:: [[Target]]` is both a real wikilink (so Obsidian's graph shows the
edge) **and** a typed field star reads back on import — so a star → vault → star
round-trip preserves relation types. A plain `[[Target]]` with no field imports
as the default type (`SEE_ALSO`, configurable via the `vault.default_link_relation`
setting).

---

## What is and isn't preserved

**Preserved:** notes, `[[wikilinks]]` (and typed Dataview link fields), `#tags`
and front-matter tags, note titles/aliases (for link resolution), and stable ids.

**Not preserved:** embeds (`![[…]]`), attachments, Canvas files, and the
`.obsidian/` configuration. Round-trip is lossy for anything outside notes,
links, tags, and front matter.

---

## Optional dependencies

Import works with **no extra packages** — a built-in parser reads simple
`key: value` / list front matter. Installing **`pyyaml`** (`pip install pyyaml`)
enables richer/nested YAML front matter. `star --deps` shows whether it is
present.

---

## Commands

| Action | Qt | TUI |
|---|---|---|
| Import a vault | File ▸ Import Obsidian Vault… | `M-x import-vault` |
| Export a vault | File ▸ Export ▸ Obsidian Vault… | `M-x export-vault` |

Both are also in the command palette (`F2`).

---

See also: [Knowledge Graph](knowledge-graph.md) · [Features](features.md) ·
[Configuration](configuration.md).
