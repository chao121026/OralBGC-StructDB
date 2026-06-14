# Accession Migration Runbook

This migration is phased. Phase 1 is inspection and dry-run planning only.
Filesystem apply, TSV rewrites, archive regeneration, database rebuilds, and URL
changes require a reviewed Phase 1 report.

## Phase 1 Dry Run

Run from the repository root:

```bash
python scripts/migrate_public_accessions.py \
  --source-root /Users/jz7982/Documents/PHRC_BGCStructDB_v1 \
  --output-root /Users/jz7982/Documents/PHRC_BGCStructDB_web \
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
```

The dry run does not modify source data and does not persist
`data/accession_registry.tsv`.

## Validation

Validate the preview or approved registry:

```bash
python scripts/validate_accession_migration.py \
  --registry artifacts/accession_migration/accession_registry_preview.tsv \
  --release-root /Users/jz7982/Documents/PHRC_BGCStructDB_web
```

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

## Current Phase 1 Result

The local package inspected at `/Users/jz7982/Documents/PHRC_BGCStructDB_v1`
produced:

- MAG: 583
- BGC: 1,913
- GCF: 179
- Protein: 22,626
- Structure: 22,622
- Collisions: 0
- Missing parents: 0
- Copyable files discovered: 22,622 structure CIF files

BGC GenBank files are present as `antismash/region_gbk.tar.gz` in the local
package, not as an expanded `antismash/region_gbk/*.gbk` directory. Phase 3
archive rewriting should expand or stream that archive deterministically before
creating accession-named GBK members.
