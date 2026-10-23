"""Gate tests for Phase 4: LLM layer with query rewrite, schema-constrained reranking, and verification guardrails."""
import json
import time
from pathlib import Path
from unittest.mock import patch
import pytest

from trailhead.config import MODEL_MAIN, OLLAMA_HOST
from trailhead.contributing import extract_checklist
from trailhead.graphio import load_graph, snippet
from trailhead.llm import extract_json_object, strip_tags
from trailhead.models import Candidate, Node, Pick
from trailhead.pipeline import run_pipeline
from trailhead.rerank import (
    build_rerank_schema,
    rerank_candidates,
    verify_and_build_picks,
)

MINI_REPO = Path(__file__).parent / "fixtures" / "mini_repo"
ISSUES_FILE = Path(__file__).parent / "fixtures" / "issues.json"

def test_invented_alias_rejected():
    """Verify V1 rule: pick with invented alias C99 is rejected, retried, and falls back to graph_only safely."""
    nodes, edges = load_graph(MINI_REPO / "graphify-out" / "graph.json", repo_root=MINI_REPO)
    nodes_by_id = {n.id: n for n in nodes}

    candidates = [
        Candidate(alias="C1", node_id="app/billing.py::apply_discount", score_fused=0.9),
        Candidate(alias="C2", node_id="app/billing.py::_clamp_total", score_fused=0.8),
    ]

    # Mock chat to always return an invented alias "C99"
    mock_response = {
        "content": json.dumps({
            "confidence": "high",
            "picks": [{"id": "C99", "role": "edit", "why": "invented alias"}]
        }),
        "raw_content": '{"confidence": "high", "picks": [{"id": "C99", "role": "edit", "why": "invented alias"}]}',
        "tokens_per_sec": 10.0,
    }

    call_count = 0
    def mock_chat(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_response

    with patch("trailhead.rerank.chat", side_effect=mock_chat):
        res = rerank_candidates(
            candidates=candidates,
            nodes_by_id=nodes_by_id,
            issue_text="Discount issue",
            hints=[],
            repo_root=MINI_REPO,
        )

    # Must retry once (2 calls total) and fall back to graph_only
    assert call_count == 2, f"Expected 2 chat calls (1 initial + 1 retry), got {call_count}"
    assert res["status"] == "graph_only"
    assert "failed candidate verification" in res["banner"]
    assert res["edit"] == []

def test_think_tags_stripped_then_parsed():
    """Verify reasoning <think> and tool tags leaking from local models are cleanly stripped."""
    leaked_raw = (
        "<think>\n"
        "The user is asking about an invoice bug.\n"
        "Let's check candidate C1.\n"
        "</think>\n"
        '{"confidence": "high", "picks": [{"id": "C1", "role": "edit", "why": "handles discount"}]}'
    )
    clean = extract_json_object(leaked_raw)
    parsed = json.loads(clean)
    assert parsed["confidence"] == "high"
    assert parsed["picks"][0]["id"] == "C1"

    # Stray tags test
    stray = '</think>{"keywords": ["discount", "invoice"]}'
    clean_stray = extract_json_object(stray)
    parsed_stray = json.loads(clean_stray)
    assert parsed_stray["keywords"] == ["discount", "invoice"]

def test_fallback_when_ollama_down():
    """Verify that when Ollama is unreachable, pipeline falls back to graph_only in under 5s with banner."""
    # Point to closed port on localhost
    with patch("trailhead.config.OLLAMA_HOST", "http://127.0.0.1:54321"), \
         patch("trailhead.llm.OLLAMA_HOST", "http://127.0.0.1:54321"):
        t0 = time.time()
        trail = run_pipeline(
            repo_path=MINI_REPO,
            issue_text="Fix billing calculation error",
            use_llm=True,
        )
        elapsed = time.time() - t0

    assert elapsed < 5.0, f"Expected fallback in < 5.0s, took {elapsed:.2f}s"
    assert trail.status == "graph_only"
    assert trail.banner is not None and len(trail.banner) > 0
    assert len(trail.edit) > 0, "Graph-only fallback must still populate candidate picks"

def test_abstain_on_ambiguous_issue():
    """Verify V4 rule: vague issue like 'it doesn't work' triggers abstain mode with 3 explore areas and clarifying question."""
    nodes, edges = load_graph(MINI_REPO / "graphify-out" / "graph.json", repo_root=MINI_REPO)
    nodes_by_id = {n.id: n for n in nodes}

    candidates = [
        Candidate(alias="C1", node_id="app_billing_create_invoice", score_fused=0.51),
        Candidate(alias="C2", node_id="app_auth_login", score_fused=0.50),
        Candidate(alias="C3", node_id="app_utils_parse_date", score_fused=0.49),
    ]


    mock_response = {
        "content": json.dumps({
            "confidence": "low",
            "picks": [{"id": "C1", "role": "edit", "why": "uncertain match"}]
        }),
        "raw_content": '{"confidence": "low", "picks": [{"id": "C1", "role": "edit", "why": "uncertain match"}]}',
        "tokens_per_sec": 12.0,
    }

    with patch("trailhead.rerank.chat", return_value=mock_response):
        res = rerank_candidates(
            candidates=candidates,
            nodes_by_id=nodes_by_id,
            issue_text="it doesn't work",
            hints=[],
            repo_root=MINI_REPO,
        )

    assert res["status"] == "low_confidence"
    assert res["confidence"] == "low"
    assert len(res["explore_areas"]) == 3
    assert res["clarifying_question"] is not None
    assert len(res["clarifying_question"]) > 10

def test_snippets_match_disk():
    """Verify V3 rule: every pick's snippet equals the actual disk content at its span."""
    trail = run_pipeline(
        repo_path=MINI_REPO,
        issue_text="Reset password token invalidation error",
        use_llm=False,
    )
    all_picks = trail.edit + trail.read_first
    assert len(all_picks) > 0

    for pick in all_picks:
        if pick.level == "span" and pick.start and pick.end:
            target_file = MINI_REPO / pick.file
            assert target_file.exists()
            lines = target_file.read_text(encoding="utf-8").splitlines()
            expected_snippet = "\n".join(lines[pick.start - 1 : min(pick.end, pick.start + 13)])
            assert pick.snippet.strip() == expected_snippet.strip()

def test_span_downgrade():
    """Verify V2 rule: out-of-range or missing span lines are safely downgraded to level 'file'."""
    node = Node(
        id="app/billing.py::fake_function",
        label="fake_function",
        file="app/billing.py",
        start=99999,
        end=100000,
    )
    nodes_by_id = {node.id: node}
    cand = Candidate(alias="C1", node_id=node.id, score_fused=0.9)
    candidate_map = {"C1": cand}

    raw_picks = [{"id": "C1", "role": "edit", "why": "testing span downgrade"}]
    edit_picks, read_first_picks = verify_and_build_picks(
        raw_picks, candidate_map, nodes_by_id, MINI_REPO
    )

    assert len(edit_picks) == 1
    assert edit_picks[0].level == "file"
    assert edit_picks[0].start is None
    assert edit_picks[0].end is None

def test_checklist_from_contributing():
    """Verify CONTRIBUTING checklist extracts at least 3 items including a pytest test command."""
    checklist = extract_checklist(MINI_REPO)
    assert len(checklist) >= 3
    joined = " ".join(checklist).lower()
    assert "pytest" in joined or "test" in joined
    assert "ruff" in joined or "lint" in joined

@pytest.mark.ollama
def test_live_rerank_fixture():
    """Live Ollama evaluation on fixture issues I1, I2, I3 (3 repeated runs)."""
    with open(ISSUES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    issues = list(data.values())

    successes = 0
    for issue in issues:
        target_hits = 0
        gold_files = issue["gold_files"]

        for run_idx in range(3):
            trail = run_pipeline(
                repo_path=MINI_REPO,
                issue_text=issue["issue_text"],
                use_llm=True,
                model=MODEL_MAIN,
            )
            assert trail.status in ("ok", "low_confidence", "graph_only")
            picks = trail.edit + trail.read_first
            top3_files = [p.file for p in picks[:3]]

            # Check if any gold file is in top 3 picks
            hit = any(g in top3_files for g in gold_files)
            if hit:
                target_hits += 1

        # Majority of 3 runs must hit the gold file
        if target_hits >= 2:
            successes += 1

    # At least 2 of 3 issues must succeed in majority of runs
    assert successes >= 2, f"Expected at least 2/3 issues to succeed across 3 runs, got {successes}/3"

