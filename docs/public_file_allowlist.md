# Public File Allowlist

Allowed categories: public tables, sequence FASTA, antiSMASH public archives, BiG-SCAPE public archives, AF3 structure archives, Foldseek public outputs, documentation, and checksums.

Explicit exclusions: `PHRC_integrated_BGC_protein_structure_summary.with_internal_priority_columns.tsv`, `drug_discovery_ranked_candidates.tsv`, `candidate_peptides.faa`, `high_priority_candidate_models.tar.gz`, internal candidate-model directories, internal ranking files, and any file or column carrying private IP-development notes.

The application exposes only files inserted into `download_manifest` by the ingestion allowlist.
