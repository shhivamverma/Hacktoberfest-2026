"""Generic utility functions."""
import re
from datetime import datetime

def parse_date(datestr: str) -> datetime:
    """Parse ISO formatted date string."""
    return datetime.fromisoformat(datestr)

def slugify(text: str) -> str:
    """Generate URL-friendly string identifier."""
    cleaned = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", cleaned)

def retry(func, attempts: int = 3):
    """Invoke callable with automatic retry."""
    for _ in range(attempts):
        try:
            return func()
        except Exception:
            pass
    return None
