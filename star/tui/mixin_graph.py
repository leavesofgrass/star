"""Knowledge-graph commands and Obsidian vault import/export.

Methods of StarApp, split out of the former monolithic star/tui.py.
Mixed into StarApp in app.py; calls other groups via ``self``.
"""
from .._runtime import *  # noqa: F401,F403


class GraphMixin:

    # ── Knowledge graph (M-x graph-*) ─────────────────────────────────────

    def _graph_doc_key(self) -> str:
        if not self.doc:
            return ""
        return self.doc.path or self.doc.title or ""

    def _graph_show(self) -> None:
        from ..graph import KnowledgeGraph

        g = KnowledgeGraph(self.settings)
        self._show_text_pager("Knowledge Graph (DOT)", "```\n" + g.to_dot() + "```")

    def _graph_rebuild(self) -> None:
        from ..graph import KnowledgeGraph

        g = KnowledgeGraph(self.settings)
        self.notify(f"Knowledge graph: {len(g.nodes)} nodes, {len(g.edges)} relations")

    def _graph_extract_concepts(self) -> None:
        if not self.doc:
            self.notify("No document loaded.", error=True)
            return
        from ..ner import extract_concepts

        domain = (self.settings.get("graph", {}) or {}).get("concept_domain", "general")
        concepts = extract_concepts(self.doc.plain_text or "", domain)
        if not concepts:
            self.notify("No concepts found.")
            return
        seen = []
        for c in concepts:
            line = f"- **{c['label']}** {c['text']}"
            if line not in seen:
                seen.append(line)
        self._show_text_pager(f"Concepts ({domain})", "\n".join(seen[:500]))

    def _graph_suggest(self) -> None:
        if not self.doc:
            self.notify("No document loaded.", error=True)
            return
        from ..ner import suggest_auto_tags

        domain = (self.settings.get("graph", {}) or {}).get("concept_domain", "general")
        anns = (self.settings.get("annotations", {}) or {}).get(
            self._graph_doc_key(), []
        ) or []
        pairs = suggest_auto_tags(self.doc.plain_text or "", anns, domain)
        if not pairs:
            self.notify("No concepts matched existing notes.")
            return
        lines = [f"- {t} → {len(ids)} note(s)" for t, ids in pairs]
        self._show_text_pager("Auto-Suggested Relations", "\n".join(lines))

    def _graph_export(self, fmt: str) -> None:
        from .. import export_graph

        g = export_graph.export_annotations_as_graph(self.settings)
        base = Path(self.doc.path) if (self.doc and self.doc.path) else Path("star")
        out = base.parent / (base.stem + ".graph." + fmt)
        writer = {
            "svg": export_graph.export_svg,
            "dot": export_graph.export_dot,
            "puml": export_graph.export_plantuml,
            "json": export_graph.export_json,
        }[fmt]
        try:
            writer(g, str(out))
            self.notify(f"Wrote {out}")
        except OSError as exc:
            self.notify(str(exc), error=True)

    def _graph_add_relation(self) -> None:
        from ..annotations import RELATION_TYPES, _ensure_id, add_relation

        key = self._graph_doc_key()
        src_items = (self.settings.get("annotations", {}) or {}).get(key, []) or []
        if not src_items:
            self.notify("This document has no notes to link from.", error=True)
            return

        def after_src(s):
            try:
                si = int(s)
            except ValueError:
                self.notify("Invalid index", error=True)
                return
            if not (0 <= si < len(src_items)):
                self.notify("Index out of range", error=True)
                return
            sid = _ensure_id(src_items[si])

            def after_type(rt):
                rt = rt.strip().upper()
                if rt not in RELATION_TYPES:
                    self.notify("Unknown relation type", error=True)
                    return

                def after_tdoc(tdoc):
                    tdoc = tdoc.strip()
                    titems = (self.settings.get("annotations", {}) or {}).get(
                        tdoc, []
                    ) or []
                    if not titems:
                        self.notify("No notes in target document", error=True)
                        return

                    def after_tidx(ti):
                        try:
                            tii = int(ti)
                        except ValueError:
                            self.notify("Invalid index", error=True)
                            return
                        if not (0 <= tii < len(titems)):
                            self.notify("Index out of range", error=True)
                            return
                        tid = _ensure_id(titems[tii])

                        def after_note(note):
                            add_relation(
                                self.settings, key, sid, rt, tdoc, tid, note.strip()
                            )
                            self.notify(f"Relation added: {rt}")

                        self._enter_minibuffer(
                            "Edge note (optional): ", on_commit=after_note, completions=[]
                        )

                    self._enter_minibuffer(
                        f"Target note # (0..{len(titems) - 1}): ",
                        on_commit=after_tidx,
                        completions=[],
                    )

                self._enter_minibuffer(
                    "Target doc path: ",
                    on_commit=after_tdoc,
                    completions=list((self.settings.get("annotations", {}) or {}).keys()),
                )

            self._enter_minibuffer(
                "Relation type: ", on_commit=after_type, completions=list(RELATION_TYPES)
            )

        self._enter_minibuffer(
            f"Source note # (0..{len(src_items) - 1}): ",
            on_commit=after_src,
            completions=[],
        )

    # ── Obsidian vault import / export (M-x import-vault / export-vault) ───

    def _obsidian_import(self) -> None:
        def after_path(path):
            path = path.strip()
            if not path:
                return

            def after_mode(m):
                m = (m.strip().lower() or "graph")
                if m not in ("graph", "library"):
                    m = "graph"
                from .. import obsidian

                try:
                    r = obsidian.import_vault(self.settings, path, mode=m)
                except Exception as exc:  # noqa: BLE001
                    self.notify(str(exc), error=True)
                    return
                if m == "library":
                    self.notify(f"Imported {r['notes']} notes into the library")
                else:
                    self.notify(
                        f"Imported {r['notes']} notes, {r['relations']} relations"
                        + (f" ({r['unresolved']} unresolved)" if r["unresolved"] else "")
                    )

            self._enter_minibuffer(
                "Import as (graph/library): ",
                initial="graph",
                on_commit=after_mode,
                completions=["graph", "library"],
            )

        self._enter_minibuffer(
            "Import vault folder: ", on_commit=after_path, completions=[]
        )

    def _obsidian_export(self) -> None:
        def do(path):
            path = path.strip()
            if not path:
                return
            from .. import obsidian

            try:
                r = obsidian.export_vault(self.settings, path)
            except Exception as exc:  # noqa: BLE001
                self.notify(str(exc), error=True)
                return
            self.notify(f"Exported {r['notes']} notes to {r['path']}")

        self._enter_minibuffer("Export vault to folder: ", on_commit=do, completions=[])
