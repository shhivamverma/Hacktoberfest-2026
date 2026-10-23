"""Trailhead contribution trail pipeline orchestrator."""
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from trailhead.config import CANDIDATES, MODEL_MAIN
from trailhead.contributing import extract_checklist
from trailhead.gitinfo import get_recent_commits
from trailhead.graphio import load_graph
from trailhead.models import Candidate, Pick, ToolCall, Trail
from trailhead.netguard import get_blocked_attempts, install_netguard
from trailhead.rerank import rerank_candidates
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

    # 2. Query rewrite via LLM (if enabled and no stacktrace hint)
    search_query = issue_text
    has_trace = any(h.kind == "trace" for h in hints)
    if use_llm and not has_trace:
        t0 = time.time()
        keywords = tools.rewrite_query(issue_text, model=model)
        if keywords:
            search_query = f"{issue_text} {' '.join(keywords)}"
        timings["query_rewrite_s"] = round(time.time() - t0, 3)

    # 3. RETRIEVE (via tool call)
    t0 = time.time()
    retrieval_scores = tools.search_graph(search_query)
    timings["retrieve_s"] = round(time.time() - t0, 3)

    # 4. GRAPH EXPAND (via tool call)
    t0 = time.time()
    candidates: List[Candidate] = tools.expand_graph(retrieval_scores, top_k=CANDIDATES)
    timings["expand_s"] = round(time.time() - t0, 3)

    # 5. LLM RERANK or GRAPH RANKING
    status = "graph_only" if not use_llm else "ok"
    confidence = "medium"
    explore_areas: List[str] = []
    clarifying_question: Optional[str] = None
    banner: Optional[str] = None
    edit_picks: List[Pick] = []
    read_first_picks: List[Pick] = []

    if use_llm and candidates:
        t0 = time.time()
        rerank_res = rerank_candidates(
            candidates=candidates,
            nodes_by_id=nodes_by_id,
            issue_text=issue_text,
            hints=hints,
            repo_root=root,
            model=model,
        )
        timings["rerank_s"] = round(time.time() - t0, 3)

        status = rerank_res.get("status", "ok")
        confidence = rerank_res.get("confidence", "medium")
        banner = rerank_res.get("banner")
        explore_areas = rerank_res.get("explore_areas", [])
        clarifying_question = rerank_res.get("clarifying_question")

        edit_picks = rerank_res.get("edit", [])
        read_first_picks = rerank_res.get("read_first", [])

    # If in graph_only mode or no picks resulted, populate picks from top fused candidates
    if not edit_picks and not read_first_picks:
        for i, cand in enumerate(candidates[:5]):
            node = nodes_by_id.get(cand.node_id)
            if not node:
                continue
            role = "edit" if i < 2 else "read_first"
            snip = tools.get_snippet(cand.node_id, max_lines=14)
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

    # 6. ENRICH: Blast radius & Tests for edit picks
    all_picks = edit_picks + read_first_picks
    blast_records: List[Dict[str, Any]] = []
    all_tests: List[str] = []

    for p in all_picks[:5]:
        # Blast radius
        blast = tools.get_callers(p.node_id, depth=2)
        blast_records.append(blast)

        # Tests
        tests = tools.find_tests(p.node_id)
        for t in tests:
            if t not in all_tests:
                all_tests.append(t)

    # 7. CONTRIBUTING checklist
    checklist = extract_checklist(root)

    timings["total_s"] = round(time.time() - t_start, 3)

    return Trail(
        status=status,
        confidence=confidence,
        edit=edit_picks,
        read_first=read_first_picks,
        blast=blast_records,
        tests=all_tests,
        checklist=checklist,
        explore_areas=explore_areas,
        clarifying_question=clarifying_question,
        banner=banner,
        trace=tools.trace,
        timing=timings,
        model={"name": model, "mode": "local_offline" if use_llm else "graph_heuristics"},
        netguard={"blocked_attempts": get_blocked_attempts()},
    )
