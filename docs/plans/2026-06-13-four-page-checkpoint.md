# Four-Page Checkpoint Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the first visual review checkpoint for PHRC_BGCStructDB with Home, protein browse, protein/structure detail, and Downloads backed by real ingested data.

**Architecture:** FastAPI serves JSON APIs and Jinja/HTMX pages from one Python process. SQLite stores public TSV rows plus generated download and CIF allowlists.

**Tech Stack:** FastAPI, Jinja2, HTMX, SQLite, SQLAlchemy 2.x, Bootstrap foundation, custom CSS, Plotly, 3Dmol.js.

---

1. Write contract tests for health, downloads exclusion, and traversal rejection; verify they fail before endpoints exist.
2. Implement ingestion with public IDs, sensitive-file exclusion, download manifest, structure file map, and indexes.
3. Implement read-only API endpoints for health, stats, proteins, downloads, columns, search, and version.
4. Implement Jinja templates for Home, protein browse, protein detail with CIF viewer, and Downloads.
5. Add custom CSS design tokens and lightweight JavaScript for charts and structure viewing.
6. Run ingestion, tests, and endpoint validation.
7. Start uvicorn and capture responsive screenshots for the four checkpoint pages.
