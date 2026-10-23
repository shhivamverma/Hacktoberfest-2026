"""Retrieve recent git commit context for repository files."""
import subprocess
from pathlib import Path
from typing import List, Union

def get_recent_commits(repo_root: Union[str, Path], file_rel_path: str, max_commits: int = 3) -> List[str]:
    """Return last N commit summaries touching the given relative file path."""
    try:
        res = subprocess.run(
            ["git", "log", f"-n{max_commits}", "--format=%h %s", "--", file_rel_path],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
    except Exception:
        pass
    return []
