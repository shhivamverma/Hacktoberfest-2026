"""Typed tool belt with execution timing and live trace logging."""
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from trailhead.expand import compute_blast_radius, expand_candidates
from trailhead.graphio import snippet
from trailhead.models import Candidate, Edge, Node, ToolCall
from trailhead.retrieve import retrieve_nodes
from trailhead.tests_finder import find_tests_for_symbol
from trailhead.textproc import extract_hints

class ToolBelt:
    """Manages typed operations for code search, graph traversal, snippet reading, and test finding."""

    def __init__(self, nodes: List[Node], edges: List[Edge], repo_root: Path):
        self.nodes = nodes
        self.edges = edges
        self.repo_root = repo_root
        self.nodes_by_id = {n.id: n for n in nodes}
        self.trace: List[ToolCall] = []

    def _record(self, name: str, args: Dict[str, Any], fn: Callable[[], Any], summary_fn: Optional[Callable[[Any], str]] = None) -> Any:
        t0 = time.time()
        ok = True
        try:
            res = fn()
            return res
        except Exception as e:
            ok = False
            res = None
            raise e
        finally:
            ms = round((time.time() - t0) * 1000, 2)
            summary = summary_fn(res) if summary_fn and ok else ("ok" if ok else "failed")
            self.trace.append(
                ToolCall(
                    name=name,
                    args=args,
                    result_summary=str(summary),
                    ms=ms,
                    ok=ok,
                )
            )

    def search_graph(self, issue_text: str) -> Dict[str, float]:
        """Tool 'graph.search': Run lexical BM25 retrieval across code nodes."""
        return self._record(
            name="graph.search",
            args={"query": issue_text[:60]},
            fn=lambda: retrieve_nodes(self.nodes, issue_text),
            summary_fn=lambda r: f"scored {len(r)} symbols",
        )

    def expand_graph(self, retrieval_scores: Dict[str, float], top_k: int = 12) -> List[Candidate]:
        """Tool 'graph.expand': Run Personalized PageRank over code relationships."""
        return self._record(
            name="graph.expand",
            args={"seeds": min(len(retrieval_scores), 8)},
            fn=lambda: expand_candidates(self.nodes, self.edges, retrieval_scores, top_candidates_count=top_k),
            summary_fn=lambda r: f"expanded to {len(r)} candidates",
        )

    def get_callers(self, candidate_id: str, depth: int = 2) -> Dict[str, Any]:
        """Tool 'graph.callers': Compute blast radius and caller reach."""
        return self._record(
            name="graph.callers",
            args={"target": candidate_id, "depth": depth},
            fn=lambda: compute_blast_radius(candidate_id, self.edges, self.nodes_by_id),
            summary_fn=lambda r: f"{r.get('total_count', 0)} callers (risk: {r.get('risk')})",
        )

    def get_snippet(self, node_id: str, max_lines: int = 14) -> str:
        """Tool 'code.snippet': Read actual source lines from disk."""
        node = self.nodes_by_id.get(node_id, Node(id=node_id, label=node_id))
        return self._record(
            name="code.snippet",
            args={"file": node.file, "symbol": node.label},
            fn=lambda: snippet(node, self.repo_root, max_lines=max_lines),
            summary_fn=lambda r: f"{len(r.splitlines())} lines from disk",
        )

    def find_tests(self, node_id: str) -> List[str]:
        """Tool 'tests.for_node': Discover tests exercising node via call graph."""
        return self._record(
            name="tests.for_node",
            args={"target": node_id},
            fn=lambda: find_tests_for_symbol(node_id, self.nodes, self.edges),
            summary_fn=lambda r: f"{len(r)} tests linked",
        )

    def rewrite_query(self, issue_text: str, model: str = "qwen3:4b") -> List[str]:
        """Tool 'query.rewrite': Local LLM extracts developer code keywords."""
        from trailhead.rerank import rewrite_query
        return self._record(
            name="query.rewrite",
            args={"chars": min(len(issue_text), 1500)},
            fn=lambda: rewrite_query(issue_text, model=model),
            summary_fn=lambda r: f"extracted {len(r)} keywords: {', '.join(r[:3])}" if r else "no keywords",
        )

