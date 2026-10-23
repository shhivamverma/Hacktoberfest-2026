# Trailhead: Implementation Progress

## Master Plan & Status Summary

| Phase | Description | Status | Gate Tests | Key Numbers / Measurements |
|---|---|---|---|---|
| **Phase 0** | Environment, Tools & Raw Data Prep | **GREEN (PASS)** | ollama, graphify, curl embed, curl chat, click extract | RAM: 8GB, CPU: Ryzen 3 7320U, Graphify: 18.8s (click), qwen3:1.7b: 11.89 tok/s, qwen3:4b: 4.39 tok/s |
| **Phase 1** | Skeleton, Graphify Adapter, Netguard, LLM Client | **GREEN (PASS)** | 8/8 tests in `tests/test_p1_*.py` | 54 nodes & 74 edges in fixture, netguard blocks 100% external, doctor writes RUN_ENV.json |
| **Phase 2** | Hints, Retrieval, Thinnest E2E Flow | **GREEN (PASS)** | 8/8 tests in `tests/test_p2_*.py` | BM25 (k1=1.5, b=0.75), stacktrace boost=5.0, I2 regression anchor rank 6, Click trail in 2.85s (<3s) |
| **Phase 3** | Graph Intelligence: PageRank, Blast Radius, Tests Finder, Tool Trace | Next | `pytest tests/test_p3_*.py` | - |
| **Phase 4** | LLM Layer with Guardrails & Abstain | Pending | `pytest tests/test_p4_*.py tests/test_policy.py` | - |
| **Phase 5** | Evaluation & Proof (Benchmark & Ablation) | Pending | `pytest tests/test_p5_*.py` | - |
| **Phase 6** | Web UI, Trail Graph (SVG), Live Trace | Pending | `pytest tests/test_p6_*.py` | - |
| **Phase 7** | Freeze, Package, Dogfood Graphify & Submit | Pending | `scripts/final_check.sh`, `pytest tests/test_submission_readiness.py` | - |

---

## Phase 2 Notes & Measurements

- **Tokenizer & Hints Extraction**:
  - `split_identifiers`: Handles snake_case, camelCase, PascalCase, digits, and domain stopwords.
  - Traceback extractor extracts `file`, `line`, and `func` from standard Python stacktraces.
  - Backticked code symbols and quoted error strings extracted with regex.
- **Lexical Retrieval (BM25)**:
  - Custom pure-Python Okapi BM25 implementation ($k_1=1.5, b=0.75$).
  - Fast AST symbol & file lines cache accelerates graph indexing and span lookup to under 0.8s on a 3,100+ node repository.
  - Stacktrace boost (+5.0) guarantees that traceback-mentioned symbols rank #1 immediately (verified on I3: `decode_token`).
  - Anchor regression verified: I2's gold `_clamp_total` is ranked #6 (outside top 5), setting up the graph expansion proof for Phase 3.
- **Benchmark Dataset Generation**:
  - `bench/data/pallets_click.jsonl`: 30 cases
  - `bench/data/psf_requests.jsonl`: 30 cases
  - `bench/data/encode_httpx.jsonl`: 29 cases
  - Total: 89 real GitHub issue/PR benchmark cases split into dev and test.
- **Thinnest E2E Flow**:
  - `trailhead trail --repo bench/repos/click --issue "show_envvar..." --no-llm` executed in **2.85s** (< 3.0s threshold) and correctly surfaced `test_show_envvar` as the #1 candidate.

---

## Phase 1 Probe Graph Output

### Probe Report on Mini Repo Fixture (`tests/fixtures/mini_repo/graphify-out/graph.json`)
- **Top-level keys**: `['directed', 'multigraph', 'graph', 'nodes', 'links', 'hyperedges', 'built_at_commit']`
- **Node count**: 58
- **Edge count**: 80
- **Node keys**: `['_callable', '_origin', 'community', 'file_type', 'id', 'label', 'norm_label', 'source_file', 'source_location']`
- **Relation types and counts**:
  - `calls`: 16
  - `imports`: 9
  - `imports_from`: 6
  - `references`: 1
  - `contains`: 24
  - `rationale_for`: 24
- **Line info**: extracted via AST span locator (`app/utils.py`, `app/tokens.py`, `app/passwords.py`, `app/billing.py`, `app/auth.py`).

### Probe Report on Click (`bench/repos/click/graphify-out/graph.json`)
- **Node count**: 3,106
- **Edge count**: 6,056
- **Relation types**: `{'calls': 1082, 'contains': 1627, 'references': 953, 'depends_on': 10, 're_exports': 8, 'imports': 432, 'imports_from': 158, 'inherits': 36, 'method': 418, 'rationale_for': 591, 'indirect_call': 464, 'uses': 277}`

---

## Phase 0 Notes & Environment Disclosure

- **Operating System**: Windows 11 Home Single Language 64-bit
- **CPU**: AMD Ryzen 3 7320U with Radeon Graphics (4 Cores, 8 Logical Processors)
- **RAM**: 8.0 GB (7.24 GB usable)
- **GPU**: AMD Radeon(TM) Graphics (Integrated)
- **Python Version**: 3.12.10
- **Package Manager**: uv 0.13.5
- **Graphify CLI**: 0.9.95 (`uv tool install graphifyy`)
- **Ollama Version**: 0.40.9 (listening on localhost:11434)
- **Local Models Pulled & Verified**:
  - `nomic-embed-text`: 274 MB, Embedding Dimension = 768
  - `qwen3:1.7b`: 1.4 GB, Speed = ~11.89 tok/s on CPU
  - `qwen3:4b`: 2.5 GB, Speed = ~4.39 tok/s on CPU
- **Cloned Benchmark Repositories & Graphify Extraction Timings**:
  - `bench/repos/click`: 18.83s (`graphify-out/graph.json` = 2,451,840 bytes)
  - `bench/repos/requests`: 11.55s
  - `bench/repos/httpx`: 11.52s
- **Raw Data Collected**:
  - `bench/raw/pallets_click_prs.json`: 30 closed PRs (October 2026)
  - `bench/raw/psf_requests_prs.json`: 30 closed PRs
  - `bench/raw/encode_httpx_prs.json`: 30 closed PRs
- **Graphify Community**: Discord invite confirmed at https://discord.gg/graphify
