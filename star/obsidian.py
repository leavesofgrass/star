"""
Import and export Obsidian vaults.

A vault is a folder of Markdown notes linked by ``[[wikilinks]]``.  star maps
each note to a document (its existing ``.md`` path) plus one whole-note
annotation that acts as the note's node in the knowledge graph; wikilinks become
typed relations between those nodes.  Pure Python and Qt-free.
"""
import re
import time
from pathlib import Path

from .annotations import RELATION_TYPES, _ensure_id

# Embeds (![[...]]) are skipped via the negative lookbehind; only real links and
# Dataview-style inline fields (key:: [[Target]]) become relations.
_WIKILINK = re.compile(r"(?<!!)\[\[([^\]\|#]+)(?:[#\|][^\]]*)?\]\]")
_INLINE_REL = re.compile(
    r"([A-Za-z][\w -]*?)\s*::\s*\[\[([^\]\|#]+)(?:[#\|][^\]]*)?\]\]"
)
_INLINE_TAG = re.compile(r"(?:^|\s)#([A-Za-z0-9_][A-Za-z0-9_/-]*)")
_NODE_TAG = "obsidian-note"


def _norm_rel(key: str) -> "str | None":
    k = (key or "").strip().upper().replace(" ", "_").replace("-", "_")
    return k if k in RELATION_TYPES else None


def _split_frontmatter(text: str):
    """Return ``(meta_dict, body)``; meta is ``{}`` when there is no front matter."""
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    if lines[0].strip() != "---":
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            block = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1 :])
            return _parse_frontmatter(block), body
    return {}, text


def _parse_frontmatter(block: str) -> dict:
    try:
        import yaml  # optional: handles nested/complex front matter

        data = yaml.safe_load(block)
        return data if isinstance(data, dict) else {}
    except Exception:
        pass
    # Minimal fallback: key: value, key: [a, b], and key:\n  - item lists.
    meta: dict = {}
    cur_key = None
    for raw in block.splitlines():
        if not raw.strip():
            continue
        if raw[:1] in (" ", "\t") and cur_key:
            item = raw.strip().lstrip("-").strip()
            if item:
                meta.setdefault(cur_key, [])
                if isinstance(meta[cur_key], list):
                    meta[cur_key].append(item.strip("\"'"))
            continue
        if ":" not in raw:
            continue
        key, _, val = raw.partition(":")
        key = key.strip()
        val = val.strip()
        if not val:
            meta[key] = []
            cur_key = key
        elif val.startswith("[") and val.endswith("]"):
            meta[key] = [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
            cur_key = None
        else:
            meta[key] = val.strip("\"'")
            cur_key = None
    return meta


def _collect_tags(meta: dict, body: str) -> list:
    tags = []
    raw = meta.get("tags") or meta.get("tag") or []
    if isinstance(raw, str):
        raw = [t.strip() for t in re.split(r"[,\s]+", raw) if t.strip()]
    for t in raw:
        t = str(t).lstrip("#").strip()
        if t and t not in tags:
            tags.append(t)
    for m in _INLINE_TAG.finditer(body):
        t = m.group(1)
        if t and t not in tags:
            tags.append(t)
    return tags


def _extract_links(body: str):
    """Return ``[(rel_type_or_None, target_name), ...]`` from a note body."""
    links = []
    consumed = []
    for m in _INLINE_REL.finditer(body):
        rt = _norm_rel(m.group(1))
        if rt:
            links.append((rt, m.group(2).strip()))
            consumed.append((m.start(), m.end()))
    for m in _WIKILINK.finditer(body):
        if any(s <= m.start() < e for s, e in consumed):
            continue
        links.append((None, m.group(1).strip()))
    return links


def _vault_node(anns: list):
    for a in anns:
        if _NODE_TAG in (a.get("tags") or []):
            return a
    return None


def _skip(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    return ".obsidian" in parts or ".trash" in parts


def _first_line(body: str) -> str:
    # A clean one-line summary for the node: link syntax is stripped so the
    # stored note text never re-introduces edges when the vault is exported.
    for line in body.splitlines():
        s = line.strip().lstrip("#").strip()
        if not s:
            continue
        s = _INLINE_REL.sub("", s)
        s = _WIKILINK.sub(lambda m: m.group(1).strip(), s)
        s = s.strip(" -")
        if s:
            return s[:200]
    return ""


def import_vault(settings, vault_dir, link_relation=None, mode="graph") -> dict:
    """Import every note under *vault_dir*.

    *mode* selects what is created:

    - ``"graph"`` (default): each note becomes a **document in the library** *and*
      a knowledge-graph node; wikilinks become relations between nodes (typed when
      written as a Dataview ``rel:: [[target]]`` field, else *link_relation*).
      Re-importing a note that carries a ``star_id`` updates it in place.
    - ``"library"``: each note is only registered as a **document in the
      library / bookshelf** — no graph nodes or relations are created.
    """
    base = Path(vault_dir)
    default_rel = (
        link_relation
        or (settings.get("vault") or {}).get("default_link_relation")
        or "SEE_ALSO"
    )
    store = settings["annotations"]
    library = settings.get("library") or {}
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    build_graph = mode != "library"

    index = {}  # lowercased note name / alias -> doc key
    parsed = []  # (key, node, links) — populated only in graph mode
    note_count = 0

    for path in sorted(base.rglob("*.md")):
        if _skip(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        meta, body = _split_frontmatter(text)
        title = str(meta.get("title") or path.stem)
        key = str(path)
        note_count += 1
        library[key] = {
            "title": title,
            "format": "markdown",
            "added": library.get(key, {}).get("added", ts),
            "last_opened": ts,
        }
        if not build_graph:
            continue

        tags = _collect_tags(meta, body)
        if _NODE_TAG not in tags:
            tags.append(_NODE_TAG)
        anns = store.setdefault(key, [])
        node = _vault_node(anns)
        if node is None:
            node = {"char_pos": 0, "word_idx": 0}
            anns.append(node)
        if meta.get("star_id"):
            node["id"] = str(meta["star_id"])
        _ensure_id(node)
        node["anchor"] = title
        node["note"] = _first_line(body) or title
        node["tags"] = tags
        node["ts"] = node.get("ts") or ts
        node["relations"] = []  # rebuilt from the file so re-import is idempotent

        index.setdefault(path.stem.lower(), key)
        index.setdefault(title.lower(), key)
        aliases = meta.get("aliases") or meta.get("alias") or []
        if isinstance(aliases, str):
            aliases = [aliases]
        for al in aliases:
            index.setdefault(str(al).lower(), key)
        parsed.append((key, node, _extract_links(body)))

    relations = 0
    unresolved = 0
    for src_key, node, links in parsed:
        seen = set()  # (rel_type, target_id) — a link listed twice yields one edge
        for rt, target in links:
            tgt_key = index.get(target.lower())
            if not tgt_key:
                unresolved += 1
                continue
            tgt_node = _vault_node(store.get(tgt_key, []))
            if tgt_node is None:
                unresolved += 1
                continue
            edge = (rt or default_rel, tgt_node["id"])
            if edge in seen:
                continue
            seen.add(edge)
            node["relations"].append(
                {
                    "rel_type": edge[0],
                    "target_doc": tgt_key,
                    "target_id": edge[1],
                    "note": "",
                }
            )
            relations += 1

    settings["library"] = library
    save = getattr(settings, "save", None)
    if callable(save):
        save()
    return {
        "vault": str(base),
        "mode": mode,
        "notes": note_count,
        "relations": relations,
        "unresolved": unresolved,
    }


_SANITIZE = re.compile(r'[<>:"/\\|?*\n\r\t]+')


def _sanitize_filename(name: str) -> str:
    out = _SANITIZE.sub(" ", (name or "note")).strip().rstrip(".")
    return (out or "note")[:120]


def export_vault(settings, out_dir, docs=None) -> dict:
    """Write the knowledge graph to *out_dir* as an Obsidian vault.

    Each graph node becomes a note; relations are written as Dataview inline
    fields under a ``## Links`` section, which both round-trips the relation type
    and shows the edge in Obsidian's graph view.
    """
    from .graph import KnowledgeGraph

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    graph = KnowledgeGraph(settings)
    nodes = graph.nodes
    if docs is not None:
        keep = {d for d in docs}
        nodes = {a: n for a, n in nodes.items() if n["doc"] in keep}

    names = {}
    used = set()
    for aid, node in nodes.items():
        ann = node["annotation"]
        base = _sanitize_filename(ann.get("anchor") or ann.get("note") or aid)
        candidate = base
        n = 2
        while candidate.lower() in used:
            candidate = f"{base} {n}"
            n += 1
        used.add(candidate.lower())
        names[aid] = candidate

    written = 0
    for aid, node in nodes.items():
        ann = node["annotation"]
        tags = [t for t in (ann.get("tags") or []) if t != _NODE_TAG]
        lines = [
            "---",
            f"star_id: {aid}",
            f"title: {ann.get('anchor', '')}",
            f"source: {node['doc']}",
            "tags: [" + ", ".join(tags) + "]",
            "---",
            "",
            ann.get("note", "") or "",
            "",
        ]
        rels = [
            r
            for r in (ann.get("relations") or [])
            if r.get("target_id") in names
        ]
        if rels:
            lines.append("## Links")
            lines.append("")
            for r in rels:
                lines.append(
                    f"- {r.get('rel_type', 'SEE_ALSO')}:: [[{names[r['target_id']]}]]"
                )
            lines.append("")
        (out / f"{names[aid]}.md").write_text("\n".join(lines), encoding="utf-8")
        written += 1

    return {"path": str(out), "notes": written}
