## 7. Discussion

### 7.1 Fabricated provenance is a distinct clinical risk

A wrong verdict and a fabricated citation are different failures with
different clinical consequences. A wrong verdict can be caught by a
disagreeing clinician; a fabricated citation actively misleads the audit that
is supposed to catch wrong verdicts. The entire value proposition of grounding
— "don't trust the model, trust the cited evidence" — inverts when 40% of
predictions cite evidence that was never retrieved. A clinician who follows a
`diet_os` citation to verify a supplement–drug claim is, two times in five,
sent to a chain that does not exist; the citation manufactures false
confidence precisely where the system was meant to earn real confidence. This
is why we argue citation faithfulness belongs with sensitivity and calibration
as a first-class safety metric for grounded clinical LLMs, rather than being
assumed from the presence of a retrieval step.

### 7.2 Why grounding manufactures the failure

The fabrication is structural, not incidental. The five non-grounded baselines
cannot fabricate citations because they make none (§6.1); fabrication appears
only once the architecture instructs agents to cite. Two ingredients combine.
First, the agents are prompted to ground their claims in retrieved chains, an
instruction they satisfy syntactically (emitting indices) even when there is
nothing to ground in. Second, the deployed KG is sparse — only 10/40 scenarios
return any chain — so the "cite your evidence" instruction is frequently issued
against an empty evidence set. An instructed-to-cite agent facing no evidence
invents an index rather than abstaining. The fix is therefore not "more
prompting to cite" but the opposite: constrain citations to the retrieved set
and require abstention-with-disclosure when it is empty (§7.4).

### 7.3 Implications for benchmarking grounded medical LLMs

Our two confounds (§6.2, §6.4) generalize beyond `diet_os`. A KG-vs-no-KG
verdict-agreement comparison reported on a single weak base model will
overstate the architecture's contribution, because a stronger base model
closes the gap (the lift inverted from +0.202 to −0.042 κ here). And a
multi-agent system that imports gold-derived red flags through a triage or
preprocessing stage will show a safety-recall advantage attributable to the
substitute, not the retrieval — detectable only by ablating the substitute,
not by comparing against external baselines that lack it. Both patterns are
common in the multi-agent-medical-KG literature; both inflate apparent
architectural gains. We recommend that grounded-LLM evaluations report
base-model sensitivity and substitute ablations as standard, alongside
faithfulness.

### 7.4 Toward faithful grounding

The instrumentation that exposed the problem also points at the remedy.
Because the retrieval executor already records the exact chain set returned for
each scenario, citation faithfulness can be *enforced* at decode or
post-process time: reject or strip any cited index outside the retrieved range,
and surface an explicit "no KG evidence retrieved" state instead of allowing
free-form citation against an empty set. Pairing this with denser coverage —
the working cases (yohimbe, ginger) show faithful grounding is achievable where
the graph is populated — and with curated interaction data for the herb–drug
setting specifically, is the path from an auditable-in-principle system to an
auditable-in-fact one. We frame these as deployment prerequisites rather than
future niceties: for a clinical supplement-safety tool, an unenforced citation
channel is a liability, not a feature.
