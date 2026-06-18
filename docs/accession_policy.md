# Public Accession Policy

OralBGC-StructDB public records use stable `BGS` accessions that are independent
of source collection names, local filenames, pipeline row order, and mutable
database row IDs.

## Namespace

The accession namespace is database-wide:

- MAG: `BGS-MAG-000001`
- BGC: `BGS-BGC-000001`
- GCF: `BGS-GCF-C03-0001`
- Protein: `BGS-PRT-000001`
- Structure: `BGS-STR-000001`

`MAG`, `BGC`, `PRT`, and `STR` use six-digit suffixes. `GCF` accessions include
the BiG-SCAPE cutoff code and a four-digit suffix.

## Permanence

Accessions are assigned once and never reused. Existing registry mappings are the
source of truth on rerun. New records receive only new suffixes after the highest
existing accession for that entity type. Removed records should be marked
`retired`; their accessions remain reserved.

## Provenance

Original pipeline identifiers are preserved as searchable provenance. Public
records must retain:

- `public_accession`
- `source_collection`
- `original_identifier`
- `original_filename`
- `source_sample_id`
- `source_bin_id`
- `source_contig_id`
- `source_region_id`
- `release_version`
- `accession_status`

Legacy identifiers may appear in explicitly named `original_*` or `source_*`
fields, but public display labels, canonical URLs, archive members, and manifest
primary filenames should use `BGS` accessions.

## Citation Language

Each MAG, BGC, GCF, protein and predicted structure is assigned a stable database
accession independent of pipeline-specific identifiers. Original sample, bin,
contig, antiSMASH-region and file identifiers are retained as searchable
provenance metadata.
