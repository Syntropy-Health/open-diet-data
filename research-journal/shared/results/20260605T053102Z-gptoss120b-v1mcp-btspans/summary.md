# DietResearchBench-Clinical — Evaluation Summary

Systems: single_llm, single_llm_rag, yang2025, medagents, mdagents, diet_os, diet_os_llm_triage  

All values: mean [95% CI bootstrap]. '—' = metric undefined for this system/split.


| System | Verdict κ | ECE | HDI Recall | Provenance | Defer Acc | Bilingual |
| --- | --- | --- | --- | --- | --- | --- |
| single_llm | 0.267 [0.031, 0.501] | 0.190 [0.060, 0.335] | 0.000 [0.000, 0.000] | — | 0.550 [0.400, 0.700] | 0.000 [0.000, 0.000] |
| single_llm_rag | 0.267 [0.031, 0.501] | 0.190 [0.060, 0.335] | 0.000 [0.000, 0.000] | — | 0.550 [0.400, 0.700] | 0.000 [0.000, 0.000] |
| yang2025 | 0.297 [0.086, 0.518] | 0.220 [0.091, 0.364] | 0.000 [0.000, 0.000] | — | 0.550 [0.400, 0.700] | 0.000 [0.000, 0.000] |
| medagents | 0.345 [0.180, 0.521] | 0.469 [0.328, 0.608] | 0.000 [0.000, 0.000] | — | 0.550 [0.400, 0.700] | 0.000 [0.000, 0.000] |
| mdagents | 0.203 [0.021, 0.389] | 0.346 [0.203, 0.492] | 0.142 [0.000, 0.500] | — | 0.625 [0.475, 0.775] | 0.000 [0.000, 0.000] |
| diet_os | 0.247 [0.041, 0.479] | 0.530 [0.385, 0.669] | 0.858 [0.500, 1.000] | — | 0.725 [0.575, 0.850] | 0.000 [0.000, 0.000] |
| diet_os_llm_triage | 0.192 [-0.040, 0.429] | 0.437 [0.286, 0.584] | 0.429 [0.000, 0.833] | — | 0.625 [0.475, 0.775] | 0.000 [0.000, 0.000] |

## Metric abbreviations

| Key | Full name |
| --- | --- |
| verdict_kappa | Verdict κ |
| ece | ECE |
| hdi_recall | HDI Recall |
| provenance | Provenance |
| defer_acc | Defer Acc |
| bilingual | Bilingual |
