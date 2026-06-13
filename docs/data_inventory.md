# Data Inventory

Source package: `/Users/jz7982/Documents/PHRC_BGCStructDB_v1`

Public TSVs inspected: MAG summary (583 rows), BGC summary (1,913), BGC protein summary (22,626), BiG-SCAPE GCF summary (179), BiG-SCAPE BGC-to-GCF (8,731), AF3 model summary (10,972), Foldseek best hit (10,972), Foldseek AF3QC merged (10,972), public integrated summary (22,626), and column dictionary (111).

Primary identifiers are unique for `mag_id`, `region_basename`, `bgc_id`, `query`, and `bigscape_gcf_id_full_primary` in their summary tables. `BiGSCAPE_BGC_to_GCF.tsv` intentionally has duplicate BGC and GCF identifiers because it stores assignments across classes/cutoffs.

CIF inventory: 22,622 extracted CIF files are present under approved structure directories: 12,551 short, 9,675 medium, and 396 long. All 10,972 AF3 model summary `query` values map to local CIF filenames by `<query>.cif`; the source `model_cif` basenames do not map directly because they refer to old extracted AF3 paths.

Network archives: `bigscape/networks.tar.gz` contains 37 `.network` files. `bigscape/cytoscape_files.tar.gz` currently contains no files, so the checkpoint exposes the archive but does not fabricate a network preview.

Checksum manifest contains 22,651 entries and includes individual CIF checksums plus top-level archives and tables.
