"""Graphify graph.json loader, normalizer, AST span locator and snippet extractor."""
import ast
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from trailhead.config import EDGE_WEIGHTS, SNIPPET_LINES
from trailhead.models import Edge, Node

_FILE_SYMBOL_CACHE: Dict[str, Dict[str, Tuple[int, int]]] = {}
_FILE_LINES_CACHE: Dict[str, List[str]] = {}

def normalize_label(label: str) -> str:
    """Normalize label, e.g. stripping trailing parentheses while preserving qualified names."""
    if not label:
        return ""
    if label.endswith("()"):
        return label[:-2]
    return label

def classify_kind(raw: dict) -> str:
    """Classify node kind as function, class, file, or other."""
    if raw.get("_callable_class") is True:
        return "class"
    if raw.get("_callable") is True:
        return "function"
    file_type = raw.get("file_type", "")
    if file_type == "file" or raw.get("id", "").endswith(".py"):
        return "file"
    return "other"

def map_relation(raw_rel: str) -> Tuple[str, float]:
    """Map raw graph relation string onto standard buckets and weights."""
    rel = (raw_rel or "").lower().strip()
    if rel in ("calls", "indirect_call", "method"):
        return "calls", EDGE_WEIGHTS.get("calls", 1.0)
    if rel in ("inherits",):
        return "inherits", EDGE_WEIGHTS.get("inherits", 0.8)
    if rel in ("contains",):
        return "contains", EDGE_WEIGHTS.get("contains", 0.7)
    if rel in ("imports", "imports_from"):
        return "imports", EDGE_WEIGHTS.get("imports", 0.5)
    return "other", EDGE_WEIGHTS.get("other", 0.3)

def _index_file_symbols(file_path: Path) -> Dict[str, Tuple[int, int]]:
    """Parse file once and index all top-level and inner symbol line ranges."""
    cache_key = str(file_path.resolve())
    if cache_key in _FILE_SYMBOL_CACHE:
        return _FILE_SYMBOL_CACHE[cache_key]

    symbols: Dict[str, Tuple[int, int]] = {}
    if not file_path.exists() or file_path.suffix.lower() != ".py":
        _FILE_SYMBOL_CACHE[cache_key] = symbols
        return symbols

    try:
        source_code = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source_code, filename=str(file_path))
        for item in ast.walk(tree):
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                end_lineno = getattr(item, "end_lineno", item.lineno)
                symbols[item.name] = (item.lineno, end_lineno)
    except Exception:
        pass

    _FILE_SYMBOL_CACHE[cache_key] = symbols
    return symbols

def locate_span(node: Node, repo_root: Union[str, Path]) -> Tuple[Optional[int], Optional[int]]:
    """Locate start and end line of the node symbol using Python's ast module."""
    if not node.file:
        return None, None

    full_path = Path(repo_root) / node.file
    symbols = _index_file_symbols(full_path)
    if not symbols:
        return None, None

    candidates_to_try = [
        node.label,
        normalize_label(node.label),
        normalize_label(node.label).split(".")[-1],
        node.id.split("_")[-1],
    ]
    for name in candidates_to_try:
        if name in symbols:
            return symbols[name]

    return None, None

def snippet(node: Node, repo_root: Union[str, Path], max_lines: int = SNIPPET_LINES) -> str:
    """Read actual code snippet from disk for the node span."""
    if not node.file:
        return ""
    full_path = Path(repo_root) / node.file
    if not full_path.exists() or not full_path.is_file():
        return ""

    cache_key = str(full_path.resolve())
    if cache_key in _FILE_LINES_CACHE:
        lines = _FILE_LINES_CACHE[cache_key]
    else:
        try:
            lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
            _FILE_LINES_CACHE[cache_key] = lines
        except Exception:
            return ""

    if not lines:
        return ""

    if node.start is not None and node.start > 0:
        start_idx = node.start - 1
        if node.end is not None and node.end >= node.start:
            end_idx = min(node.end, start_idx + max_lines)
        else:
            end_idx = min(len(lines), start_idx + max_lines)
        selected = lines[start_idx:end_idx]
    else:
        selected = lines[:max_lines]

    return "\n".join(selected)

def load_graph(
    json_path: Union[str, Path],
    repo_root: Optional[Union[str, Path]] = None,
    populate_spans: bool = True,
) -> Tuple[List[Node], List[Edge]]:
    """Load nodes and edges from graphify graph.json, supporting both 'links' and 'edges'."""
    p = Path(json_path)
    if not p.exists():
        raise FileNotFoundError(f"Graph file not found: {json_path}")

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_nodes = data.get("nodes", [])
    raw_edges = data.get("links", data.get("edges", []))

    root = Path(repo_root) if repo_root else p.parent.parent

    nodes: List[Node] = []
    for raw in raw_nodes:
        node_id = str(raw.get("id", ""))
        label = str(raw.get("label", node_id))
        norm_label = normalize_label(label)
        kind = classify_kind(raw)
        source_file = str(raw.get("source_file", ""))
        community = int(raw.get("community", 0))

        n = Node(
            id=node_id,
            label=norm_label,
            kind=kind,
            file=source_file,
            community=community,
        )

        if populate_spans and root.exists() and source_file.endswith(".py"):
            start, end = locate_span(n, root)
            n.start = start
            n.end = end
            n.text = snippet(n, root)

        nodes.append(n)

    edges: List[Edge] = []
    for raw in raw_edges:
        src = str(raw.get("source", raw.get("src", "")))
        dst = str(raw.get("target", raw.get("dst", "")))
        raw_rel = str(raw.get("relation", raw.get("type", "other")))
        bucket, weight = map_relation(raw_rel)
        confidence = str(raw.get("confidence", "EXTRACTED"))

        edges.append(
            Edge(
                src=src,
                dst=dst,
                relation=bucket,
                confidence=confidence,
                weight=float(raw.get("weight", weight)),
            )
        )

    return nodes, edges
