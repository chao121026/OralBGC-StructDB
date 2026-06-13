# Accessibility and Responsive Audit

Pages reviewed: Home, MAGs, BGCs, GCFs, Proteins, Structures, Search, Networks, Downloads, Help, About, Contact, and entity detail pages.

Implemented:

- Semantic page headings and table captions.
- Skip-to-content link and visible focus states.
- Labeled filter controls and accessible empty/loading states.
- Horizontal scrolling for wide data tables instead of cramped mobile columns.
- Responsive grids for stat cards and detail panels.
- Textual explanation for charts, networks, and gene-cluster tracks.
- Gene-cluster SVG includes an accessible label and per-gene tooltips.

Viewport considerations:

- At 1440x1000, browse tables use dense scientific layouts.
- At 1024x768 and 768x1024, stat and detail grids collapse cleanly.
- At 390x844, tables scroll horizontally and filter panels stack.

Known follow-up: run `scripts/capture_screenshots.py` with Playwright/Chromium in an environment where browser automation is installed.

