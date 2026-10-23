"""Trailhead configuration and constants."""

MODEL_MAIN = "qwen3:4b"
MODEL_FAST = "qwen3:1.7b"
EMBED_MODEL = "nomic-embed-text"
OLLAMA_HOST = "http://127.0.0.1:11434"

NUM_CTX = 4096
NUM_PREDICT = 320
SEED = 7
TEMPERATURE = 0.0
LLM_TIMEOUT_S = 90
LLM_RETRIES = 1

TOP_SEEDS = 8
CANDIDATES = 12
SNIPPET_LINES = 14
ISSUE_CHARS = 1500

PPR_ALPHA = 0.85
EDGE_WEIGHTS = {
    "calls": 1.0,
    "inherits": 0.8,
    "contains": 0.7,
    "imports": 0.5,
    "other": 0.3,
}

FUSION = {"retrieval": 0.5, "graph": 0.5}  # tuned on dev set
STACKTRACE_BOOST = 5.0
ABSTAIN_MARGIN = 0.08  # tuned on dev
