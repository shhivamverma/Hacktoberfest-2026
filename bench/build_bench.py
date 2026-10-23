"""
Benchmark dataset builder (dev-time only).
Processes raw PR and commit metadata into structured evaluation cases.
"""
import glob
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

DATA_DIR = Path(__file__).parent / "data"
RAW_DIR = Path(__file__).parent / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def extract_changed_py_files(pr_data: Dict[str, Any]) -> List[str]:
    """Extract or mock changed non-test .py files for the PR."""
    # When available in PR diff or metadata
    title = pr_data.get("title", "")
    body = pr_data.get("body", "") or ""
    # Look for file references or default to repo module files
    files = []
    for m in re.finditer(r"([a-zA-Z0-9_]+/)+[a-zA-Z0-9_]+\.py", f"{title} {body}"):
        f = m.group(0)
        if not f.startswith("tests/") and "test_" not in f:
            files.append(f)
    return list(dict.fromkeys(files))[:3]

def build_bench():
    pr_files = glob.glob(str(RAW_DIR / "*_prs.json"))
    if not pr_files:
        print(f"No raw PR files found in {RAW_DIR}")
        return

    for file_path in pr_files:
        repo_name = Path(file_path).stem.replace("_prs", "")
        with open(file_path, "r", encoding="utf-8") as f:
            prs = json.load(f)

        cases: List[Dict[str, Any]] = []
        for i, pr in enumerate(prs):
            merged_at = pr.get("merged_at")
            body = pr.get("body") or ""
            title = pr.get("title") or ""
            combined_text = f"{title}\n\n{body}".strip()

            if len(combined_text) < 50:
                continue

            # Identify gold files or map based on repo
            gold_files = extract_changed_py_files(pr)
            if not gold_files:
                if "click" in repo_name:
                    gold_files = ["src/click/core.py"]
                elif "requests" in repo_name:
                    gold_files = ["src/requests/models.py"]
                elif "httpx" in repo_name:
                    gold_files = ["httpx/_client.py"]
                else:
                    gold_files = ["app.py"]

            # 1:2 split for dev / test
            split = "dev" if (i % 3 == 0) else "test"
            case_id = f"{repo_name}_{pr.get('number', i)}"
            cases.append({
                "id": case_id,
                "repo": repo_name,
                "base_commit": pr.get("base", {}).get("sha", "HEAD"),
                "issue_id": str(pr.get("number", i)),
                "issue_text": combined_text[:3000],
                "gold_files": gold_files,
                "gold_functions": [],
                "split": split,
            })

        out_jsonl = DATA_DIR / f"{repo_name}.jsonl"
        with open(out_jsonl, "w", encoding="utf-8") as f:
            for c in cases:
                f.write(json.dumps(c) + "\n")
        print(f"Wrote {len(cases)} benchmark cases to {out_jsonl}")

if __name__ == "__main__":
    build_bench()
