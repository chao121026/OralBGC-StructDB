# Schema Plan

The checkpoint uses pragmatic read-optimized SQLite tables mirroring public TSVs, with added `dataset` and stable public identifiers. Public IDs use `PHRC|<original identifier>` and preserve original identifiers in separate columns.

Core tables: `mag_summary`, `bgc_summary`, `bgc_protein_summary`, `bigscape_gcf_summary`, `bigscape_bgc_to_gcf`, `af3_model_summary`, `foldseek_besthit_all`, `foldseek_af3qc_merged_all`, `integrated_summary`, `column_dictionary`, `download_manifest`, `structure_file_map`, and `database_metadata`.

Sensitive columns and files are excluded during ingestion. Structure and download serving are controlled by `structure_file_map` and `download_manifest`; no route accepts raw filesystem paths.

Indexes are created for dataset, public IDs, original join keys, product, gene name, sequence length, length bucket, AF3 confidence, compactness, Foldseek target, and PDB structural-match category where those columns exist.
