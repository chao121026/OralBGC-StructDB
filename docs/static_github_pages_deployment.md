# Static GitHub Pages Deployment

This is an alternate and archival deployment path. After milestone 6F, the
selected editor-preview website is the original server-rendered Jinja
FastAPI application running under Uvicorn on Railway. GitHub Pages is not the
primary demo hosting architecture.

## Architecture

- GitHub Pages serves generated HTML, CSS, JavaScript, and compact JSON.
- NYUAD Globus serves release files, archives, tables, and CIF downloads
  through direct HTTPS URLs only.
- ENA assembly accessions can be added to MAG records after deposition.

The exporter uses a local prebuild model. It generates `site/`
locally from the SQLite database and active public release root, but `site/` is
ignored by git by default.

## Local Build

```bash
python scripts/export_static_site.py \
  --db app/data/phrc_bgcstructdb.sqlite \
  --release-root /Users/jz7982/Documents/PHRC_BGCStructDB_BGS_v1 \
  --output site \
  --base-url http://127.0.0.1:8080 \
  --globus-collection-url "PLACEHOLDER_GLOBUS_COLLECTION_URL" \
  --globus-base-url "PLACEHOLDER_GLOBUS_HTTPS_BASE_URL" \
  --globus-release-path "OralBGC-StructDB/releases/v1" \
  --structure-delivery-mode download-only \
  --entity-scope all \
  --max-site-bytes 996147200 \
  --strict \
  --clean
```

Serve the output with a plain static server:

```bash
python -m http.server 8080 --directory site
```

Do not use `file://` for validation.

Run browser validation against the static server:

```bash
BASE_URL=http://127.0.0.1:8080 pytest -q tests/test_browser_regression.py
```

On macOS sandboxed runners, Playwright may need to run outside the sandbox so
Chromium can register its Mach port.

## Globus Configuration

Keep these concepts separate:

- `GLOBUS_COLLECTION_URL`: operator-only Globus collection or file-manager URL
  retained for reconciliation context.
- `GLOBUS_HTTPS_BASE_URL`: direct HTTPS file base, if available.
- `GLOBUS_RELEASE_PATH`: immutable public release prefix.
- `GLOBUS_STRUCTURE_FETCH_ENABLED`: whether browser CORS-compatible CIF fetch is
  verified.
- `RELEASE_PUBLICATION_STATE`: one of `prepromotion`, `staging_validation`, or
  `published`.

The collection URL is not assumed to be browser-fetchable. The first milestone
uses `download-only` structure delivery until anonymous HTTPS and CORS are
verified.

Generated visitor output is direct-download-only. It must not contain Globus
collection browsing URLs, collection UUIDs, `origin_id` query strings, or
`Browse in Globus` actions. Collection URLs may appear in local operator env
files and runbooks, but public static HTML, JavaScript, and JSON derive visitor
links only from the approved direct HTTPS base plus the selected immutable or
staging release root.

Publication-state behavior is explicit. `prepromotion` displays resource
metadata but strips release-folder links, direct HTTPS URLs, and browser-fetch
URLs. `staging_validation` is a local QA mode that must be built outside
`site/`; it derives direct URLs under `staging/v1`, shows a visible staging
banner, and may load verified CIFs in the browser. `published` derives direct
URLs under the immutable `releases/v1` root and must not show the staging
banner.

## Static Output

The exporter writes:

- directory-style pages such as `networks/index.html`;
- exactly one reusable detail app each for MAG, BGC, GCF, protein, structure, and peptide;
- zero per-record scientific entity HTML pages;
- `data/releases/v1/entities/<entity>/` browse and numeric-range detail shards;
- `data/releases/v1/relationships/` parent-range relationship shards;
- `data/releases/v1/search/` token-prefix search partitions;
- `data/releases/v1/legacy/` exact normalized legacy lookup shards;
- `data/networks/manifest.json`;
- `data/networks/<BGS-GCF-C03-*>.json`;
- `data/networks/files/<network_id>.json`;
- local assets under `assets/`;
- `.nojekyll`;
- `404.html`;
- `build-report.json`.

The milestone-4 full export is below the milestone-3 logical size and file
count: six reusable entity apps, zero per-record scientific HTML pages, zero
legacy redirect pages, 212 network JSON files, and shared static assets. The
current warning threshold is 180 MB logical output for release `v1`; strict
builds still enforce the configured `--max-site-bytes` hard limit.

## Reusable Entity Routes

Every entity detail route is a reusable query-string app:

```text
/mag/?id=BGS-MAG-000001
/bgc/?id=BGS-BGC-000001
/gcf/?id=BGS-GCF-C03-0001
/protein/?id=BGS-PRT-000001
/structure/?id=BGS-STR-000001
/peptide/?id=BGS-PEP-000001
```

Each page validates the accession format, computes the numeric range shard,
fetches one core detail shard, and renders public metadata without FastAPI.
Related records are separate parent-range relationship shards and are loaded
only when a relationship panel is opened. Peptide records are not present in
release `v1`; the peptide shell validates `BGS-PEP-*` accessions and displays
an unavailable-state message.

## Immutable Release Metadata

Generated data uses a versioned layout:

```text
data/current.json
data/releases/v1/manifest.json
data/releases/v1/accessions/manifest.json
data/releases/v1/entities/{mags,bgcs,gcfs,proteins,structures,peptides}/manifest.json
data/releases/v1/entities/<entity>/browse/chunk-*.json
data/releases/v1/entities/<entity>/detail/range-*.json
data/releases/v1/relationships/
data/releases/v1/search/
data/releases/v1/legacy/
```

`data/current.json` points to the active immutable release manifest. Entity
manifests include schema version, record count, browse chunk size, detail range
span, shard filenames, accession ranges, record counts, and SHA-256 checksums.
Shard membership is deterministic by stable accession numbering. Browse shard
size is configured with `--browse-shard-size`; detail range span is configured
with `--detail-range-span`.

## Indexes and Search

Browse pages load the entity manifest and first required browse shard initially.
Pagination fetches additional shards on demand. Supported text filtering and
sorting are global: when a filter or non-default sort is requested, the browser
loads the compact browse shards for that entity and applies the operation across
the full static release. Unsupported advanced filters are intentionally not
presented as global filters.

Search uses partitioned release search data under `data/releases/v1/search/`.
The search page fetches only token-prefix partitions required by the submitted
query and intersects token matches client-side. Exact accession detail lookup is
separate and uses the accession manifest plus one numeric-range detail shard; it
does not initialize full-text search. Search indexes include compact public
tokens from accessions, provenance IDs, products, gene names, classes, and
structural annotations; full sequences, CIF data, raw Foldseek output, and raw
pipeline output are excluded.

## Legacy Redirects

Mass legacy redirect pages are no longer generated. The static `/legacy/`
resolver performs exact-match lookup from the validated accession mapping shards,
constructs only trusted internal targets, and displays unresolved identifiers
without fuzzy matching or external redirects. GitHub Pages therefore serves a
static resolver page rather than per-record HTTP redirect pages. Lookup shards
are selected by a deterministic SHA-256 prefix of the normalized legacy
identifier.

Large release archives, raw imports, the SQLite database, logs, internal
documentation, and CIF files are not copied into `site/`.

## GitHub Pages Base Paths

The exporter uses the path part of `--base-url` for generated links. This
supports both root deployments and repository subpath deployments such as:

```text
https://USERNAME.github.io/REPOSITORY/
```

For localhost builds, the host is not embedded in generated output so strict
checks can reject `127.0.0.1` and `localhost`.

Local subpath smoke testing can be done with:

```bash
python scripts/export_static_site.py \
  --db app/data/phrc_bgcstructdb.sqlite \
  --release-root /Users/jz7982/Documents/PHRC_BGCStructDB_BGS_v1 \
  --output /private/tmp/phrc-static-subpath/OralBGC-StructDB \
  --base-url http://127.0.0.1:8081/OralBGC-StructDB \
  --globus-base-url "PLACEHOLDER_GLOBUS_HTTPS_BASE_URL" \
  --strict \
  --clean
python -m http.server 8081 --directory /private/tmp/phrc-static-subpath
```

## Structure Viewer Modes

`download-only`:

- shows structure metadata;
- links to a configured direct HTTPS CIF URL when the publication state permits
  visitor downloads;
- does not load 3Dmol or fetch CIFs in the browser.

`globus-fetch`:

- loads the vendored 3Dmol.js 2.4.2 asset from `assets/vendor/3dmol/2.4.2/`;
- fetches only the selected structure's validated `browser_fetch_url`;
- is available only for `staging_validation` or `published` builds with
  CORS-validated `structure_cif` resource rows;
- falls back to the CIF download if the viewer library or browser fetch fails.

## Migration Strategy

1. Build and validate representative static output locally.
2. Verify Globus anonymous downloads and structure CORS.
3. Publish to a temporary GitHub Pages URL.
4. Compare static pages against FastAPI pages.
5. Freeze a release and switch public DNS only after validation.

GitHub Pages workflow automation is intentionally deferred until the local
static export is stable.

## Milestone 6 Resource Metadata

Deployment candidates can consume a reviewed integrated resource manifest:

```bash
python scripts/export_static_site.py \
  --db app/data/phrc_bgcstructdb.sqlite \
  --release-root /path/to/validated/release \
  --resource-manifest /path/to/integrated-resource-manifest.json \
  --base-url https://USERNAME.github.io/OralBGC-StructDB \
  --globus-collection-url "$OPERATOR_COLLECTION_URL" \
  --globus-release-collection-url "$OPERATOR_RELEASE_COLLECTION_URL" \
  --globus-base-url "https://example.invalid" \
  --output site \
  --strict \
  --clean
```

Resource metadata is written under `data/releases/v1/resources/` as entity-range
shards plus a compact bulk catalog. MAG and structure detail pages fetch only
the relevant bounded resource shard. BGC pages use the bulk BGC archive catalog
and must not expose individual BGC GenBank links for the current release.
Protein pages expose the complete protein FASTA as a bulk resource and label it
`Download complete protein FASTA`; the current release does not contain
individual protein FASTA files.

Do not populate `browser_fetch_url` or enable the structure viewer unless CORS
validation has explicitly passed. Collection browsing, direct HTTPS downloads,
and browser CORS remain separate capabilities.

Visitor-facing resource panels never fall back to Globus collection browsing.
If a direct download URL is unavailable for the current publication state, the
static page displays the resource metadata and an unavailable-download message.

## Milestone 6C Production Candidate

Use the confirmed guest collection only with the immutable release-relative
root:

```text
GLOBUS_COLLECTION_URL=<operator-only collection URL>
GLOBUS_RELEASE_COLLECTION_URL=<operator-only release-folder collection URL>
GLOBUS_DIRECT_HTTPS_BASE_URL=https://g-f2d91c.6d8b.03c0.data.globus.org
GLOBUS_BROWSER_FETCH_BASE_URL=https://g-f2d91c.6d8b.03c0.data.globus.org
GLOBUS_RELEASE_RELATIVE_ROOT=releases/v1
RELEASE_PUBLICATION_STATE=prepromotion
```

The administrative mapped base path must not appear in public output. Staging
URLs are validation-only and must not be emitted by a GitHub Pages candidate.
GitHub Pages deployment remains pending until immutable promotion and post-copy
validation are complete.

## Milestone 6E Visual Parity

The FastAPI/Jinja server-rendered application is the reference for static-page
appearance. Static reusable detail pages keep the shared header, navigation,
footer, record hero, metric panels, resource panels, table styling, responsive
wrapping, and accessibility landmarks from `base.html` and `site.css`; the
static exporter must not reintroduce a runtime ASGI dependency.

Capture reference and candidate screenshots under
`artifacts/milestone6e-visual-parity/` before promotion-oriented review. The
comparison should cover home, browse, search, downloads, networks, and
representative MAG, BGC, and structure detail routes at desktop, tablet, and
mobile widths.
