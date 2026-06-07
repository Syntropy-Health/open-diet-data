# Appendix

This appendix follows the bibliography and is excluded from the ML4H Findings 4-page body budget per venue convention. Sections relocated here from the body retain full numerical content and reviewer-relevant detail.

## A.1 Pre-fetch design rationale and pilot data

_Source: relocated from §3.1 (T14.9). Body keeps a one-clause back-reference._

The §3.1 pre-fetched design choice is motivated by the following pilot observation:

This **pre-fetched** design is a deliberate departure from LLM-driven tool
calls. Our pilot found Nemotron-30B emits `RoleVerdict` JSON whose `notes`
field claims tool use ("Used `kg_diet_to_compounds`…") while transcript-level
tool-invocation counts remain zero across all roles — the model hallucinates
tool use from training-data priors (`e2-panel-mcp-wiring-results.md`).
Pre-fetching guarantees every panel deliberation receives a non-empty bundle,
so HDI-Recall and provenance metrics (§4) become measurable rather than null.

## A.2 Cost & latency per-role traces

_Source: relocated from §5 cost-and-latency paragraph (T14.10). Body keeps a one-clause "see A.2" pointer._

Per-role cost and latency detail relocated from §5:

**Cost and latency.** Per-role token usage and latency are captured by
the `cost_tracker` decorator wrapping `ConversableAgent.generate_reply`.
Free-tier rate limits dominate end-to-end matrix wall-clock (full-40
× 6 baselines completed in ~3 hours; the `diet_os_llm_triage` ablation
adds ~2 hours due to free-tier RPM throttling on the additional triage
LLM call). Detailed per-role traces are available in the companion code
release; we omit the table here for space.

## A.3 Citation-faithfulness case studies

Each `diet_os` prediction records the runtime trace-span IDs of its kg-mcp
tool calls and, per agent verdict, the indices of the chains it cites. The
three cases below — a fabrication, a faithful citation, and a working herbal
grounding — illustrate the §6.3 findings at the level of an individual
recommendation. Span IDs resolve in the `diet-os-eval` trace project; chain
counts and cited indices are read directly from the committed prediction JSON.

**Case 1 — Fabricated provenance: `case-hdi-005-ginkgo-aspirin`.** Retrieval
returned **zero** chains (the gateway did not resolve "ginkgo"/"aspirin" to KG
entities; trace spans `c7e5b6fd-…` and `162900a7-…`), so `candidate_chains = 0`.
Nonetheless the Pharmacologist verdict cites chains `[101, 112]` and the TCM
Practitioner cites `[1, 2, 3]` — five references into an empty evidence set.
Only the Dietitian abstains from citing. This is fabrication in its starkest
form: the agents emit specific, confident-looking chain indices for evidence
that does not exist, and a downstream reader following those citations finds
nothing. The verdict itself (`caution`, with deferral) is not unreasonable —
which is exactly why the verdict-level metrics do not flag the problem.

**Case 2 — Faithful citation: `case-hdi-010-yohimbe-clonidine`.** Retrieval
returned 10 chains via the mechanism-traversal tool (spans `4a8779b9-…`,
`80108f23-…`), `candidate_chains = 10`. All three speaking roles (Dietitian,
Pharmacologist, TCM Practitioner) cite chain `[1]` — a valid index — and the
Pharmacologist's note reasons explicitly from the retrieved adrenergic-signalling
chain to the mechanism of concern: yohimbine is an α2-antagonist that opposes
clonidine's central α2-agonism, risking rebound hypertension. Here the citation
channel does what grounding promises: the claim is traceable to a real,
on-topic chain.

**Case 3 — Working herbal grounding: `case-herbal-001-ginger-cinv`.**
Canonical-binomial resolution ("Zingiber officinale") returns 20 chains
(span `ebcaaf3c-…`), `candidate_chains = 20`; the Dietitian and Safety Reviewer
each cite chain `[19]`, in range. The case shows that where the KG covers the
entity, faithful grounding is the default rather than the exception — the
fabrication in Case 1 is a coverage-gap behaviour, not an intrinsic property of
the model.

**Aggregate.** Across all 40 `diet_os` predictions there are 352 individual
chain citations, of which 246 are faithful and 106 (30%) are not. The
per-prediction mean citation faithfulness reported in §6.1 is 0.657 [0.262,
0.858] (averaged over predictions that cite at least once; the pooled
citation-level fraction is 0.699). 16/40 predictions contain ≥1 fabricated
citation (fabrication rate 0.400), of which 13 cite chains while
`candidate_chains` is empty. Only 10/40 predictions carry any real chains
(6 herbal, 4 interaction), the rest reflecting the KG coverage gaps of §6.5.

## A.4 Extended related work

_Reserve target for any §2 prose squeezed out by C-ADDS (T14.13–T14.15) or for HealthGenie / additional comparators if they need framing without body weight._

(Content placeholder — populated only if needed during C-ASSEMBLE.)

## A.5 Limitations and Broader Impact

_Source: relocated from §8 in entirety (T14.11). Body §8 keeps only a 3-line stub referencing this section._

The body §8 stub references this section. Below are the full limitation subsections relocated from §8:

### 8.1 Single-author gold standard at n=40

DietResearchBench-Clinical v1 uses single-author gold annotations across 40 scenarios with no inter-annotator agreement (IAA) measurement. A v2 expansion (n=200, two-annotator design with κ ≥ 0.6 gating and calibration-aware Platt/isotonic scoring) is in progress as a companion paper [@v2benchmark2026].

### 8.2 Free-tier base model

The matrix runs on free-tier gpt-oss-120b (Cerebras, `reasoning_effort = low`,
5 req/min · 150/hr · 1M tok/day). We adopt a free-tier model deliberately to
keep the constrained-inference framing, while choosing one capable enough that
the non-grounded baselines are not artificially near zero (the weaker
Nemotron-3-nano-30B used for the §6.2 base-model comparison drives every
baseline to κ ≈ 0, which is exactly the confound §6.2 documents). Results are
base-model-version-sensitive; a fuller base-model sweep is future work (§8).

### 8.3 HDI Recall is in-panel, not universe-recall

Per the KG coverage audit (`docs/kg-coverage-audit.md`), HDI-Safe-50 covers 86.2% of the curated public HDI universe known to NIH ODS and NCCIH (n=15 reference pairs). Reported HDI Recall is therefore in-panel recall against the curated v1 panel, not absolute recall against the broader herb-drug interaction literature.

### 8.4 Source-attribution provenance, not Cypher round-trip

Provenance metric uses the source-id-prefix proxy (`cmaup:`, `duke:`, `herb2:`, `symmap:`, `hdi-safe-50:`) rather than full Cypher round-trip verification against Aura. Edges retrieved through Layer-B/C MCP traversals are KG-faithful by construction; Cypher verification for adversarial cases is deferred to v2.

### 8.5 AG2-specific orchestration

diet_os is implemented in AG2 v0.12. Pydantic-AI re-ports (estimated 1.5-day migration; native MCP streamable-HTTP, Logfire observability) are deferred to v2 as a framework ablation.

## A.6 Reproducibility extended

_Source: relocated from §9.2 reproducibility detail (T14.12). Body §9.2 keeps the URL + commit pin + a forward-pointer; full commands, stats config, LLM/KG details live here. Plan B integrity bullet (T14.20) inserts here._

Full reproducibility detail relocated from §9.2 of the body:

- **Eval matrix.** The full 40 × 7 prediction matrix, per-system
  `summary.md` (with the Cite-Faith / Fabricate columns), and the
  herb–drug-interaction ablation are committed at
  `research-journal/shared/results/20260605T053102Z-gptoss120b-v1mcp-btspans/`.
  Each `diet_os` / `diet_os_llm_triage` prediction JSON carries
  `candidate_chains`, per-verdict `cited_chains`, and `bt_span_ids`.
- **Re-render.** `python3 -m eval.report --results-dir <dir>` regenerates
  `summary.md`, `paired_tests.md`, `category_breakdown_verdict_kappa.md`, and
  `reliability_diagram.png`. The Cite-Faith / Fabricate columns are computed
  by `eval.metrics.citation_faithfulness` and `citation_fabrication_rate`
  directly from the committed predictions (no live KG needed).
- **Citation-faithfulness audit.** Faithfulness = fraction of
  `cited_chains` indices `i` with `0 ≤ i < len(candidate_chains)`
  (per-prediction mean for the headline; pooled fraction also reported in
  §A.3). Fabrication rate = fraction of predictions with ≥1 out-of-range
  citation. Both are deterministic functions of the committed JSON.
- **Stats.** Per-metric bootstrap CIs with B = 10 000, Davison-Hinkley
  `(k+1)/(B+1)` p-value, fixed seed = 42. The base-model confound (§6.2)
  compares the same 7-system matrix against the earlier Nemotron-30B run at
  `research-journal/shared/results/20260504T230617Z-final-7sys/`.
- **LLM.** Free-tier gpt-oss-120b (Cerebras Inference, `reasoning_effort = low`,
  temperature 0, seed 42; 5 req/min · 150/hr · 1M tok/day). The earlier
  base-model comparison uses free-tier Nemotron-3-nano-30B.
- **KG.** Neo4j AuraDB hosting `unified_diet_kg` (166K nodes, ~5M
  relationships). Read-only Bearer-auth streamable-HTTP gateway at
  `kg-mcp-test.up.railway.app/mcp`; every tool call emits a runtime trace
  span whose ID is recorded on the prediction.
