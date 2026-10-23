"""Tests for Phase 2: textproc, BM25 retrieval, stacktrace boosting, and evaluation metrics."""
import json
import subprocess
from pathlib import Path
import pytest

from bench.metrics import hit_at_k, mrr, recall_at_k
from trailhead.graphio import load_graph
from trailhead.retrieve import retrieve_nodes
from trailhead.textproc import extract_hints, split_identifiers

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mini_repo"
GRAPH_JSON = FIXTURE_DIR / "graphify-out" / "graph.json"
ISSUES_JSON = Path(__file__).parent / "fixtures" / "issues.json"

@pytest.fixture
def issues():
    with open(ISSUES_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def test_split_identifiers():
    res = split_identifiers("getUserName_v2")
    assert res == ["get", "user", "name", "v2"]

def test_extract_traceback_hints(issues):
    i3_text = issues["I3"]["issue_text"]
    hints = extract_hints(i3_text)
    trace_hints = [h for h in hints if h.kind == "trace"]
    assert len(trace_hints) >= 1
    
    # Traceback frame ending in app/tokens.py, in decode_token
    token_frame = [h for h in trace_hints if "tokens.py" in (h.file or "") and h.func == "decode_token"]
    assert len(token_frame) == 1
    assert token_frame[0].line == 8

def test_extract_backtick_and_error_hints():
    text = "Error occurred: `reset_password` threw 'Invalid token' during execution."
    hints = extract_hints(text)
    
    id_hints = [h.value for h in hints if h.kind == "identifier"]
    err_hints = [h.value for h in hints if h.kind == "error"]
    
    assert "reset_password" in id_hints
    assert "Invalid token" in err_hints

def test_bm25_ranks_gold_first(issues):
    nodes, _ = load_graph(GRAPH_JSON, repo_root=FIXTURE_DIR)
    
    # Test Issue I1
    i1 = issues["I1"]
    hints1 = extract_hints(i1["issue_text"])
    scores1 = retrieve_nodes(nodes, i1["issue_text"], hints=hints1)
    
    ranked_func_nodes1 = [
        n for n in nodes if n.kind in ("function", "class") and scores1.get(n.id, 0.0) > 0.0
    ]
    ranked_func_nodes1.sort(key=lambda n: scores1.get(n.id, 0.0), reverse=True)
    top_3_files1 = [n.file for n in ranked_func_nodes1[:3]]
    assert any(g in top_3_files1 for g in i1["gold_files"])

    # Test Issue I3
    i3 = issues["I3"]
    hints3 = extract_hints(i3["issue_text"])
    scores3 = retrieve_nodes(nodes, i3["issue_text"], hints=hints3)
    ranked_func_nodes3 = [
        n for n in nodes if n.kind in ("function", "class") and scores3.get(n.id, 0.0) > 0.0
    ]
    ranked_func_nodes3.sort(key=lambda n: scores3.get(n.id, 0.0), reverse=True)
    top_3_files3 = [n.file for n in ranked_func_nodes3[:3]]
    assert any(g in top_3_files3 for g in i3["gold_files"])

def test_stacktrace_boost(issues):
    nodes, _ = load_graph(GRAPH_JSON, repo_root=FIXTURE_DIR)
    i3 = issues["I3"]
    hints3 = extract_hints(i3["issue_text"])
    scores3 = retrieve_nodes(nodes, i3["issue_text"], hints=hints3, stacktrace_boost=5.0)
    
    ranked_nodes = sorted(
        [n for n in nodes if n.kind in ("function", "class")],
        key=lambda n: scores3.get(n.id, 0.0),
        reverse=True
    )
    assert len(ranked_nodes) > 0
    # decode_token should be ranked #1
    assert "decode_token" in ranked_nodes[0].label

def test_bm25_misses_i2_as_expected(issues):
    """Anchor test: I2's gold _clamp_total is lexically unrelated so BM25 alone must miss it."""
    nodes, _ = load_graph(GRAPH_JSON, repo_root=FIXTURE_DIR)
    i2 = issues["I2"]
    hints2 = extract_hints(i2["issue_text"])
    scores2 = retrieve_nodes(nodes, i2["issue_text"], hints=hints2)
    
    ranked_nodes = sorted(
        [n for n in nodes if n.kind in ("function", "class")],
        key=lambda n: scores2.get(n.id, 0.0),
        reverse=True
    )
    top_5_labels = [n.label for n in ranked_nodes[:5]]
    # _clamp_total MUST NOT be in BM25's top 5
    assert not any("_clamp_total" in lbl for lbl in top_5_labels)

def test_metrics_exact():
    preds = ["a", "b", "c", "d", "e"]
    gold = ["c", "z"]

    assert hit_at_k(preds, gold, 1) == 0.0
    assert hit_at_k(preds, gold, 2) == 0.0
    assert hit_at_k(preds, gold, 3) == 1.0
    assert hit_at_k(preds, gold, 5) == 1.0

    assert recall_at_k(preds, gold, 2) == 0.0
    assert recall_at_k(preds, gold, 3) == 0.5  # 1 out of 2 gold items
    assert recall_at_k(preds, gold, 5) == 0.5

    # 'c' is at rank 3 (1-indexed), so MRR = 1/3
    assert abs(mrr(preds, gold) - (1.0 / 3.0)) < 1e-6
    assert mrr(["x", "y"], ["z"]) == 0.0

def test_cli_trail_no_llm_runs(issues):
    issue_text = issues["I1"]["issue_text"]
    proc = subprocess.run(
        ["uv", "run", "trailhead", "trail", "--repo", str(FIXTURE_DIR), "--issue", issue_text, "--no-llm"],
        capture_output=True,
        text=True,
        check=True
    )
    assert proc.returncode == 0
    assert "app/tokens.py" in proc.stdout or "app/passwords.py" in proc.stdout
