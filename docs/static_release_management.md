# Static Release Management

This document describes the static-export release model used after milestone 5.
It is operational guidance, not a new scientific release.

Milestone 6F retains this workflow for snapshots, regression checks, and
archival builds. The selected editor-preview website is the server-rendered
Jinja application on Railway, backed by the bundled read-only SQLite database
and direct HTTPS resource delivery.

## Immutable Releases

Published scientific releases are immutable. A future release such as `v2` must
be prepared in a new staging directory, compared with its parent release, and
reviewed before publication. Existing `v1` source data, BGS accessions, and
relationships must not be modified by the static exporter.

The release-preparation workflow is local-only:

```bash
python scripts/prepare_static_release.py \
  --parent-release v1 \
  --new-release v2 \
  --parent-manifest parent.json \
  --source-manifest proposed.json \
  --output /tmp/oralbgc-v2-review \
  --dry-run
```

The workflow reports accession and relationship differences, refuses to
overwrite an existing output directory, supports validation-only mode, and does
not assign accessions automatically.

## Stable Source Keys

Stable source keys must come from scientific provenance, not database row order.

| Entity | Stable key policy |
| --- | --- |
| MAG | Original MAG/bin identifier plus source collection provenance. |
| BGC | antiSMASH source record, contig, coordinates, strand, product/class provenance, and parent MAG. |
| GCF | Reviewed BiG-SCAPE lineage decision for a cutoff-specific family; membership similarity alone is not sufficient. |
| Protein | Parent BGC plus original protein/CDS identifier and sequence provenance. |
| Structure | Stable source protein plus prediction method, model identifier, run provenance, and version semantics. |
| Peptide | Not defined for the current public release; future HROM identifiers must not be based on transient row numbers. |

Records lacking a stable source key are invalid for automatic accession
assignment.

## Review Classifications

Accession-diff reports classify records as:

```text
unchanged
metadata_updated
relationship_updated
new_unassigned
new_proposed
missing_from_new_source
ambiguous
collision
invalid
```

GCF lineage review must separately classify family changes as:

```text
unchanged family
new family
possible continuation
possible split
possible merge
membership change
unresolved
```

AlphaFold 3 growth review must distinguish:

```text
new structure entity
new version or rerun of an existing prediction
additional model for an existing protein
metadata or QC update
duplicate result
invalid or incomplete result
```

Any category that can alter scientific identity requires explicit review before
publication.

## Globus Resources

The static site distinguishes these URL types:

| Field | Meaning |
| --- | --- |
| `collection_url` | Operator-only Globus collection landing page for reconciliation context. |
| `collection_release_url` | Operator-only page for one immutable release folder. |
| `direct_https_base_url` | Verified direct HTTPS download base, if available. |
| `browser_fetch_base_url` | Verified CORS-compatible HTTPS base, if independently tested. |

Collection URLs are never treated as direct file URLs. Browser CIF fetching
remains disabled until anonymous direct HTTPS access and CORS are independently
validated.

Collection URLs must not be emitted into visitor-facing generated HTML,
JavaScript, or public JSON. Public resource actions are direct-download-only:
when publication state suppresses direct URLs, pages show metadata and an
unavailable-download note instead of linking to Globus collection browsing.

Direct URLs are derived by the exporter, not trusted from user input:

```text
approved HTTPS base + publication-state release root + manifest relative_path
```

Manifest relative paths must be release-relative POSIX paths. Absolute paths,
`..`, backslashes, query strings, fragments, non-HTTPS URLs, and hosts outside
the configured allowlist fail strict export.

Resource manifests are reviewed local JSON files validated with:

```bash
python scripts/validate_globus_resources.py \
  --manifest resources.json \
  --release v1 \
  --allowed-host example.org
```

The manifest stores release-relative paths and optional verified public URLs.
It must not contain local filesystem paths, guessed URLs, or unapproved
individual BGC GenBank links.

## Static Browse And Search

Browse applications load the entity manifest and one generated result page for
the current view. Supported global browse operations are:

| Entity | Default order | Additional global sort |
| --- | --- | --- |
| MAG | accession ascending | BGC count |
| BGC | accession ascending | class |
| GCF | accession ascending | class |
| Protein | accession ascending | none in the current release |
| Structure | accession ascending | mean pLDDT |

Tokenized browse filters currently use compact class/compactness tokens only.
Unsupported arbitrary substring scans are reported as unsupported rather than
presented as global filtering.

Full-text search uses token-prefix manifests and paginated postings. Exact BGS
accession lookup is separate and must not initialize the full-text postings
index.

## Resource Shards

When a reviewed integrated resource manifest is supplied, the exporter writes
public resource metadata under:

```text
data/releases/v1/resources/
```

Entity resources are sharded by accession range. Bulk resources are listed in a
compact catalog. Detail pages resolve resources from those static shards and do
not construct file URLs from query parameters. Individual BGC GenBank resources
remain disabled for the current release; BGC pages may reference only the
verified bulk archive.

The 6D audit found zero individual BGC GBK mappings for 1,913 BGC records and
one complete protein FASTA file,
`proteins/fasta/sequences/BGS_BGC_proteins_v1.0.faa`, for 22,626 proteins.
Therefore BGC and protein detail pages must keep bulk-only download labels
unless a future release adds one-to-one checked resources.

## Prepromotion Publication State

Milestone 6C exports use `--release-publication-state prepromotion`. In this
state the static site can display validated MAG and structure resource metadata
from the integrated manifest, but it removes production release-folder links,
direct HTTPS links, and browser-fetch URLs from public resource shards until the
immutable `/releases/v1/` copy and post-copy validation are complete.

Switch to `published` only after the promotion runbook has copied the release,
verified destination checksums and counts, created a separate anonymous read-only
ACL for `/releases/v1/`, and confirmed direct HTTPS, byte-range requests, and
CORS from the immutable path. Collection browsing may be validated by operators,
but it is not a visitor delivery mechanism.

`staging_validation` is not a deployment state. It is for local QA artifacts
under `/private/tmp`, must show a visible staging banner, and must derive links
under `staging/v1`. Generated `site/` output must remain `prepromotion` until
the immutable release is explicitly published.
