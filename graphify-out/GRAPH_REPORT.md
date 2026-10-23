# Graph Report - Hacktober  (2026-10-24)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 437 nodes · 973 edges · 15 communities (11 shown, 4 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 53 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f2a7b55f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 12
- Community 14

## God Nodes (most connected - your core abstractions)
1. `Node` - 28 edges
2. `run_pipeline()` - 27 edges
3. `load_graph()` - 26 edges
4. `retrieve_nodes()` - 21 edges
5. `extract_hints()` - 19 edges
6. `expand_candidates()` - 18 edges
7. `rerank_candidates()` - 18 edges
8. `Candidate` - 17 edges
9. `run_benchmark()` - 17 edges
10. `ToolBelt` - 16 edges

## Surprising Connections (you probably didn't know these)
- `test_span_downgrade()` --uses--> `Node`  [INFERRED]
  tests/test_p4_llm_guardrails.py → src/trailhead/models.py
- `test_trail_svg_valid()` --uses--> `Pick`  [INFERRED]
  tests/test_p6_ui.py → src/trailhead/models.py
- `test_expand_performance()` --uses--> `Edge`  [INFERRED]
  tests/test_p3_graph_intelligence.py → src/trailhead/models.py
- `test_expand_performance()` --uses--> `Node`  [INFERRED]
  tests/test_p3_graph_intelligence.py → src/trailhead/models.py
- `test_netguard_blocks_external()` --uses--> `OfflineViolation`  [INFERRED]
  tests/test_p1_netguard.py → src/trailhead/netguard.py

## Import Cycles
- None detected.

## Communities (15 total, 4 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (18): build_graph(), compute_blast_radius(), expand_candidates(), _find_reason_path(), is_test_path(), _normalize_scores(), run_ppr(), Edge (+10 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (16): doctor(), get_graphify_bin(), get_graphify_version(), get_ollama_info(), index(), serve(), trail(), get_blocked_attempts() (+8 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (22): classify_kind(), _index_file_symbols(), load_graph(), locate_span(), map_relation(), normalize_label(), snippet(), chat() (+14 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (18): hallucination_rate(), hit_at_k(), mrr(), recall_at_k(), top_k_stability(), main(), run_benchmark(), run_naive_baseline() (+10 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (15): fetch_json(), main(), probe_graph(), embed(), extract_json_object(), strip_tags(), test_doctor_writes_json(), test_llm_smoke() (+7 more)

### Community 5 - "Community 5"
Cohesion: 0.07
Nodes (10): Trail, render_markdown(), render_trail_svg(), get_status(), get_svg(), index_page(), stream_trail(), run_worker() (+2 more)

### Community 6 - "Community 6"
Cohesion: 0.08
Nodes (8): extract_checklist(), run_pipeline(), ToolBelt, test_tool_trace_logged(), test_checklist_from_contributing(), test_fallback_when_ollama_down(), test_live_rerank_fixture(), test_snippets_match_disk()

### Community 7 - "Community 7"
Cohesion: 0.08
Nodes (11): build_bench(), extract_changed_py_files(), parse_date(), retry(), slugify(), test_html_has_no_external_urls(), test_env_example_has_placeholders_only(), test_gitignore_contains_env() (+3 more)

### Community 8 - "Community 8"
Cohesion: 0.10
Nodes (12): create_session(), login(), verify_token(), hash_password(), reset_password(), verify_password(), decode_token(), is_expired() (+4 more)

### Community 9 - "Community 9"
Cohesion: 0.10
Nodes (14): BM25, build_node_document(), retrieve_nodes(), extract_hints(), split_identifiers(), test_bm25_misses_i2_as_expected(), test_bm25_ranks_gold_first(), test_extract_backtick_and_error_hints() (+6 more)

### Community 10 - "Community 10"
Cohesion: 0.16
Nodes (7): apply_discount(), calculate_tax(), _clamp_total(), create_invoice(), test_apply_discount_caps(), test_calculate_tax_rounding(), test_create_invoice_total_amount()

## Knowledge Gaps
- **1 isolated node(s):** `trailhead`
  These have ≤1 connection - possible missing edges. (Counts symbols only; 200 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_pipeline()` connect `Community 6` to `Community 0`, `Community 1`, `Community 2`, `Community 5`, `Community 9`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `Node` (e.g. with `build_graph()` and `compute_blast_radius()`) actually correct?**
  _`Node` has 16 INFERRED edges - model-reasoned connections that need verification._
- **What connects `trailhead` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.06956521739130435 - nodes in this community are weakly interconnected._
- **Why does `load_graph()` connect `Community 2` to `Community 0`, `Community 1`, `Community 3`, `Community 4`, `Community 6`, `Community 9`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `run_pipeline()` (e.g. with `Candidate` and `.expand_graph()`) actually correct?**
  _`run_pipeline()` has 7 INFERRED edges - model-reasoned connections that need verification._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.06775510204081632 - nodes in this community are weakly interconnected._