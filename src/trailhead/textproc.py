"""Text processing: identifier splitting, tokenization, hint and traceback extraction."""
import re
from typing import List, Optional, Set
from trailhead.models import Hint

STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't",
    "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have",
    "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers", "herself",
    "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is",
    "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours",
    "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should",
    "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their", "theirs", "them",
    "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've",
    "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we",
    "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's", "where",
    "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would",
    "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves",
    "def", "class", "return", "import", "from", "self", "none", "true", "false",
}

def split_identifiers(text: str, remove_stopwords: bool = True) -> List[str]:
    """
    Split snake_case, camelCase, PascalCase, numbers and punctuation.
    Example: 'getUserName_v2' -> ['get', 'user', 'name', 'v2']
    """
    if not text:
        return []
    # Replace separators with spaces
    s = re.sub(r"[_\-\./\\:]+", " ", text)
    # Insert space before camelCase transitions
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    # Tokenize words/digits
    tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9]+", s)]
    if remove_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS and len(t) > 1]
    return tokens

def extract_hints(issue_text: str) -> List[Hint]:
    """Extract actionable hints from issue text: tracebacks, backticks, errors, and paths."""
    hints: List[Hint] = []
    if not issue_text:
        return hints

    # 1. Python tracebacks: File "path/to/file.py", line 123, in func_name
    tb_pattern = re.compile(
        r'File\s+["\'](?P<file>[^"\']+)["\'],\s+line\s+(?P<line>\d+)(?:,\s+in\s+(?P<func>\w+))?'
    )
    for m in tb_pattern.finditer(issue_text):
        f = m.group("file").replace("\\", "/")
        line = int(m.group("line"))
        func = m.group("func")
        hints.append(
            Hint(
                kind="trace",
                value=m.group(0),
                file=f,
                line=line,
                func=func,
            )
        )

    # 2. Backtick identifiers: `identifier`
    backtick_pattern = re.compile(r"`([^`\n]+)`")
    for m in backtick_pattern.finditer(issue_text):
        val = m.group(1).strip()
        if val and not val.startswith("http"):
            hints.append(Hint(kind="identifier", value=val))

    # 3. Quoted error strings: 'Invalid token' or "Malformed token"
    quoted_pattern = re.compile(r'["\']([^"\'\n]{4,80})["\']')
    for m in quoted_pattern.finditer(issue_text):
        val = m.group(1).strip()
        # Avoid file paths already captured
        if not re.search(r"\.(?:py|json|md|txt)$", val):
            hints.append(Hint(kind="error", value=val))

    # 4. Explicit file paths: app/tokens.py or src/click/core.py
    path_pattern = re.compile(r"(?:[a-zA-Z0-9_\-\.]+/)+[a-zA-Z0-9_\-\.]+\.(?:py|json|toml|yaml|yml)")
    for m in path_pattern.finditer(issue_text):
        val = m.group(0).replace("\\", "/")
        hints.append(Hint(kind="path", value=val, file=val))

    return hints
