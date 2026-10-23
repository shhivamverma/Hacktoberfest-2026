"""Trailhead contribution trail pipeline orchestrator."""
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from trailhead.config import CANDIDATES, MODEL_MAIN
from trailhead.graphio import load_graph
from trailhead.models import Candidate, Pick, ToolCall, Trail
from trailhead.netguard import get_blocked_attempts, install_netguard
from trailhead.textproc import extract_hints
from trailhead.tools import ToolBelt

def run_pipeline(
    repo_path: Union[str, Path],
    issue_text: str,
    use_llm: bool = False,
    model: str = MODEL_MAIN,
) -> Trail:
    """Execute end-to-end Trailhead pipeline steps 1 through 8."""
    install_netguard()
    t_start = time.time()
    timings: Dict[str, float] = {}

    root = Path(repo_path).resolve()
    graph_json = root / "graphify-out" / "graph.json"
    if not graph_json.exists():
        raise FileNotFoundError(f"Missing graph.json in {graph_json}. Run 'trailhead index' first.")

    t0 = time.time()
    nodes, edges = load_graph(graph_json, repo_root=root)
    timings["load_graph_s"] = round(time.time() - t0, 3)

    nodes_by_id = {n.id: n for n in nodes}
    tools = ToolBelt(nodes, edges, root)

    # 1. HINTS extraction
    t0 = time.time()
    hints = extract_hints(issue_text)
    timings["extract_hints_s"] = round(time.time() - t0, 3)

    # 2. RETRIEVE (via tool call)
    t0 = time.time()
    retrieval_scores = tools.search_graph(issue_text)
    timings["retrieve_s"] = round(time.time() - t0, 3)

    # 3. GRAPH EXPAND (via tool call)
    t0 = time.time()
    candidates: List[Candidate] = tools.expand_graph(retrieval_scores, top_k=CANDIDATES)
    timings["expand_s"] = round(time.time() - t0, 3)

    # In v1 / no-llm mode, rank directly by fused score
    edit_picks: List[Pick] = []
    read_first_picks: List[Pick] = []
    all_tests: List[str] = []
    blast_records: List[Dict[str, Any]] = []

    # Process top candidates
    for i, cand in enumerate(candidates[:5]):
        node = nodes_by_id.get(cand.node_id)
        if not node:
            continue

        role = "edit" if i < 2 else "read_first"
        
        # 4. Read snippet from disk (via tool call)
        snip = tools.get_snippet(cand.node_id, max_lines=14)
        
        # 5. Blast radius (via tool call)
        blast = tools.get_callers(cand.node_id, depth=2)
        blast_records.append(blast)

        # 6. Test finder (via tool call)
        tests = tools.find_tests(cand.node_id)
        for t in tests:
            if t not in all_tests:
                all_tests.append(t)

        level = "span" if (node.start is not None and node.end is not None) else "file"
        why_msg = f"Fused score {cand.score_fused:.2f} via {cand.reason_path}" if cand.reason_path else "High graph relevance"

        p = Pick(
            alias=cand.alias,
            node_id=cand.node_id,
            role=role,
            why=why_msg[:160],
            file=node.file,
            start=node.start,
            end=node.end,
            snippet=snip,
            level=level,
        )

        if role == "edit":
            edit_picks.append(p)
        else:
            read_first_picks.append(p)

    timings["total_s"] = round(time.time() - t_start, 3)

    return Trail(
        status="graph_only" if not use_llm else "ok",
        confidence="medium",
        edit=edit_picks,
        read_first=read_first_picks,
        blast=blast_records,
        tests=all_tests,
        checklist=[
            "Read CONTRIBUTING.md before opening your pull request",
            "Run local test suite and ensure all tests pass",
            "Verify code adheres to project formatting and lint standards",
        ],
        explore_areas=[],
        trace=tools.trace,
        timing=timings,
        model={"name": model, "mode": "local_offline"},
        netguard={"blocked_attempts": get_blocked_attempts()},
    )
