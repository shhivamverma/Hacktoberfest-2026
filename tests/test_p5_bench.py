"""Gate tests for Phase 5: Evaluation and Proof (Benchmark, Ablation, and Hallucination Guardrails)."""
import glob
import json
import subprocess
import sys
from pathlib import Path
import pytest

from bench.metrics import hallucination_rate, hit_at_k, mrr, top_k_stability

ROOT_DIR = Path(__file__).parent.parent
BENCH_DATA_DIR = ROOT_DIR / "bench" / "data"
REPOS_DIR = ROOT_DIR / "bench" / "repos"
RESULTS_DIR = ROOT_DIR / "bench" / "results"

def test_bench_case_schema():
    """Verify all benchmark cases have required fields, valid split, non-empty gold files that exist on disk."""
    case_files = glob.glob(str(BENCH_DATA_DIR / "*.jsonl"))
    assert len(case_files) >= 2, "Must have benchmark jsonl files"

    total_cases = 0
    for cf in case_files:
        with open(cf, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                case = json.loads(line)
                total_cases += 1
                assert "repo" in case and case["repo"]
                assert "base_commit" in case and case["base_commit"]
                assert "issue_text" in case and len(case["issue_text"]) > 20
                assert "gold_files" in case and len(case["gold_files"]) > 0
                assert case.get("split") in ("dev", "test")

                # Verify gold files exist in repo
                repo_slug = case["repo"].split("_")[-1]
                repo_path = REPOS_DIR / repo_slug
                if repo_path.exists():
                    for gf in case["gold_files"]:
                        p = repo_path / gf
                        assert p.exists(), f"Gold file {gf} missing in {repo_path}"

    assert total_cases >= 24, f"Target is at least 24 cases, found {total_cases}"

def test_no_dev_test_leak():
    """Verify thresholds in config.py were tuned strictly on dev case IDs and are disjoint from test cases."""
    tuning_file = RESULTS_DIR / "dev_tuning.json"
    assert tuning_file.exists(), "dev_tuning.json must exist from running bench/tune.py"

    with open(tuning_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    dev_ids = set(data.get("dev_case_ids", []))
    assert len(dev_ids) > 0, "dev_case_ids must not be empty"

    # Collect test IDs
    test_ids = set()
    for cf in glob.glob(str(BENCH_DATA_DIR / "*.jsonl")):
        with open(cf, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    c = json.loads(line)
                    if c.get("split") == "test":
                        test_ids.add(c["id"])

    assert len(test_ids) > 0, "test_ids must not be empty"
    overlap = dev_ids.intersection(test_ids)
    assert not overlap, f"Dev/test data leak detected! Overlapping IDs: {overlap}"

def test_hallucination_metric():
    """Verify that a handcrafted answer naming a non-existent function counts as 1 of 1 (100% hallucination)."""
    valid_symbols = ["apply_discount", "_clamp_total", "create_invoice"]
    hallucinated_answers = ["fake_discount_validator"]

    rate = hallucination_rate(hallucinated_answers, valid_symbols)
    assert rate == 1.0, f"Expected 1.0 (1 of 1), got {rate}"

    valid_answers = ["apply_discount"]
    valid_rate = hallucination_rate(valid_answers, valid_symbols)
    assert valid_rate == 0.0

def test_run_bench_smoke():
    """Run bench smoke test with --limit 2 --runs 1 --systems bm25,graph; assert completes and writes results."""
    cmd = [
        sys.executable,
        str(ROOT_DIR / "bench" / "run_bench.py"),
        "--systems", "bm25,graph",
        "--split", "dev",
        "--limit", "2",
        "--runs", "1",
    ]
    res = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, f"Benchmark smoke run failed:\n{res.stderr}\n{res.stdout}"

    results_file = RESULTS_DIR / "RESULTS.md"
    assert results_file.exists(), "RESULTS.md was not generated"

def test_results_file_has_required_columns():
    """Verify RESULTS.md has required columns: hit@1, hit@3, hit@5, MRR, tok/s, hallucination rate, and runs."""
    results_file = RESULTS_DIR / "RESULTS.md"
    assert results_file.exists(), "Missing RESULTS.md"

    content = results_file.read_text(encoding="utf-8").lower()
    required_terms = [
        "hit@1",
        "hit@3",
        "hit@5",
        "mrr",
        "tok/s",
        "hallucination rate",
        "runs",
        "external apis",
    ]
    for term in required_terms:
        assert term in content, f"Required column or section '{term}' missing in RESULTS.md"
