"""Evaluation metrics for issue localization benchmarks: Hit@k, Recall@k, and MRR."""
from typing import List, Sequence

def hit_at_k(predictions: Sequence[str], gold: Sequence[str], k: int) -> float:
    """Return 1.0 if any gold item is in top-k predictions, else 0.0."""
    if not gold or not predictions or k <= 0:
        return 0.0
    top_k = set(predictions[:k])
    gold_set = set(gold)
    return 1.0 if bool(top_k & gold_set) else 0.0

def recall_at_k(predictions: Sequence[str], gold: Sequence[str], k: int) -> float:
    """Return fraction of gold items retrieved in top-k predictions."""
    if not gold:
        return 0.0
    if not predictions or k <= 0:
        return 0.0
    top_k = set(predictions[:k])
    gold_set = set(gold)
    return len(top_k & gold_set) / float(len(gold_set))

def mrr(predictions: Sequence[str], gold: Sequence[str]) -> float:
    """Mean Reciprocal Rank: 1 / (rank of first relevant item)."""
    if not gold or not predictions:
        return 0.0
    gold_set = set(gold)
    for rank, pred in enumerate(predictions, start=1):
        if pred in gold_set:
            return 1.0 / float(rank)
    return 0.0
