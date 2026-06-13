# PHRC_BGCStructDB Web

Public FastAPI/Jinja website for PHRC_BGCStructDB_v1. The app serves a no-login scientific database for oral microbiome MAG-associated BGC proteins, predicted structures, AF3 QC metrics where available, and Foldseek/PDB structural annotations where available.

## Configuration

Copy `.env.example` and set deployment-specific paths:

```bash
PACKAGE_ROOT=../PHRC_BGCStructDB_v1
DATABASE_PATH=app/data/phrc_bgcstructdb.sqlite
PUBLIC_BASE_URL=http://127.0.0.1:8000
ENVIRONMENT=development
LOG_LEVEL=info
```

The production application does not require `SECRET_KEY` for the current read-only public release.

## Setup

```bash
python -m pip install -r requirements.txt
python scripts/ingest_package_to_sqlite.py --package-root "$PACKAGE_ROOT" --db "$DATABASE_PATH"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Checkpoint Pages

- `/` Home
- `/proteins` Protein browse
- `/proteins/{public_protein_id}` Protein/structure detail
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

Run uvicorn behind Nginx using the sample files in `deployment/`. Keep the SQLite database backed up before each ingestion update. For future HROM data, rebuild with the same schema and `dataset` public identifiers.
