# DietResearchBench-Clinical — Paired Bootstrap Tests

Comparison: Diet-OS vs each baseline system.  

Null hypothesis: Diet-OS performs no better than the baseline (mean_diff ≤ 0).  

Bonferroni correction applied across the full comparison family: n_baselines = 5, n_metrics_tested = 6 (verdict_kappa, ece, hdi_recall, defer_acc — excludes vacuous provenance + bilingual), n_comparisons = 30, adjusted α = 0.0017 per comparison.  

Bootstrap iterations: B = 10000; p-value via (k+1)/(B+1) convention; p_raw floor = 0.00010.  


| System | Metric | mean_diff | CI_lo | CI_hi | p_raw | p_adj (Bonferroni) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| single_llm | verdict_kappa | 0.024 | -0.125 | 0.175 | 0.44346 | 1.00000 |
| single_llm | ece | 0.053 | -0.070 | 0.177 | 0.19788 | 1.00000 |
| single_llm | hdi_recall | 1.000 | 1.000 | 1.000 | 0.00010 | 0.00300 |
| single_llm | provenance | — | — | — | — | — |
| single_llm | defer_acc | 0.199 | 0.075 | 0.325 | 0.00020 | 0.00600 |
| single_llm | bilingual | 0.000 | 0.000 | 0.000 | 1.00000 | 1.00000 |
| single_llm | cite_faith | — | — | — | — | — |
| single_llm | fabricate | — | — | — | — | — |
| single_llm_rag | verdict_kappa | 0.024 | -0.125 | 0.175 | 0.44346 | 1.00000 |
| single_llm_rag | ece | 0.053 | -0.070 | 0.177 | 0.19788 | 1.00000 |
| single_llm_rag | hdi_recall | 1.000 | 1.000 | 1.000 | 0.00010 | 0.00300 |
| single_llm_rag | provenance | — | — | — | — | — |
| single_llm_rag | defer_acc | 0.199 | 0.075 | 0.325 | 0.00020 | 0.00600 |
| single_llm_rag | bilingual | 0.000 | 0.000 | 0.000 | 1.00000 | 1.00000 |
| single_llm_rag | cite_faith | — | — | — | — | — |
| single_llm_rag | fabricate | — | — | — | — | — |
| yang2025 | verdict_kappa | -0.001 | -0.150 | 0.125 | 0.57684 | 1.00000 |
| yang2025 | ece | 0.050 | -0.071 | 0.169 | 0.20498 | 1.00000 |
| yang2025 | hdi_recall | 1.000 | 1.000 | 1.000 | 0.00010 | 0.00300 |
| yang2025 | provenance | — | — | — | — | — |
| yang2025 | defer_acc | 0.199 | 0.075 | 0.325 | 0.00020 | 0.00600 |
| yang2025 | bilingual | 0.000 | 0.000 | 0.000 | 1.00000 | 1.00000 |
| yang2025 | cite_faith | — | — | — | — | — |
| yang2025 | fabricate | — | — | — | — | — |
| medagents | verdict_kappa | 0.049 | -0.100 | 0.200 | 0.31997 | 1.00000 |
| medagents | ece | 0.084 | -0.039 | 0.214 | 0.09259 | 1.00000 |
| medagents | hdi_recall | 1.000 | 1.000 | 1.000 | 0.00010 | 0.00300 |
| medagents | provenance | — | — | — | — | — |
| medagents | defer_acc | 0.199 | 0.075 | 0.325 | 0.00020 | 0.00600 |
| medagents | bilingual | 0.000 | 0.000 | 0.000 | 1.00000 | 1.00000 |
| medagents | cite_faith | — | — | — | — | — |
| medagents | fabricate | — | — | — | — | — |
| mdagents | verdict_kappa | 0.149 | -0.050 | 0.350 | 0.07639 | 1.00000 |
| mdagents | ece | 0.149 | 0.024 | 0.282 | 0.00870 | 0.26097 |
| mdagents | hdi_recall | 0.859 | 0.571 | 1.000 | 0.00010 | 0.00300 |
| mdagents | provenance | — | — | — | — | — |
| mdagents | defer_acc | 0.124 | -0.025 | 0.275 | 0.06039 | 1.00000 |
| mdagents | bilingual | 0.000 | 0.000 | 0.000 | 1.00000 | 1.00000 |
| mdagents | cite_faith | — | — | — | — | — |
| mdagents | fabricate | — | — | — | — | — |

**Interpretation:** p_adj < 0.05 (Bonferroni-adjusted across 30 comparisons) indicates Diet-OS statistically outperforms the baseline on that metric.  

Note: for ECE, lower is better; mean_diff < 0 is favourable for Diet-OS.  

Note: provenance + bilingual are excluded from the Bonferroni family (vacuous under v1 source-attribution proxy / no CJK content emitted); their p_adj rows are reported as 1.0.  
