# Four-Page Design Checkpoint

Checkpoint pages:

1. Home (`/`)
2. Protein browse (`/proteins`)
3. Protein/structure detail (`/proteins/{public_protein_id}`)
4. Downloads (`/downloads`)

Local review URL: `http://127.0.0.1:8000`

## Data Used

The checkpoint uses the ingested SQLite database built from `${PACKAGE_ROOT}`. Live stats are 583 MAGs, 1,913 BGCs, 179 primary c0.3 GCFs, 22,626 BGC proteins, 22,622 predicted structures available, 10,972 proteins with AF3 QC, and 10,972 proteins with Foldseek/PDB annotation. The protein detail page uses a real approved CIF route when a structure is available.

## Color Tokens

- Deep navy: `#09233d`
- Ink: `#10202f`
- Muted text: `#617080`
- Structural biology teal: `#007c89`
- Light cyan: `#d8f3f5`
- Warm highlight: `#b56b1d`
- Border: `#d8e0e8`
- Background: `#f7f9fb`

## Typography Tokens

- UI sans: Inter, Source Sans 3, system UI fallback
- Identifier monospace: IBM Plex Mono, SFMono, Consolas fallback
- Page titles use the largest scale only for record/page identity.
- Tables and badges use compact text for high information density.
- Identifier columns are selectively monospace; descriptive biology text is not.

## Component Inventory

- Template inheritance via `base.html`
- Reusable Jinja macros in `app/templates/components/macros.html`
- Skip link and global navigation with Browse dropdown
- Scientific hero with version/dataset context
- Workflow visualization
- Statistic cards
- Plotly chart grid: BGC class, AF3 confidence, length bucket, structural-match category
- HTMX filter toolbar and loading state
- Server-rendered protein table with availability badges
- Record hero, metadata badges, metric panels
- 3Dmol-enabled structure viewer panel
- Download manifest rows with checksums
- Empty/error states

## Design Rationale

The interface is a restrained scientific resource rather than an admin dashboard or commercial SaaS landing page. The homepage explains the data hierarchy and database scale quickly; the protein browse page keeps dense records server-paginated; the detail page makes the predicted structure viewer the central visual element while clearly separating structure availability, AF3 QC, and Foldseek/PDB annotation; the downloads page emphasizes trust through allowlisted files and checksums.

## Accessibility and Responsive Notes

Implemented: semantic headings, skip link, keyboard-visible focus states, table captions, labeled filters, textual chart summaries, responsive grids, horizontal table scrolling, and reduced-motion CSS. The screenshot script covers 1440x1000, 768x1024, and 390x844 once Playwright/Chromium is installed.

## Limitations

- Screenshots were not generated in this environment because Playwright/Chromium is not installed.
- Plotly and 3Dmol are still loaded from public CDNs; local vendoring remains a deployment hardening follow-up.
- Per-residue pLDDT coloring is not implemented because residue-level confidence parsing is not yet exposed in the public SQLite schema.
