# The United States and Strategic Resources, 1861–1992

A static, FRUS-led historical decision-support and orientation platform for
understanding how the United States sought access to critical minerals and
strategic resources. It is designed for Department of State employees, Foreign
Service Officers, historians, policy researchers, and students.

**Live site:**
[therealjameswilson.github.io/critical-minerals-records-stage-v2/records-stage.html](https://therealjameswilson.github.io/critical-minerals-records-stage-v2/records-stage.html)

> **Statutory standard:** FRUS is to be “a thorough, accurate, and reliable
> documentary record.” See [22 U.S.C. § 4351(a)](https://uscode.house.gov/view.xhtml?req=%28title%3A22%20section%3A4351%20edition%3Aprelim%29).

The main historical experience is hard-bounded to 1861–1992. Post-1992 material
appears only in a separately labeled Modern Context layer.

## What v2 Provides

- A historical homepage organized by atlas, mineral, country, period, episode,
  agreement, law, archive, stockpile case, and FRUS record.
- Reusable History Stack pages that connect an entity to twelve layers: FRUS,
  timeline, official statistics, agreements, geography, law, stockpiles,
  archives, decision process, outcomes, provenance, and Modern Context.
- A complete metadata-only FRUS Subjects discovery index for 1861–1992:
  16,811 document links across 545 volumes.
- A pilot with 10 minerals, including uranium and rare earth elements; 9
  countries or territories; 8 periods; 15 typed agreements or policy
  instruments; 3 laws; 5 administrations; 32 linked FRUS records; and 30 NARA
  query plans.
- 7,602 unit-defined annual observations for the nine DS140-backed atlas
  materials, extracted from official USGS workbooks without project
  interpolation.
- A lazy-loaded Data Series 140 library containing 61,133 numeric observations
  across 92 official commodity workbooks, 122 worksheet series, and 956
  published measures through 1992.
- 1,476 source-defined long-run trade records covering every selectable year,
  plus 294 contemporaneous rare-earth category rows for 1970-1990 and 3,669
  USITC DataWeb partner-product rows for 1989-1992. UN Comtrade contributes
  2,010 classification-bounded strategic-material rows plus 177 rare-earth
  continuity and mirror observations for 1962-1992.
- 1,759 source-preserving USGS Statistical Compendium supply-chain rows:
  country production for supported 1986-1990 mining, smelting, and refining
  tables, plus Census-derived cobalt imports by country for 1975-1990.
- A Historical Geostrategic Atlas with a 1861–1992 year control, historical
  names, documentary access lines, agreements, stockpile policy, NARA query
  plans, production geography, a supply-chain comparison lens, reported-partner
  trade using Comtrade for 1962-1988 and DataWeb for 1989-1992,
  classification-aware evidence panels, and an accessible table alternative.
- A visible atlas layer registry that keeps unsupported supplier-share,
  infrastructure, alliance, boundary, and risk views locked until compatible
  official data and citations exist.
- A source-visible NARA discovery layer that can use a secret-bearing serverless
  proxy without exposing the API key to GitHub Pages.

This is a public research demonstrator, not an official Department of State or
U.S. Government product.

## Trust Model

FRUS is the narrative spine, not the entire archive. The interface distinguishes:

- **Reviewed FRUS document:** document-level pilot metadata has been checked.
- **FRUS discovery lead:** only subject-authority and volume or chapter context
  are known; open the document before making a claim.
- **Official statistic:** value, unit, year, publication, workbook location,
  source URL, extraction method, and confidence are retained.
- **Partial coverage:** at least one evidence layer is linked and named gaps remain.
- **Research queue:** the schema or discovery route exists but needs verification.

The project never embeds full FRUS or NARA document text. Missing values are not
invented, estimated, or converted to zero. Historical country names are stored
by period. Formal treaties are distinguished from negotiations, concessions,
purchasing agreements, and domestic policy instruments.

Read the [full methodology](methodology.html) or
[`docs/methodology.md`](docs/methodology.md).

## Repository Structure

- `records-stage.html`: historical portal entry point
- `usgs-ds140.html`: complete, lazy-loaded DS140 statistical explorer
- `history-stack.html`: reusable entity and document detail route
- `methodology.html`: public methodology page
- `assets/portal.js`: homepage rendering, filters, search, and FRUS index
- `assets/atlas.js`: MapLibre atlas state, layers, synchronization, and URL state
- `assets/vendor/maplibre-gl/`: pinned MapLibre GL JS 5.24.0 runtime and license
- `assets/history-stack.js`: reusable twelve-layer entity rendering
- `assets/history-data.js`: shared loaders, escaping, badges, links, and cards
- `assets/portal.css`: responsive, accessible archival interface
- `assets/frus-subjects-index.js`: full metadata-only FRUS discovery index
- `data/history-stack/`: normalized pilot JSON modules
- `data/atlas/`: generated atlas layer registry, overlays, and orientation geometry
- `data/usgs-ds140/`: compact catalog and one source-preserving JSON file per commodity
- `schemas/`: JSON schemas for core entity types
- `scripts/build_history_pilot.py`: reproducible editorial pilot builder
- `scripts/build_atlas_data.py`: reproducible atlas overlays and basemap builder
- `scripts/build_annual_atlas.py`: one evidence ledger for every year and pilot material
- `scripts/ingest_usgs_ds140.py`: official XLSX extractor
- `scripts/ingest_usgs_ds140_library.py`: full official DS140 catalog and workbook extractor
- `scripts/ingest_usgs_supply_chain.py`: USGS Compendium country production and cobalt-import extractor
- `scripts/ingest_trade_data.py`: official Census and USGS trade extractor
- `scripts/ingest_un_comtrade_rare_earth.py`: 1962-1992 reporter-partner continuity importer
- `scripts/ingest_un_comtrade_strategic_materials.py`: classification-bounded partner trade for nine strategic materials
- `scripts/ingest_usitc_dataweb.py`: official 1989-1992 partner-trade importer
- `scripts/validate_history_data.py`: dates, references, provenance, and secret checks
- `connectors/nara.py`: server-side, metadata-only NARA API client
- `nara_proxy_worker.js`: deployable serverless proxy for the static site
- `local_server.py`: optional local NARA proxy

The original parser, scorer, taxonomy, compact event-cache, Records Studio, and
NARA image-support code remain available for compatible metadata workflows, but
the v2 homepage no longer uses the old post-1992 demonstration cache.

## Run Locally

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python scripts/build_history_pilot.py
python scripts/ingest_usgs_ds140.py
python scripts/ingest_usgs_ds140_library.py --cache-dir .cache/usgs-ds140-full
python scripts/ingest_trade_data.py
python scripts/ingest_usitc_dataweb.py --cache-dir .cache/usitc-dataweb
python scripts/build_atlas_data.py
python scripts/build_annual_atlas.py
python scripts/validate_history_data.py
python -m http.server 8000
open http://localhost:8000/records-stage.html
```

The site must be served over HTTP because browsers do not allow modular JSON
`fetch()` calls from a `file://` page.

The annual atlas generation method and source-acquisition sequence are documented
in [`docs/annual-atlas-coverage-plan.md`](docs/annual-atlas-coverage-plan.md).

To test only with the committed datasets:

```bash
python -m http.server 8000
```

## Rebuild Official USGS Statistics

The atlas extractor downloads nine official Data Series 140 workbooks and
writes every numeric annual cell through 1992 for the materials already linked
to the FRUS-led atlas. It preserves USGS units and worksheet coordinates, and
skips missing, withheld, estimated-text, and nonnumeric cells rather than
treating them as zero.

The full-library extractor discovers the official USGS catalog, resolves all 92
workbooks, preserves 122 separate worksheet series, and writes one compact JSON
file per commodity. This keeps the 61,133-observation library lazy-loaded rather
than adding its full weight to the portal homepage.

```bash
python scripts/ingest_usgs_ds140.py --access-date YYYY-MM-DD
python scripts/ingest_usgs_ds140_library.py \
  --access-date YYYY-MM-DD \
  --cache-dir .cache/usgs-ds140-full
python scripts/ingest_usgs_supply_chain.py \
  --access-date YYYY-MM-DD \
  --cache-dir .cache/usgs-supply-chain
python scripts/validate_history_data.py
```

Use `--cache-dir <path>` to retain downloaded XLSX files outside the repository.

## Rebuild the UN Comtrade Layers

The Comtrade importers add official international reporter-partner context for
1962-1992 while keeping FRUS as the documentary spine. They use separate SITC
Revision 1, 2, and 3 baskets, preserve product-scope contamination, and never
splice revisions or mirror reports into a single synthetic series. The
strategic-material code registry is maintained in
`data/crosswalks/comtrade_sitc_mineral_codes.yml`.

```bash
python scripts/ingest_un_comtrade_rare_earth.py \
  --access-date YYYY-MM-DD \
  --cache-dir .cache/un-comtrade
python scripts/ingest_un_comtrade_strategic_materials.py \
  --access-date YYYY-MM-DD \
  --cache-dir .cache/un-comtrade
python scripts/build_annual_atlas.py
python scripts/validate_history_data.py
```

The public preview service permits one period per query and is rate limited, so
uncached refreshes take several minutes. The committed manifests include
zero-result years as well as successful queries. No API key is required or
stored. UN Comtrade is labeled Tier 2 international context; USITC DataWeb
remains the authoritative U.S.-reported verification layer for 1989-1992. The
UNCCD Knowledge Hub entry is a discovery pointer; data are retrieved from the
official UN Statistics Division API.

## Rebuild USITC DataWeb Partner Trade

DataWeb supplies the portal's official bilateral statistical layer for the four
years in which its electronic series overlaps this project: 1989-1992. The
importer uses the public anonymous query session, writes a sanitized static JSON
cache for GitHub Pages, and does not require or store an API token.

```bash
python scripts/ingest_usitc_dataweb.py \
  --access-date YYYY-MM-DD \
  --cache-dir .cache/usitc-dataweb
python scripts/build_atlas_data.py
python scripts/validate_history_data.py
```

The checked-in query manifest preserves years, six-digit HTS/Schedule B
headings, result counts, and a payload hash. Partner country is the reported
origin or destination; it is not presented as mine origin, route, ownership,
end use, import dependence, or strategic importance. FRUS remains the
documentary and narrative spine throughout the interface.

## Rebuild Historical U.S. Trade

The trade extractor writes a source-bounded record for every selected year.
For 1861-1899 it uses published Census multi-year averages for the broad
economic class "crude materials." For 1900-1992 it extracts exact-year imports
and exports from the available USGS Data Series 140 commodity workbooks.

```bash
python scripts/ingest_trade_data.py --access-date YYYY-MM-DD
python scripts/validate_history_data.py
```

The two series are not merged. The Census rows are not mineral-specific, and
the USGS rows are national totals without partner-country attribution. Uranium
remains available as a FRUS-led mineral profile, but the trade tab labels its
annual series unavailable because no compatible uranium workbook is currently
normalized. See [`docs/historical-trade-data-model.md`](docs/historical-trade-data-model.md).

## Rebuild the Historical Atlas

The atlas builder derives relationships, instruments, events, stockpile-policy
markers, and NARA discovery overlays from normalized History Stack IDs. The
separate supply-chain ingestion adds published country production and cobalt
import geography. The interface does not infer supplier shares, physical route
volume, ownership, access, alliance membership, facility coordinates, or
strategic risk.

```bash
python scripts/build_atlas_data.py
python scripts/validate_history_data.py
```

The builder also downloads and trims the public-domain Natural Earth 1:110m
country polygons used for modern spatial orientation. Use `--skip-basemap` when
only regenerating documentary overlays. Historical names and status come from
dated project records; these polygons are not historical boundary evidence.

The site vendors MapLibre GL JS 5.24.0 so GitHub Pages does not depend on a
runtime map CDN. Its BSD license is retained at
`assets/vendor/maplibre-gl/LICENSE.txt`.

## Configure NARA Safely

Create an ignored local file from the empty example:

```bash
cp .env.example .env.local
```

Set `NARA_API_KEY` in `.env.local` or export it in the environment. Never place
the key in `records-stage.html`, `assets/runtime-config.js`, browser JavaScript,
screenshots, logs, documentation, or a committed file.

Local proxy:

```bash
pip install flask flask-cors
python local_server.py --no-browser-open
```

When the site itself is served from `localhost` or `127.0.0.1`, the browser
automatically uses `http://localhost:5757` for NARA requests.

GitHub Pages cannot hold a server-side secret. Deploy `nara_proxy_worker.js` as a
serverless Worker, store the key as a secret named `NARA_API_KEY`, and put only
the public Worker URL in `assets/runtime-config.js`:

```js
window.HISTORY_RUNTIME_CONFIG = Object.freeze({
  naraProxyUrl: "https://your-worker.example"
});
```

NARA’s current API terms say not to cache or store returned API content, so v2
uses on-demand, `no-store` responses instead of a GitHub Actions cache. Static
query plans and authoritative Catalog links remain available if the API fails.
See [`docs/nara-integration.md`](docs/nara-integration.md).

## Add or Correct Historical Data

1. Add the official source to `data/history-stack/sources.json` through
   `scripts/build_history_pilot.py`.
2. Add or update the normalized entity and link existing IDs rather than copying
   descriptions into multiple files.
3. Preserve historical names, dates, units, official URLs, and completeness.
4. Leave unavailable fields empty and add a precise `data_gaps` note.
5. Rebuild statistics only from official machine-readable files or reviewed
   page-level transcriptions.
6. Run validation and tests before publication.

Core schemas are under `schemas/`. Crosswalks for aliases, HS codes, agencies,
countries, and supply-chain terms remain under `data/crosswalks/`. HS-code
mappings must retain confidence and caveats because product codes may not
identify mined origin.

## Rebuild the FRUS Subject Index

The index combines the subject mappings in
[`therealjameswilson/frus-subjects`](https://github.com/therealjameswilson/frus-subjects)
with official lightweight TOC files from
[`HistoryAtState/frus`](https://github.com/HistoryAtState/frus). It contains no
document body text.

```bash
python build_frus_subject_index.py \
  --subjects-root ../frus-subjects \
  --toc-root ../frus/frus-toc
```

See [`docs/frus-subject-index.md`](docs/frus-subject-index.md).

## Tests

```bash
. .venv/bin/activate
python -m pytest tests/ -v
python scripts/validate_history_data.py
```

Validation checks entity minimums, unique IDs, cross-file references, the
1861–1992 boundary, year-by-year trade coverage, statistical provenance, atlas
layer semantics, `.env.example`, and tracked-file secret patterns.

## Provenance

This repository is a standalone v2 adaptation of
[`therealjameswilson/toolkit-template`](https://github.com/therealjameswilson/toolkit-template),
which descends from the FRUS On This Day toolkit. The v1 repository remains
preserved at
[`therealjameswilson/critical-minerals-records-stage`](https://github.com/therealjameswilson/critical-minerals-records-stage).
