# Model, QC, and Foldseek Coverage Report

The apparent discrepancy is expected after inspecting the real files. The public package contains predicted-structure CIF files for nearly every BGC protein, while AF3 QC and Foldseek/PDB annotation tables currently cover a smaller integrated subset. In this release, AF3 QC and Foldseek/PDB rows are present for 10,972 short proteins. Medium, long, and very-long proteins can still have downloadable CIF structures without parsed AF3 QC or Foldseek rows.

The website therefore uses three distinct concepts: `Structure available`, `AF3 QC available`, and `Foldseek/PDB annotation available`. It does not report the 22,622 CIF files as AF3 QC-annotated models.

| Length bucket | Total proteins | Available CIF files | AF3 QC rows | Foldseek rows | Missing CIFs | CIFs lacking AF3 QC | CIFs lacking Foldseek |
|---|---:|---:|---:|---:|---:|---:|---:|
| short | 12555 | 12551 | 10972 | 10972 | 4 | 1579 | 1579 |
| medium | 9675 | 9675 | 0 | 0 | 0 | 9675 | 9675 |
| long | 351 | 351 | 0 | 0 | 0 | 351 | 351 |
| very_long | 45 | 45 | 0 | 0 | 0 | 45 | 45 |

Notes:
- The 45 `very_long` proteins have CIFs in the long structure archive/directory, so the protein length bucket and archive bucket are not always identical.
- Four short proteins do not have an approved CIF file in the current package.
- CIF route authorization is based on `structure_file_map`; AF3 QC and Foldseek availability are based on their respective public TSVs.
