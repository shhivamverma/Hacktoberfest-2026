"""
scripts/probe_graph.py
Inspects a graphify graph.json and prints schema, counts, relations, sample nodes/edges, and line info.
"""
import json
import sys
from collections import Counter
from pathlib import Path

def probe_graph(json_path: str):
    path = Path(json_path)
    if not path.exists():
        print(f"Error: {json_path} does not exist", file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"=== PROBE REPORT: {path} ===")
    print(f"Top-level keys: {list(data.keys())}")

    nodes = data.get("nodes", [])
    # Support both 'links' and 'edges'
    edges = data.get("links", data.get("edges", []))

    print(f"Node count: {len(nodes)}")
    print(f"Edge count: {len(edges)}")

    if nodes:
        sample_node_keys = set().union(*(n.keys() for n in nodes[:50]))
        print(f"Node keys: {sorted(sample_node_keys)}")
        has_lines = any("line" in n or "start" in n or "start_line" in n or "span" in n or "lineno" in n for n in nodes)
        print(f"Nodes have line info: {has_lines}")
        print("\n--- 5 Sample Nodes ---")
        for i, n in enumerate(nodes[:5]):
            print(f"Node {i}: {json.dumps(n, indent=2)}")

    if edges:
        relation_counter = Counter(e.get("relation", e.get("type", "unknown")) for e in edges)
        print(f"\nRelation strings with counts: {dict(relation_counter)}")
        print("\n--- 5 Sample Edges ---")
        for i, e in enumerate(edges[:5]):
            print(f"Edge {i}: {json.dumps(e, indent=2)}")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/mini_repo/graphify-out/graph.json"
    probe_graph(target)
