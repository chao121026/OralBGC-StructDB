# OralBGC-StructDB Web

Public FastAPI/Jinja website for OralBGC-StructDB, a BGS accession release developed at the Public Health Research Center, New York University Abu Dhabi. The app serves a no-login scientific database for oral microbiome MAG-associated BGC proteins, predicted structures, AF3 QC metrics where available, and Foldseek/PDB structural annotations where available.

Each MAG, BGC, primary c0.3 GCF, protein, and predicted structure is assigned a stable BGS accession independent of pipeline-specific identifiers. Original PHRC identifiers are preserved as searchable provenance metadata and remain usable through legacy redirects.

The public-facing database name is intentionally separate from internal historical repository names, Python package names, environment variables, database files, and provenance fields. Use `DATABASE_PUBLIC_NAME`, `DATABASE_SUBTITLE`, `DATABASE_INSTITUTION`, and `DATABASE_INSTITUTION_URL` to adjust public branding without changing BGS accessions or internal paths.

The BiG-SCAPE public layer uses BiG-SCAPE 2.0.3 output from the 2026-06-12 run. Stable GCF pages use the primary c0.3 assignments; alternative cutoffs remain available as curated download files. The Networks page includes a locally vendored Cytoscape.js 3.29.2 viewer for bounded BGS-mapped GCF subnetworks and renderable public network files. See `docs/bigscape_public_release.md` for the public file layout, rendering limits, and raw-provenance policy.

## Configuration

Copy `.env.example` and set deployment-specific paths:

```bash
PHRC_BGCSTRUCTDB_DATA_ROOT=../PHRC_BGCStructDB_BGS_v1
DATABASE_PUBLIC_NAME=OralBGC-StructDB
DATABASE_INSTITUTION="Public Health Research Center, New York University Abu Dhabi"
PUBLIC_BASE_URL=http://127.0.0.1:8000
BIGSCAPE_MAX_NODES=2000
BIGSCAPE_MAX_EDGES=10000
BIGSCAPE_MAX_JSON_BYTES=10485760
ENVIRONMENT=development
LOG_LEVEL=info
```

The production application does not require `SECRET_KEY` for the current read-only public release.

## Setup

```bash
python -m pip install -r requirements.txt
python scripts/ingest_package_to_sqlite.py --package-root "$PHRC_BGCSTRUCTDB_DATA_ROOT" --db app/data/phrc_bgcstructdb.sqlite
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Railway Editor Preview

The selected editor-preview website is the original FastAPI/Jinja
server-rendered ASGI application running directly under Uvicorn on Railway. The
app uses the bundled read-only SQLite database and a packaged sanitized runtime
manifest at `app/data/integrated-resource-manifest.json` to deliver scientific
files through anonymous direct HTTPS URLs. Globus is a storage and HTTPS
delivery backend only; visitor pages must not expose Globus collection
browsing, transfer links, collection UUIDs, or `origin_id` URLs.

Railway uses:

```bash
uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --proxy-headers
```

Preview mode:

```text
DEPLOYMENT_MODE=editor_preview
RELEASE_PUBLICATION_STATE=staging_validation
GLOBUS_DIRECT_HTTPS_BASE_URL=https://g-f2d91c.6d8b.03c0.data.globus.org
GLOBUS_BROWSER_FETCH_BASE_URL=https://g-f2d91c.6d8b.03c0.data.globus.org
GLOBUS_RELEASE_RELATIVE_ROOT=staging/v1
GLOBUS_ALLOWED_HOSTS=g-f2d91c.6d8b.03c0.data.globus.org
```

Future publication should switch only `GLOBUS_RELEASE_RELATIVE_ROOT` to
`releases/v1` after immutable promotion and validation. See
`docs/railway_editor_preview_deployment.md`.

## Static Production Export

The static exporter is retained for snapshots, regression checks, and archival
deployment experiments. It is not the selected editor-preview or production
website architecture after milestone 6F. The preferred visitor interface is the
server-rendered Jinja application above.
All scientific entity detail views use reusable query-string pages plus
versioned metadata shards rather than one HTML file per record:

```text
/mag/?id=BGS-MAG-000001
/bgc/?id=BGS-BGC-000001
/gcf/?id=BGS-GCF-C03-0001
/protein/?id=BGS-PRT-000001
/structure/?id=BGS-STR-000001
/peptide/?id=BGS-PEP-000001
```

The current release has no peptide records; the peptide route is an
architecture-ready unavailable-state shell.

```bash
python scripts/export_static_site.py \
  --db app/data/phrc_bgcstructdb.sqlite \
  --release-root "$PHRC_BGCSTRUCTDB_DATA_ROOT" \
  --output site \
  --base-url http://127.0.0.1:8080 \
  --globus-collection-url "PLACEHOLDER_GLOBUS_COLLECTION_URL" \
  --globus-base-url "PLACEHOLDER_GLOBUS_HTTPS_BASE_URL" \
  --globus-release-path "OralBGC-StructDB/releases/v1" \
  --structure-delivery-mode download-only \
  --entity-scope all \
  --max-site-bytes 996147200 \
  --browse-shard-size 1000 \
  --detail-range-span 500 \
  --relationship-page-size 100 \
  --strict \
  --clean
python -m http.server 8080 --directory site
```

Run browser checks against the static output with:

```bash
BASE_URL=http://127.0.0.1:8080 pytest -q tests/test_browser_regression.py
```

`site/` is ignored by git by default. The milestone-4 full export uses six
reusable entity apps, zero per-record scientific HTML pages, numeric-range
detail shards under `data/releases/v1/entities/`, lazy relationship shards,
partitioned client-side search, and exact prefix-sharded legacy lookup. See
`docs/static_github_pages_deployment.md` for the deployment model, Globus
configuration, static index/search architecture, redirect behavior, structure
delivery modes, subpath testing, and migration strategy. MAG archival deposition
in ENA is in progress as a separate public repository-link layer.

## Checkpoint Pages

- `/` Home
- `/proteins` Protein browse
- `/protein/?id={BGS-PRT-accession}` Protein detail
- `/structure/?id={BGS-STR-accession}` Structure detail
- `/networks` BiG-SCAPE GCF overview, Cytoscape.js viewer, and network downloads
- `/downloads` Public downloads

## Optional screenshot capture

Playwright is a development-only dependency and is not required in production.

```bash
pip install playwright
playwright install chromium
python scripts/capture_screenshots.py --base-url http://127.0.0.1:8000
```

Screenshots are written to `artifacts/screenshots/`.

## Public Data Policy

The ingestion allowlist excludes internal candidate-ranking and IP-development files, including `PHRC_integrated_BGC_protein_structure_summary.with_internal_priority_columns.tsv`. Public APIs and generated SQLite tables omit raw source path columns and sensitive ranking fields.

## Deployment

Run uvicorn behind Nginx using the sample files in `deployment/`. Keep the SQLite database backed up before each ingestion update. For future HROM data, rebuild with the same schema and stable BGS-style public accessions while retaining source identifiers in provenance columns.

## Static Globus Candidate

Milestone 6 adds a local reconciliation workflow for the staged Globus release.
Use `scripts/reconcile_globus_release.py` to build a reviewed integrated
resource manifest, then pass that manifest to `scripts/export_static_site.py`
with `--resource-manifest`. The static site consumes only sharded public
resource metadata; it does not copy scientific files into `site/`.

See `docs/globus_release_reconciliation.md` and
`docs/deployment_candidate_checklist.md` before promoting Globus files or
deploying GitHub Pages.

Milestone 6C consumes the copied HPC evidence bundle at
`/Users/jz7982/Documents/OralBGC-StructDB_Globus_reconciliation/v1` and writes
promotion-candidate metadata under
`artifacts/milestone6c-release-candidate/`. The integrated payload manifest has
23,305 entries: 22,722 original approved resources plus 583 validated MAG FASTA
records. Static exports must use `--release-publication-state prepromotion`
until `/releases/v1/` is copied, checksummed, anonymously tested, and explicitly
approved for publication. In prepromotion state, resource metadata is visible but
production release-folder links, direct HTTPS downloads, and browser-fetch links
are disabled in public output.

Milestone 6D adds controlled direct-link publication states. `prepromotion`
remains the default for `site/` and suppresses direct URLs and CIF browser
fetching. `staging_validation` is for local QA artifacts under `/private/tmp`
and emits visible staging banners plus `staging/v1` direct links. `published`
is reserved for the immutable `releases/v1` path after explicit promotion.
Static structure pages use the vendored 3Dmol.js 2.4.2 viewer only when a
validated `structure_cif` resource has a CORS-approved browser URL. BGC GenBank
and protein FASTA remain bulk-only in the current release: no one-to-one BGC
GBK map exists, and the only protein FASTA is
`proteins/fasta/sequences/BGS_BGC_proteins_v1.0.faa`.

Milestone 6E keeps the previous FastAPI/Jinja server-rendered pages as the visual
reference while preserving the static architecture. Static reusable entity
pages now use the same public header, footer, record hero, metric panels,
resource panels, and responsive table classes as the server-rendered site.
Visitor resource delivery is direct-download-only: Globus collection browsing
URLs are operator-side reconciliation inputs and must not be emitted into
generated HTML, JavaScript, or public JSON. Structure viewing remains enabled
only for `staging_validation` or `published` builds with verified direct HTTPS
and CORS-compatible CIF URLs.
