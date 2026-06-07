## 5. Experimental setup

**LLM.** All seven systems share one free-tier open-weight base model,
gpt-oss-120b (OpenAI open-weight 120B MoE), served by Cerebras Inference at
`reasoning_effort = low`, temperature 0, seed 42. Holding the base model
constant across systems isolates architectural differences; running on a
free-tier model keeps the constrained-inference framing while — unlike the
30B model used in the earlier comparison of §6.2 — being capable enough that
the non-grounded baselines are not artificially near zero. Free-tier rate
limits (5 requests/min, 150/hr, 1M tokens/day) are respected by a
sliding-window client-side limiter; the full 40 × 7 matrix runs in ~5.5 h.

**Orchestration.** AG2 v0.12.1 (the AG2AI Apache-2.0 fork) with a `GroupChat`
round-robin and Pydantic-typed messages. Panel agents emit structured
`RoleVerdict` output and therefore do not register live MCP tools — Cerebras
rejects simultaneous `tools` + `response_format`, and the pre-fetch design
(§3.1) supplies retrieval before deliberation regardless — so retrieval is
fully pre-fetched and the agents' role of *citing* it is what the audit
measures.

**Knowledge graph.** Neo4j AuraDB hosting `unified_diet_kg` (166K nodes,
~5M relationships) ingested from Duke phytochemical, FooDB, CMAUP, SymMap
v2.0, HERB 2.0, HDI-Safe-50, and OpenNutrition. The deployed graph resolves
herbs primarily by Latin binomial; coverage is sparse for foods, nutrients,
TCM terms, and direct interaction pairs (§6.5).

**MCP gateway.** Streamable-HTTP at `kg-mcp-test.up.railway.app/mcp` exposing
typed traversal + lookup tools across three layers (Layer A `kg_query`;
Layer B six typed traversals; Layer C `kg_hdi_check`, `kg_bilingual_term`,
`kg_node_neighborhood`). Every tool invocation is wrapped in a runtime trace
span whose ID is returned to the caller (§3.4), giving each retrieval a stable
provenance handle. The session is singleton-per-process across the matrix.

**Baselines.** Five external baselines plus `diet_os` and its triage ablation
share base model, KG, and gateway: `single_llm` (no tools), `single_llm_rag`
(naïve semantic-search RAG), `yang2025` (two-agent
barrier-identification + strategy-execution) [@yang2025],
`medagents` [@medagents2024], `mdagents` [@mdagents2024], **`diet_os`** (this
work; deterministic gold-triage substitute, §5.4), and **`diet_os_llm_triage`**
(the triage ablation replacing the deterministic substitute with a base-model
call). We report the full N = 40 matrix across all seven systems.

**Cost and latency.** Per-role token usage and latency are captured by a
`cost_tracker` decorator and reported in the companion code release and
Appendix A.2; free-tier rate-limit pacing dominates wall-clock.

### 5.4 The gold-triage substitute

In its canonical configuration `diet_os` does not run the triage stage with
the base model; it substitutes a deterministic `Triage` derived from the
scenario's gold metadata — `expected_complexity` selects the panel size and
`expected_red_flags` are injected as the suspected red flags. This is a
disclosed evaluation simplification: free-tier models emit unreliable
structured triage output, so the substitute removes triage noise to isolate
downstream behaviour. It also imports gold-derived safety signal, which is
precisely why the herb–drug-interaction recall must be read with the ablation
of §6.4 rather than at face value. The `diet_os_llm_triage` system is the
ablation that removes the substitute, running triage with the base model
instead; comparing the two isolates how much of `diet_os`'s safety behaviour
is the substitute rather than the retrieval.
