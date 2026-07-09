# Critical Minerals Data Sources

This project is metadata-only. Source modules should collect titles, dates, URLs, summaries, caveats, identifiers, and classification fields. They should not put full document body text into `events_cache.json`, `events_cache.js`, or embedded HTML.

## Source Modules

| Source | Intended use |
|---|---|
| [FRUS / HistoryAtState](https://history.state.gov/historicaldocuments) | Historical diplomatic records and source-note-ready context for mineral diplomacy, strategic materials, seabed mining, resource nationalism, and stockpiling. |
| [NARA Catalog API](https://www.archives.gov/research/catalog/help/api) | Broader archival discovery across record groups, presidential libraries, still images, textual records, maps, and item/series metadata. |
| [Census International Trade API](https://www.census.gov/data/developers/data-sets/international-trade.html) | U.S. imports/exports by HS, HTS, Schedule B, partner, period, and flow. Use HS-code caveats because commodity codes are proxies. |
| [USGS](https://www.usgs.gov/science/science-explorer/minerals/critical-minerals) | U.S. critical minerals lists, methodology, commodity summaries, mineral science, and import-reliance context. |
| [DOE](https://www.energy.gov/cmei/ammto/articles/2023-doe-critical-materials-assessment) | Critical materials for energy technologies, criticality assessments, supply risk, and technology relevance. |
| [DLA Strategic Materials](https://www.dla.mil/Strategic-Materials/) | Defense-relevant strategic materials, stockpiling, material uses, procurement, recycling, and supply-risk context. |
| [Federal Register](https://www.federalregister.gov/documents/2025/11/07/2025-19813/final-2025-list-of-critical-minerals) | Official notices, final lists, legal determinations, requests for comment, and agency actions. |
| [State Department](https://www.state.gov/releases/office-of-the-spokesperson/2026/02/2026-critical-minerals-ministerial) | Releases, ministerial announcements, investment climate statements, public diplomacy material, and partner-country context. |
| USTR / Commerce / EXIM / DFC | Future extensions for trade policy, industrial base, export finance, and development-finance records. |

## Key Caveats

- FRUS and NARA records need source-note or catalog-level verification before use.
- Census trade rows should retain query parameters, HS-code vintage, partner coding, and flow direction.
- HS codes often describe products or baskets, not mined origin.
- USGS and DOE criticality frameworks overlap but are not identical.
- State Department releases can change URLs or block automated fetches; verify live browser access before clearance.
