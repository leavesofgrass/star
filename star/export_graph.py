"""
Export the knowledge graph to external formats: SVG, PlantUML, DOT, JSON.
"""
import json


def export_svg(graph, path: str) -> str:
    text = graph.to_svg()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def export_dot(graph, path: str) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(graph.to_dot())
    return path


def export_plantuml(graph, path: str) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(graph.to_plantuml())
    return path


def export_json(graph, path: str) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(graph.to_json(), fh, indent=2, ensure_ascii=False)
    return path


def export_annotations_as_graph(settings, doc_path=None):
    """Build a KnowledgeGraph from settings, optionally filtered to one document."""
    from .graph import KnowledgeGraph

    graph = KnowledgeGraph(settings)
    if doc_path is not None:
        keep = [
            aid for aid, node in graph.nodes.items() if node["doc"] == doc_path
        ]
        graph = graph.subgraph(keep)
    return graph
