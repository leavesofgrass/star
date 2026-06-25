"""GraphMixin — knowledge-graph and Obsidian-vault methods for StarWindow.

Extracted from main_window.py.  These methods operate on StarWindow instance
state (the open document, annotations, the graph dock) and call other
StarWindow methods via ``self``; GraphMixin holds no state of its own and is
mixed in via ``class StarWindow(GraphMixin, QMainWindow)``.  Every heavy
dependency (graph_view, ..ner, ..export_graph, ..obsidian, graphviz, plantuml)
is imported lazily inside the methods.

IMPORT SAFETY: references Qt at module scope — import lazily only (imported by
main_window.py, itself imported lazily by runner.py after the _QT guard).
"""
from .._runtime import *  # noqa: F401,F403
from ._qtcompat import _RIGHT_DOCK, _USER_ROLE


class GraphMixin:
    # ── Knowledge graph ────────────────────────────────────────────────
    def _graph_get_dock(self):
        dock = getattr(self, "_graph_dock", None)
        if dock is None:
            from .graph_view import GraphViewDock

            dock = GraphViewDock(self)
            dock.node_activated.connect(self._graph_node_activated)
            dock.setVisible(False)
            self.addDockWidget(_RIGHT_DOCK, dock)
            self._graph_dock = dock
        return dock

    def _graph_toggle(self) -> None:
        dock = self._graph_get_dock()
        show = not dock.isVisible()
        if show:
            dock.rebuild()
        dock.setVisible(show)

    def _graph_rebuild(self) -> None:
        self._graph_get_dock().rebuild()
        self.statusBar().showMessage("Knowledge graph rebuilt")

    def _graph_node_activated(self, doc_path: str, ann_id: str) -> None:
        from ..annotations import get_annotation_by_id

        if doc_path and self.doc and doc_path != (self.doc.path or ""):
            try:
                self._open_path(doc_path)
            except Exception:
                self.statusBar().showMessage(f"Could not open {doc_path}")
                return
        ann = get_annotation_by_id(self.settings, doc_path, ann_id)
        if not ann:
            return
        char_pos = int(ann.get("char_pos", 0) or 0)
        if char_pos <= 0:
            wi = int(ann.get("word_idx", 0) or 0)
            if self._qt_word_map and 0 <= wi < len(self._qt_word_map):
                char_pos = self._qt_word_map[wi]
        doc_len = self.editor.document().characterCount()
        char_pos = max(0, min(char_pos, doc_len - 1))
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(char_pos)
        self.editor.setTextCursor(cursor)
        self.editor.ensureCursorVisible()

    def _graph_selected_ann(self):
        """Return (doc_key, ann_id) for the note selected in the Notes dock."""
        from ..annotations import _ensure_id

        lst = getattr(self, "_annot_list", None)
        item = lst.currentItem() if lst is not None else None
        if item is None:
            return None
        key = self._annot_key()
        if not key:
            return None
        char_pos = int(item.data(_USER_ROLE + 1) or -(10**9))
        tip = item.toolTip() or ""
        for ann in (self.settings["annotations"] or {}).get(key, []) or []:
            if int(ann.get("char_pos", -(10**9))) == char_pos and (
                not tip
                or str(ann.get("note", "")) == tip
                or str(ann.get("anchor", "")) == tip
            ):
                return key, _ensure_id(ann)
        return None

    def _graph_add_relation(self) -> None:
        from ..annotations import get_annotation_by_id

        sel = self._graph_selected_ann()
        if sel is None:
            QMessageBox.information(
                self,
                "Add Relation",
                "Select a note in the Notes panel first "
                "(View → Toggle Notes Panel).",
            )
            return
        key, sid = sel
        src = get_annotation_by_id(self.settings, key, sid)
        label = (src.get("anchor") or src.get("note") or sid) if src else sid
        from .graph_view import RelationDialog

        dlg = RelationDialog(self, self.settings, key, sid, str(label)[:80])
        if dlg.exec():
            if getattr(self, "_graph_dock", None) is not None:
                self._graph_dock.rebuild()
            self.statusBar().showMessage("Relation added")

    def _graph_edit_relations(self) -> None:
        from ..annotations import get_annotation_by_id, remove_relation

        sel = self._graph_selected_ann()
        if sel is None:
            QMessageBox.information(
                self, "Edit Relations", "Select a note in the Notes panel first."
            )
            return
        key, sid = sel
        src = get_annotation_by_id(self.settings, key, sid)
        rels = (src.get("relations") if src else None) or []
        if not rels:
            QMessageBox.information(
                self, "Edit Relations", "This note has no relations yet."
            )
            return
        labels = [
            f"{i}: {r.get('rel_type', '?')} → {Path(r.get('target_doc', '')).name}"
            f" [{r.get('target_id', '')}]"
            for i, r in enumerate(rels)
        ]
        choice, ok = QInputDialog.getItem(
            self, "Edit Relations", "Delete which relation?", labels, 0, False
        )
        if ok and choice:
            remove_relation(self.settings, key, sid, labels.index(choice))
            if getattr(self, "_graph_dock", None) is not None:
                self._graph_dock.rebuild()
            self.statusBar().showMessage("Relation deleted")

    def _graph_extract_concepts(self) -> None:
        if not self.doc:
            QMessageBox.information(self, "Extract Concepts", "Open a document first.")
            return
        from ..ner import extract_concepts

        domain = (self.settings.get("graph", {}) or {}).get("concept_domain", "general")
        concepts = extract_concepts(self.doc.plain_text or "", domain)
        if not concepts:
            QMessageBox.information(
                self, "Extract Concepts", "No concepts found in this document."
            )
            return
        seen = []
        for c in concepts:
            line = f"{c['label']:<12} {c['text']}"
            if line not in seen:
                seen.append(line)
        self._graph_text_dialog(
            f"Extracted Concepts ({domain})", "\n".join(seen[:500])
        )

    def _graph_auto_suggest(self) -> None:
        if not self.doc:
            QMessageBox.information(self, "Auto-Suggest", "Open a document first.")
            return
        from ..ner import suggest_auto_tags

        domain = (self.settings.get("graph", {}) or {}).get("concept_domain", "general")
        anns = (self.settings["annotations"] or {}).get(self._annot_key(), []) or []
        pairs = suggest_auto_tags(self.doc.plain_text or "", anns, domain)
        if not pairs:
            QMessageBox.information(
                self,
                "Auto-Suggest Relations",
                "No concepts matched existing notes. Add a few notes first, "
                "then try again.",
            )
            return
        lines = [
            f"{text}  →  {len(ids)} matching note(s)" for text, ids in pairs
        ]
        self._graph_text_dialog("Auto-Suggested Relations", "\n".join(lines))

    def _graph_text_dialog(self, title: str, text: str) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(560, 480)
        lay = QVBoxLayout(dlg)
        view = QTextEdit()
        view.setReadOnly(True)
        view.setPlainText(text)
        lay.addWidget(view)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        box.rejected.connect(dlg.reject)
        box.accepted.connect(dlg.accept)
        lay.addWidget(box)
        dlg.exec()

    def _graph_export(self, fmt: str) -> None:
        from .. import export_graph

        graph = export_graph.export_annotations_as_graph(self.settings)
        gdir = (self.settings.get("graph", {}) or {}).get("last_export_dir", "")
        spec = {
            "svg": ("SVG (*.svg)", export_graph.export_svg),
            "puml": ("PlantUML (*.puml)", export_graph.export_plantuml),
            "dot": ("DOT (*.dot *.gv)", export_graph.export_dot),
            "json": ("JSON (*.json)", export_graph.export_json),
        }[fmt]
        path, _ = QFileDialog.getSaveFileName(self, "Export Graph", gdir, spec[0])
        if not path:
            return
        spec[1](graph, path)
        cfg = dict(self.settings.get("graph", {}) or {})
        cfg["last_export_dir"] = str(Path(path).parent)
        self.settings.set("graph", cfg)
        self.statusBar().showMessage(f"Exported graph: {path}")

    def _graph_export_svg(self) -> None:
        self._graph_export("svg")

    def _graph_export_plantuml(self) -> None:
        self._graph_export("puml")

    def _graph_export_dot(self) -> None:
        self._graph_export("dot")

    def _graph_export_json(self) -> None:
        self._graph_export("json")

    def _graph_open_svg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open SVG", "", "SVG (*.svg)"
        )
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Open SVG", str(exc))
            return
        self._graph_show_svg(text, Path(path).name)

    def _graph_open_dot(self) -> None:
        self._graph_open_rendered("DOT (*.dot *.gv)", "dot")

    def _graph_open_plantuml(self) -> None:
        self._graph_open_rendered("PlantUML (*.puml *.plantuml)", "plantuml")

    def _graph_open_rendered(self, filt: str, kind: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", filt)
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Open File", str(exc))
            return
        svg = None
        try:
            if kind == "dot":
                import graphviz

                svg = graphviz.Source(text).pipe(format="svg").decode("utf-8")
            else:
                import plantuml  # noqa: F401

                # plantuml renders via a server/binary; if it cannot, fall to text.
                svg = None
        except Exception:
            svg = None
        if svg:
            self._graph_show_svg(svg, Path(path).name)
        else:
            self._graph_text_dialog(Path(path).name, text)

    def _graph_show_svg(self, svg_text: str, title: str) -> None:
        try:
            from .graph_view import _HAS_SVG

            if not _HAS_SVG:
                raise ImportError
            from PyQt6.QtCore import QByteArray
            from PyQt6.QtSvg import QSvgRenderer
            from PyQt6.QtSvgWidgets import QGraphicsSvgItem
            from PyQt6.QtWidgets import QGraphicsScene, QGraphicsView
        except ImportError:
            try:
                from .graph_view import _HAS_SVG

                if not _HAS_SVG:
                    raise ImportError
                from PyQt5.QtCore import QByteArray  # type: ignore
                from PyQt5.QtSvg import (  # type: ignore
                    QGraphicsSvgItem,
                    QSvgRenderer,
                )
                from PyQt5.QtWidgets import (  # type: ignore
                    QGraphicsScene,
                    QGraphicsView,
                )
            except ImportError:
                self._graph_text_dialog(title, svg_text)
                return
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(720, 600)
        lay = QVBoxLayout(dlg)
        scene = QGraphicsScene(dlg)
        view = QGraphicsView(scene)
        renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
        item = QGraphicsSvgItem()
        item.setSharedRenderer(renderer)
        scene.addItem(item)
        view.setSceneRect(item.boundingRect())
        lay.addWidget(view)
        dlg.exec()

    # ── Obsidian vault import / export ─────────────────────────────────
    def _obsidian_import(self) -> None:
        from .. import obsidian

        start = (self.settings.get("vault", {}) or {}).get("last_vault_dir", "")
        vault = QFileDialog.getExistingDirectory(
            self, "Import Obsidian Vault (folder)", start
        )
        if not vault:
            return
        choices = ["Knowledge graph (notes + links)", "Library only (documents)"]
        choice, ok = QInputDialog.getItem(
            self, "Import Obsidian Vault", "Import as:", choices, 0, False
        )
        if not ok:
            return
        mode = "library" if choice.startswith("Library") else "graph"
        try:
            report = obsidian.import_vault(self.settings, vault, mode=mode)
        except Exception as exc:
            QMessageBox.warning(self, "Import Obsidian Vault", str(exc))
            return
        cfg = dict(self.settings.get("vault", {}) or {})
        cfg["last_vault_dir"] = vault
        self.settings.set("vault", cfg)
        if hasattr(self, "_qt_build_annotations"):
            self._qt_build_annotations()
        if getattr(self, "_graph_dock", None) is not None:
            self._graph_dock.rebuild()
        if mode == "library":
            self.statusBar().showMessage(
                f"Imported {report['notes']} notes into the library"
            )
        else:
            self.statusBar().showMessage(
                f"Imported {report['notes']} notes, {report['relations']} relations"
                + (
                    f" ({report['unresolved']} links unresolved)"
                    if report["unresolved"]
                    else ""
                )
            )

    def _obsidian_export(self) -> None:
        from .. import obsidian

        start = (self.settings.get("vault", {}) or {}).get("last_vault_dir", "")
        out = QFileDialog.getExistingDirectory(
            self, "Export Obsidian Vault (target folder)", start
        )
        if not out:
            return
        try:
            report = obsidian.export_vault(self.settings, out)
        except Exception as exc:
            QMessageBox.warning(self, "Export Obsidian Vault", str(exc))
            return
        self.statusBar().showMessage(
            f"Exported {report['notes']} notes to {report['path']}"
        )

