# Architecture

PHRC_BGCStructDB_web is a single FastAPI service with Jinja2 template inheritance, HTMX for progressive table interactions, SQLite for read-optimized public data, SQLAlchemy 2.x for runtime queries, custom CSS design tokens, Plotly charts, and 3Dmol.js for CIF visualization.

The data package remains read-only. Ingestion copies public TSV content into SQLite, adds dataset/public ID fields, and creates strict allowlists for downloads and structure files. Future HROM support is handled by the `dataset` column and the same public ID pattern.
