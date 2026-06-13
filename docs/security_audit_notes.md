# Security Audit Notes

- No login, registration, or password routes were added.
- Public downloads are served only by `file_key` from `download_manifest`; no route accepts a filesystem path.
- CIF structures are served only by `public_protein_id` from `structure_file_map`; traversal and path separators are rejected.
- Raw `model_cif`, `region_file`, and path-like columns are redacted from public JSON responses.
- The internal priority TSV and candidate/priority/internal filenames are excluded from ingestion and download manifest generation.
- Tests cover traversal rejection, sensitive download exclusion, raw path absence, page rendering, and ingestion security basics.
