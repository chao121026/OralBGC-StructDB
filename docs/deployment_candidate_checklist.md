# Deployment Candidate Checklist

Do not deploy until every required item is explicitly passed or accepted as
pending by the project owner.

## Release Reconciliation

- Staging inventory completed.
- Integrated resource manifest generated.
- Integrated checksums generated.
- MAG mappings validated: 583 expected.
- Structure mappings validated: 22,622 expected.
- Private files absent from public manifest.
- Individual BGC GenBank links absent.
- Individual protein FASTA links absent unless a future manifest supplies
  one-to-one checked protein files; current release uses one complete protein
  FASTA.

## Globus Validation

- Operator-only collection landing page access tested.
- Operator-only release-folder access tested.
- Representative bulk archive tested.
- Representative MAG file tested.
- Representative CIF file tested.
- Direct HTTPS tested separately from collection access.
- CORS tested separately before browser-fetch features are enabled.
- Visitor-facing generated output contains no Globus collection navigation,
  `origin_id` URLs, collection UUIDs, or `Browse in Globus` actions.
- `staging_validation` builds checked under `/private/tmp` with visible staging
  banner and `staging/v1` links only.
- `site/` remains `prepromotion` until immutable `/releases/v1/` publication is
  explicitly approved.

## Static Builds

- Static export is now an alternate or archival path. The selected
  editor-preview host is Railway running the original FastAPI/Jinja
  server-rendered ASGI application.
- Root build generated from the integrated resource manifest.
- Repository-subpath build generated from the same manifest.
- No scientific files are copied into `site/`.
- No `/api/`, local paths, HPC paths, SQLite, private IDs, or placeholder links
  appear in generated output.
- Browser regression suite passes at root.
- Browser regression suite passes under `/OralBGC-StructDB/`.
- Visual parity screenshots are captured for FastAPI reference and static
  candidate pages under `artifacts/milestone6e-visual-parity/`.

## Promotion Rehearsal

Before promotion, verify that the immutable destination does not exist:

```bash
test ! -e /archive/jz7982/OralBGC-StructDB/releases/v1
```

Promotion must copy staged files to a new immutable release path only after
checksums and public access plans have been reviewed. Do not replace the staged
top-level manifest automatically. Globus anonymous sharing is a collection
permission and policy step; Unix mode changes alone do not establish anonymous
Globus access.

## Rollback

If validation fails before publication, discard the deployment candidate and
rebuild from the reconciled staging inputs. Published immutable release folders
must not be edited in place.

## Milestone 6C Readiness Matrix Notes

- HPC file inventory: passed for staging evidence.
- Original checksums: passed for 22,722 original entries.
- MAG checksums, manifest consistency, gzip, and FASTA validation: passed on HPC
  for 583 MAG FASTA files.
- Integrated manifest and integrated checksum list: generated locally from the
  copied evidence bundle.
- MAG and structure entity mapping: passed against the SQLite database.
- Anonymous staging access, direct HTTPS, byte ranges, and CORS: user-confirmed
  on staging.
- Public ACL read-only state: pending explicit confirmation that Write is
  unchecked.
- Immutable `/releases/v1/` copy, destination checksums, production release
  links, GitHub Pages deployment, and staging ACL removal: pending.

## Milestone 6F Railway Preview

- One Railway web service, one replica, direct Uvicorn process.
- No Railway PostgreSQL, Redis, volume, worker, or cron service.
- Health check path: `/health`.
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --proxy-headers`.
- Bundled SQLite is opened read-only.
- Packaged runtime resource manifest: `app/data/integrated-resource-manifest.json`.
- Visitor resource actions use direct HTTPS links derived from the validated
  manifest relative path plus configured `staging/v1` or `releases/v1` root.
- Globus collection browsing remains absent from visitor HTML, JavaScript, and
  public JSON.
