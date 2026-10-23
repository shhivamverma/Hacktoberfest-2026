"""Locate relevant tests exercising target code symbols via call-graph reachability and naming heuristics."""
from pathlib import Path
from typing import Dict, List, Set

from trailhead.graphio import normalize_label
from trailhead.models import Edge, Node

def is_test_node(node: Node) -> bool:
    """Identify if a node represents an automated test function or test module."""
    f = (node.file or "").replace("\\", "/").lower()
    in_test_path = f.startswith("tests/") or "/tests/" in f or "test_" in Path(f).name or f.endswith("_test.py")
    is_test_func = node.label.startswith("test_") or node.id.startswith("test_")
    return in_test_path and (is_test_func or node.kind == "function")

def find_tests_for_symbol(
    target_id: str,
    nodes: List[Node],
    edges: List[Edge],
    max_hops: int = 2,
) -> List[str]:
    """
    Find pytest node IDs for tests exercising target_id:
    1. Reachable test nodes via caller edges within 2 hops.
    2. Fallback to name similarity (test_<symbol_name>).
    """
    nodes_by_id: Dict[str, Node] = {n.id: n for n in nodes}
    test_node_ids: List[str] = []

    target_node = nodes_by_id.get(target_id)
    target_clean = normalize_label(target_node.label).split(".")[-1] if target_node else ""

    # 1. Backward call graph reachability: who calls target_id?
    frontier: Set[str] = {target_id}
    visited: Set[str] = {target_id}
    reaching_tests: Set[str] = set()

    for hop in range(max_hops):
        next_frontier: Set[str] = set()
        for curr in frontier:
            for e in edges:
                if e.dst == curr and e.relation == "calls":
                    caller_id = e.src
                    if caller_id not in visited:
                        visited.add(caller_id)
                        next_frontier.add(caller_id)
                        caller_node = nodes_by_id.get(caller_id)
                        if caller_node and is_test_node(caller_node):
                            reaching_tests.add(caller_id)
        frontier = next_frontier

    for tid in sorted(reaching_tests):
        tn = nodes_by_id[tid]
        clean_lbl = normalize_label(tn.label)
        clean_file = (tn.file or "").replace("\\", "/")
        test_node_ids.append(f"{clean_file}::{clean_lbl}")

    # 2. Fallback by naming pattern if no call graph links were found
    if not test_node_ids and target_clean:
        for n in nodes:
            if is_test_node(n):
                clean_lbl = normalize_label(n.label)
                if clean_lbl == f"test_{target_clean}" or target_clean in clean_lbl:
                    clean_file = (n.file or "").replace("\\", "/")
                    item = f"{clean_file}::{clean_lbl}"
                    if item not in test_node_ids:
                        test_node_ids.append(item)

    return test_node_ids

def build_pytest_command(test_node_ids: List[str]) -> str:
    """Format copy-ready pytest command for the identified test nodes."""
    if not test_node_ids:
        return "pytest"
    return f"pytest -v {' '.join(test_node_ids)}"
