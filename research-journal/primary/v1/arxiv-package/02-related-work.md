## 2. Related Work

### Multi-agent clinical reasoning

MedAgents [@medagents2024] frames zero-shot medical reasoning as a
multi-role panel; MDAgents [@mdagents2024] adds adaptive routing
between solo and multi-disciplinary configurations. CAMP [@camp2026]
adds case-adaptive panel composition with three-valued voting on
MIMIC-IV, the closest methodological peer to our verdict-κ + abstain
framing, but operates without KG-grounded retrieval. Yang et al.
[@yang2025], the JMIR baseline of behavioral-science-informed agentic
workflows, propose a two-agent design (barrier-identification +
strategy-execution) for personalized-nutrition adherence coaching,
which we re-implement as our third behavioral baseline. NutriOrion
[@nutriorion2026] forward-extends the JMIR Yang design with a
four-specialist panel, validating that the behavioral-nutrition
multi-agent design space remains active. We extend MedAgents, MDAgents,
and Yang with Layer-B/C role-priored KG retrieval; CAMP and NutriOrion
are positioning peers, not re-implemented baselines. Wu et al. [@wu2025] report
single-GP performance comparable to a multi-disciplinary debate panel
on medication-conflict resolution; §7.2 places that finding on an axis
orthogonal to ours.

### KG-grounded LLM clinical reasoning

AMG-RAG [@amgrag2025] constructs a medical knowledge graph agentically and
reports F1 74.1 % on MedQA; MedRAG [@medrag2025] fuses a four-tier
hierarchical diagnostic KG with EHR retrieval; KG-SMILE [@kgsmile2025] adds
explainability to KG-RAG. Our pre-fetched typed-Cypher retrieval is
offline-constructed and queried deterministically through the MCP gateway
(§3.1), so live KG construction is orthogonal rather than competing.
KG4Diagnosis [@kg4diagnosis2025] (ML4H 2025) couples hierarchical
multi-agent diagnosis with KG augmentation; we share the KG-grounded
multi-agent thesis but target diet/herb evidence rather than diagnostic
reasoning. Across this line of work, evaluation reports task accuracy, F1, or
extraction precision — measures of *whether the answer is right* — but not
whether the evidence a grounded agent *cites* was actually retrieved. We treat
that gap, citation faithfulness, as a first-class safety property (§3.4, §6.3)
rather than assuming it from the presence of a retrieval step.

### TCM multi-agent and KG systems

The closest direct competitor is JingFang [@jingfang2025], a multi-agent TCM
consultation system with syndrome differentiation and dual-stage retrieval.
JingFang is prescription-only, has no Western-nutrition coverage, lacks an
English/bilingual interface, and exposes no KG query layer. OpenTCM
[@opentcm2025] applies GraphRAG over a 48K-entity TCM KG (P = 98.55 % on
classical-text extraction) but is TCM-only; our 5M-edge KG is a superset
combining Western nutrition with TCM. AgentClinic [@agentclinic2024]
introduced multimodal sequential clinical decision benchmarks; we operate in
the static-question evaluation paradigm.

### Citation faithfulness, attribution, and hallucination-despite-retrieval

A parallel literature studies whether grounded generations are actually
supported by their sources. Attribution-evaluation work formalizes the
question: ALCE [@gao2023alce] benchmarks citation precision and recall for
LLM-generated text, Attributed QA [@bohnet2022attributedqa] frames answers as
(claim, source-pointer) pairs scored by attributability, and a human study of
commercial generative search engines [@liu2023verifiability] finds only ~51.5%
of generated sentences are fully supported by their citations — establishing
that an inline-citation interface does not guarantee verifiable attribution.
On the RAG side, faithfulness is now a standard evaluation axis (RAGAS
[@es2023ragas]) and dedicated corpora document hallucination *despite*
retrieved context: RAGTruth [@niu2024ragtruth] provides ~18K word-level
hallucination annotations in RAG settings, FActScore [@min2023factscore]
measures atomic factual precision against a source, and "lost-in-the-middle"
effects [@liu2023lostmiddle] give a mechanism by which models fail to use
evidence that is present in the prompt. In medicine the stakes are explicit:
Med-HALT [@pal2023medhalt] benchmarks medical-domain hallucination, broad
surveys catalogue it [@zhang2023sirens], and clinical reviews flag fabricated
diagnoses and recommendations as a patient-safety concern [@thirunavukarasu2023llmmedicine].
Multi-agent debate has been proposed as a factuality mitigation
[@du2024debate; @liang2024mad], though agents sharing one base model can
reinforce rather than correct a shared error.

Our work differs in three ways. First, prior attribution evaluation targets
single-model generative search or QA in the general domain; we measure
attribution inside a *multi-agent KG-grounded clinical panel*, where each role
agent emits its own citations. Second, where ALCE-style metrics ask whether a
cited source *semantically supports* a claim, we measure a stricter, more basic
precondition — whether the cited chain index *resolves to evidence that was
retrieved at all* — and surface the limiting failure of citing specific indices
when retrieval returned nothing (§6.3). Third, we show this fabrication is a
hazard the grounding apparatus *introduces*: the non-grounded baselines emit no
citations and cannot fabricate. To our knowledge no prior work measures
citation faithfulness in a multi-agent KG-grounded system for supplement–drug
safety specifically.

### Existing benchmarks

TCM-Eval [@tcmeval2025] and TCM-5CEval [@tcm5ceval2025] cover TCM
knowledge questions only, with no clinical-deliberation evaluation.
MedQA [@medqa2021], MedMCQA [@medmcqa2022], and AgentClinic
[@agentclinic2024] are general or multimodal benchmarks without diet or
herb content. DietResearchBench-Clinical (§4) is the first public
benchmark covering herb-drug interaction reasoning, diet-bioactive
inference, and TCM-syndrome / Western-nutrition crosswalk in one set.
