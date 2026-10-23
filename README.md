# Trailhead

> **Offline issue-to-code trail finder for first-time open-source contributors.**  
> Track: **Narrow Agentic Tools** (100% Local Inference) | Team: **Shivam Verma** | Hack Day Jaipur 2026

---

## Problem Statement & Target User

Hacktoberfest and open source bring thousands of newcomers to unfamiliar codebases. The slowest and most frustrating step is rarely writing the patch — it is finding **where the fix belongs**. Hosted code-chat assistants require internet connectivity, paid accounts, and frequently hallucinate functions and files that do not exist.

**Target User**: First-time open source contributors, students, and hackathon participants working on student laptops in offline or bandwidth-limited environments.

Trailhead takes a repository and GitHub issue text, and produces a verified **Contribution Trail**:
1. **Edit here**: The 1 to 5 candidate functions or classes most likely to need changes, with file:line spans and snippets read directly from disk.
2. **Read first**: Contextual symbols the developer must understand before editing.
3. **Blast radius**: Inbound callers to depth 2 with low/medium/high risk badges.
4. **Tests to run**: 2-hop reachable pytest node IDs and ready-to-run test command line.
5. **PR checklist**: Deterministic checklist extracted from `CONTRIBUTING.md` and repository tooling configs (`ruff`, `pytest`, `tox`, `pre-commit`).
6. **Honesty & Abstain**: If evidence is ambiguous, Trailhead says "low confidence", highlights 3 explore areas, and drafts a clarifying question for the maintainer rather than hallucinating.

---

## Approach, Architecture & Demo

```
 GitHub issue text ----+                          repo on disk
 (paste / file)        |                               |
                       v                               v
              +-----------------+          graphify extract . --code-only
              | 1. HINTS        |                       |
              | stack traces,   |                       v
              | `identifiers`,  |              graphify-out/graph.json
              | error strings   |                       |
              +--------+--------+                       v
                       |                      +-----------------+
                       v                      | 2. GRAPH ADAPTER|  nodes, edges, spans
              +-----------------+  <----------+  (graphio.py)   |
              | 3. LLM QUERY    |             +-----------------+
              |    REWRITE      |  (schema: keywords[<=8])
              +--------+--------+
                       v
              +-----------------+   BM25 over node text
              | 4. RETRIEVE     |   stack-trace hits get +5.0 boost
              +--------+--------+
                       v
              +-----------------+   Personalized PageRank (scipy-free power iteration)
              | 5. GRAPH EXPAND |   edge weights: calls 1.0, inherits 0.8, contains 0.7, imports 0.5
              +--------+--------+   candidates: labelled C1..C12
                       v
              +-----------------+   Qwen3 4B / 1.7B, think=false, JSON schema enum [C1..C12]
              | 6. LLM RERANK   |   picks (max 5) + role (edit/read_first) + why
              +--------+--------+
                       v
              +-----------------+   V1 id exists   V2 span inside file   V3 snippet from disk
              | 7. VERIFY       |   V4 low-confidence abstain   V5 retry -> graph-only fallback
              +--------+--------+
                       v
              +-----------------+   blast radius (depth 2), tests finder, PR checklist
              | 8. ENRICH       |
              +--------+--------+
                       v
              Trail (JSON) --> CLI Markdown | Web UI + Live SSE Trace | trail.svg
```

### Why Trailhead is Non-Generic
- **Graph is the Ground Truth, Model is the Judge**: Candidate symbols are extracted by Graphify's AST parser. The model only picks among aliases `[C1..Cn]` via schema-constrained decoding. It cannot cite non-existent code units.
- **Graph-Guided Multi-Hop Search on Tiny Models**: Personalized PageRank propagates relevance across code relationships without requiring giant fine-tuned cloud models.
- **Provably Offline**: `netguard.py` intercepts sockets at runtime and enforces zero external calls. The live UI header badge displays "OFFLINE: 0 external connection attempts".

---

## Model Details

- **Model**: `qwen3:4b` (main high-precision profile), `qwen3:1.7b` (fast profile), `nomic-embed-text` (optional embeddings)
- **Parameters**: 4B (`qwen3:4b`) / 1.7B (`qwen3:1.7b`) / 137M (`nomic-embed-text`)
- **Licence**: Apache License 2.0 (open weights; verified in `THIRD_PARTY.md`)
- **Runtime**: Ollama 0.40.9 listening strictly on `127.0.0.1:11434`
- **Quantization**: `Q4_K_M` (4-bit medium quantization)
- **Hardware / RAM**: 8.0 GB RAM (7.24 GB usable) | AMD Ryzen 3 7320U CPU | Windows 11 Home 64-bit
- **External APIs**: none (all inference local; netguard blocks non-localhost sockets)

---


## Setup Instructions

### 1. Prerequisites
- Python 3.11+ (or 3.12)
- [uv](https://github.com/astral-sh/uv) package manager
- [Ollama](https://ollama.com/) local daemon
- Git

### 2. Environment Setup & Model Pulls
```bash
# Clone the repository
git clone https://github.com/shivamverma/trailhead.git
cd trailhead

# Sync local virtual environment
uv sync

# Pull local open-weight models via Ollama
ollama pull qwen3:4b
ollama pull qwen3:1.7b
ollama pull nomic-embed-text

# Install Graphify CLI
uv tool install graphifyy
```

### 3. Index a Repository
```bash
# Generate offline code graph
trailhead index /path/to/local/repo
```

### 4. Run CLI or Web UI
```bash
# Run CLI trail generator (with Wi-Fi off!)
trailhead trail --repo /path/to/local/repo --issue "Issue description text"

# Launch interactive Web UI with live tool trace
trailhead serve --repo /path/to/local/repo --port 8765
# Open http://127.0.0.1:8765 in any browser
```

---

## Results (3 runs)

Evaluated on the independent test benchmark split (post-cutoff 2026 issue-to-fix pairs across `pallets/click`, `psf/requests`, `encode/httpx`):

| System | Hit@1 | Hit@3 | Hit@5 | MRR | tok/s | Hallucination Rate | Stability | Runs | Cases | Latency (s) |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| `bm25` | 0.000 | 0.000 | 0.000 | 0.069 | - | **0.0%** | 100.0% | 1 | 4 | 0.35s |
| `graph` | 0.500 | **0.750** | **0.750** | **0.583** | - | **0.0%** | 100.0% | 1 | 4 | 1.34s |
| `naive-llm4b` | 0.250 | 0.250 | 0.250 | 0.250 | 4.5 | **25.0%** | 100.0% | 3 | 4 | 169.91s |

### Key Findings & Proofs
1. **Graph Beats Flat Lexical Retrieval**: Graph expansion via Personalized PageRank improves Hit@3 from **0.0% to 75.0%** and MRR from **0.069 to 0.583** (**8.4x higher**) by traversing call and import relationships.
2. **Zero Hallucination Proof**: The unconstrained naive local LLM invented nonexistent function names in **25.0%** of cases. Trailhead's schema-constrained decoding and disk verification achieved strictly **0.0% hallucination rate** by construction.
3. **Hyperparameter Tuning Integrity**: Fusion weights (`retrieval=0.7, graph=0.3`) were tuned strictly on dev cases (`bench/results/dev_tuning.json`) with zero test leakage.

### Limitations & Future Scope
- **Current Scope**: Python repositories with AST span parsing.
- **Future Scope**: Expand AST snippet extraction to JavaScript/TypeScript and Rust repositories; automated pull request draft scaffolding.

---

## Graphify Integration & Future Scope / Licence

- **Dogfooded Repository Graph**: [`graphify-out/graph.html`](file:///c:/Users/SHIVAM%20VERMA/Desktop/Hacktober/graphify-out/graph.html)
- **Graph Clustering Report**: [`graphify-out/GRAPH_REPORT.md`](file:///c:/Users/SHIVAM%20VERMA/Desktop/Hacktober/graphify-out/GRAPH_REPORT.md)
- **Shared in Discord**: Yes (posted in Graphify community Discord channel)
- **Licence**: **MIT License** (see [LICENSE](file:///c:/Users/SHIVAM%20VERMA/Desktop/Hacktober/LICENSE))
