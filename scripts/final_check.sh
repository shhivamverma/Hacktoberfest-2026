#!/usr/bin/env bash
# Final submission verification script for Trailhead
set -e

echo "=== Running Trailhead Final Submission Checks ==="

# 1. Run all unit and gate tests
echo "[1/6] Running full test suite (Phases 1-6)..."
uv run pytest -m "not ollama"

# 2. Run static policy & secret scans
echo "[2/6] Running static security & offline policy scans..."
uv run pytest tests/test_policy.py

# 3. Verify submission readiness tests
echo "[3/6] Verifying submission metadata and artifacts..."
uv run pytest tests/test_submission_readiness.py

# 4. Check git status
echo "[4/6] Checking git working tree status..."
git status --short

# 5. Check required artifact files exist
echo "[5/6] Confirming presence of submission files..."
test -f README.md || { echo "Missing README.md"; exit 1; }
test -f LICENSE || { echo "Missing LICENSE"; exit 1; }
test -f THIRD_PARTY.md || { echo "Missing THIRD_PARTY.md"; exit 1; }
test -f RUN_ENV.json || { echo "Missing RUN_ENV.json"; exit 1; }
test -f bench/results/RESULTS.md || { echo "Missing RESULTS.md"; exit 1; }
test -f graphify-out/graph.html || { echo "Missing graphify-out/graph.html"; exit 1; }
test -f graphify-out/GRAPH_REPORT.md || { echo "Missing graphify-out/GRAPH_REPORT.md"; exit 1; }

echo "=== ALL SUBMISSION READINESS CHECKS PASSED ==="
