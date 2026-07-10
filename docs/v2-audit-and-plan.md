# v2 Architecture Audit and Implementation Record

## Audit Findings

The inherited application was a static GitHub Pages site with several assets
worth preserving:

- a compact metadata event contract
- a 16,811-document FRUS subject-authority index
- source-tier, confidence, and caveat treatments
- shareable URL state
- dark mode and responsive navigation
- NARA response normalization and image support
- parser, scorer, taxonomy, and Records Studio workflows

The inherited homepage data did not fit the new historical boundary: most of
its compact demonstration records were post-1992 and the page opened with a
2025–2026 command-center frame. The event cache also could not support reusable
mineral, country, treaty, law, statistic, or stockpile pages without duplicating
content.

## Implemented Architecture

v2 keeps the site static and adds modular JSON under `data/history-stack/`.
Shared IDs connect entities without copying narrative across files. A homepage
or detail page resolves those links at runtime with `assets/history-data.js`.

The main routes are:

- `records-stage.html`: historical orientation and discovery
- `history-stack.html?type=...&id=...`: reusable entity and document profiles
- `methodology.html`: source and data-quality rules

The FRUS index remains a separate advanced discovery layer. Its unreviewed rows
display only volume span, document identifier, subject flags, chapter context,
and authoritative URL.

## Pilot Content Boundary

The pilot demonstrates all major contracts without pretending to be complete:

- 8 mineral profiles
- 8 country or territory profiles
- 6 historical periods
- 14 agreements or policy instruments
- 3 laws
- 4 administrations
- 2 stockpile case studies
- 20 linked FRUS documents, including 4 reviewed records
- 25 NARA structured query plans
- 1,114 USGS observations

## Known Weak Areas

- NARA live results require deployment of the secret-bearing proxy.
- No API-returned NARA descriptions are committed because current NARA terms
  prohibit storing or caching returned content.
- Country-level production and U.S. import-source shares are not yet populated.
- Treaty-series and TIAS citations are incomplete for most wartime purchasing
  and control records.
- Mine, smelter, port, rail, and shipping-route coordinates remain unpopulated.
- Historical outcomes are mostly research queues rather than inferred stories.
- The pilot has four administration profiles, not complete Lincoln-through-Bush
  coverage.

## Next Content Sequence

1. Bolivian tin: official purchasing texts, supplier shares, prices, and route.
2. Surinam and Guianan bauxite: production, transport, mine protection, and law.
3. Turkish and Rhodesian chromium: contracts, denial policy, sanctions, and trade.
4. Congo and Northern Rhodesian cobalt/copper: production, ownership, refining,
   decolonization, and transport.
5. National Defense Stockpile: material-level goals, holdings, acquisitions,
   disposals, and agency responsibility from official reports.
