# Accession Migration Runbook

This migration is phased. Phase 1 is inspection and dry-run planning only.
Phase 2 creates the accession-based release tree. Phase 3 rebuilds the website
SQLite database and routes so stable BGS accessions are canonical public
identifiers while original PHRC identifiers remain searchable provenance.

## Phase 1 Dry Run

Run from the repository root:

```bash
python scripts/migrate_public_accessions.py \
  --source-root /path/to/PHRC_BGCStructDB_v1 \
  --output-root /path/to/planning_artifacts \
  --registry data/accession_registry.tsv \
  --release-version v1.0 \
  --dry-run
```

Dry run writes:

```text
artifacts/accession_migration/accession_registry_preview.tsv
artifacts/accession_migration/file_rename_plan.tsv
artifacts/accession_migration/tsv_column_plan.tsv
artifacts/accession_migration/collision_report.tsv
artifacts/accession_migration/missing_reference_report.tsv
artifacts/accession_migration/legacy_reference_report.tsv
artifacts/accession_migration/count_summary.json
artifacts/accession_migration/rollback_manifest.tsv
artifacts/accession_migration/source_root_inventory.tsv
artifacts/accession_migration/gbk_archive_inventory.tsv
artifacts/accession_migration/gbk_transform_plan.tsv
artifacts/accession_migration/legacy_reference_classification.tsv
artifacts/accession_migration/internal_accession_registry.tsv
artifacts/accession_migration/public_accession_mapping.tsv
```

The dry run does not modify source data and does not persist
`data/accession_registry.tsv`.

`internal_accession_registry.tsv` retains relative source and public paths for
migration operations. `public_accession_mapping.tsv` omits path and checksum
columns so public downloads do not expose local filesystem layout.

## Validation

Validate the preview or approved registry:

```bash
python scripts/validate_accession_migration.py \
  --registry artifacts/accession_migration/accession_registry_preview.tsv \
  --release-root /path/to/planning_artifacts \
  --phase dry-run
```

`--phase dry-run` treats accession-named public files with checksums as planned
outputs. `--phase applied` treats those missing files as errors.

Run automated tests:

```bash
pytest -q tests/test_accession_migration.py
pytest -q
```

## Apply Mode

Apply mode is disabled unless `--apply` is passed explicitly:

```bash
python scripts/migrate_public_accessions.py \
  --source-root /path/to/current/release \
  --output-root /path/to/accession_release \
  --registry data/accession_registry.tsv \
  --release-version v1.0 \
  --apply
```

Apply mode aborts if collisions or required missing parent relationships are
present. It does not delete the original data tree. Planned file operations copy
source files to accession-based paths and refuse to overwrite existing files with
different content.

## Current Validated Result

The reviewed PHRC source package
produced:

- MAG: 583
- BGC: 1,913
- GCF: 179
- Protein: 22,626
- Structure: 22,622
- Collisions: 0
- Missing parents: 0
- Copyable files discovered: 22,622 structure CIF files
- GBK archive members: 1,925 file members
- GBK members matched to BGC accessions: 1,913
- GBK members not present in the BGC registry: 12
- Approved GBK exclusions: 12
- Unresolved GBKs: 0

BGC GenBank files in the accession release are published as
`antismash/BGS_BGC_GBK_v1.0.tar.gz` with 1,913 accession-named members. The 12
reviewed extra source GBKs remain excluded from public archives and documented
in provenance.

## Phase 3 Website Switch

The public app should run with:

```bash
PHRC_BGCSTRUCTDB_DATA_ROOT=/path/to/PHRC_BGCStructDB_BGS_v1
python scripts/ingest_package_to_sqlite.py \
  --package-root "$PHRC_BGCSTRUCTDB_DATA_ROOT" \
  --db app/data/phrc_bgcstructdb.sqlite
```

Canonical URLs are `/mags/BGS-MAG-*`, `/bgcs/BGS-BGC-*`,
`/gcfs/BGS-GCF-C03-*`, `/proteins/BGS-PRT-*`, and `/structures/BGS-STR-*`.
Exact legacy PHRC identifiers redirect with HTTP 308 to the matching BGS URL.

## Phase 2 GBK Plan

For each matched BGC GBK:

1. stream the source member from `antismash/region_gbk.tar.gz`;
2. validate with Biopython GenBank parsing;
3. preserve `record.id`, `record.name`, LOCUS, feature coordinates, and
   biological annotations;
4. add or merge a Biopython structured comment section named
   `PHRC_BGCStructDB`;
5. write the target member as `BGS-BGC-XXXXXX.gbk` in a clean output directory;
6. rebuild the archive with stable member ordering and normalized timestamps;
7. verify exactly one transformed GBK member exists per mapped BGC.

Planned structured comment payload:

```python
{
    "PHRC_BGCStructDB": {
        "Public-Accession": "BGS-BGC-000001",
        "Source-Collection": "PHRC",
        "Original-BGC-Identifier": "...",
        "Original-Filename": "...",
    }
}
```

The 12 unmatched GBK members are true region-level records in public MAG
directories, but they are absent from the curated public BGC, protein, and
integrated summary tables used for the 1,913 public BGC count. Ten are classified
as `superseded_record`; two have exact sequence checksums already represented by
public BGC accessions and are classified as `duplicate_content`. They are listed
in `artifacts/accession_migration/unmatched_gbk_review.tsv` and approved for
internal exclusion in `artifacts/accession_migration/gbk_exclusion_manifest.tsv`.
Phase 2 apply must pass the reviewed manifest with `--gbk-exclusion-manifest`;
unknown extra archive members remain blocking.
