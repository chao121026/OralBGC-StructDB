# PHRC_BGCStructDB Web

Public FastAPI/Jinja website for PHRC_BGCStructDB_v1. The app serves a no-login scientific database for oral microbiome MAG-associated BGC proteins, AF3 structures, AF3 QC metrics, and Foldseek/PDB structural annotations.

## Setup

```bash
python -m pip install -r requirements.txt
python scripts/ingest_package_to_sqlite.py --package-root /Users/jz7982/Documents/PHRC_BGCStructDB_v1 --db app/data/phrc_bgcstructdb.sqlite
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Checkpoint Pages

- `/` Home
- `/proteins` Protein browse
- `/proteins/{public_protein_id}` Protein/structure detail
- `/downloads` Public downloads

## Deployment

Run behind Nginx with proxy buffering enabled and serve large files efficiently through the controlled `/downloads/file/{file_key}` route or an internal Nginx alias after validating keys in the application. See `deployment/deployment_notes.md`.

## Public Data Policy

The ingestion allowlist excludes internal candidate-ranking and IP-development files, including `PHRC_integrated_BGC_protein_structure_summary.with_internal_priority_columns.tsv`.
