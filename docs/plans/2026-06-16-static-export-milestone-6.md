# Static Export Milestone 6

Milestone 6 connects the scalable static architecture to the staged Globus
scientific-file release without promoting, publishing, or deploying it.

## Scope

- Reconcile the real or copied HPC staging tree.
- Generate an integrated resource manifest and checksum list.
- Validate MAG and structure entity mappings.
- Keep BGC downloads bulk-only.
- Shard resource metadata for bounded static detail-page transfers.
- Validate root and repository-subpath deployment candidates.

## Non-Goals

- No accession reassignment.
- No `v2` scientific data processing.
- No Globus promotion.
- No GitHub Pages deployment.
- No interactive structure viewer or browser CIF fetching in prepromotion
  output.

## Implementation

`scripts/reconcile_globus_release.py` inventories and validates staged resources
and writes candidate metadata outside the release root unless explicitly
configured otherwise. `scripts/export_static_site.py` consumes a reviewed
resource manifest and writes deterministic resource shards under
`data/releases/v1/resources/`.

## Validation

The deployment candidate must pass static export tests, browser regression tests
at root and subpath, generated-site leak scans, placeholder scans, and resource
manifest validation.

## Milestone 6C Closure Criteria

6C integrates the copied HPC evidence bundle rather than requiring local MAG
binaries. The candidate manifest has 23,305 payload entries: 22,722 original
approved resource records and 583 validated MAG FASTA records. Root and
repository-subpath builds remain prepromotion candidates: resource metadata is
available, but production release-folder links, direct HTTPS downloads, and
browser fetch links remain disabled until `/releases/v1/` exists and passes
post-copy validation. Public ACL read-only status remains pending explicit
confirmation that Write is unchecked.

## Milestone 6D Addendum

6D introduces explicit publication states. `prepromotion` continues to suppress
direct release URLs and browser-fetch URLs. `staging_validation` is local-QA
only, writes outside `site/`, shows a visible staging banner, and derives links
under `staging/v1`. `published` derives links under `releases/v1` after explicit
promotion approval. Structure detail pages load the vendored 3Dmol.js 2.4.2
viewer only when a selected `structure_cif` row has validated direct HTTPS and
CORS evidence. The BGC and protein audits remain bulk-only for release `v1`.

## Milestone 6E Addendum

6E aligns static reusable pages with the previous FastAPI/Jinja visual
surface without restoring a runtime server dependency. Static entity pages reuse
the shared header, footer, record hero, metrics, resource panel, table, and
responsive wrapping classes from the server-rendered templates.

Visitor resource delivery is direct-download-only. Public generated HTML,
JavaScript, and JSON must not contain Globus collection browsing URLs,
collection UUIDs, `origin_id` query strings, or `Browse in Globus` actions.
Collection URLs remain operator-only reconciliation inputs; visitor links are
derived only from approved direct HTTPS bases and the selected publication-state
release root.

## Milestone 6F Addendum

The selected editor-preview architecture has changed back to the original
FastAPI/Jinja server-rendered ASGI application, deployed as one Railway web
service under Uvicorn. Static export remains useful for snapshots and regression
checks, but `site/` is not the Railway website. Runtime resource delivery
follows the same direct-download-only policy and uses the packaged sanitized
runtime manifest with `staging/v1` for editor preview and `releases/v1` for
future publication.
