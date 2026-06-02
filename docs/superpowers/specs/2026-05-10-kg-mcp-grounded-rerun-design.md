# kg-mcp Grounded Re-run for Paper-1 v1 Camera-Ready — Design

**Date:** 2026-05-10
**Status:** Approved by user
**Affects:** paper-1 v1 camera-ready milestone (#28), Sep 8 ML4H Findings deadline

## §1. Goal + Scope

**Goal.** Re-run DietResearchBench-Clinical v1 (n=40, 7 systems) against the updated kg-mcp tool surface and Cerebras Qwen-3-235B free-tier LLM, with every kg-mcp tool call captured as a Braintrust span. Ship 4 grounded case studies whose every retrieval claim is traceable to a recorded span. Update paper-1 v1 §6.1 / §6.5 / §A.3 with the new numbers if they shift materially. Re-tag a fresh `paper-1-v1-arxiv-submission` SHA.

**Out of scope.** Benchmark expansion (n stays at 40); two-annotator IAA (v2 paper concern); paid-tier LLM ablation; gold-triage bypass elimination (deferred to v2); upstream LightRAG submodule changes.

## §2. Architecture

PR #92 (`feat/braintrust-runtime-tracing`) lands first as a prerequisite. It wraps every kg-mcp tool handler in `mcp/src/kg_mcp/braintrust_runtime.py::tool_span` so every live `kg_query`, traversal, `kg_hdi_check`, etc. emits a Braintrust span with input args, response shape, latency, and `source_id` prefixes of returned entities. The eval pipeline then drives the 40-scenario × 7-system matrix through this instrumented surface. Two variables change at once relative to paper-1 v1: the LLM (free-tier Nemotron-3-nano-30B → free-tier Cerebras Qwen-3-235B-Instruct, preserving the "constrained-inference findings" framing) and the tool surface (10 Layer-A/B/C tools → 6 new tools: `get-entity`, `semantic-search`, `get-subgraph`, `list-labels`, `get-health`, `ingest-knowledge`). The architectural ablation `diet_os_llm_triage` is the load-bearing comparator — if its parse-failure rate drops from v1's 82.5% to <20% on Qwen-3-235B, §6.5's ablation narrative shifts and the paper honestly discloses this.

## §3. Components

| Module | Change |
|---|---|
| `eval/baselines/diet_os.py` | Re-point retrieval from v1 Layer-B traversals (`kg_diet_to_compounds`, etc.) to new tool surface: `semantic-search` → entity resolution; `get-subgraph` → typed-traversal replacement; `get-entity` → canonical-name lookup; `list-labels` → label inventory. Keep gold-triage substitute as primary path (unchanged from v1). |
| `eval/baselines/diet_os_llm_triage.py` | Same retrieval re-point. Triage step now hits Cerebras Qwen-3-235B for structured-JSON output. Expected outcome: parse-failure rate drops; ablation result shifts. |
| `eval/baselines/{single_llm,single_llm_rag,yang2025,medagents,mdagents}.py` | Swap OpenRouter Nemotron client → Cerebras Qwen-3-235B client. Hold prompts constant. |
| `eval/runner.py` | No change to orchestration. New run-dir naming: `<timestamp>-qwen-new-mcp/`. |
| `mcp/src/kg_mcp/braintrust_runtime.py` | Lands via PR #92. Wraps every tool handler with span emission. No re-work in this re-run. |
| `eval/cost_tracker.py` | Tee per-role token + latency into a Braintrust span metric (`cost.{role}.{prompt|completion}_tokens`). |
| `agents/panel.py` | No architectural change. Panel deliberation now consumes Qwen-3-235B; verify the JSON `RoleVerdict` parser still tolerates the model's output style. |
| `scripts/render_ablation_test.py` | No code change; outputs go to new results dir. |
| `eval/report.py` | Add `--baseline-results-dir` arg so the run can byte-diff against v1 paper-grade results and emit a delta table. |
| `agents/models.py` | Add `bt_span_ids: list[str] = Field(default_factory=list)` to `ResearchSynthesis` for full retrieval-trace provenance. |
| `research-journal/primary/v1/06-results.md` + `A0-appendix.md` | Conditional update if deltas are material. New §A.3 case-study blocks (4 of them). |

**No mock test doubles anywhere in the eval path.** Every retrieval chain in the case studies must be backed by a Braintrust span ID; §A.3 will cite span IDs as provenance.

## §4. Data flow

```
1. scenario.gold loaded by eval/runner
2. gold-triage substitute extracts: complexity, intervention seed, expected red flags
3. kg-mcp tool call sequence (per scenario):
   a. semantic-search(intervention) → candidate entity_ids
   b. get-entity(top entity_id) → canonical Compound/Herb/Disease record
   c. get-subgraph(canonical_id, depth=2) → mechanism chain candidates
   d. (optional) list-labels for category-aware filtering
4. Each call produces a Braintrust span with: tool_name, args, response,
   elapsed_ms, source_id_prefixes-of-returned-entities, hash-of-result-set
5. Panel deliberation (5 roles × Qwen-3-235B): consumes the chain bundle
6. Synthesis → verdict + confidence + cited_chains[]
7. Per-prediction JSON written with new field: bt_span_ids[] (list of span IDs
   for full retrieval-trace provenance)
8. eval/report renders summary.md / paired_tests.md / ablation_test.md
9. Comparison: report.py --baseline-results-dir 20260504T230617Z-final-7sys/
   emits delta-table (v1 → new for every metric)
```

The `bt_span_ids[]` field is what makes the case-study constraint enforceable: a §A.3 case study claiming "semantic-search resolved 'SJW' to Hypericum perforatum" must cite the BT span ID that proves it.

## §5. Error handling

- **Tool-call failure**: kg-mcp tool returns non-200 OR malformed JSON → BT span captures failure → runner records the failure in prediction JSON's `notes` field with the span ID → that scenario's chain is empty (`retrieval_empty` failure mode). No retry, no fallback synthesis. Honest empty result.
- **LLM parse failure** (Qwen-3-235B emits invalid JSON): mirrors v1 Nemotron handling — runner-error captured in triage rationale, prediction marked verdict='caution' default, confidence=0.0. This IS the `diet_os_llm_triage` ablation signal; do not retry.
- **Cerebras rate limit hit** (1M tok/day cap): runner exits cleanly with partial-results manifest; can resume from last-completed scenario. NOT silently skipped.
- **Braintrust API down**: span emission is soft-import + try/except — failure logged but doesn't break the eval (matches PR #92's no-op fallback). Eval continues; just no span recorded for that call. Case-study sourcing later will skip any unrecorded calls.

## §6. Testing

- **Pre-run**: `pytest mcp/ -m unit` green (covers braintrust_runtime + tool stubs); `pytest shrine-diet-bioactivity/eval/ -m unit` green.
- **Integration smoke**: 1-scenario dry-run end-to-end (`case-hdi-001-sjw-sertraline`) before full matrix. Verifies BT span emission + Cerebras token consumption + result JSON shape.
- **Mid-matrix gate**: after scenarios 1–10 complete, byte-diff against v1 prediction JSONs for *structure* (not content). Catches schema drift early.
- **Post-matrix gate**: `eval/report.py` runs cleanly; numeric-consistency sweep over all paper-grade numbers; cite-key audit (19 keys unchanged + new case-study span ID refs added).
- **Reproducibility**: every run captures `manifest.json` with `git rev-parse HEAD`, `kg-mcp version` (gateway /health response), `BRAINTRUST_PROJECT`, `cerebras_model_name`, `seed=42`.

No new pytest fixtures using test-double constructs.

## §7. Paper integration

If deltas are material (>0.05 absolute in any headline metric):
- §6.1 matrix table: 7-row update; v1 numbers move to a `tables/headline-matrix-v1.md` appendix file for traceability.
- §6.2 paired tests: re-rendered against new run; prose updated if significance picture changes.
- §6.5 ablation: most likely shift site. If Qwen-3-235B's LLM-triage parse rate is materially better, the architectural-lift narrative needs a 1-paragraph honest disclosure (e.g., "with a more capable free-tier LLM, the gold-triage substitute's load-bearing role weakens from κ +0.476 to +0.X; remaining lift attributable to tool surface").
- §A.3 case studies: 4 new blocks, each ~80–150w, citing BT span IDs and `source_id` prefixes for provenance.
- §A.6 commit pin: refreshed to new merge SHA + new results dir.
- Tag `paper-1-v1-arxiv-submission` moves to the new SHA. The old tag stays as `paper-1-v1` for the original run.

If deltas are not material (no metric shifts >0.05 absolute), the eval re-run still ships as a §A.3 robustness check ("we replicated v1 numbers on the updated tool surface with a more capable free-tier LLM; numbers reproduce within bootstrap CI"). Case studies still ship.

## Reference decisions (locked during brainstorming)

1. **Outcome**: Both eval matrix re-run AND qualitative case studies; affects camera-ready.
2. **Triage methodology**: Gold-triage as primary path; LLM-triage ablation re-run on new kg-mcp.
3. **LLM**: Cerebras Qwen-3-235B free tier (replaces Nemotron-3-nano-30B).
4. **Benchmark scope**: Same 40 scenarios (apples-to-apples vs v1).
5. **Case studies**: 4, selected from top-failed v1 scenarios.
6. **Execution**: Approach A — sequential; PR #92 lands first.
7. **"Source data only from kg-mcp"**: enforced via Braintrust spans (every retrieval claim backed by a span ID; no test-double stubs anywhere in the eval path).
