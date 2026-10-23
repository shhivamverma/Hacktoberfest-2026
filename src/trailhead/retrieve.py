"""BM25 lexical retrieval and stacktrace boosting over repository code nodes."""
import math
from collections import Counter
from typing import Dict, List, Optional, Tuple

from trailhead.config import STACKTRACE_BOOST
from trailhead.models import Hint, Node
from trailhead.textproc import extract_hints, split_identifiers

class BM25:
    """Okapi BM25 implementation for indexing and scoring code node documents."""

    def __init__(self, corpus: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.doc_lens = [len(doc) for doc in corpus]
        self.avg_dl = sum(self.doc_lens) / self.corpus_size if self.corpus_size > 0 else 1.0

        # Precompute document frequencies
        self.df: Dict[str, int] = Counter()
        self.doc_freqs: List[Dict[str, int]] = []
        for doc in corpus:
            freqs = Counter(doc)
            self.doc_freqs.append(freqs)
            for term in freqs:
                self.df[term] += 1

        # Precompute IDF
        self.idf: Dict[str, float] = {}
        for term, freq in self.df.items():
            self.idf[term] = math.log(((self.corpus_size - freq + 0.5) / (freq + 0.5)) + 1.0)

    def score(self, query: List[str]) -> List[float]:
        """Compute BM25 scores for all documents given tokenized query."""
        scores = [0.0] * self.corpus_size
        for term in query:
            if term not in self.idf:
                continue
            idf_val = self.idf[term]
            for i, freqs in enumerate(self.doc_freqs):
                tf = freqs.get(term, 0)
                if tf > 0:
                    denom = tf + self.k1 * (1.0 - self.b + self.b * (self.doc_lens[i] / self.avg_dl))
                    scores[i] += idf_val * (tf * (self.k1 + 1.0)) / denom
        return scores

def build_node_document(node: Node) -> List[str]:
    """Build token document for a node: weighted label + path tokens + code snippet."""
    label_tokens = split_identifiers(node.label) * 3
    file_tokens = split_identifiers(node.file) * 2
    body_tokens = split_identifiers(node.text)
    return label_tokens + file_tokens + body_tokens

def retrieve_nodes(
    nodes: List[Node],
    issue_text: str,
    hints: Optional[List[Hint]] = None,
    stacktrace_boost: float = STACKTRACE_BOOST,
) -> Dict[str, float]:
    """Score nodes against issue text using BM25 and apply stacktrace boosts."""
    if not nodes:
        return {}

    if hints is None:
        hints = extract_hints(issue_text)

    # Build tokenized query
    query_tokens = split_identifiers(issue_text)
    for h in hints:
        if h.kind in ("identifier", "error"):
            query_tokens.extend(split_identifiers(h.value) * 2)

    # Build corpus
    corpus = [build_node_document(n) for n in nodes]
    bm25 = BM25(corpus)
    scores = bm25.score(query_tokens)

    node_scores: Dict[str, float] = {}
    for i, n in enumerate(nodes):
        raw_score = scores[i]

        # Stack-trace boost: check if node matches traceback frame
        for h in hints:
            if h.kind == "trace":
                h_file = (h.file or "").replace("\\", "/")
                n_file = (n.file or "").replace("\\", "/")
                
                file_match = h_file.endswith(n_file) or n_file.endswith(h_file)
                func_match = bool(h.func and (h.func == n.label or h.func in n.id))
                line_match = False
                if h.line is not None and n.start is not None and n.end is not None:
                    line_match = (n.start <= h.line <= n.end)

                if file_match and (func_match or line_match):
                    raw_score += stacktrace_boost

        node_scores[n.id] = raw_score

    return node_scores
