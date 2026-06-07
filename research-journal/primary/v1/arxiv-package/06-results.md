## 6. Results

We report the full N = 40 × 7-system matrix run on the free-tier open-weight
model gpt-oss-120b (reasoning_effort = low; §5). All values are mean
[95% bootstrap CI, B = 10 000]. The headline matrix, paired tests, per-category
breakdown, and reliability diagram are bundled as `summary.md`,
`paired_tests.md`, `category_breakdown_verdict_kappa.md`, and
`reliability_diagram.png`. Two columns — **Cite-Faith** (citation faithfulness)
and **Fabricate** (fabrication rate) — are the audit instruments introduced in
§3 and are the focus of this paper.

### 6.1 Headline matrix

| System | Verdict κ | ECE | HDI Recall | Defer Acc | Cite-Faith | Fabricate |
| --- | --- | --- | --- | --- | --- | --- |
| single_llm | 0.267 | 0.190 | 0.000 | 0.550 | — | 0.000 |
| single_llm_rag | 0.267 | 0.190 | 0.000 | 0.550 | — | 0.000 |
| yang2025 | 0.297 | 0.220 | 0.000 | 0.550 | — | 0.000 |
| medagents | 0.345 | 0.469 | 0.000 | 0.550 | — | 0.000 |
| mdagents | 0.203 | 0.346 | 0.142 | 0.625 | — | 0.000 |
| **diet_os** | 0.303 | 0.556 | 1.000 | 0.749 | **0.657** | **0.400** |
| diet_os_llm_triage | 0.217 | 0.456 | 0.429 | 0.625 | **0.269** | **0.350** |

The only systems that can fabricate are the two that cite: the five
non-grounded baselines emit no chain citations (Cite-Faith undefined,
Fabricate 0.000) because they have no retrieval to cite. The grounding
apparatus is what creates the citation surface — and, as the next subsections
show, the fabrication surface. The headline that a reader would normally take
from this table — `diet_os` posts the top HDI Recall (1.000) and a respectable
mid-pack κ — is exactly the headline the audit columns undercut.

### 6.2 The verdict-agreement "lift" is a base-model artifact

The motivating claim for KG-grounded panels is a verdict-agreement lift over
non-grounded baselines. On a weak base model that lift is real; under a
stronger one it disappears. Re-running the identical 7-system comparison
across two free-tier base models:

| | weak base (Nemotron-30B) | strong base (gpt-oss-120b) |
| --- | --- | --- |
| diet_os Verdict κ | 0.258 | 0.303 |
| best non-grounded baseline κ | 0.056 (single_llm) | 0.345 (medagents) |
| diet_os lead over best baseline | **+0.202** | **−0.042** |

On Nemotron-30B, `diet_os` leads the strongest baseline by +0.202 κ; on
gpt-oss-120b every baseline reaches κ 0.20–0.35 and the gap inverts
(`medagents` 0.345 > `diet_os` 0.303). The grounding does not get worse — the
baselines get better, because a capable base model already encodes much of the
verdict-relevant prior the KG was supplying. A KG-vs-no-KG κ comparison is
therefore only informative relative to a stated base-model capability; reported
in isolation it measures the base model, not the architecture.

### 6.3 Citation faithfulness: grounded panels fabricate provenance

Because every agent verdict records the indices of the chains it cites and the
retrieval executor records the chains actually returned, we can check each
citation directly. A citation is *faithful* iff its index `i` satisfies
`0 ≤ i < len(candidate_chains)`; otherwise it is *fabricated* — the agent
claims provenance for evidence that was never retrieved (§3.4).

`diet_os` achieves citation faithfulness 0.657 [0.262, 0.858] with a
fabrication rate of 0.400 [0.250, 0.550]: in 40% of predictions at least one
agent cites a chain that does not exist, and a third of all citations are
unfaithful. Under model-driven triage (`diet_os_llm_triage`) faithfulness
falls to 0.269 and fabrication to 0.350. The starkest pattern is citation
*without retrieval*: in 13/40 `diet_os` scenarios the retrieval returned zero
chains, yet agents still emitted specific chain indices. In
`case-hdi-005-ginkgo-aspirin` (candidate_chains = 0) the Pharmacologist cites
chains `[101, 112]` and the TCM Practitioner cites `[1, 2, 3]` — five
references into an empty evidence set (full trace, with runtime span IDs, in
§A.3).

These failures are invisible to the metrics by which such systems are usually
judged. The same `diet_os` predictions that fabricate at 40% post the
matrix-best HDI Recall (1.000) and a competitive κ (0.303): verdict-level
scores certify the *answer* and say nothing about whether the *evidence trail
behind it is real*. A clinician auditing a `diet_os` recommendation by
following its citations would, two times in five, be led to a chain that was
never retrieved.

### 6.4 The herb–drug-interaction recall is a triage artifact, not retrieval

`diet_os`'s headline safety number — HDI Recall 1.000 on severe interactions —
does not come from the knowledge graph. HDI Recall counts a severe-HDI scenario
as caught when the panel returns a `reject` verdict or sets
`defer_to_clinician`. The deferral is driven by red-flag tokens injected
through the deterministic gold-triage substitute (§5.4), not by retrieved
evidence. Two observations isolate this:

1. **Deferral is independent of retrieval.** `diet_os` flags severe-HDI
   scenarios identically whether the panel received 20 KG chains or zero — the
   defer flag fires from the injected red flags either way.

2. **Removing the gold substitute halves recall, even with KG chains.** We
   re-ran the 10 herb–drug-interaction scenarios after wiring the
   interaction-check intent to a mechanism-traversal tool that *does* return
   evidence (e.g. `Hypericum perforatum` → 20 chains). With real chains in
   hand, `diet_os` (gold triage) catches 7/7 severe cases, but
   `diet_os_llm_triage` (model triage, no injected red flags) catches only 3/7
   — the supplied KG evidence does not recover the safety signal. The herb's
   pharmacological profile is not interaction-specific evidence; the recall was
   the gold substitute all along.

The corollary is a benchmarking caution: a KG-grounded system that imports gold
red flags through its triage stage will show a safety-recall advantage that an
ablation, not a baseline comparison, is needed to detect.

### 6.5 Where grounding does work, and why coverage is the real limit

The audit is not an argument against grounding — it is an argument for checking
it. Where the KG returns evidence, agents reason from it correctly and cite it
faithfully. In `case-hdi-010-yohimbe-clonidine` (candidate_chains = 10) all
three speaking roles cite chain `[1]`, and the Pharmacologist's note reasons
explicitly from the retrieved adrenergic-signalling chain to the
clonidine-antagonism mechanism (§A.3). The working cases share one property:
the KG actually covers the entity. Only 10/40 `diet_os` predictions carry any
real chains (6 herbal, 4 interaction), because the deployed graph resolves
herbs by Latin binomial and is sparse for foods, nutrients, TCM terms, and
direct interaction pairs. Faithful grounding is achievable here — the yohimbe
and ginger (20-chain) cases show it — but only to the extent the graph is
populated and the retrieval is verified. The combination of sparse coverage and
unchecked citation is what produces the 40% fabrication rate: when retrieval
returns nothing, an instructed-to-cite agent invents a reference rather than
abstaining.
