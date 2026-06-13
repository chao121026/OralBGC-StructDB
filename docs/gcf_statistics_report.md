# GCF Statistics Report

The website summary uses the primary BiG-SCAPE GCF assignment recorded in `BiGSCAPE_GCF_summary.tsv` and `BGC_summary.tsv`. All 179 public GCF summary rows use the `c0.3|...|FAM_...` identifier pattern, so the checkpoint labels this count as primary c0.3 GCFs.

| Metric | Count |
|---|---:|
| Primary c0.3 GCFs in summary table | 179 |
| BGCs with primary GCF assignment | 1744 |
| BGCs without primary GCF assignment | 169 |

All-cutoff assignments remain available through `BiGSCAPE_BGC_to_GCF.tsv` and downloads:

| BiG-SCAPE cutoff | Distinct GCFs | Distinct BGC keys |
|---|---:|---:|
| 0.3 | 179 | 1761 |
| 0.4 | 170 | 1809 |
| 0.5 | 182 | 2000 |
| 0.6 | 338 | 3161 |

Interpretation: the future GCF browser should be labeled as primary c0.3 GCFs by default. All-cutoff assignment tables should remain downloadable and can power advanced network/cutoff views later.
