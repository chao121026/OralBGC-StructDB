# Refinement Validation Pass Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Validate and refine the four-page checkpoint without expanding to additional full pages.

**Architecture:** Keep the existing FastAPI/Jinja/HTMX/SQLite checkpoint. Fix the data model so structure availability, AF3 QC availability, and Foldseek/PDB annotation availability are separate facts derived from approved tables/maps, not inferred from stale source file paths. Make deployment paths environment-driven and keep raw local paths out of generated SQLite, HTML, and JSON.

**Tech Stack:** FastAPI, Jinja2, HTMX, SQLite, SQLAlchemy, pytest, optional Playwright screenshot helper.

---

### Task 1: Add regression tests

**Files:**
- Modify: `tests/test_contract.py`
- Modify: `tests/test_ingestion_security.py`

**Steps:**
1. Add tests for precise stats keys: `predicted_structures_available`, `proteins_with_af3_qc`, and `proteins_with_foldseek_annotation`.
2. Add tests that SQLite public tables contain no local absolute source-path prefixes values and no raw path columns such as `model_cif`, `region_file`, or `bigscape_source_file`.
3. Add tests for sensitive ranking field absence in APIs and SQLite.
4. Add tests that one short QC+Foldseek record, one medium/long CIF-only record, and one no-CIF record render accurate detail states.
5. Run pytest and verify these tests fail against the current checkpoint.

### Task 2: Fix ingestion and stats

**Files:**
- Modify: `scripts/ingest_package_to_sqlite.py`
- Modify: `app/services/stats.py`
- Modify: `app/queries.py`

**Steps:**
1. Exclude source path columns from ingested public tables.
2. Build `structure_file_map` from approved local CIF filenames.
3. Add separate availability flags to `bgc_protein_summary`: `structure_available`, `af3_qc_available`, and `foldseek_annotation_available`.
4. Update stats to expose separate counts for predicted structures, AF3 QC rows, and Foldseek/PDB annotations.
5. Re-ingest and verify tests pass.

### Task 3: Documentation reports

**Files:**
- Create: `docs/model_qc_coverage_report.md`
- Create/modify: `docs/gcf_statistics_report.md`
- Modify: `docs/data_inventory.md`
- Modify: `docs/design_checkpoint.md`

**Steps:**
1. Document by length bucket: total proteins, CIF files mapped to proteins, AF3 QC rows, Foldseek rows, missing CIFs, CIFs lacking AF3 QC, and CIFs lacking Foldseek.
2. Document GCF c0.3 primary cutoff interpretation and other cutoff assignment availability.
3. Update existing checkpoint docs to use precise terminology.

### Task 4: Portability and public safety

**Files:**
- Modify: `app/config.py`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: tests

**Steps:**
1. Replace `PACKAGE_ROOT` / `DATABASE_PATH`, retaining legacy fallback only if useful.
2. Add `PUBLIC_BASE_URL`, `ENVIRONMENT`, and `LOG_LEVEL`; include `SECRET_KEY` as optional future-proof config without requiring it for the public read-only app.
3. Remove hardcoded local paths from docs and tests, except illustrative placeholders.
4. Verify repo scans do not find local absolute source-path prefixes outside historical docs if any remain intentionally explained.

### Task 5: Visual refinement and screenshot support

**Files:**
- Modify: `app/templates/home.html`
- Modify: `app/templates/browse/proteins.html`
- Modify: `app/templates/detail/protein.html`
- Modify: `app/static/css/site.css`
- Create: `docs/frontend_audit.md`
- Create: `scripts/capture_screenshots.py`

**Steps:**
1. Improve stat labels, descriptions, status badges, empty/loading states, and detail-page availability panels.
2. Add frontend audit with concrete changes.
3. Add optional Playwright screenshot script and docs.
4. Run tests, re-ingest, validate endpoints/pages, and report screenshot status.
