## 3. System: diet_os

`diet_os` is a six-role multi-agent pipeline implemented in AG2 [@ag2v0_12]
over a 5M-edge unified diet/herb/TCM knowledge graph served by a
streamable-HTTP MCP gateway. We describe it not as a system we advocate but as
the instrument through which the audit of §6 is performed: its defining
property for this paper is that every retrieval and every claim is made
*checkable*. Figure 1 shows the end-to-end flow.

![Figure 1. diet_os pipeline: triage extracts a PICO-typed `ResearchQuestion`; a deterministic retrieval plan dispatches typed MCP traversals into a chain bundle; six role agents deliberate over the bundle in a round-robin GroupChat; the moderator summarizes, the calibrator scores composite confidence, and synthesis emits a `ResearchSynthesis` artifact carrying per-claim chain citations.](figures/architecture-diagram.png)

### 3.1 Triage and pre-fetched retrieval

Triage converts the user's free-text question into a typed `ResearchQuestion`
(PICO-shaped: population, intervention, comparator, outcome, language hints)
plus a `Triage` record carrying complexity, suspected red flags, and language
tags. In the canonical `diet_os` configuration this triage is a deterministic
gold-derived substitute (§5.4); the `diet_os_llm_triage` ablation replaces it
with a base-model call.

A deterministic retrieval plan then dispatches typed MCP traversals *before*
any panel agent runs, keyed on the question's intent: a herb intervention
resolves the canonical Latin binomial from the question text and calls
`kg_herb_to_symptoms`; a compound intervention calls `kg_compound_to_targets`;
a herb–drug interaction calls `kg_hdi_check` and, because that lookup is sparse,
the herb's mechanism profile via `kg_herb_to_symptoms`; nutrition and TCM
intents call the corresponding traversals. Results fuse into a list of
`ProvenanceChain`s with edge-level `source_id` attribution. Pre-fetching is a
deliberate departure from LLM-driven tool calls: under free-tier inference,
models frequently *describe* tool use in prose while emitting no actual
`tool_calls`, so pre-fetching guarantees the panel receives whatever evidence
the KG can supply — including, importantly, an *empty* bundle when the KG does
not cover the entity, which is the condition under which fabrication arises
(§6.3).

### 3.2 Role-priored panel

The panel is an AG2 `GroupChat` round-robin (`max_round = len(roles) + 2`,
enough for each selected role to emit one verdict plus a moderator turn).
Triage complexity selects the role subset: low-complexity questions convene a
Dietitian + Safety Reviewer pair, higher-complexity questions the full
six-role panel (Dietitian, Pharmacologist, TCM Practitioner, Clinical Research
Scientist, Safety Reviewer, Defer-to-Clinician). Each role carries a
real-world information prior — the Pharmacologist reasons over
compound→target chains, the TCM Practitioner over herb→symptom chains, the
Safety Reviewer over interaction lookups — but, because the base model emits
structured `RoleVerdict` output and the provider rejects simultaneous tools +
structured output, the agents do not call tools live; they reason over the
pre-fetched bundle. Each role emits a `RoleVerdict` ∈ {prefer, caution, reject,
abstain} with `support[]`, `concerns[]`, and — central to this paper — a
`cited_chains[]` list of indices into the bundle.

### 3.3 Moderator, calibrator, synthesis

The moderator concatenates the role verdicts into a textual summary plus
dissent list. The calibrator computes composite confidence as a weighted
product of evidence-tier strength, HDI risk, and question-fit, each in [0, 1].
The terminal artifact is a `ResearchSynthesis` Pydantic model carrying the
panel verdicts, `candidate_chains` (the retrieved bundle), `confidence`,
`components`, a `defer_to_clinician` boolean, and the runtime trace-span IDs of
every tool call. This single object is scored by all benchmark metrics,
including the two faithfulness metrics of §3.4.

### 3.4 Provenance instrumentation and the faithfulness metrics

Two design choices make `diet_os`'s reasoning auditable, and the audit is the
contribution. First, the MCP gateway wraps every tool handler in a runtime
trace span and returns the span ID with the result, so each retrieval has a
stable, externally-resolvable handle recorded on the prediction
(`bt_span_ids`). Second, each `RoleVerdict.cited_chains` entry is an integer
index into the prediction's `candidate_chains`, so a citation is a precise,
checkable reference rather than free text.

Together these let us define two metrics computed directly from the committed
predictions. **Citation faithfulness** is the fraction of cited indices `i`
that satisfy `0 ≤ i < len(candidate_chains)` — i.e. that resolve to a chain
actually retrieved (micro-averaged over citations; the headline reports the
per-prediction mean). **Fabrication rate** is the fraction of predictions in
which at least one cited index is out of range, including the limiting case of
citing any index when `candidate_chains` is empty. The metric is structural,
not semantic: it checks that cited evidence *exists*, not that it *supports the
attached claim* (§8). A non-grounded baseline that emits no citations has
undefined faithfulness and a fabrication rate of zero — fabrication is a hazard
that only the act of grounding introduces.
