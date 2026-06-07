# Abstract

Knowledge-graph grounding is widely proposed to make multi-agent clinical
LLM systems trustworthy: if every claim cites a retrieved evidence chain,
the reasoning becomes auditable. We stress-test this premise on
supplement–drug safety reasoning and find that grounding can manufacture a
new failure mode rather than remove one. We build `diet_os`, a 6-role
multi-agent system over a unified 5M-edge diet/herb/TCM knowledge graph
served through a streamable-HTTP MCP gateway, instrumented so that every
tool call emits a runtime trace span and every agent claim carries explicit
chain citations. Running the full DietResearchBench-Clinical matrix (40
scenarios × 7 systems) on a free-tier open-weight model (gpt-oss-120b), we
audit each citation against the evidence actually retrieved. We report three
findings. **(1) Fabricated provenance:** `diet_os` cites at least one
non-existent evidence chain in 40% of predictions; only 66% of its citations
resolve to a retrieved chain, dropping to 27% when triage is also
model-driven — including agents that cite specific chain indices when *zero*
chains were retrieved. These failures are invisible to the verdict-agreement
and safety-recall metrics by which such systems are usually judged. **(2) A
verdict-agreement confound:** the architectural κ "lift" reported for
KG-grounded panels over non-grounded baselines vanishes under a stronger
base model — every baseline reaches κ 0.20–0.35, erasing the gap. **(3) A
safety-recall confound:** the system's high herb–drug-interaction recall
traces to a gold-derived triage substitute, not to retrieval — an ablation
that removes it more than halves recall even when real KG chains are
supplied. We argue that for clinically deployed grounded LLMs,
citation-faithfulness must be measured and enforced as a first-class safety
property, and we release the auditing instrumentation and benchmark to
enable it.
