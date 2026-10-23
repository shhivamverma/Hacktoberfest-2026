"""LLM candidate reranker, query rewriter, verification guardrails, and abstain handler."""
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from trailhead.config import ABSTAIN_MARGIN, CANDIDATES, ISSUE_CHARS, MODEL_MAIN, TEMPERATURE
from trailhead.graphio import snippet
from trailhead.llm import chat
from trailhead.models import Candidate, Hint, Node, Pick

REWRITE_SYSTEM = (
    "List up to 8 identifiers or words a developer might have used in the CODE for the "
    "behaviour described in the issue (function names, module words, error strings). JSON only."
)

REWRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "keywords": {
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string", "maxLength": 30},
        }
    },
    "required": ["keywords"],
}

RERANK_SYSTEM = (
    "You locate where in a code repository a GitHub issue should be fixed.\n"
    "You are given the issue and candidate code units labelled C1..Cn.\n"
    "Choose at most 5. Mark each as \"edit\" (code that likely must change) or\n"
    "\"read_first\" (context needed to understand it). Use only the given ids.\n"
    "Give a short reason (max 20 words) that cites something visible in the snippet.\n"
    "If the evidence is weak, set confidence to \"low\". Output JSON only."
)

def rewrite_query(issue_text: str, model: str = MODEL_MAIN) -> List[str]:
    """Call local LLM to extract up to 8 developer code identifiers for the issue."""
    messages = [
        {"role": "system", "content": REWRITE_SYSTEM},
        {"role": "user", "content": issue_text[:ISSUE_CHARS]},
    ]
    try:
        res = chat(messages=messages, schema=REWRITE_SCHEMA, model=model, temperature=0.0)
        data = json.loads(res["content"])
        return data.get("keywords", [])
    except Exception:
        return []

def build_rerank_schema(candidate_aliases: List[str]) -> Dict[str, Any]:
    """Dynamically construct JSON schema constrained strictly to candidate aliases."""
    return {
        "type": "object",
        "properties": {
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "picks": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "enum": candidate_aliases},
                        "role": {"type": "string", "enum": ["edit", "read_first"]},
                        "why": {"type": "string", "maxLength": 160},
                    },
                    "required": ["id", "role", "why"],
                },
            },
        },
        "required": ["confidence", "picks"],
    }

def format_candidates_prompt(
    candidates: List[Candidate],
    nodes_by_id: Dict[str, Node],
    repo_root: Path,
) -> str:
    """Format candidate code blocks with aliases C1..Cn and on-disk snippets."""
    blocks: List[str] = []
    for c in candidates:
        n = nodes_by_id.get(c.node_id)
        if not n:
            continue
        rel_path = n.file
        lines_str = f" (calls: {c.reason_path})" if c.reason_path and "calls" in c.reason_path else ""
        header = f"{c.alias}  {rel_path}  {n.label}{lines_str}"
        snip = snippet(n, repo_root, max_lines=14)
        blocks.append(f"{header}\n{snip}")
    return "\n\n".join(blocks)

def verify_and_build_picks(
    raw_picks: List[Dict[str, Any]],
    candidate_map: Dict[str, Candidate],
    nodes_by_id: Dict[str, Node],
    repo_root: Path,
) -> Tuple[List[Pick], List[Pick]]:
    """
    Apply verification rules V1, V2, V3:
    V1: id must exist in candidates.
    V2: file exists and span within file bounds, else downgrade to 'file'.
    V3: snippet read independently from disk.
    """
    edit_picks: List[Pick] = []
    read_first_picks: List[Pick] = []

    for item in raw_picks:
        alias = item.get("id", "")
        # V1: invented alias check
        if alias not in candidate_map:
            continue

        cand = candidate_map[alias]
        node = nodes_by_id.get(cand.node_id)
        if not node:
            continue

        role = item.get("role", "read_first")
        why = (item.get("why") or "")[:160]

        # V2: check file existence and span
        file_path = repo_root / node.file
        level = "span"
        start, end = node.start, node.end

        if not file_path.exists():
            level = "file"
            start, end = None, None
        else:
            try:
                line_count = len(file_path.read_text(encoding="utf-8", errors="replace").splitlines())
                if start is None or end is None or start < 1 or end > line_count or start > end:
                    level = "file"
                    start, end = None, None
            except Exception:
                level = "file"
                start, end = None, None

        # V3: Snippet re-read independently from disk
        snip = snippet(node, repo_root, max_lines=14)

        pick = Pick(
            alias=alias,
            node_id=node.id,
            role=role if role in ("edit", "read_first") else "read_first",
            why=why,
            file=node.file,
            start=start,
            end=end,
            snippet=snip,
            level=level,
        )

        if pick.role == "edit":
            edit_picks.append(pick)
        else:
            read_first_picks.append(pick)

    return edit_picks, read_first_picks

def generate_clarifying_question(
    issue_text: str,
    top_candidates: List[Candidate],
    nodes_by_id: Dict[str, Node],
    model: str = MODEL_MAIN,
) -> str:
    """Draft a clarifying question when evidence is ambiguous (V4 abstain mode)."""
    fallback = (
        "Could you clarify the expected behavior or share a minimal reproduction example "
        "or stacktrace to help pinpoint the issue?"
    )
    names = [nodes_by_id[c.node_id].label for c in top_candidates[:3] if c.node_id in nodes_by_id]
    names_str = ", ".join(names)
    prompt = (
        f"The issue '{issue_text[:300]}' is ambiguous across areas: {names_str}. "
        f"Write one concise clarifying question (max 180 chars) to the maintainer. Output only the question."
    )
    schema = {
        "type": "object",
        "properties": {"question": {"type": "string", "maxLength": 200}},
        "required": ["question"],
    }
    try:
        res = chat(
            messages=[{"role": "user", "content": prompt}],
            schema=schema,
            model=model,
            temperature=0.0,
            timeout=20.0,
        )
        data = json.loads(res["content"])
        return data.get("question", fallback)
    except Exception:
        return fallback

def rerank_candidates(
    candidates: List[Candidate],
    nodes_by_id: Dict[str, Node],
    issue_text: str,
    hints: List[Hint],
    repo_root: Path,
    model: str = MODEL_MAIN,
) -> Dict[str, Any]:
    """
    Rerank candidate symbols using local LLM, enforce guardrails V1..V5,
    and return structured result dictionary.
    """
    if not candidates:
        return {
            "status": "graph_only",
            "confidence": "low",
            "edit": [],
            "read_first": [],
            "explore_areas": [],
            "banner": "No candidates available for reranking.",
        }

    candidate_aliases = [c.alias for c in candidates]
    candidate_map = {c.alias: c for c in candidates}
    schema = build_rerank_schema(candidate_aliases)

    prompt_user = (
        f"ISSUE:\n{issue_text[:ISSUE_CHARS]}\n\n"
        f"CANDIDATES:\n{format_candidates_prompt(candidates, nodes_by_id, repo_root)}"
    )

    messages = [
        {"role": "system", "content": RERANK_SYSTEM},
        {"role": "user", "content": prompt_user},
    ]

    llm_succeeded = False
    data: Dict[str, Any] = {}
    banner = ""

    # Attempt 1
    try:
        res = chat(messages=messages, schema=schema, model=model, temperature=TEMPERATURE)
        data = json.loads(res["content"])
        llm_succeeded = True
    except Exception:
        banner = "Ollama local model unavailable or timed out; returned graph-verified ranking."

    if not llm_succeeded or not data.get("picks"):
        return {
            "status": "graph_only",
            "confidence": "medium",
            "edit": [],
            "read_first": [],
            "explore_areas": [],
            "banner": banner or "Model returned empty selection; fell back to graph ranking.",
        }

    raw_picks = data.get("picks", [])
    confidence = data.get("confidence", "medium")

    # Apply V1, V2, V3
    edit_picks, read_first_picks = verify_and_build_picks(raw_picks, candidate_map, nodes_by_id, repo_root)

    # V1 check: if all picks were invalid/invented, retry once with strict instruction
    if not edit_picks and not read_first_picks:
        retry_messages = list(messages) + [
            {
                "role": "user",
                "content": f"ERROR: The previous response used invalid IDs. You MUST only pick from: {', '.join(candidate_aliases)}. Output JSON only.",
            }
        ]
        try:
            res_retry = chat(messages=retry_messages, schema=schema, model=model, temperature=0.0)
            data_retry = json.loads(res_retry["content"])
            raw_picks_retry = data_retry.get("picks", [])
            edit_picks, read_first_picks = verify_and_build_picks(raw_picks_retry, candidate_map, nodes_by_id, repo_root)
            confidence = data_retry.get("confidence", confidence)
        except Exception:
            pass

    # If still all invalid after retry, fall back to graph_only
    if not edit_picks and not read_first_picks:
        return {
            "status": "graph_only",
            "confidence": "low",
            "edit": [],
            "read_first": [],
            "explore_areas": [],
            "banner": "Model picks failed candidate verification after retry; fell back to graph ranking.",
        }


    # V4 Abstain check:
    # Abstain if confidence is low, or if (top-1 fused - top-2 fused) < ABSTAIN_MARGIN with no stacktrace
    has_trace = any(h.kind == "trace" for h in hints)
    fused_margin = 0.0
    if len(candidates) >= 2:
        fused_margin = candidates[0].score_fused - candidates[1].score_fused

    should_abstain = (
        confidence == "low"
        or (len(issue_text.strip()) < 30 and not has_trace)
        or (fused_margin < ABSTAIN_MARGIN and not has_trace and confidence != "high")
    )

    if should_abstain:
        # Generate 3 distinct explore areas (top files or communities)
        explore_files = list(dict.fromkeys(nodes_by_id[c.node_id].file for c in candidates if c.node_id in nodes_by_id))
        explore_areas = explore_files[:3]
        while len(explore_areas) < 3:
            explore_areas.append(f"Component area {len(explore_areas) + 1}")

        clarifying_q = generate_clarifying_question(issue_text, candidates, nodes_by_id, model=model)

        return {
            "status": "low_confidence",
            "confidence": "low",
            "edit": edit_picks,
            "read_first": read_first_picks,
            "explore_areas": explore_areas[:3],
            "clarifying_question": clarifying_q,
            "banner": "Confidence is low. Suggested 3 exploration areas and a draft clarifying question.",
        }

    return {
        "status": "ok",
        "confidence": confidence,
        "edit": edit_picks,
        "read_first": read_first_picks,
        "explore_areas": [],
        "clarifying_question": None,
        "banner": "",
    }
