"""Extract pre-PR checklist and verification steps from repo tooling and CONTRIBUTING.md."""
import re
from pathlib import Path
from typing import List, Union

def extract_checklist(repo_root: Union[str, Path]) -> List[str]:
    """Parse CONTRIBUTING.md and tooling configs for developer PR requirements."""
    root = Path(repo_root)
    checklist: List[str] = []

    # 1. Inspect CONTRIBUTING.md
    for name in ("CONTRIBUTING.md", "CONTRIBUTING.rst", "contributing.md", ".github/CONTRIBUTING.md"):
        contrib_path = root / name
        if contrib_path.exists():
            try:
                content = contrib_path.read_text(encoding="utf-8", errors="replace")
                keywords = [
                    "test", "pytest", "lint", "format", "ruff", "black", "flake8",
                    "changelog", "sign-off", "dco", "commit message", "branch",
                ]
                for line in content.splitlines():
                    cleaned = line.strip().lstrip("#*- \t")
                    if 15 <= len(cleaned) <= 180:
                        lower = cleaned.lower()
                        if any(kw in lower for kw in keywords):
                            if cleaned not in checklist:
                                checklist.append(cleaned)
                    if len(checklist) >= 4:
                        break
            except Exception:
                pass
            break

    # 2. Inspect project tooling configurations
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            txt = pyproject.read_text(encoding="utf-8", errors="replace").lower()
            if "tool.ruff" in txt:
                checklist.append("Run 'ruff check .' to verify formatting and linting")
            if "tool.black" in txt:
                checklist.append("Run 'black --check .' to verify code formatting")
            if "tool.pytest" in txt or "pytest" in txt:
                checklist.append("Run 'pytest' to execute unit and regression tests")
        except Exception:
            pass

    pre_commit = root / ".pre-commit-config.yaml"
    if pre_commit.exists():
        checklist.append("Run 'pre-commit run --all-files' before opening your pull request")

    tox_ini = root / "tox.ini"
    if tox_ini.exists():
        checklist.append("Run 'tox' to execute multi-environment matrix tests")

    # Fallback checklist if none detected
    if not checklist:
        checklist = [
            "Run test suite: `pytest`",
            "Verify linting and formatting standards",
            "Review git diff to ensure no unrelated changes are included",
        ]

    return checklist[:6]
