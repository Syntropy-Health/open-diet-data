# 8. Limitations

**Scale and single run.** The benchmark is n = 40 with a single-author gold
standard, and the matrix is a single seed at temperature 0; the bootstrap CIs
on the faithfulness columns are correspondingly wide (e.g. `diet_os`
Cite-Faith 0.657 [0.262, 0.858]). The fabrication *direction* is robust — it is
a structural property of an instructed-to-cite agent facing empty retrieval,
and the most damning cases (citation into an empty chain set) are
deterministic, not statistical — but the point estimates should be read as
indicative, not precise. A larger benchmark with multi-annotator agreement
(companion v2, n = 200) and multiple seeds is needed to tighten them.

**The faithfulness metric is structural, not semantic.** Our metric verifies
that a cited index points to a chain that was *retrieved*; it does not verify
that the retrieved chain *supports the claim it is attached to*. A citation can
be faithful in our sense (index in range) yet semantically irrelevant. We
therefore report faithfulness as a necessary, not sufficient, condition for
trustworthy grounding; semantic citation-support checking is future work.

**Single base model.** All results are on gpt-oss-120b at reasoning_effort =
low; the confound in §6.2 is established across two base models (Nemotron-30B
and gpt-oss-120b) but a fuller base-model sweep would strengthen the claim that
the verdict-agreement lift is generically capability-dependent.

**KG coverage, not architecture, bounds the working set.** Only 10/40 scenarios
return real chains because the deployed graph resolves herbs by Latin binomial
and is sparse for foods, nutrients, TCM terms, and direct interaction pairs.
The fabrication rate is thus entangled with coverage; on a denser graph the
absolute rate would differ, though the failure mode (cite-when-empty) would
persist wherever coverage gaps remain. Bilingual recall is 0.000 for every
system — gpt-oss-120b is weak on Chinese and the TCM-term coverage is sparse —
so the bilingual setting is out of scope for the present claims.

**HDI recall is in-panel.** Recall is measured against the benchmark's
severe-HDI subset, not against a universe of real-world interactions; the
ablation in §6.4 isolates the gold-triage substitute as its driver but does not
establish an absolute safety ceiling.

**Orchestration-specific.** The system is AG2-specific and the citation channel
is a property of our prompt + parsing contract; other multi-agent frameworks
may surface or suppress fabrication differently. The general point — that a
citation channel must be verified, not assumed — is framework-independent, but
the specific rates are not portable.
