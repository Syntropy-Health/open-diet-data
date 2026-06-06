# DietResearchBench-Clinical — Paired Bootstrap Tests

Comparison: Diet-OS vs each baseline system.  

Null hypothesis: Diet-OS performs no better than the baseline (mean_diff ≤ 0).  

Bonferroni correction applied across the full comparison family: n_baselines = 5, n_metrics_tested = 4 (verdict_kappa, ece, hdi_recall, defer_acc — excludes vacuous provenance + bilingual), n_comparisons = 20, adjusted α = 0.0025 per comparison.  

Bootstrap iterations: B = 10000; p-value via (k+1)/(B+1) convention; p_raw floor = 0.00010.  


| System | Metric | mean_diff | CI_lo | CI_hi | p_raw | p_adj (Bonferroni) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| single_llm | verdict_kappa | -0.000 | -0.150 | 0.150 | 0.56794 | 1.00000 |
| single_llm | ece | 0.030 | -0.095 | 0.151 | 0.31737 | 1.00000 |
| single_llm | hdi_recall | 0.858 | 0.571 | 1.000 | 0.00010 | 0.00200 |
| single_llm | provenance | — | — | — | — | — |
| single_llm | defer_acc | 0.175 | 0.075 | 0.300 | 0.00050 | 0.01000 |
| single_llm | bilingual | 0.000 | 0.000 | 0.000 | 1.00000 | 1.00000 |
| single_llm_rag | verdict_kappa | -0.000 | -0.150 | 0.150 | 0.56794 | 1.00000 |
| single_llm_rag | ece | 0.030 | -0.095 | 0.151 | 0.31737 | 1.00000 |
| single_llm_rag | hdi_recall | 0.858 | 0.571 | 1.000 | 0.00010 | 0.00200 |
| single_llm_rag | provenance | — | — | — | — | — |
| single_llm_rag | defer_acc | 0.175 | 0.075 | 0.300 | 0.00050 | 0.01000 |
| single_llm_rag | bilingual | 0.000 | 0.000 | 0.000 | 1.00000 | 1.00000 |
| yang2025 | verdict_kappa | -0.026 | -0.150 | 0.100 | 0.72303 | 1.00000 |
| yang2025 | ece | 0.026 | -0.095 | 0.145 | 0.33137 | 1.00000 |
| yang2025 | hdi_recall | 0.858 | 0.571 | 1.000 | 0.00010 | 0.00200 |
| yang2025 | provenance | — | — | — | — | — |
| yang2025 | defer_acc | 0.175 | 0.075 | 0.300 | 0.00050 | 0.01000 |
| yang2025 | bilingual | 0.000 | 0.000 | 0.000 | 1.00000 | 1.00000 |
| medagents | verdict_kappa | 0.025 | -0.125 | 0.175 | 0.44226 | 1.00000 |
| medagents | ece | 0.060 | -0.054 | 0.182 | 0.15908 | 1.00000 |
| medagents | hdi_recall | 0.858 | 0.571 | 1.000 | 0.00010 | 0.00200 |
| medagents | provenance | — | — | — | — | — |
| medagents | defer_acc | 0.175 | 0.075 | 0.300 | 0.00050 | 0.01000 |
| medagents | bilingual | 0.000 | 0.000 | 0.000 | 1.00000 | 1.00000 |
| mdagents | verdict_kappa | 0.125 | -0.050 | 0.300 | 0.11489 | 1.00000 |
| mdagents | ece | 0.125 | 0.007 | 0.253 | 0.01890 | 0.37796 |
| mdagents | hdi_recall | 0.717 | 0.429 | 1.000 | 0.00030 | 0.00600 |
| mdagents | provenance | — | — | — | — | — |
| mdagents | defer_acc | 0.100 | -0.025 | 0.225 | 0.10079 | 1.00000 |
| mdagents | bilingual | 0.000 | 0.000 | 0.000 | 1.00000 | 1.00000 |

**Interpretation:** p_adj < 0.05 (Bonferroni-adjusted across 20 comparisons) indicates Diet-OS statistically outperforms the baseline on that metric.  

Note: for ECE, lower is better; mean_diff < 0 is favourable for Diet-OS.  

Note: provenance + bilingual are excluded from the Bonferroni family (vacuous under v1 source-attribution proxy / no CJK content emitted); their p_adj rows are reported as 1.0.  
