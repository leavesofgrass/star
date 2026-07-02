"""
Interactive knowledge graph viewer (Qt dock widget).
Renders SVG output from KnowledgeGraph.to_svg() in a QGraphicsView.
"""
from .._runtime import *  # noqa: F401,F403
from ..annotations import RELATION_TYPES, _ensure_id, add_relation
from ..i18n import tr

# QtSvgWidgets/QtSvg are a separate wheel component that is not always present
# (e.g. a minimal PyQt6 install); when absent the dock falls back to showing the
# DOT source as text, so the viewer still works without it.
try:
    from PyQt6.QtWidgets import QGraphicsScene, QGraphicsView
    from PyQt6.QtCore import QByteArray

    try:
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtSvgWidgets import QGraphicsSvgItem

        _HAS_SVG = True
    except ImportError:
        _HAS_SVG = False
except ImportError:  # PyQt5 layout
    from PyQt5.QtWidgets import QGraphicsScene, QGraphicsView  # type: ignore
    from PyQt5.QtCore import QByteArray  # type: ignore

    try:
        from PyQt5.QtSvg import QGraphicsSvgItem, QSvgRenderer  # type: ignore

        _HAS_SVG = True
    except ImportError:
        _HAS_SVG = False


class RelationDialog(QDialog):
    def __init__(self, parent, settings, src_doc, src_id, src_label):
        super().__init__(parent)
        self._settings = settings
        self._src_doc = src_doc
        self._src_id = src_id
        self.setWindowTitle("Add Relation")
        self.resize(520, 480)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"From:  {src_label}"))

        self._type = QComboBox()
        self._type.addItems(RELATION_TYPES)
        self._type.setAccessibleName(tr("Relation type"))
        layout.addWidget(QLabel("Relation type:"))
        layout.addWidget(self._type)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter target annotations…")
        self._search.setAccessibleName(tr("Filter target annotations"))
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._populate)
        layout.addWidget(QLabel("Target annotation:"))
        layout.addWidget(self._search)

        self._targets = QListWidget()
        self._targets.setAccessibleName(tr("Target annotation"))
        layout.addWidget(self._targets)

        self._note = QLineEdit()
        self._note.setPlaceholderText("Optional edge label…")
        self._note.setAccessibleName(tr("Edge label (optional)"))
        layout.addWidget(QLabel("Note (optional):"))
        layout.addWidget(self._note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Add")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._candidates = []
        self._populate()
        self._search.setFocus()

    def _populate(self):
        query = (self._search.text() or "").strip().lower()
        self._targets.clear()
        self._candidates = []
        store = self._settings["annotations"] or {}
        for doc, items in store.items():
            for ann in items or []:
                aid = _ensure_id(ann)
                if doc == self._src_doc and aid == self._src_id:
                    continue
                anchor = (ann.get("anchor") or ann.get("note") or "").strip()
                label = f"{Path(doc).name} — {anchor[:60]}"
                if query and query not in label.lower():
                    continue
                item = QListWidgetItem(label)
                self._targets.addItem(item)
                self._candidates.append((doc, aid))

    def _accept(self):
        row = self._targets.currentRow()
        if row < 0 or row >= len(self._candidates):
            QMessageBox.information(self, "Add Relation", "Select a target annotation.")
            return
        tgt_doc, tgt_id = self._candidates[row]
        add_relation(
            self._settings,
            self._src_doc,
            self._src_id,
            self._type.currentText(),
            tgt_doc,
            tgt_id,
            self._note.text().strip(),
        )
        self.accept()


class GraphViewDock(QDockWidget):
    node_activated = pyqtSignal(str, str)  # (doc_path, ann_id)

    def __init__(self, window):
        super().__init__("Knowledge Graph", window)
        self._window = window
        self.setObjectName("graph_dock")
        self.setAccessibleName(tr("Knowledge graph panel"))
        self._graph = None
        self._node_index = []  # parallel to the node list rows: (doc, ann_id)

        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        bar = QToolBar()
        bar.addAction(QAction("Rebuild", self, triggered=lambda: self.rebuild()))
        bar.addAction(QAction("Filter", self, triggered=self._toggle_filter))
        bar.addAction(QAction("Export SVG", self, triggered=lambda: self._export("svg")))
        bar.addAction(QAction("Export UML", self, triggered=lambda: self._export("puml")))
        bar.addAction(QAction("Export DOT", self, triggered=lambda: self._export("dot")))
        bar.addAction(QAction("Export JSON", self, triggered=lambda: self._export("json")))
        outer.addWidget(bar)

        self._filter_box = QWidget()
        fl = QHBoxLayout(self._filter_box)
        fl.setContentsMargins(0, 0, 0, 0)
        self._filter_text = QLineEdit()
        self._filter_text.setPlaceholderText("Search text / #tag…")
        self._filter_text.setAccessibleName(tr("Filter graph nodes"))
        self._filter_text.returnPressed.connect(self.rebuild)
        fl.addWidget(self._filter_text)
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self.rebuild)
        fl.addWidget(apply_btn)
        self._filter_box.setVisible(False)
        outer.addWidget(self._filter_box)

        if _HAS_SVG:
            self._scene = QGraphicsScene(self)
            self._view = QGraphicsView(self._scene)
            outer.addWidget(self._view, 1)
        else:
            self._view = None
            self._dot_text = QTextEdit()
            self._dot_text.setReadOnly(True)
            outer.addWidget(self._dot_text, 1)

        outer.addWidget(QLabel("Nodes (double-click to open):"))
        self._node_list = QListWidget()
        self._node_list.setAccessibleName(tr("Graph nodes"))
        self._node_list.setAccessibleDescription(
            tr("Annotations in the knowledge graph. "
               "Double-click or press Enter to open a node.")
        )
        self._node_list.itemClicked.connect(self._on_select)
        self._node_list.itemDoubleClicked.connect(self._on_activate)
        # itemActivated fires on Enter too, so a node is reachable by keyboard
        # (itemDoubleClicked alone is mouse-only).
        self._node_list.itemActivated.connect(self._on_activate)
        outer.addWidget(self._node_list, 1)

        self._info = QLabel("No relations yet. Add relations via Graph > Add Relation…")
        self._info.setWordWrap(True)
        outer.addWidget(self._info)

        self.setWidget(panel)

    def _toggle_filter(self):
        self._filter_box.setVisible(not self._filter_box.isVisible())

    def rebuild(self):
        from ..graph import KnowledgeGraph

        graph = KnowledgeGraph(self._window.settings)
        query = (self._filter_text.text() or "").strip()
        if query:
            ids = set(graph.search(query_str=query))
            graph = graph.subgraph(ids)
        self._graph = graph
        self._render()

    def _render(self):
        graph = self._graph
        if graph is None:
            return
        if _HAS_SVG and self._view is not None:
            svg = graph.to_svg(
                layout=self._window.settings.get("graph", {}).get("default_layout", "spring")
            )
            renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
            self._scene.clear()
            item = QGraphicsSvgItem()
            item.setSharedRenderer(renderer)
            self._scene.addItem(item)
            self._view.setSceneRect(item.boundingRect())
        else:
            self._dot_text.setPlainText(graph.to_dot())

        self._node_list.clear()
        self._node_index = []
        for aid, node in graph.nodes.items():
            ann = node["annotation"]
            anchor = (ann.get("anchor") or ann.get("note") or "").strip()
            self._node_list.addItem(
                QListWidgetItem(f"{Path(node['doc']).name} — {anchor[:60]}")
            )
            self._node_index.append((node["doc"], aid))
        n_edges = len(graph.edges)
        if not graph.nodes:
            self._info.setText(
                "No relations yet. Add relations via Graph > Add Relation…"
            )
        else:
            self._info.setText(f"{len(graph.nodes)} nodes · {n_edges} relations")

    def _on_select(self, item):
        row = self._node_list.row(item)
        if not (0 <= row < len(self._node_index)):
            return
        doc, aid = self._node_index[row]
        node = self._graph.nodes.get(aid) if self._graph else None
        if not node:
            return
        ann = node["annotation"]
        rels = len(ann.get("relations") or [])
        self._info.setText(
            f"{(ann.get('anchor') or '').strip()[:80]}\n"
            f"{(ann.get('note') or '').strip()[:120]}\n"
            f"{rels} outgoing relation(s) · {Path(doc).name}"
        )

    def _on_activate(self, item):
        row = self._node_list.row(item)
        if 0 <= row < len(self._node_index):
            doc, aid = self._node_index[row]
            self.node_activated.emit(doc, aid)

    def _export(self, fmt):
        if self._graph is None:
            self.rebuild()
        from .. import export_graph

        gdir = self._window.settings.get("graph", {}).get("last_export_dir", "")
        filt = {
            "svg": "SVG (*.svg)",
            "puml": "PlantUML (*.puml)",
            "dot": "DOT (*.dot *.gv)",
            "json": "JSON (*.json)",
        }[fmt]
        path, _ = QFileDialog.getSaveFileName(self, "Export Graph", gdir, filt)
        if not path:
            return
        writer = {
            "svg": export_graph.export_svg,
            "puml": export_graph.export_plantuml,
            "dot": export_graph.export_dot,
            "json": export_graph.export_json,
        }[fmt]
        writer(self._graph, path)
        graph_cfg = dict(self._window.settings.get("graph", {}))
        graph_cfg["last_export_dir"] = str(Path(path).parent)
        self._window.settings.set("graph", graph_cfg)
        self._info.setText(f"Exported: {path}")
