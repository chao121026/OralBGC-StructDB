# Frontend Audit

Scope: public scientific database UI with emphasis on the four checkpoint pages.

## Implemented refinements

- Added reusable Jinja macros for statistic cards and badges.
- Reworked homepage charting into four scientific Plotly panels: BGC class distribution, AF3 confidence distribution, protein length distribution, and PDB structural-match category distribution.
- Preserved a restrained visual system: white/light neutral surfaces, deep navy header, teal structural biology accent, and a limited warm highlight.
- Improved workflow treatment and version/update-history visibility.
- Kept tables dense but readable with monospace limited to identifiers.
- Maintained explicit distinctions between predicted structure availability, AF3 QC availability, and Foldseek/PDB annotation availability.
- Protein detail keeps the structure viewer prominent while showing truthful unavailable states for CIF-only and no-CIF records.
- Downloads remain trust-oriented with public allowlist, descriptions, file sizes, and checksums.

## Design risks checked

- Does not use default Bootstrap dashboard cards as the main visual language.
- Does not use glassmorphism, decorative animation, oversized rounded SaaS cards, or generic illustrations.
- Does not label weak/no PDB matches as candidates or therapeutic leads.
- Does not expose raw filesystem paths or candidate-priority fields in public HTML/API tests.

## Remaining limitations

- Browser screenshots require installing Playwright and Chromium.
- CDN assets should be vendored for production if external asset dependency is unacceptable.
- Structure viewer controls are minimal; fullscreen/surface/spin controls can be added after screenshot review.
