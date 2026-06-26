"""Direct unit tests for :mod:`star.graph` — the KnowledgeGraph data model and
its exporters.  Built from an in-memory annotations store via a tiny settings
stub; no Qt (the graph view lives in star/gui/graph_view.py).
"""
from star.graph import KnowledgeGraph, _node_label, _rel_color


class _Settings:
    """Minimal settings stub exposing only ``settings['annotations']``."""

    def __init__(self, annotations):
        self._a = annotations

    def __getitem__(self, key):
        if key == "annotations":
            return self._a
        raise KeyError(key)


def _graph():
    anns = {
        "doc1.pdf": [
            {
                "id": "a1",
                "anchor": "Alpha",
                "tags": ["t1"],
                "relations": [{"target_id": "a2", "rel_type": "SUPPORTS", "note": "n"}],
            },
            {"id": "a2", "note": "Beta", "tags": [], "relations": []},
        ],
        "doc2.pdf": [
            {"id": "a3", "anchor": "Gamma", "tags": [], "relations": []},
        ],
    }
    return KnowledgeGraph(_Settings(anns))


# ── module helpers ────────────────────────────────────────────────────────────


def test_rel_color_known_vs_unknown():
    assert _rel_color("SUPPORTS").startswith("#")
    assert _rel_color("NOT_A_REAL_REL") == "#888888"


def test_node_label_prefers_anchor_then_note_then_id():
    assert _node_label({"anchor": "A", "note": "B", "id": "x"}) == "A"
    assert _node_label({"note": "B", "id": "x"}) == "B"
    assert _node_label({"id": "x"}) == "x"


# ── build / queries ───────────────────────────────────────────────────────────


def test_rebuild_nodes_and_edges():
    g = _graph()
    assert set(g.nodes) == {"a1", "a2", "a3"}
    assert len(g.edges) == 1
    e = g.edges[0]
    assert (e["src"], e["dst"], e["rel_type"]) == ("a1", "a2", "SUPPORTS")


def test_neighbors_and_reverse():
    g = _graph()
    fwd = g.neighbors("a1")
    assert len(fwd) == 1 and fwd[0][1]["annotation"]["id"] == "a2"
    rev = g.reverse_neighbors("a2")
    assert len(rev) == 1 and rev[0][1]["annotation"]["id"] == "a1"
    assert g.neighbors("a3") == []


def test_connected_component():
    g = _graph()
    comp = set(g.connected_component("a1"))
    assert {"a1", "a2"} <= comp
    assert "a3" not in comp  # isolated node, different component


def test_subgraph_keeps_only_selected():
    g = _graph()
    sub = g.subgraph(["a1", "a2"])
    assert set(sub.nodes) == {"a1", "a2"}
    assert len(sub.edges) == 1


def test_search_by_relation_type():
    g = _graph()
    res = g.search(rel_types=["SUPPORTS"])
    assert res is not None


# ── exporters ─────────────────────────────────────────────────────────────────


def test_to_json_shape():
    j = _graph().to_json()
    assert isinstance(j, dict)
    assert "nodes" in j and "edges" in j


def test_to_dot_is_graphviz():
    dot = _graph().to_dot()
    assert "digraph" in dot
    assert "a1" in dot and "a2" in dot


def test_to_plantuml():
    uml = _graph().to_plantuml()
    assert "@startuml" in uml and "@enduml" in uml


def test_to_svg_emits_svg():
    svg = _graph().to_svg()
    assert "<svg" in svg and "</svg>" in svg


def test_empty_graph():
    g = KnowledgeGraph(_Settings({}))
    assert g.nodes == {} and g.edges == []
    assert "<svg" in g.to_svg()  # renders without nodes
