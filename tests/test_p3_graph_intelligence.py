"""Tests for Phase 3: PageRank graph expansion, blast radius, test link finder, and pipeline tool trace."""
import json
import time
from pathlib import Path
import networkx as nx
import pytest

from trailhead.expand import build_graph, compute_blast_radius, expand_candidates, run_ppr
from trailhead.graphio import load_graph
from trailhead.models import Edge, Node
from trailhead.pipeline import run_pipeline
from trailhead.retrieve import retrieve_nodes
from trailhead.tests_finder import find_tests_for_symbol
from trailhead.textproc import extract_hints

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mini_repo"
GRAPH_JSON = FIXTURE_DIR / "graphify-out" / "graph.json"
ISSUES_JSON = Path(__file__).parent / "fixtures" / "issues.json"

@pytest.fixture
def graph_data():
    nodes, edges = load_graph(GRAPH_JSON, repo_root=FIXTURE_DIR)
    return nodes, edges

@pytest.fixture
def issues():
    with open(ISSUES_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def test_ppr_pulls_in_callee(graph_data, issues):
    """
    Key Graph Advantage Test:
    For I2, _clamp_total is lexically unrelated and missed by BM25 top-5,
    but PPR expansion propagates score along the call edge from apply_discount,
    pulling _clamp_total into the top 5 fused candidates!
    """
    nodes, edges = graph_data
    i2_text = issues["I2"]["issue_text"]
    hints = extract_hints(i2_text)
    bm25_scores = retrieve_nodes(nodes, i2_text, hints=hints)

    # Confirm BM25 alone misses _clamp_total in top 5
    ranked_bm25 = sorted(
        [n for n in nodes if n.kind in ("function", "class")],
        key=lambda n: bm25_scores.get(n.id, 0.0),
        reverse=True,
    )
    assert not any("_clamp_total" in n.label for n in ranked_bm25[:5])

    # Now expand with PageRank and fused scoring
    candidates = expand_candidates(nodes, edges, bm25_scores, top_candidates_count=12)
    top_5_cand_ids = [c.node_id for c in candidates[:5]]
    nodes_by_id = {n.id: n for n in nodes}
    top_5_labels = [nodes_by_id[cid].label for cid in top_5_cand_ids if cid in nodes_by_id]

    # _clamp_total MUST now appear in the fused top 5
    assert any("_clamp_total" in lbl for lbl in top_5_labels), f"Expected _clamp_total in top 5 candidates, got: {top_5_labels}"

def test_ppr_deterministic(graph_data, issues):
    """Ensure two repeated runs produce identical candidate ordering."""
    nodes, edges = graph_data
    i1_text = issues["I1"]["issue_text"]
    scores = retrieve_nodes(nodes, i1_text)

    cands_run1 = expand_candidates(nodes, edges, scores, top_candidates_count=10)
    cands_run2 = expand_candidates(nodes, edges, scores, top_candidates_count=10)

    ordering1 = [c.node_id for c in cands_run1]
    ordering2 = [c.node_id for c in cands_run2]
    assert ordering1 == ordering2

def test_candidates_have_multiple_files(graph_data, issues):
    """Verify multi-file diversity in candidate generation for I1."""
    nodes, edges = graph_data
    i1_text = issues["I1"]["issue_text"]
    scores = retrieve_nodes(nodes, i1_text)

    candidates = expand_candidates(nodes, edges, scores, top_candidates_count=10)
    nodes_by_id = {n.id: n for n in nodes}
    candidate_files = {nodes_by_id[c.node_id].file for c in candidates if c.node_id in nodes_by_id}
    
    assert len(candidate_files) >= 2, f"Expected at least 2 distinct files, got {candidate_files}"

def test_blast_radius_counts(graph_data):
    """Verify caller list and risk badge for decode_token."""
    nodes, edges = graph_data
    nodes_by_id = {n.id: n for n in nodes}

    decode_nodes = [n for n in nodes if "decode_token" in n.id]
    assert len(decode_nodes) > 0
    target_id = decode_nodes[0].id

    blast = compute_blast_radius(target_id, edges, nodes_by_id)
    assert blast["risk"] in ("low", "medium", "high")
    assert blast["total_count"] >= 1
    # verify_token in auth.py calls decode_token
    assert any("verify_token" in caller for caller in blast["all_callers"])

def test_tests_finder_links_tests(graph_data):
    """Verify call graph reachability links target functions to their tests."""
    nodes, edges = graph_data

    # 1. verify_token -> tests/test_auth.py::test_verify_token_expired
    vtoken_nodes = [n for n in nodes if "verify_token" in n.id]
    assert len(vtoken_nodes) > 0
    auth_tests = find_tests_for_symbol(vtoken_nodes[0].id, nodes, edges)
    assert any("test_verify_token_expired" in t for t in auth_tests)

    # 2. apply_discount and _clamp_total -> billing test
    disc_nodes = [n for n in nodes if "apply_discount" in n.id]
    clamp_nodes = [n for n in nodes if "clamp_total" in n.id]
    assert len(disc_nodes) > 0 and len(clamp_nodes) > 0

    disc_tests = find_tests_for_symbol(disc_nodes[0].id, nodes, edges)
    clamp_tests = find_tests_for_symbol(clamp_nodes[0].id, nodes, edges)

    assert any("test_apply_discount" in t for t in disc_tests)
    assert any("test_apply_discount" in t for t in clamp_tests)

def test_tool_trace_logged():
    """Verify that pipeline execution records at least 4 typed ToolCall entries."""
    trail = run_pipeline(repo_path=FIXTURE_DIR, issue_text="User password reset token expired", use_llm=False)
    assert len(trail.trace) >= 4

    tool_names = [tc.name for tc in trail.trace]
    assert "graph.search" in tool_names
    assert "graph.expand" in tool_names
    assert "code.snippet" in tool_names
    assert "graph.callers" in tool_names or "tests.for_node" in tool_names

    for tc in trail.trace:
        assert tc.ms >= 0.0
        assert tc.ok is True
        assert len(tc.result_summary) > 0

def test_expand_performance():
    """Performance gate: a synthetic 5,000-node graph expands in under 1.5 seconds."""
    syn_nodes = [
        Node(id=f"node_{i}", label=f"func_{i}", kind="function", file=f"pkg/mod_{i % 50}.py")
        for i in range(5000)
    ]
    # Build 10,000 edges forming a scale-free network
    syn_edges = []
    for i in range(1, 5000):
        parent = i // 2
        syn_edges.append(Edge(src=f"node_{parent}", dst=f"node_{i}", relation="calls", weight=1.0))
        if i % 3 == 0:
            syn_edges.append(Edge(src=f"node_{i}", dst=f"node_{i % 100}", relation="imports", weight=0.5))

    retrieval_scores = {f"node_{i}": 10.0 - (i * 0.1) for i in range(10)}

    t0 = time.time()
    candidates = expand_candidates(syn_nodes, syn_edges, retrieval_scores, top_candidates_count=12)
    elapsed = time.time() - t0

    assert elapsed < 1.5, f"expand_candidates took {elapsed:.3f}s (must be < 1.5s)"
    assert len(candidates) == 12
