# Globus Release Reconciliation

Milestone 6 reconciles the staged `v1` scientific-file release with static
website metadata. This is a local/HPC validation workflow only; it does not
promote, publish, or overwrite an immutable release.

## Staging Layout

Administrator-only staging path:

```text
/archive/jz7982/OralBGC-StructDB/staging/v1
```

Expected public MAG files are under:

```text
mags/individual/BGS-MAG-*.fna.gz
mags/MAG_SHA256SUMS
mags/public_mag_file_manifest.tsv
```

The original top-level `manifest.json` and `SHA256SUMS` describe the curated
resources that existed before MAG files were added. They are inputs, not the
final integrated metadata.

## Reconciliation Commands

Run on the HPC or against a copied staging tree:

```bash
python scripts/reconcile_globus_release.py validate \
  --release-root /archive/jz7982/OralBGC-StructDB/staging/v1 \
  --release-id v1 \
  --expected-mag-count 583 \
  --expected-structure-count 22622
```

Build candidate metadata without replacing the staged top-level files:

```bash
python scripts/reconcile_globus_release.py build-candidate-manifest \
  --release-root /archive/jz7982/OralBGC-StructDB/staging/v1 \
  --release-id v1 \
  --output-report /scratch/jz7982/oralbgc_v1_reconciliation \
  --expected-mag-count 583 \
  --expected-structure-count 22622
```

The output includes:

```text
integrated-resource-manifest.json
SHA256SUMS.integrated
reconciliation-summary.json
```

## Counting Policy

Scientific resources include MAG FASTA files, structure CIF files, structure
archives, the bulk BGC GenBank archive, protein FASTA, Foldseek tables,
BiG-SCAPE public resources, AlphaFold/QC tables, and public metadata tables.

Release metadata is counted separately and includes manifests, checksum files,
README files, and release documentation. `SHA256SUMS.integrated` does not
checksum itself. A release manifest may record the checksum of the checksum
file, but self-referential hashes are not used.

## Validation Rules

The reconciler detects missing files, duplicate paths, duplicate entity
mappings, checksum mismatches, size mismatches, unsafe paths, private filenames,
invalid MAG/structure accessions, and release-version mismatches.

Individual BGC GenBank files are not enabled for this release. BGC download
behavior is bulk-only until separately generated, mapped, checksummed, and
validated individual files exist.

Milestone 6D audit result: the integrated manifest contains one
`bgc_bulk_archive` and zero BGC individual-download rows for 1,913 BGC records.
The release tree contains `antismash/BGS_BGC_GBK_v1.0.tar.gz` and no loose
`.gbk` files. Protein resources are also bulk-only: the only FASTA is
`sequences/BGS_BGC_proteins_v1.0.faa`, covering 22,626 protein accessions.

## URL Validation

Collection pages, direct HTTPS downloads, and browser CORS are separate
capabilities. Use:

```bash
python scripts/validate_public_resource_urls.py \
  --url https://example.org/path/to/resource \
  --allowed-host example.org \
  --output /tmp/oralbgc-url-validation.json
```

Use `--cors-url` only for CORS-specific checks. Ordinary download success does
not imply browser fetch support.

For static publication, direct links are derived from the approved HTTPS base,
the selected publication-state root (`staging/v1` for staging validation or
`releases/v1` for publication), and the manifest `relative_path`. Collection
URLs are never used as file bases.

Milestone 6E makes visitor delivery direct-download-only. Public static output
must not expose Globus collection browsing URLs, collection UUIDs, `origin_id`
query strings, or `Browse in Globus` actions. Collection URLs remain
operator-side reconciliation context only.

Milestone 6F applies the same direct-download-only policy to the runtime
Railway editor preview. The server-rendered app constructs visitor links only
from the approved HTTPS base, configured release-relative root, and validated
manifest `relative_path`; changing the root from `staging/v1` to `releases/v1`
is the intended future publication switch after promotion and validation.

## Milestone 6C Evidence Integration

The copied HPC evidence bundle is consumed from
`/Users/jz7982/Documents/OralBGC-StructDB_Globus_reconciliation/v1`. It records
the real June 16, 2026 HPC validation of `/staging/v1/`: 23,310 physical files,
22,722 original manifest/checksum entries, 583 MAG checksum entries, 583 MAG
public-manifest rows, zero checksum failures, zero missing/unexpected files, and
zero private filename or metadata-content hits.

`build-candidate-from-evidence` validates the evidence files without requiring
local MAG binaries, checks MAG and structure database coverage, and writes:

```text
artifacts/milestone6c-release-candidate/integrated-resource-manifest.json
artifacts/milestone6c-release-candidate/SHA256SUMS.integrated
artifacts/milestone6c-release-candidate/release-summary.json
artifacts/milestone6c-release-candidate/resource-counts.json
artifacts/milestone6c-release-candidate/evidence-validation-report.json
artifacts/milestone6c-release-candidate/promotion-readiness.json
artifacts/milestone6c-release-candidate/production-config-candidate.env
```

The integrated payload count is 23,305: the 22,722 original approved resource
entries plus 583 validated MAG FASTA records. `SHA256SUMS.integrated` covers
the 23,305 payload entries and does not include itself.
