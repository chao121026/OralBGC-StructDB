# Performance Audit

Implemented safeguards:

- Browse pages query SQLite; TSV files are not parsed during requests.
- Protein, MAG, BGC, GCF, and structure browse pages use server-side pagination.
- Search is grouped and bounded by page size.
- Structure viewer JavaScript loads only on protein detail pages with a structure.
- Downloads are served through strict manifest keys.
- Network rendering is not enabled until graph files are parsed and size-screened.
- Ingestion creates indexes for common identifier/filter columns.

Known follow-up:

- Add `EXPLAIN QUERY PLAN` snapshots for the highest-traffic browse queries before production launch.
- Configure Nginx `X-Accel-Redirect` or an equivalent internal file-serving path for very large archives if needed.

