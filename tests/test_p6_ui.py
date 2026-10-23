"""Gate tests for Phase 6: Web UI, live SSE trace, trail SVG, and offline zero-external asset validation."""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from trailhead.models import Candidate, Pick, Trail
from trailhead.render import render_markdown, render_trail_svg
from trailhead.server import app

ROOT_DIR = Path(__file__).parent.parent
MINI_REPO = ROOT_DIR / "tests" / "fixtures" / "mini_repo"
WEB_HTML = ROOT_DIR / "src" / "trailhead" / "web" / "index.html"

client = TestClient(app)

def test_server_health():
    """Verify /api/status returns 200 with required keys: netguard, model, ollama_reachable, env."""
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data and data["status"] == "ok"
    assert "netguard" in data and "blocked_attempts" in data["netguard"]
    assert "model" in data
    assert "ollama_reachable" in data
    assert "env" in data

def test_html_has_no_external_urls():
    """Verify web/index.html contains zero external URLs (no CDNs, fonts, or external scripts)."""
    assert WEB_HTML.exists(), "web/index.html must exist"
    content = WEB_HTML.read_text(encoding="utf-8")

    # Find any http:// or https:// URLs
    url_pattern = re.compile(r"https?://[^\s'\"<>]+")
    urls = url_pattern.findall(content)

    allowed = ["http://127.0.0.1", "http://localhost", "https://127.0.0.1", "https://localhost", "http://www.w3.org"]
    violations = [u for u in urls if not any(u.startswith(a) for a in allowed)]
    assert not violations, f"External URLs found in web/index.html:\n" + "\n".join(violations)

def test_trail_svg_valid():
    """Verify trail SVG parses as valid XML, has circles for picks + neighbors, and contains no <script>."""
    trail = Trail(
        status="ok",
        confidence="high",
        edit=[
            Pick(alias="C1", node_id="app/billing.py::apply_discount", role="edit", why="discount caps", file="app/billing.py"),
            Pick(alias="C2", node_id="app/billing.py::_clamp_total", role="edit", why="floor", file="app/billing.py"),
        ],
        read_first=[
            Pick(alias="C3", node_id="app/billing.py::calculate_tax", role="read_first", why="tax context", file="app/billing.py"),
        ],
        blast=[
            {"target": "app/billing.py::apply_discount", "risk": "low", "total_count": 2, "callers": ["test_apply_discount", "client_code"]},
        ],
    )

    svg_str = render_trail_svg(trail)
    assert "<script" not in svg_str.lower(), "SVG must not contain script tags"

    # Strictly parse as XML
    root = ET.fromstring(svg_str)
    assert root.tag.endswith("svg"), "Root element must be svg"

    # Find circles
    circles = root.findall(".//{http://www.w3.org/2000/svg}circle")
    # Must have circles for picks (3), callers (>=1), legend, guides
    assert len(circles) >= 6, f"Expected at least 6 circles, found {len(circles)}"

def test_sse_event_order():
    """Verify SSE streaming delivers events in order: index, tool_call (at least 4), llm_start, llm_done, trail."""
    mock_chat_response = {
        "content": json.dumps({
            "confidence": "high",
            "picks": [{"id": "C1", "role": "edit", "why": "fixes discount boundary"}]
        }),
        "raw_content": '{"confidence": "high", "picks": [{"id": "C1", "role": "edit", "why": "fixes discount boundary"}]}',
        "tokens_per_sec": 12.5,
    }

    with patch("trailhead.rerank.chat", return_value=mock_chat_response):
        res = client.post(
            "/api/trail",
            json={
                "repo": str(MINI_REPO),
                "issue_text": "A 100% discount makes the invoice total negative.",
                "model": "qwen3:4b",
            },
        )
        assert res.status_code == 200

        text = res.text
        events = []
        for line in text.splitlines():
            if line.startswith("event: "):
                events.append(line.replace("event: ", "").strip())

        assert "index" in events, "SSE stream must emit 'index'"
        tool_calls = [ev for ev in events if ev == "tool_call"]
        assert len(tool_calls) >= 4, f"Expected at least 4 tool_call events, got {len(tool_calls)}"
        assert "llm_start" in events, "SSE stream must emit 'llm_start'"
        assert "llm_done" in events, "SSE stream must emit 'llm_done'"
        assert "trail" in events, "SSE stream must emit 'trail'"

        # Verify relative ordering
        idx_index = events.index("index")
        idx_first_tool = events.index("tool_call")
        idx_llm_start = events.index("llm_start")
        idx_llm_done = events.index("llm_done")
        idx_trail = events.index("trail")

        assert idx_index < idx_first_tool < idx_llm_start < idx_llm_done < idx_trail

def test_ui_graph_only_banner():
    """Verify that when Ollama is unreachable, stream finishes with status graph_only and banner text."""
    with patch("trailhead.config.OLLAMA_HOST", "http://127.0.0.1:54321"), \
         patch("trailhead.llm.OLLAMA_HOST", "http://127.0.0.1:54321"):
        res = client.post(
            "/api/trail",
            json={
                "repo": str(MINI_REPO),
                "issue_text": "Crash on empty token decode",
                "model": "qwen3:4b",
            },
        )
        assert res.status_code == 200
        text = res.text

        trail_data = None
        for chunk in text.split("\n\n"):
            if "event: trail" in chunk:
                for line in chunk.splitlines():
                    if line.startswith("data: "):
                        trail_data = json.loads(line.replace("data: ", ""))

        assert trail_data is not None, "Final trail event must be delivered"
        assert trail_data["status"] == "graph_only"
        assert trail_data["banner"] is not None and len(trail_data["banner"]) > 0
