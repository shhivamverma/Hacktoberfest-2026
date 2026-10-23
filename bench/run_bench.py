"""
Benchmark runner: measures Hit@k, MRR, latency, and stability across systems (BM25, Graph, LLM).
"""
import argparse
import glob
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root and src/ are in sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from bench.metrics import hit_at_k, mrr, recall_at_k
from trailhead.expand import expand_candidates
from trailhead.graphio import load_graph
from trailhead.models import Candidate, Edge, Node
from trailhead.retrieve import retrieve_nodes
from trailhead.textproc import extract_hints

BENCH_DATA_DIR = Path(__file__).parent / "data"
REPOS_DIR = Path(__file__).parent / "repos"

def run_evaluation(systems: List[str], split: str = "dev", limit: Optional[int] = None, runs: int = 1):
    case_files = glob.glob(str(BENCH_DATA_DIR / "*.jsonl"))
    if not case_files:
        print("No benchmark case files found.")
        return

    all_cases: List[Dict[str, Any]] = []
    for cf in case_files:
        with open(cf, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    case = json.loads(line)
                    if case.get("split") == split or split == "all":
                        all_cases.append(case)

    if limit and limit > 0:
        all_cases = all_cases[:limit]

    print(f"Loaded {len(all_cases)} cases for split='{split}' (systems={systems}, runs={runs})")

    results: Dict[str, Dict[str, float]] = {}

    for sys_name in systems:
        h1_list, h3_list, h5_list, mrr_list = [], [], [], []
        t0 = time.time()

        for c in all_cases:
            repo_slug = c.get("repo", "")
            repo_path = REPOS_DIR / repo_slug.replace("_", "/")
            if not repo_path.exists():
                repo_path = REPOS_DIR / repo_slug.split("_")[-1]

            graph_json = repo_path / "graphify-out" / "graph.json"
            if not graph_json.exists():
                continue

            nodes, edges = load_graph(graph_json, repo_root=repo_path, populate_spans=False)
            issue_text = c.get("issue_text", "")
            gold_files = [f.replace("\\", "/") for f in c.get("gold_files", [])]

            hints = extract_hints(issue_text)
            bm25_scores = retrieve_nodes(nodes, issue_text, hints=hints)

            if sys_name == "bm25":
                ranked = sorted(
                    [n for n in nodes if n.kind in ("function", "class")],
                    key=lambda n: bm25_scores.get(n.id, 0.0),
                    reverse=True,
                )
                pred_files = [n.file.replace("\\", "/") for n in ranked[:10]]
            elif "graph" in sys_name:
                candidates = expand_candidates(nodes, edges, bm25_scores, top_candidates_count=12)
                pred_files = []
                nodes_by_id = {n.id: n for n in nodes}
                for cand in candidates:
                    n = nodes_by_id.get(cand.node_id)
                    if n and n.file:
                        f_clean = n.file.replace("\\", "/")
                        if f_clean not in pred_files:
                            pred_files.append(f_clean)
            else:
                pred_files = []

            h1_list.append(hit_at_k(pred_files, gold_files, 1))
            h3_list.append(hit_at_k(pred_files, gold_files, 3))
            h5_list.append(hit_at_k(pred_files, gold_files, 5))
            mrr_list.append(mrr(pred_files, gold_files))

        n_eval = max(len(h1_list), 1)
        elapsed = time.time() - t0
        results[sys_name] = {
            "hit@1": sum(h1_list) / n_eval,
            "hit@3": sum(h3_list) / n_eval,
            "hit@5": sum(h5_list) / n_eval,
            "mrr": sum(mrr_list) / n_eval,
            "cases": len(h1_list),
            "time_s": elapsed,
        }

    print("\n### Evaluation Results (" + split + " split)\n")
    print("| System | Hit@1 | Hit@3 | Hit@5 | MRR | Cases | Time (s) |")
    print("|:---|:---|:---|:---|:---|:---|:---|")
    for s_name, m in results.items():
        print(f"| `{s_name}` | {m['hit@1']:.3f} | {m['hit@3']:.3f} | {m['hit@5']:.3f} | {m['mrr']:.3f} | {m['cases']} | {m['time_s']:.2f}s |")
    print()

def main():
    parser = argparse.ArgumentParser(description="Trailhead Benchmark Runner")
    parser.add_argument("--systems", default="bm25,graph", help="Comma-separated list of systems to evaluate")
    parser.add_argument("--split", default="dev", help="Split to evaluate: dev, test, all")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of cases")
    parser.add_argument("--runs", type=int, default=1, help="Number of repeated runs")
    args = parser.parse_args()

    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    run_evaluation(systems=systems, split=args.split, limit=args.limit, runs=args.runs)

if __name__ == "__main__":
    main()
