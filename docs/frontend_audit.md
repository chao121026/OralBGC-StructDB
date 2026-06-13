# Frontend Audit

Scope: public scientific database UI with emphasis on the four checkpoint pages.

## Implemented refinements

- Added reusable Jinja macros for statistic cards and badges.
- Reworked homepage charting into four scientific Plotly panels: BGC class distribution, AF3 confidence distribution, protein length distribution, and PDB structural-match category distribution.
- Replaced the placeholder scientific-overview card with a data-layer boundary panel that explains the difference between structure availability, AF3 QC, and Foldseek/PDB annotation.
- Converted the workflow into linked, compact process steps on desktop and a vertical flow on mobile.
- Preserved a restrained visual system: white/light neutral surfaces, deep navy header, teal structural biology accent, and a limited warm highlight.
- Improved workflow treatment and version/update-history visibility.
- Kept tables dense but readable with monospace limited to identifiers.
- Added mobile-card table rendering for browse pages and BGC protein lists so long identifiers no longer force horizontal scrolling.
- Added short visible identifiers with full IDs preserved in titles, links, and detail context blocks.
- Maintained explicit distinctions between predicted structure availability, AF3 QC availability, and Foldseek/PDB annotation availability.
- Protein detail keeps the structure viewer prominent while showing truthful unavailable states for CIF-only and no-CIF records.
- Repaired structure-viewer containment: the 3Dmol canvas is constrained to the viewer, the viewer reserves a responsive height, and loading/error states are explicit.
- Replaced the mobile Bootstrap collapse with an app-controlled drawer that starts closed, locks body scrolling only while open, and closes via Escape, outside click, or navigation.
- Improved machine-label readability by converting underscore-heavy labels such as `moderate_remote_PDB_like` into human-readable text in visible UI.
- Added a BGC gene-track legend and compact BGC protein rows.
- Downloads remain trust-oriented with public allowlist, descriptions, file sizes, and checksums.

## Design risks checked

- Does not use default Bootstrap dashboard cards as the main visual language.
- Does not use glassmorphism, decorative animation, oversized rounded SaaS cards, or generic illustrations.
- Does not label weak/no PDB matches as candidates or therapeutic leads.
- Does not expose raw filesystem paths or candidate-priority fields in public HTML/API tests.
- Mobile layout includes regression coverage for horizontal overflow on Home, Protein browse, Downloads, and one real protein detail page.
- Structure viewer includes regression coverage for detached canvas detection when Playwright Chromium is installed.

## Browser Regression Support

- Added Playwright-backed pytest coverage in `tests/test_browser_regression.py`.
- The tests launch the FastAPI app on a local ephemeral port and validate mobile overflow, mobile drawer behavior, and structure-viewer canvas containment.
- Playwright remains optional. If the Python package or Chromium browser runtime is missing, these tests skip with an explicit reason.
- Screenshot capture in `scripts/capture_screenshots.py` now waits for `.structure-ready`, `.structure-error`, or `.empty-viewer` on protein detail pages before saving images.

## Remaining limitations

- Browser screenshots require installing Playwright and Chromium.
- CDN assets should be vendored for production if external asset dependency is unacceptable.
- Structure viewer controls are minimal; fullscreen/surface/spin controls can be added after this checkpoint is approved.
