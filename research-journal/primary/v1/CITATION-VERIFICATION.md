# Citation-verification checklist — `references.bib` (31 entries)

**Why this matters most for *this* paper:** the thesis is that grounded LLMs
fabricate citations. The paper must not. **Every entry below is UNVERIFIED in
the drafting session** — this checklist is the to-do, not a sign-off. Confidence
labels are the author's prior, not a verification: `Confident` = well-known
work the author is highly confident exists; `Plausible` = likely real, details
unconfirmed; `SUSPECT` = placeholder/auto-generated metadata, treat as
possibly-fabricated until confirmed on arXiv/ACL/DOI.

Verification protocol per entry: (1) confirm the work exists; (2) confirm
title/authors/year; (3) confirm venue OR arXiv ID (not a guessed one);
(4) confirm it actually supports the sentence that cites it.

---

## Tier 1 — BLOCKER: placeholder / missing-author / unconfirmed-arXiv-ID

These have empty or `and others` authors and/or arXiv IDs that were not
confirmed against arXiv. **bibtex already warns on the first three.** Highest
fabrication risk — verify or remove before any submission.

| key | claim | issue | action |
|---|---|---|---|
| `camp2026` | "CAMP: Case-Adaptive Multi-agent Panel", arXiv **2604.00085** | **no author**; arXiv ID is future-dated (Apr 2026) and unconfirmed | confirm the paper + ID exist; fill authors; else cut (it's only a positioning peer in §2) |
| `nutriorion2026` | "NutriOrion: four-specialist agent panel", arXiv **2602.18650** | **no author**; ID unconfirmed (Feb 2026) | confirm exists + authors; else cut (positioning peer) |
| `kg4diagnosis2025` | "KG4Diagnosis", PMLR, arXiv **2412.16833** | **empty author** (note says "Zuo et al."); ID plausible (Dec 2024) | confirm ID 2412.16833 + author list + ML4H 2024 PMLR venue |
| `medrag2025` | "MedRAG: KG-Elicited Clinical Reasoning with EHR", ACM Web Conf 2025 | author = "Zhao and others" | confirm full author list + WWW'25 venue/pages |
| `opentcm2025` | "OpenTCM: GraphRAG over 48K-entity TCM KG", arXiv 2504.20118 | author = "He and others" | confirm ID + full authors |

## Tier 2 — HIGH: §2 attribution / faithfulness literature (added in `dc07768`)

The intellectual core of the related-work positioning. Author is `Confident`
these are real, well-known works, but exact venue/year/pages must be confirmed
(and that each supports its citing sentence in §2).

| key | claim | confidence | confirm |
|---|---|---|---|
| `gao2023alce` | Gao et al., "Enabling LLMs to Generate Text with Citations" (ALCE), EMNLP 2023 | Confident | EMNLP'23 pages; citation-precision/recall claim |
| `liu2023verifiability` | Liu et al., "Evaluating Verifiability in Generative Search Engines", Findings EMNLP 2023 | Confident | the ~51.5% fully-supported figure quoted in §2 |
| `bohnet2022attributedqa` | Bohnet et al., "Attributed Question Answering", arXiv 2022 | Confident | arXiv ID; (claim, source) framing |
| `es2023ragas` | Es et al., "RAGAS", arXiv 2023 / EACL 2024 demo | Confident | which venue to cite (arXiv vs EACL'24) |
| `min2023factscore` | Min et al., "FActScore", EMNLP 2023 | Confident | EMNLP'23 pages |
| `niu2024ragtruth` | Niu et al., "RAGTruth", ACL 2024 | Confident | ACL'24 pages; the ~18K-annotation figure quoted in §2 |
| `liu2023lostmiddle` | Liu et al., "Lost in the Middle", TACL 2024 | Confident | TACL vol/year (often mis-cited as 2023) |
| `pal2023medhalt` | Pal et al., "Med-HALT", CoNLL 2023 | Confident | CoNLL'23 pages |
| `thirunavukarasu2023llmmedicine` | "LLMs in medicine", Nature Medicine 2023 | Confident | vol/issue/pages + DOI |
| `zhang2023sirens` | Zhang et al., "Siren's Song in the AI Ocean", arXiv 2309.01219 | Confident | arXiv ID |
| `du2024debate` | Du et al., "Improving Factuality... Multiagent Debate", ICML 2024 | Confident | ICML'24 |
| `liang2024mad` | Liang et al., "Encouraging Divergent Thinking... Multi-Agent Debate", EMNLP 2024 | Confident | EMNLP'24 pages |

## Tier 3 — CONFIRM: core baselines + domain peers

| key | claim | confidence | confirm |
|---|---|---|---|
| `medagents2024` | Tang et al., "MedAgents", Findings ACL 2024 | Confident | venue (Findings ACL vs EMNLP) |
| `mdagents2024` | Kim et al., "MDAgents", NeurIPS 2024 | Confident | NeurIPS'24 |
| `yang2025` | Yang et al., JMIR Formative Research 2025 | **Verified earlier** (DOI 10.2196/75421) | ✓ keep |
| `agentclinic2024` | Schmidgall et al., "AgentClinic", arXiv 2405.07960 | Confident | arXiv ID |
| `medqa2021` | Jin et al., "What Disease...", Applied Sciences 2021 | Confident | vol/pages |
| `medmcqa2022` | Pal et al., "MedMCQA", CHIL 2022 | Confident | add `year=2022`; PMLR vol |
| `wu2025` | Wu et al., "Lessons Learned from Eval of LLM Multi-agents..." 2025 | Plausible | full title/venue/ID |
| `amgrag2025` | Rezaei et al., "Agentic Medical KGs..." 2025 | Plausible | venue/ID |
| `kgsmile2025` | "Explainable KG-RAG (KG-SMILE)" 2025 | Plausible | venue/ID |
| `jingfang2025` | Yang et al., "Jingfang: LLM multi-agent TCM" 2025 | Plausible | venue/ID |
| `tcmeval2025` | Cheng et al., "TCM-Eval" 2025 | Plausible | venue/ID |
| `tcm5ceval2025` | Huang et al., "TCM-5CEval" 2025 | Plausible | venue/ID |

## Tier 4 — internal / software (no external verification)

| key | note |
|---|---|
| `ag2v0_12` | AG2 framework v0.12 (GitHub URL) — confirm URL + version pin only |
| `v2benchmark2026` | DietResearchBench v2 — "in preparation" companion; ensure it's flagged as forthcoming, not a live citation |

---

## Build status (LaTeX)

`arxiv-package/` builds clean: `pdflatex → bibtex → pdflatex×2` (`./build.sh`) →
21-page `paper.pdf`, **0 undefined citations**, 31 bibitems emitted. The only
bibtex warnings are the missing-author sort keys for `camp2026`,
`nutriorion2026`, `kg4diagnosis2025` (Tier 1) — fixing those clears the
warnings too.
