# Public File Allowlist

Allowed categories: public tables, sequence FASTA, antiSMASH public archives, BiG-SCAPE public archives, AF3 structure archives, Foldseek public outputs, documentation, and checksums.

Explicit exclusions: `PHRC_integrated_BGC_protein_structure_summary.with_internal_priority_columns.tsv`, `drug_discovery_ranked_candidates.tsv`, `candidate_peptides.faa`, `high_priority_candidate_models.tar.gz`, internal candidate-model directories, internal ranking files, and any file or column carrying private IP-development notes.

The application exposes only files inserted into `download_manifest` by the ingestion allowlist.

## Presentation Hierarchy

The public allowlist is broader than the default visual emphasis on `/downloads`. Recommended downloads are the primary integrated metadata table, BGC protein FASTA, primary c0.3 BiG-SCAPE GCF summary, antiSMASH region GenBank archive, AF3 structure archives, README, column dictionary, and checksum manifest.

Component tables, Foldseek resources, BiG-SCAPE bundles, antiSMASH reproducibility bundles, workflow notes, citation text, and duplicate documentation entries remain allowlisted for reproducibility but are grouped under Advanced analysis and reproducibility files.

`PHRC_integrated_BGC_protein_structure_summary.tsv` is marked as the recommended primary metadata table because it combines public BGC, protein, AF3 structure, AF3 QC, and Foldseek/PDB metadata. Component tables should be used when auditing or rebuilding a specific layer.

The 45-byte `cytoscape_files.tar.gz` archive is retained in the manifest for traceability but is marked unavailable in the public presentation because it contains no usable Cytoscape content in this release.
