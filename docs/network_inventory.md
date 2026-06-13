# Network Inventory

Inspected public BiG-SCAPE network resources from the source package.

| File | Size | Contents | Direct rendering status |
|---|---:|---|---|
| `bigscape/networks.tar.gz` | 20,165,161 bytes | 37 `.network` files across c0.3, c0.4, c0.5, c0.6, and full network outputs | Downloadable now; direct rendering deferred until individual files are extracted, parsed, size-screened, and allowlisted |
| `bigscape/cytoscape_files.tar.gz` | 45 bytes | Empty archive | Downloadable for completeness; no viewer data available |
| `bigscape/gcf_tables.tar.gz` | 304,265 bytes | 40 clustering/annotation TSV files | Downloadable now |

The Networks page does not fabricate example graphs. Cytoscape.js rendering should be enabled only after adding an ingestion step that registers individual network files in a strict allowlist, rejects oversized graphs by default, and maps node identifiers to public BGC/GCF routes.

