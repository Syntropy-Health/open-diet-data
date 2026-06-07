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

### 8.2 Free-tier 30B LLM — not a calibration ceiling

Free-tier Nemotron-3-nano-30B has known JSON-quality issues at long contexts and is rate-limited to 20 RPM. We adopt this constraint deliberately to validate the architectural-headline framing under cost-zero inference. v2 ablates against Qwen-3-235B-Instruct via Cerebras (1M tok/day free tier) and paid-tier alternatives (Sonnet 4.6).

### 8.3 HDI Recall is in-panel, not universe-recall

Per the KG coverage audit (`docs/kg-coverage-audit.md`), HDI-Safe-50 covers 86.2% of the curated public HDI universe known to NIH ODS and NCCIH (n=15 reference pairs). Reported HDI Recall is therefore in-panel recall against the curated v1 panel, not absolute recall against the broader herb-drug interaction literature.

### 8.4 Source-attribution provenance, not Cypher round-trip

Provenance metric uses the source-id-prefix proxy (`cmaup:`, `duke:`, `herb2:`, `symmap:`, `hdi-safe-50:`) rather than full Cypher round-trip verification against Aura. Edges retrieved through Layer-B/C MCP traversals are KG-faithful by construction; Cypher verification for adversarial cases is deferred to v2.

### 8.5 AG2-specific orchestration

diet_os is implemented in AG2 v0.12. Pydantic-AI re-ports (estimated 1.5-day migration; native MCP streamable-HTTP, Logfire observability) are deferred to v2 as a framework ablation.

## A.6 Reproducibility extended

_Source: relocated from §9.2 reproducibility detail (T14.12). Body §9.2 keeps the URL + commit pin + a forward-pointer; full commands, stats config, LLM/KG details live here. Plan B integrity bullet (T14.20) inserts here._

Full reproducibility detail relocated from §9.2 of the body:

- **Commit pin.** Headline matrix, §6.5 ablation paired tests, and the
  reproducibility instructions in this section are all consistent at the
  tip of branch `paper-1/camera-ready` (tag `paper-1-v1-arxiv-submission`).
  Eval-pipeline integrity fix (issue #16: fail-loud `_neutral_stub`
  refactor with `--allow-stubs` opt-in) lands on `main` at merge commit
  `9657c1f` (`fix/lightrag-test-debt` → `main`).
- **Eval matrix.** Combined 7-system results dir at
  `research-journal/shared/results/20260504T230617Z-final-7sys/`
  (symlinks 6 systems from `20260504T042540Z` plus the
  `diet_os_llm_triage` ablation from
  `20260504T204413Z-llm-triage-ablation`).
- **Re-render.** `python3 -m eval.report --results-dir <dir>
  --cypher-runner source-attribution` regenerates `summary.md`,
  `paired_tests.md`, `category_breakdown_verdict_kappa.md`, and
  `reliability_diagram.png`. `python3 -m scripts.render_ablation_test
  --results-dir <dir>` regenerates `ablation_test.md`.
- **Stub safety.** The `eval.report` renderer fails-fast when manifest
  `scenario_ids` and benchmark `scenario_ids` diverge; permissive
  rendering for partial debug runs requires explicit `--allow-stubs`.
  Paper-grade renders use the default fail-loud mode.
- **Stats.** Paired bootstrap with B = 10 000, Davison-Hinkley
  `(k+1)/(B+1)` p-value, fixed seed = 42, Bonferroni over 5 baselines ×
  4 metrics_tested = 20 cells (provenance + bilingual excluded as
  vacuous under v1; see §6.2).
- **LLM.** Free-tier OpenRouter Nemotron-3-nano-30B (`nvidia/nemotron-3-nano-30b-a3b:free`),
  ≤20 RPM. The free-tier rate limit is what drives the LLM-triage parse
  failures observed in §6.5; results are model-version-sensitive.
- **KG.** Neo4j AuraDB Professional 8 GB hosting `unified_diet_kg` (166K
  nodes, ~5M relationships). Read-only Bearer-auth gateway at
  `kg-mcp-test.up.railway.app/mcp`.
