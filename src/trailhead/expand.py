"""Personalized PageRank expansion, graph-guided candidate selection, and blast radius calculation."""
import math
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
import numpy as np

from trailhead.config import CANDIDATES, FUSION, PPR_ALPHA, TOP_SEEDS
from trailhead.models import Candidate, Edge, Node

def is_test_path(path: str) -> bool:
    """Check if file path belongs to test suite."""
    p = (path or "").replace("\\", "/").lower()
    return p.startswith("tests/") or "/tests/" in p or "test_" in p or p.endswith("_test.py")

def build_graph(nodes: List[Node], edges: List[Edge]) -> nx.Graph:
    """Build an undirected weighted graph from nodes and edges for PageRank traversal."""
    G = nx.Graph()
    for n in nodes:
        G.add_node(n.id, label=n.label, kind=n.kind, file=n.file)

    for e in edges:
        if G.has_edge(e.src, e.dst):
            curr_w = G[e.src][e.dst].get("weight", 1.0)
            if e.weight > curr_w:
                G[e.src][e.dst]["weight"] = e.weight
                G[e.src][e.dst]["relation"] = e.relation
        else:
            G.add_edge(e.src, e.dst, weight=e.weight, relation=e.relation)

    return G

def run_ppr(
    G: nx.Graph,
    retrieval_scores: Dict[str, float],
    top_seeds_k: int = TOP_SEEDS,
    alpha: float = PPR_ALPHA,
) -> Dict[str, float]:
    """Execute personalized PageRank via fast deterministic power iteration (scipy-free)."""
    node_list = list(G.nodes())
    N = len(node_list)
    if N == 0:
        return {}

    node_idx = {n: i for i, n in enumerate(node_list)}

    # Positive seed weights
    positive_seeds = {nid: s for nid, s in retrieval_scores.items() if s > 0.0 and nid in node_idx}
    sorted_seeds = sorted(positive_seeds.items(), key=lambda kv: kv[1], reverse=True)[:top_seeds_k]
    total_seed_score = sum(s for _, s in sorted_seeds)

    v = np.zeros(N, dtype=np.float64)
    if total_seed_score > 0:
        for nid, s in sorted_seeds:
            v[node_idx[nid]] = s / total_seed_score
    else:
        v[:] = 1.0 / N

    # Build adjacency with weights
    adj: List[List[Tuple[int, float]]] = [[] for _ in range(N)]
    for u, u_nbrs in G.adj.items():
        iu = node_idx[u]
        for v_node, data in u_nbrs.items():
            iv = node_idx[v_node]
            w = float(data.get("weight", 1.0))
            adj[iu].append((iv, w))

    # Precalculate sum of outgoing weights
    out_weights = np.zeros(N, dtype=np.float64)
    for i in range(N):
        out_weights[i] = sum(w for _, w in adj[i])

    # Power iteration
    p = v.copy()
    for _ in range(40):
        next_p = np.zeros(N, dtype=np.float64)
        for i in range(N):
            tot_w = out_weights[i]
            if tot_w > 0:
                share = (alpha * p[i]) / tot_w
                for j, w in adj[i]:
                    next_p[j] += share * w
            else:
                next_p += (alpha * p[i]) / N

        next_p += (1.0 - alpha) * v
        diff = np.sum(np.abs(next_p - p))
        p = next_p
        if diff < 1e-6:
            break

    return {node_list[i]: float(p[i]) for i in range(N)}

def _normalize_scores(scores: Dict[str, float]) -> Dict[str, float]:
    """Min-max normalize a dictionary of scores into [0, 1]."""
    if not scores:
        return {}
    vals = list(scores.values())
    min_v, max_v = min(vals), max(vals)
    if max_v - min_v < 1e-9:
        return {k: 1.0 if max_v > 0 else 0.0 for k in scores}
    return {k: (v - min_v) / (max_v - min_v) for k, v in scores.items()}

def _find_reason_path(G: nx.Graph, source_id: str, target_id: str, nodes_by_id: Dict[str, Node]) -> str:
    """Find short explanation path between seed node and expanded target."""
    if not source_id or not target_id or source_id == target_id:
        return "direct lexical match"
    try:
        path = nx.shortest_path(G, source=source_id, target=target_id)
        if len(path) == 2:
            rel = G[path[0]][path[1]].get("relation", "connected")
            s_name = nodes_by_id.get(path[0], Node(id=path[0], label=path[0])).label
            t_name = nodes_by_id.get(path[1], Node(id=path[1], label=path[1])).label
            return f"{s_name} -> {t_name} ({rel})"
        elif len(path) > 2:
            s_name = nodes_by_id.get(path[0], Node(id=path[0], label=path[0])).label
            mid_name = nodes_by_id.get(path[1], Node(id=path[1], label=path[1])).label
            t_name = nodes_by_id.get(path[-1], Node(id=path[-1], label=path[-1])).label
            return f"{s_name} -> {mid_name} -> {t_name}"
    except Exception:
        pass
    return "graph neighborhood"

def expand_candidates(
    nodes: List[Node],
    edges: List[Edge],
    retrieval_scores: Dict[str, float],
    top_candidates_count: int = CANDIDATES,
) -> List[Candidate]:
    """Fuse lexical BM25 and graph Personalized PageRank to select top candidates with multi-file diversity."""
    nodes_by_id = {n.id: n for n in nodes}
    G = build_graph(nodes, edges)
    ppr_scores = run_ppr(G, retrieval_scores)

    norm_r = _normalize_scores(retrieval_scores)
    norm_g = _normalize_scores(ppr_scores)

    w_r = FUSION.get("retrieval", 0.5)
    w_g = FUSION.get("graph", 0.5)

    fused_scores: Dict[str, float] = {}
    for n in nodes:
        if n.kind not in ("function", "class"):
            continue
        sr = norm_r.get(n.id, 0.0)
        sg = norm_g.get(n.id, 0.0)
        # Prioritize implementation code over tests for candidate edit targets
        base_fused = (w_r * sr) + (w_g * sg)
        if is_test_path(n.file):
            base_fused *= 0.5
        fused_scores[n.id] = base_fused

    # Sort descending by fused score
    sorted_node_ids = sorted(fused_scores.keys(), key=lambda nid: fused_scores[nid], reverse=True)

    # Ensure diversity of files across the candidate set
    selected_ids: List[str] = []
    seen_files: Set[str] = set()

    for nid in sorted_node_ids:
        selected_ids.append(nid)
        seen_files.add(nodes_by_id[nid].file)
        if len(selected_ids) >= top_candidates_count:
            break

    # If fewer than 2 distinct files in candidates, pull in top from other files
    if len(seen_files) < 2 and len(sorted_node_ids) > len(selected_ids):
        for nid in sorted_node_ids[len(selected_ids):]:
            if nodes_by_id[nid].file not in seen_files:
                selected_ids[-1] = nid
                seen_files.add(nodes_by_id[nid].file)
                break

    top_seed_id = max(retrieval_scores.items(), key=lambda kv: kv[1])[0] if retrieval_scores else ""

    candidates: List[Candidate] = []
    for rank, nid in enumerate(selected_ids, start=1):
        reason = _find_reason_path(G, top_seed_id, nid, nodes_by_id)
        candidates.append(
            Candidate(
                alias=f"C{rank}",
                node_id=nid,
                score_retrieval=retrieval_scores.get(nid, 0.0),
                score_graph=ppr_scores.get(nid, 0.0),
                score_fused=fused_scores.get(nid, 0.0),
                reason_path=reason,
            )
        )

    return candidates

def compute_blast_radius(
    candidate_id: str,
    edges: List[Edge],
    nodes_by_id: Dict[str, Node],
) -> Dict[str, Any]:
    """Calculate blast radius for target symbol: depth 2 callers and risk badge."""
    direct_callers: Set[str] = set()
    for e in edges:
        if e.dst == candidate_id and e.relation == "calls":
            direct_callers.add(e.src)

    depth2_callers: Set[str] = set()
    for caller in direct_callers:
        for e in edges:
            if e.dst == caller and e.relation == "calls":
                depth2_callers.add(e.src)

    all_callers = (direct_callers | depth2_callers) - {candidate_id}
    caller_labels = [
        nodes_by_id[cid].label for cid in sorted(all_callers) if cid in nodes_by_id
    ]

    inbound_counts: Dict[str, int] = {}
    for e in edges:
        if e.relation == "calls":
            inbound_counts[e.dst] = inbound_counts.get(e.dst, 0) + 1

    target_count = len(direct_callers)
    all_counts = list(inbound_counts.values()) or [0]
    p50 = float(np.percentile(all_counts, 50))
    p90 = float(np.percentile(all_counts, 90))

    if target_count < p50:
        risk = "low"
    elif target_count <= p90:
        risk = "medium"
    else:
        risk = "high"

    return {
        "node_id": candidate_id,
        "direct_callers": [nodes_by_id[cid].label for cid in sorted(direct_callers) if cid in nodes_by_id][:5],
        "all_callers": caller_labels[:5],
        "total_count": len(all_callers),
        "risk": risk,
    }
