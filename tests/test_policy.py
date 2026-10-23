"""Static policy enforcement tests to verify 100% offline local operation and security compliance."""
import re
from pathlib import Path
import pytest

FORBIDDEN_HOSTED_APIS = [
    "openai",
    "anthropic",
    "google.generativeai",
    "cohere",
    "mistralai",
    "groq",
    "together",
]

ALLOWED_URL_PREFIXES = [
    "http://127.0.0.1",
    "http://localhost",
    "https://127.0.0.1",
    "https://localhost",
    "http://www.w3.org",
]


def test_no_hosted_api_imports_or_references():
    """Verify src/ contains zero references to external hosted LLM provider libraries."""
    src_dir = Path(__file__).resolve().parent.parent / "src"
    py_files = list(src_dir.rglob("*.py"))
    assert len(py_files) > 0, "No python files found in src/"

    violations = []
    for f in py_files:
        content = f.read_text(encoding="utf-8", errors="replace")
        for api in FORBIDDEN_HOSTED_APIS:
            # Check for import statements or explicit API usage strings
            if re.search(rf"\b(import\s+{api}|from\s+{api}\b|['\"]{api}['\"])", content):
                violations.append(f"{f.name}: references forbidden API '{api}'")

    assert not violations, f"Hosted LLM API violations found:\n" + "\n".join(violations)

def test_no_external_urls_in_src():
    """Verify src/ python files contain no external internet URLs (only localhost/127.0.0.1)."""
    src_dir = Path(__file__).resolve().parent.parent / "src"
    py_files = list(src_dir.rglob("*.py"))

    violations = []
    url_pattern = re.compile(r"https?://[a-zA-Z0-9.\-_:]+")

    for f in py_files:
        content = f.read_text(encoding="utf-8", errors="replace")
        for match in url_pattern.finditer(content):
            url = match.group(0)
            if not any(url.startswith(prefix) for prefix in ALLOWED_URL_PREFIXES):
                violations.append(f"{f.name}: external URL found '{url}'")

    assert not violations, f"External URL violations found:\n" + "\n".join(violations)

def test_no_hardcoded_secrets_in_src():
    """Verify src/ does not contain hardcoded API tokens or secret keys."""
    src_dir = Path(__file__).resolve().parent.parent / "src"
    py_files = list(src_dir.rglob("*.py"))

    secret_patterns = [
        re.compile(r"sk-[a-zA-Z0-9]{20,}"),
        re.compile(r"ghp_[a-zA-Z0-9]{20,}"),
        re.compile(r"(api_key|secret_key|auth_token)\s*=\s*['\"][a-zA-Z0-9_\-]{16,}['\"]", re.IGNORECASE),
    ]

    violations = []
    for f in py_files:
        content = f.read_text(encoding="utf-8", errors="replace")
        for pat in secret_patterns:
            matches = pat.findall(content)
            if matches:
                violations.append(f"{f.name}: potential hardcoded secret pattern found")

    assert not violations, f"Secret key violations found:\n" + "\n".join(violations)

def test_gitignore_contains_env():
    """Verify .env is excluded in .gitignore."""
    root = Path(__file__).resolve().parent.parent
    gitignore = root / ".gitignore"
    assert gitignore.exists(), "Missing .gitignore file"
    lines = [line.strip() for line in gitignore.read_text(encoding="utf-8").splitlines()]
    assert ".env" in lines, ".env must be explicitly in .gitignore"

def test_env_example_has_placeholders_only():
    """Verify .env.example contains only non-secret placeholders."""
    root = Path(__file__).resolve().parent.parent
    env_example = root / ".env.example"
    assert env_example.exists(), "Missing .env.example file"
    content = env_example.read_text(encoding="utf-8")
    assert "sk-" not in content
    assert "ghp_" not in content
    assert "secret" not in content.lower() or "placeholders" in content.lower()
