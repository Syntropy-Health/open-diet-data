## 1. Introduction

Supplement–drug interactions are a high-stakes clinical blind spot: patients
combine herbs and supplements with prescription drugs, and the supporting
evidence is scattered across heterogeneous resources (Duke, FooDB, CMAUP,
SymMap v2.0, HERB 2.0, HDI-Safe-50). Multi-agent LLM systems are an
attractive interface for this setting — a dietitian, a pharmacologist, a TCM
practitioner, a safety reviewer, and a deferral authority can each contribute
a different prior — and a now-common design move is to *ground* such panels
on a knowledge graph (KG): agents retrieve typed evidence chains and cite
them, so that recommendations are not free-floating model assertions but
auditable, source-linked claims. The implicit safety argument is that
citation makes the system trustworthy.

We test that argument directly. We build `diet_os`, a 6-role multi-agent
system over a unified 5M-edge diet/herb/TCM KG served through a
streamable-HTTP MCP gateway, and we make its provenance *checkable*: every
tool call emits a runtime trace span, and every agent verdict records the
indices of the KG chains it claims to cite. This instrumentation lets us do
something the verdict-level metrics in prior work cannot — open each
recommendation and ask whether the cited evidence was actually retrieved.

On the full DietResearchBench-Clinical matrix (40 scenarios × 7 systems) run
on a free-tier open-weight model, the audit is unflattering, and that is the
point. `diet_os` cites a non-existent evidence chain in 40% of predictions;
agents routinely cite specific chain indices when no chains were retrieved at
all. Worse, the apparent advantages that would normally justify the
architecture do not survive scrutiny: the verdict-agreement "lift" over
non-grounded baselines disappears under a stronger base model, and the
herb–drug-interaction recall traces to a gold-derived triage substitute
rather than to the KG.

We make three contributions:

1. **Citation-faithfulness as a measurable safety property.** We formalize
   two metrics — citation faithfulness (fraction of cited indices that
   resolve to a retrieved chain) and fabrication rate (fraction of
   predictions citing ≥1 non-existent chain) — and the auditing
   instrumentation (MCP-gateway trace spans + per-claim chain indices) that
   makes them computable. The metrics expose fabrication that
   verdict-agreement and safety-recall scores hide.

2. **An empirical audit of a grounded clinical panel.** On
   DietResearchBench-Clinical, `diet_os` achieves 66% citation faithfulness
   with a 40% fabrication rate (27% / 35% under model-driven triage), while
   the five non-grounded baselines make no citations and so cannot fabricate
   — the grounding apparatus *creates* the hallucinated-provenance surface.

3. **Two confounds in multi-agent-KG evaluation.** We show, by re-running a
   prior KG-grounded vs. non-grounded comparison, that (a) the verdict-κ
   "architectural lift" is an artifact of a weak base model, and (b) the
   herb–drug-interaction recall is an artifact of a gold-derived triage
   substitute, isolated by ablation. Both cautionary results bear directly on
   how grounded medical-LLM systems should be benchmarked.

We release the benchmark, the auditing instrumentation, and the full result
matrix. Our claim is not that knowledge grounding is unhelpful, but that
*unverified* grounding is unsafe: for clinical deployment, citation
faithfulness must be measured and enforced, not assumed.
