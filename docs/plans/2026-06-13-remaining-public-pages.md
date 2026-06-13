# Remaining Public Pages Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete the public database pages and API endpoints beyond the approved four-page checkpoint while preserving public-data safety, path redaction, and structure/QC/Foldseek distinctions.

**Architecture:** Keep FastAPI/Jinja/HTMX/SQLite. Add entity-specific SQL query helpers for MAG, BGC, GCF, structures, and search. Render pages server-side with partial table templates and use existing strict download/CIF allowlists.

**Tech Stack:** FastAPI, Jinja2, HTMX, SQLite, SQLAlchemy text queries, Plotly/3Dmol/Cytoscape placeholders, pytest.

---

1. Add failing tests for remaining API endpoints and pages.
2. Add entity query service functions with validated sort/filter maps.
3. Implement API endpoints for MAG/BGC/GCF detail/list, structures, search, version.
4. Replace placeholder page routes with browse/detail/search/network/help/about/contact implementations.
5. Add gene-cluster SVG track using `integrated_summary` coordinates.
6. Add network inventory documentation from real archives.
7. Add cross-link, accessibility, and performance audits.
8. Update screenshot script to include all major pages.
9. Run tests, live endpoint validation, path/sensitive scans, and commit.
