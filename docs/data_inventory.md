# Data Inventory

Source package: `${PACKAGE_ROOT}`

Public TSVs inspected: MAG summary (583 rows), BGC summary (1,913), BGC protein summary (22,626), BiG-SCAPE GCF summary (179), BiG-SCAPE BGC-to-GCF (8,731), AF3 model summary (10,972), Foldseek best hit (10,972), Foldseek AF3QC merged (10,972), public integrated summary (22,626), and column dictionary (111).

Primary identifiers are unique for `mag_id`, `region_basename`, `bgc_id`, `query`, and `bigscape_gcf_id_full_primary` in their summary tables. `BiGSCAPE_BGC_to_GCF.tsv` intentionally has duplicate BGC and GCF identifiers because it stores assignments across classes/cutoffs.

CIF inventory: 22,622 extracted CIF files are present under approved structure directories: 12,551 short, 9,675 medium, and 396 long-directory CIFs. Joined by protein query, these correspond to 12,551 short proteins, 9,675 medium proteins, 351 long proteins, and 45 very-long proteins. AF3 QC and Foldseek/PDB rows currently cover 10,972 short proteins; see `docs/model_qc_coverage_report.md`. Source path columns are excluded from generated SQLite records.

Network archives: `bigscape/networks.tar.gz` contains 37 `.network` files. `bigscape/cytoscape_files.tar.gz` currently contains no files, so the checkpoint exposes the archive but does not fabricate a network preview.

Checksum manifest contains 22,651 entries and includes individual CIF checksums plus top-level archives and tables.
