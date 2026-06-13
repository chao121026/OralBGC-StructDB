# Four-Page Design Checkpoint

Implemented checkpoint pages:

1. Home (`/`)
2. Protein browse (`/proteins`)
3. Protein/structure detail (`/proteins/{public_protein_id}`)
4. Downloads (`/downloads`)

Local review URL: `http://127.0.0.1:8000`

## Data Used

The checkpoint uses the ingested SQLite database built from `${PACKAGE_ROOT}`. Live stats are 583 MAGs, 1,913 BGCs, 179 primary c0.3 GCFs, 22,626 BGC proteins, 22,622 predicted structures available, 10,972 proteins with AF3 QC, and 10,972 proteins with Foldseek/PDB annotation. The CIF viewer is wired to a real approved CIF route.

## Visual Tokens

Colors: deep navy `#09233d`, ink `#10202f`, muted text `#617080`, protein-structure teal `#007c89`, light cyan `#d8f3f5`, restrained warm accent `#b56b1d`, border `#d8e0e8`, background `#f7f9fb`.

Typography: Inter/Source Sans/system sans for UI, IBM Plex Mono/SFMono/Consolas for identifiers and files. Letter spacing remains normal except small uppercase eyebrow labels.

Spacing: tokenized 4, 8, 12, 16, 24, and 32 px increments. Cards and panels use 8 px radius and subtle shadows only for framed tools or repeated records.

## Component Inventory

Header with skip link, responsive navigation, version badge, scientific hero, workflow list, statistic cards, chart panel, feature cards, HTMX filter form, server-rendered data table, badge tokens, pagination, record hero, structure viewer panel, metric panel, download rows, error pages.

## Design Rationale

The checkpoint uses a restrained scientific database style rather than an administration dashboard. The homepage explains the resource quickly, the protein browse page keeps dense data server-paginated, the detail page makes the structure viewer the visual centerpiece, and the downloads page emphasizes trust through descriptions, sizes, checksums, and a strict allowlist.

## Accessibility Notes

Implemented: semantic headings, skip link, keyboard-visible focus styles, table captions, high-contrast navy/white header, labeled filter controls, textual chart summary, responsive horizontal table handling, and reduced-motion CSS.

## Mobile Behavior

At narrow widths, hero and detail grids collapse to one column, statistic and feature cards stack, filters become single-column, and tables remain horizontally scrollable to preserve data integrity.

## Known Placeholders

MAG, BGC, GCF, structures browse, search, networks, help, about, and contact are scaffolded or lightly documented but intentionally not completed before this visual checkpoint. Cytoscape rendering is deferred because `cytoscape_files.tar.gz` is empty and network rendering requires parsing `.network` files.

## Screenshot Status

Required viewport captures: 1440x1000, 768x1024, and 390x844 for the four checkpoint pages. Automated screenshot support is available in `scripts/capture_screenshots.py`. In this environment Playwright/Chromium is not installed, so screenshots have not been generated here.
