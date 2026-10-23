"""Tests for Phase 1: graphio loader, normalizer, AST span locator and snippet extraction."""
import json
import shutil
from pathlib import Path
import pytest

from trailhead.graphio import load_graph, locate_span, normalize_label, snippet
from trailhead.models import Node

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mini_repo"
GRAPH_JSON = FIXTURE_DIR / "graphify-out" / "graph.json"

def test_graphio_loads_nodes_edges(tmp_path):
    assert GRAPH_JSON.exists(), f"Missing fixture graph at {GRAPH_JSON}"
    
    # 1. Test loading with 'links' (default from Graphify)
    nodes, edges = load_graph(GRAPH_JSON, repo_root=FIXTURE_DIR)
    assert len(nodes) >= 15, f"Expected >= 15 nodes, got {len(nodes)}"
    assert len(edges) >= 10, f"Expected >= 10 edges, got {len(edges)}"

    # 2. Test loading when JSON uses 'edges' instead of 'links'
    with open(GRAPH_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["edges"] = data.pop("links")
    copy_path = tmp_path / "graph_edges.json"
    with open(copy_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    nodes2, edges2 = load_graph(copy_path, repo_root=FIXTURE_DIR)
    assert len(nodes2) == len(nodes)
    assert len(edges2) == len(edges)

def test_label_normalization():
    assert normalize_label("main()") == "main"
    assert normalize_label("decode_token()") == "decode_token"
    assert normalize_label("MyClass.method()") == "MyClass.method"
    assert normalize_label("module.attr") == "module.attr"
    assert normalize_label("") == ""

def test_locate_span_python():
    nodes, _ = load_graph(GRAPH_JSON, repo_root=FIXTURE_DIR)
    function_nodes = [n for n in nodes if n.kind == "function" and n.file.endswith(".py")]
    assert len(function_nodes) > 0, "No function nodes found in fixture"

    located_count = 0
    for node in function_nodes:
        start, end = locate_span(node, repo_root=FIXTURE_DIR)
        if start is not None and end is not None:
            located_count += 1
            code_lines = (FIXTURE_DIR / node.file).read_text(encoding="utf-8").splitlines()
            span_text = "\n".join(code_lines[start - 1 : end])
            clean_name = normalize_label(node.label).split(".")[-1]
            assert f"def {clean_name}" in span_text, f"Expected 'def {clean_name}' in span text, got:\n{span_text}"

    assert located_count >= len(function_nodes) * 0.8, f"Located {located_count}/{len(function_nodes)} spans"

def test_snippet_from_disk_matches_file():
    nodes, _ = load_graph(GRAPH_JSON, repo_root=FIXTURE_DIR)
    # Find decode_token node
    decode_nodes = [n for n in nodes if "decode_token" in n.id]
    assert len(decode_nodes) > 0
    node = decode_nodes[0]
    
    snip = snippet(node, repo_root=FIXTURE_DIR, max_lines=14)
    assert "def decode_token" in snip
    file_lines = (FIXTURE_DIR / node.file).read_text(encoding="utf-8").splitlines()
    assert snip.splitlines()[0] == file_lines[node.start - 1]
