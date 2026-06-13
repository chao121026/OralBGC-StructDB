# Frontend Audit

Scope: four checkpoint pages only: Home, Protein browse, Protein/structure detail, and Downloads.

## Findings and implemented refinements

- Typography hierarchy: retained large homepage title, tightened stat-card labels, and kept table text compact but readable.
- Spacing rhythm: adjusted stat-grid responsiveness and compact status badges so the homepage does not read like a SaaS landing page.
- Navigation clarity: retained stable database navigation, version badge, and skip link. Full downstream pages remain placeholders until checkpoint review.
- Table density: added concise availability columns for Structure, AF3 QC, and Foldseek/PDB instead of showing all raw metrics. Empty table state now gives a clear recovery action.
- Badge consistency: added neutral status badges for available/not-available annotation layers.
- Chart legibility: homepage chart remains a real Plotly chart with textual summary; labels now clarify blank categories.
- Scientific notation: changed “AF3 models” summary language to “predicted structures available” and “proteins with AF3 QC” to avoid over-claiming.
- Loading states: added an HTMX loading indicator for protein table updates.
- Mobile responsiveness: stat cards now collapse from seven columns to four, two, then one column; detail layout remains single-column on narrower screens.
- Protein detail balance: made the CIF viewer conditional and prominent, and added an annotation-layer panel so CIF-only records are scientifically accurate.
- Accessibility: preserved visible focus states, semantic headings, table captions, high-contrast header, labeled inputs, and reduced-motion behavior.

## Remaining visual limitations

- Browser screenshots still require a local Playwright/Chromium installation.
- Network and entity browse pages remain intentionally unimplemented beyond placeholders.
- The structure viewer uses 3Dmol defaults; residue confidence coloring should wait until per-residue pLDDT parsing is available.
