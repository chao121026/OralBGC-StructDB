# Public Identifier Schema

The permanent registry lives at `data/accession_registry.tsv` when approved for
commit. Phase 1 writes a preview to
`artifacts/accession_migration/accession_registry_preview.tsv`.

## Registry Columns

Required columns:

- `entity_type`
- `public_accession`
- `source_collection`
- `original_identifier`
- `original_filename`
- `parent_public_accession`
- `parent_original_identifier`
- `source_sample_id`
- `source_bin_id`
- `source_contig_id`
- `source_region_id`
- `release_version_created`
- `accession_status`
- `source_path`
- `public_path`
- `source_sha256`
- `public_sha256`

## Constraints

- `public_accession` is globally unique.
- `(entity_type, original_identifier)` is unique.
- Reruns reuse existing registry rows.
- Removed records are retired rather than renumbered.
- Parent accessions must resolve when the source record has a required parent.

## Relationships

Strict hierarchy:

```text
MAG
  BGC
    Protein
      Structure
```

GCF accessions link to BGCs through assignment tables and are not strict parents
in the biological hierarchy.

## Public Paths

Phase 1 plans these public filenames:

- MAG: `mags/BGS-MAG-000001.fna`
- BGC GenBank: `antismash/region_gbk/BGS-BGC-000001.gbk`
- Protein FASTA: `sequences/proteins/BGS-PRT-000001.faa`
- Structure CIF: `structures/BGS-STR-000001.cif`
- GCF bundle: `bigscape/gcfs/BGS-GCF-C03-0001`

Phase 3 should rewrite TSVs, archives, manifests, and website/database records to
use these as the public-facing identifiers while preserving original IDs in
provenance columns.
