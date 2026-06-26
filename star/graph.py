"""
Knowledge graph built from cross-annotation relations.
Nodes are annotations; edges are typed relations (CONFLICTS_WITH, etc.).

Pure Python and Qt-free, so it is usable from both the GUI and the TUI. The SVG
renderer works with no external packages (a built-in Fruchterman-Reingold spring
layout); graphviz, when installed, is used for nicer layouts.
"""
import html
import math

from .annotations import RELATION_TYPES, _ensure_id

# One fixed colour per relation type, indexed by position in RELATION_TYPES, so
# edges are colour-coded consistently across SVG/DOT regardless of which types
# are present in a given graph.
_PALETTE = [
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990",
]


def _rel_color(rel_type: str) -> str:
    try:
        return _PALETTE[RELATION_TYPES.index(rel_type) % len(_PALETTE)]
    except ValueError:
        return "#888888"


def _node_label(ann: dict) -> str:
    text = (ann.get("anchor") or ann.get("note") or "").strip().replace("\n", " ")
    return text or ann.get("id", "?")


class KnowledgeGraph:
    def __init__(self, settings=None):
        self.settings = settings
        self.nodes: dict = {}
        self.edges: list = []
        if settings is not None:
            self.rebuild()

    def rebuild(self) -> None:
        self.nodes = {}
        self.edges = []
        anns = (self.settings["annotations"] if self.settings is not None else {}) or {}
        for doc, items in anns.items():
            for ann in items or []:
                aid = _ensure_id(ann)
                self.nodes[aid] = {"doc": doc, "annotation": ann}
        for doc, items in anns.items():
            for ann in items or []:
                src = ann["id"]
                for rel in ann.get("relations") or []:
                    self.edges.append(
                        {
                            "src": src,
                            "dst": rel.get("target_id", ""),
                            "rel_type": rel.get("rel_type", "SEE_ALSO"),
                            "note": rel.get("note", "") or "",
                        }
                    )

    # ── queries ──────────────────────────────────────────────────────────────

    def neighbors(self, ann_id: str):
        return [
            (e, self.nodes.get(e["dst"])) for e in self.edges if e["src"] == ann_id
        ]

    def reverse_neighbors(self, ann_id: str):
        return [
            (e, self.nodes.get(e["src"])) for e in self.edges if e["dst"] == ann_id
        ]

    def subgraph(self, ann_ids) -> "KnowledgeGraph":
        keep = set(ann_ids)
        sub = KnowledgeGraph(None)
        sub.nodes = {k: v for k, v in self.nodes.items() if k in keep}
        sub.edges = [
            e for e in self.edges if e["src"] in keep and e["dst"] in keep
        ]
        return sub

    def connected_component(self, ann_id: str):
        if ann_id not in self.nodes:
            return set()
        adj: dict = {}
        for e in self.edges:
            adj.setdefault(e["src"], set()).add(e["dst"])
            adj.setdefault(e["dst"], set()).add(e["src"])
        seen = {ann_id}
        queue = [ann_id]
        while queue:
            cur = queue.pop()
            for nxt in adj.get(cur, ()):
                if nxt in self.nodes and nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return seen

    def search(self, query_str=None, rel_types=None, docs=None, tags=None):
        q = (query_str or "").strip().lower()
        rel_types = set(rel_types) if rel_types else None
        docs = set(docs) if docs else None
        tags = {t.lower() for t in tags} if tags else None

        typed_nodes = None
        if rel_types is not None:
            typed_nodes = set()
            for e in self.edges:
                if e["rel_type"] in rel_types:
                    typed_nodes.add(e["src"])
                    typed_nodes.add(e["dst"])

        out = []
        for aid, node in self.nodes.items():
            ann = node["annotation"]
            if q:
                hay = f"{ann.get('anchor', '')} {ann.get('note', '')}".lower()
                if q not in hay:
                    continue
            if docs is not None and node["doc"] not in docs:
                continue
            if tags is not None:
                ntags = {str(t).lower() for t in ann.get("tags", []) or []}
                if not (ntags & tags):
                    continue
            if typed_nodes is not None and aid not in typed_nodes:
                continue
            out.append(aid)
        return out

    # ── serialization ─────────────────────────────────────────────────────────

    def to_json(self) -> dict:
        return {
            "nodes": [
                {
                    "id": aid,
                    "doc": node["doc"],
                    "anchor": node["annotation"].get("anchor", ""),
                    "note": node["annotation"].get("note", ""),
                    "tags": node["annotation"].get("tags", []) or [],
                }
                for aid, node in self.nodes.items()
            ],
            "edges": list(self.edges),
        }

    def to_dot(self) -> str:
        lines = ["digraph star_knowledge {", '  rankdir=LR;', '  node [shape=box, style=rounded];']
        for aid, node in self.nodes.items():
            label = _node_label(node["annotation"])[:40].replace('"', "'")
            lines.append(f'  "{aid}" [label="{label}"];')
        for e in self.edges:
            if e["dst"] not in self.nodes:
                continue
            edge_label = (e["rel_type"] + (f": {e['note']}" if e["note"] else "")).replace('"', "'")
            lines.append(
                f'  "{e["src"]}" -> "{e["dst"]}" '
                f'[label="{edge_label}", color="{_rel_color(e["rel_type"])}"];'
            )
        lines.append("}")
        return "\n".join(lines) + "\n"

    def to_plantuml(self) -> str:
        lines = ["@startuml", "left to right direction"]
        for aid, node in self.nodes.items():
            label = _node_label(node["annotation"])[:40].replace('"', "'")
            lines.append(f'object "{label}" as {aid}')
        for e in self.edges:
            if e["dst"] not in self.nodes:
                continue
            tail = f" : {e['note']}" if e["note"] else ""
            lines.append(f'{e["src"]} --> {e["dst"]} : {e["rel_type"]}{tail}')
        lines.append("@enduml")
        return "\n".join(lines) + "\n"

    def to_svg(self, layout="auto") -> str:
        if layout in ("auto", "dot", "neato", "fdp"):
            try:
                import graphviz  # optional: nicer layout when present

                engine = layout if layout in ("dot", "neato", "fdp") else "dot"
                src = graphviz.Source(self.to_dot(), engine=engine)
                return src.pipe(format="svg").decode("utf-8")
            except Exception:
                pass
        return self._render_svg(self._layout_spring())

    # ── pure-Python layout + SVG ───────────────────────────────────────────────

    def _layout_spring(self, width=900, height=640, iterations=300):
        ids = list(self.nodes.keys())
        n = len(ids)
        if n == 0:
            return {}
        # Fruchterman-Reingold: k is the ideal edge length; the 0.75 factor keeps
        # disconnected nodes from drifting to the far edges of a sparse graph.
        area = width * height
        k = 0.75 * math.sqrt(area / n)
        pos = {}
        radius = min(width, height) / 3.0
        for i, aid in enumerate(ids):
            angle = 2 * math.pi * i / n
            pos[aid] = [
                width / 2 + radius * math.cos(angle),
                height / 2 + radius * math.sin(angle),
            ]
        edge_pairs = [
            (e["src"], e["dst"])
            for e in self.edges
            if e["src"] in self.nodes and e["dst"] in self.nodes
        ]
        temp = width / 8.0
        cool = temp / (iterations + 1)
        for _ in range(iterations):
            disp = {aid: [0.0, 0.0] for aid in ids}
            for i in range(n):
                ai = ids[i]
                for j in range(i + 1, n):
                    aj = ids[j]
                    dx = pos[ai][0] - pos[aj][0]
                    dy = pos[ai][1] - pos[aj][1]
                    dist = math.hypot(dx, dy) or 0.01
                    rep = k * k / dist
                    ux, uy = dx / dist, dy / dist
                    disp[ai][0] += ux * rep
                    disp[ai][1] += uy * rep
                    disp[aj][0] -= ux * rep
                    disp[aj][1] -= uy * rep
            for u, v in edge_pairs:
                dx = pos[u][0] - pos[v][0]
                dy = pos[u][1] - pos[v][1]
                dist = math.hypot(dx, dy) or 0.01
                att = dist * dist / k
                ux, uy = dx / dist, dy / dist
                disp[u][0] -= ux * att
                disp[u][1] -= uy * att
                disp[v][0] += ux * att
                disp[v][1] += uy * att
            for aid in ids:
                dx, dy = disp[aid]
                d = math.hypot(dx, dy) or 0.01
                pos[aid][0] += (dx / d) * min(d, temp)
                pos[aid][1] += (dy / d) * min(d, temp)
                pos[aid][0] = min(width - 20, max(20, pos[aid][0]))
                pos[aid][1] = min(height - 20, max(20, pos[aid][1]))
            temp = max(1.0, temp - cool)
        return pos

    def _render_svg(self, pos, width=900, height=640) -> str:
        if not pos:
            return (
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
                f'<text x="{width // 2}" y="{height // 2}" text-anchor="middle" '
                f'font-family="sans-serif" font-size="16" fill="#888">'
                f'No relations yet.</text></svg>'
            )
        out = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'font-family="sans-serif">'
        ]
        out.append("<defs>")
        for i, color in enumerate(_PALETTE):
            out.append(
                f'<marker id="arr{i}" viewBox="0 0 10 10" refX="9" refY="5" '
                f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                f'<path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>'
            )
        out.append("</defs>")
        for e in self.edges:
            if e["src"] not in pos or e["dst"] not in pos:
                continue
            color = _rel_color(e["rel_type"])
            mi = _PALETTE.index(color) if color in _PALETTE else 0
            x1, y1 = pos[e["src"]]
            x2, y2 = pos[e["dst"]]
            out.append(
                f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="{color}" stroke-width="1.5" marker-end="url(#arr{mi})">'
                f'<title>{html.escape(e["rel_type"])}'
                f'{": " + html.escape(e["note"]) if e["note"] else ""}</title></line>'
            )
        for aid, node in self.nodes.items():
            if aid not in pos:
                continue
            x, y = pos[aid]
            ann = node["annotation"]
            label = html.escape(_node_label(ann)[:16])
            tip = html.escape(
                f"{ann.get('anchor', '')}\n{ann.get('note', '')}".strip()
                or aid
            )
            out.append(
                f'<g><title>{tip}</title>'
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="13" fill="#cfe8ff" '
                f'stroke="#2b6cb0" stroke-width="1.5"/>'
                f'<text x="{x:.1f}" y="{y + 26:.1f}" text-anchor="middle" '
                f'font-size="11" fill="#222">{label}</text></g>'
            )
        out.append("</svg>")
        return "\n".join(out)
