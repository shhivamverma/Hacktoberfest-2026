#!/usr/bin/env bash
# Verification script for 100% offline local operation
set -e

echo "=== Trailhead Offline Verification ==="

# 1. Run static policy test (verifies no hosted APIs, no external URLs)
echo "[1/4] Running static security & offline policy scans..."
uv run pytest -v tests/test_policy.py

# 2. Verify netguard blocks external socket connections
echo "[2/4] Verifying netguard runtime socket interception..."
uv run pytest -v tests/test_p1_netguard.py

# 3. Verify web/index.html has zero external URLs
echo "[3/4] Verifying UI has zero external URLs or CDNs..."
uv run pytest -v tests/test_p6_ui.py -k "test_html_has_no_external_urls"

# 4. Run end-to-end trail on mini_repo offline
echo "[4/4] Executing offline trail generation..."
uv run python -c "from trailhead.pipeline import run_pipeline; t = run_pipeline('tests/fixtures/mini_repo', 'Password reset token error', use_llm=False); assert t.netguard['blocked_attempts'] == 0; print('Offline verification succeeded! Blocked external attempts:', t.netguard['blocked_attempts'])"

echo "=== ALL OFFLINE CHECKS PASSED ==="
