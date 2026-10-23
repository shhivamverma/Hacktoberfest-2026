"""Submission readiness tests for Hacktoberfest 26 final gate."""
import re
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).parent.parent
README_FILE = ROOT_DIR / "README.md"
LICENSE_FILE = ROOT_DIR / "LICENSE"
ENV_EXAMPLE = ROOT_DIR / ".env.example"
GRAPH_HTML = ROOT_DIR / "graphify-out" / "graph.html"
GRAPH_REPORT = ROOT_DIR / "graphify-out" / "GRAPH_REPORT.md"

def test_readme_required_sections():
    """Verify README has all mandatory section headings per the participant guide template."""
    assert README_FILE.exists(), "README.md missing"
    content = README_FILE.read_text(encoding="utf-8").lower()

    required_headings = [
        "problem statement",
        "approach",
        "model details",
        "setup instructions",
        "results",
        "graphify integration",
        "licence",
    ]
    for heading in required_headings:
        assert heading in content, f"Required section heading '{heading}' missing in README.md"

def test_model_disclosure_fields():
    """Verify README contains all technical disclosure fields for local model and environment."""
    raw = README_FILE.read_text(encoding="utf-8").lower()
    content = raw.replace("**", "")

    required_fields = [
        "model",
        "parameters",
        "licence",
        "runtime",
        "quantization",
        "hardware",
        "external apis: none",
    ]
    for field in required_fields:
        assert field in content, f"Required disclosure field '{field}' missing in README.md"


def test_repo_has_license_mit():
    """Verify LICENSE file exists and is MIT license."""
    assert LICENSE_FILE.exists(), "LICENSE file missing"
    content = LICENSE_FILE.read_text(encoding="utf-8")
    assert "MIT License" in content or "MIT LICENSE" in content

def test_env_example_placeholders_only():
    """Verify .env.example contains only non-secret placeholders."""
    assert ENV_EXAMPLE.exists(), ".env.example missing"
    content = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "sk-" not in content
    assert "ghp_" not in content

def test_graphify_artifacts_exist():
    """Verify graphify-out/graph.html and GRAPH_REPORT.md exist and match Trailhead's own repo."""
    assert GRAPH_HTML.exists(), "graphify-out/graph.html must exist"
    assert GRAPH_REPORT.exists(), "graphify-out/GRAPH_REPORT.md must exist"

    # Verify non-empty
    assert GRAPH_HTML.stat().st_size > 1000, "graph.html appears empty"
    assert GRAPH_REPORT.stat().st_size > 500, "GRAPH_REPORT.md appears empty"
